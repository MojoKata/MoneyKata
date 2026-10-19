"""Reading a receipt (requirements S9.8.2): what runs in the worker process.

1. A PDF with a text layer (at least 20 characters on a page) is read with pypdfium2: no OCR.
2. Images and scanned PDFs are prepared: Pillow applies the EXIF orientation, reads HEIC,
   turns them grey and scales the long side to 2,000 pixels; pypdfium2 renders at most the
   first 3 pages at 300 DPI.
3. RapidOCR on ONNX Runtime (CPU, 2 threads) runs the PP-OCR models: text detection,
   orientation, recognition. The models are the ones in the pinned rapidocr wheel, loaded by
   their paths and checked against their SHA-256 first, so nothing is ever downloaded.
4. Lines are put in reading order from their boxes, and the field parser takes over.
"""

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

TEXT_LAYER_CHARS = 20
MAX_PAGES = 3  # a receipt's
STATEMENT_PAGES = 30  # a scanned statement's, each page read in turn within its time limit
LONG_SIDE = 2000
DPI = 300
# Pixels an image may have, or a PDF page be drawn at, before it is refused or drawn smaller
# (S9.8.4.3).
MAX_PIXELS = 40_000_000
THREADS = 2

MODELS = {
    "det": (
        "PP-OCRv6_det_small.onnx",
        "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    ),
    "cls": (
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
    ),
    "rec": (
        "PP-OCRv6_rec_small.onnx",
        "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
    ),
}


class ReadError(Exception):
    """A receipt that couldn't be read, with the reason a person is shown."""


@dataclass
class Read:
    lines: list[str]
    method: str  # "text" or "ocr"
    engine: str


def models_dir() -> Path:
    import rapidocr

    return Path(rapidocr.__file__).parent / "models"


def check_models() -> dict[str, Path]:
    out = {}
    folder = models_dir()
    for key, (name, digest) in MODELS.items():
        path = folder / name
        if not path.exists():
            raise ReadError(f"the OCR model {name} is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ReadError(f"the OCR model {name} is not the one MoolaKata was built with")
        out[key] = path
    return out


_engine = None


def engine():
    global _engine
    if _engine is None:
        import onnxruntime
        from rapidocr import RapidOCR

        # ONNX Runtime ships a telemetry client that would upload to Microsoft (its 1DS
        # collector). Nothing leaves the server but the calls of R3.1, so it is switched off
        # before the first session is made, whatever the wheel's default.
        onnxruntime.disable_telemetry_events()
        paths = check_models()
        _engine = RapidOCR(
            params={
                "Global.log_level": "error",
                "Det.model_path": str(paths["det"]),
                "Cls.model_path": str(paths["cls"]),
                "Rec.model_path": str(paths["rec"]),
                "EngineConfig.onnxruntime.intra_op_num_threads": THREADS,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
    return _engine


def engine_name() -> str:
    from importlib.metadata import version

    return f"rapidocr {version('rapidocr')}, onnxruntime {version('onnxruntime')}, PP-OCRv6 small"


def _prepare(img):
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(img).convert("L")
    w, h = img.size
    scale = LONG_SIDE / max(w, h)
    if scale < 1:
        img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    return img


def in_order(boxes, texts) -> list[str]:
    """Words into lines: boxes whose vertical middles are close make one line, read left to
    right; lines top to bottom."""
    items = []
    for box, text in zip(boxes, texts, strict=False):
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((sum(ys) / len(ys), max(ys) - min(ys), min(xs), text))
    items.sort(key=lambda x: x[0])
    lines: list[list] = []
    for mid, height, x, text in items:
        if lines and abs(mid - lines[-1][0]) <= max(height, lines[-1][1]) * 0.5:
            line = lines[-1]
            line[2].append((x, text))
        else:
            lines.append([mid, height, [(x, text)]])
    return [" ".join(t for _, t in sorted(words)) for _, _, words in lines]


def _ocr(images) -> list[str]:
    import numpy as np

    out: list[str] = []
    for img in images:
        result = engine()(np.array(_prepare(img).convert("RGB")))
        if result.boxes is None or result.txts is None:
            continue
        out += in_order(result.boxes, result.txts)
    return out


def text_layer(data: bytes) -> list[str] | None:
    """A PDF's text layer as lines, or None when it has none worth reading: what a statement
    kept without reading is named by (S1.3.3.6), with no OCR."""
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception:
        raise ReadError("the PDF can't be opened") from None
    try:
        texts = [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
    finally:
        pdf.close()
    if not any(len(t.strip()) >= TEXT_LAYER_CHARS for t in texts):
        return None
    return [ln.strip() for t in texts for ln in t.splitlines() if ln.strip()]


def _rendered(page):
    """A page at the reading DPI, or smaller when that would pass the pixel cap: a page of
    any size is never drawn bigger than an image may be."""
    w, h = page.get_size()  # in points
    scale = DPI / 72
    if w * h * scale * scale > MAX_PIXELS:
        scale = (MAX_PIXELS / max(w * h, 1)) ** 0.5
    return page.render(scale=max(scale, 0.01)).to_pil()


def read(data: bytes, media_type: str, pages: int = MAX_PAGES) -> Read:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    if media_type == "application/pdf":
        import pypdfium2 as pdfium

        lines = text_layer(data)
        if lines is not None:
            return Read(lines, "text", "pypdfium2 text layer")
        pdf = pdfium.PdfDocument(data)
        try:
            # Rendered one at a time, so a long statement holds one page in memory, each
            # within the images' pixel cap (S9.8.4.3).
            lines = _ocr(_rendered(pdf[i]) for i in range(min(len(pdf), pages)))
        finally:
            pdf.close()
        return Read(lines, "ocr", engine_name())
    try:
        import pi_heif

        pi_heif.register_heif_opener()
        img = Image.open(io.BytesIO(data))
        if img.size[0] * img.size[1] > MAX_PIXELS:
            raise ReadError("the image is larger than 40 million pixels")
        img.load()
    except ReadError:
        raise
    except Exception as e:
        raise ReadError(f"the image can't be opened ({type(e).__name__})") from None
    return Read(_ocr([img]), "ocr", engine_name())
