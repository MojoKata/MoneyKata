# S9. Receipts

1. **Upload** from the browser: drag and drop, or the file picker. One or many at once.
   Taking a photo of a receipt with a phone belongs to the mobile PWA ([out of scope](out-of-scope.md)).
   Formats: PDF, JPEG, PNG, WebP, and HEIC, the format of iPhone photos (converted to JPEG
   for display, with the photo's orientation applied). Each file is at most
   25 MB (a Setting).
2. **Stored on disk**, not in the database, under the data directory as
   `receipts/<random-id>.mkr`, **encrypted** (S15.3) and written once, never changed. The
   database holds the metadata: owner, original name, type, size, hash, upload time, date,
   amount, payee, notes, tags and links. Identical files are stored once, found by the hash
   in the database, never by the file's name.
3. **Links**: a receipt can be attached to any number of transactions, tax items (a donation,
   a medical expense) or tax documents (a 1099), physical-asset items (a purchase receipt,
   an appraisal, a certificate, photos, S1.10), loans (a closing disclosure, a statement),
   529 qualified expenses, gifts and donations, or to nothing yet (the **inbox**). Attaching
   one suggests matching transactions by amount and date.
4. **Viewing**: thumbnails in a grid, a viewer with zoom for images and the browser's own PDF
   viewer for PDFs, served `Content-Disposition: inline` with `Content-Security-Policy:
   sandbox` and `X-Content-Type-Options: nosniff`, from a path that needs the session. The
   server checks the type by the file's content, never by its name, and refuses anything else.
5. **Thumbnails** are made on upload (Pillow for images, pypdfium2 for a PDF's first page)
   and stored beside the file.
6. **Sharing** follows what the receipt is attached to: whoever can read a transaction can
   see its receipts. An unattached receipt is its owner's alone. Receipts cross a link only
   when the owner ticks **Include receipts** on that share, and then only as encrypted files
   in the other side's linked copy (S11.5, S11.9).
7. **Retention**: a receipt is deleted only by its owner and only when nothing links to it.
   The file stays while any receipt row names its hash, deleted or not (`schema.md` §4).
   Backups include the receipts directory (S14.6).
8. **Reading receipts (OCR)**: MoneyKata reads the date, total and merchant from each receipt
   **on the server, with RapidOCR**, and suggests the transaction it belongs to. Nothing
   leaves the server, and no external service, model download or GPU is involved.
   1. **What it produces**: the receipt's full text, and **suggested fields**: date, total,
      merchant, and where printed, tax and the card's last four digits. Each field carries a
      confidence. These are **suggestions**: they fill the receipt's empty fields, marked
      *read from the receipt*, and the user confirms or corrects them. OCR never overwrites a
      value a person entered, and never attaches a receipt by itself.
   2. **The pipeline**, per receipt:
      1. **PDF with a text layer** (an emailed invoice, a downloaded statement): the text is
         read with pypdfium2, with no OCR. A page counts as having a text layer when it gives
         at least 20 characters.
      2. **Images and scanned PDFs** are prepared first. Pillow applies the EXIF orientation,
         converts HEIC, converts to greyscale, and scales the long side to 2,000 pixels.
         pypdfium2 renders at most the first 3 PDF pages at 300 DPI.
      3. **RapidOCR** (the `rapidocr` package on **ONNX Runtime**, CPU only) runs the
         PP-OCR models: text detection, orientation classification, then text recognition.
         It returns each line's box, text and confidence. Skewed, curled and faded thermal
         receipts are within what these models are trained for.
      4. **Lines are put in reading order** from their boxes, and amounts that the
         recognizer split are joined (`14 2.18` → `142.18`).
      5. **The field parser** (MoneyKata's own code, rules plus tests):
         1. **total**: the amount on a line labelled TOTAL, AMOUNT DUE, BALANCE DUE, GRAND
            TOTAL or similar, skipping SUBTOTAL, TAX, CHANGE, CASH, SAVINGS and TIP lines,
            preferring the last such line; failing that, the largest amount;
         2. **date**: every common format (`10/09/2026`, `2026-10-09`, `09 OCT 26`,
            `Oct 9, 2026`), the most plausible one: not in the future, not before the
            account's opening;
         3. **merchant**: from the top lines, normalised by the user's payee rules (S2.7) and
            matched against payees they already have;
         4. **card**: `XXXX1234`, `****1234`, `ending in 1234`.
      6. **Matching**: the user's transactions (in accounts they can write to) with the same
         amount, within 5 days of the date, ranked by date distance and payee similarity. A
         transaction up to 25% larger also matches, to allow for a tip added after the
         receipt was printed. The best match is offered as *Attach to …*, with the next two
         as alternatives.
   3. **Models ship with the app.** The PP-OCR ONNX model files (detection, orientation,
      English/Latin recognition, about 15 MB) are committed and pinned by SHA-256, like the
      browser libraries. They are loaded from the install directory, and RapidOCR is
      configured with their local paths so it never tries to download a model at run time;
      the egress guard (S13.5) would refuse it anyway. Other scripts' recognition models
      (Chinese, Japanese, Korean, Cyrillic, …) can be added later the same way.
   4. **It runs as a background job**, never in a request:
      1. an upload queues the receipt and answers at once; the receipt shows *Reading…* until
         the job finishes, and the live-updates stream (S12.6) refreshes it;
      2. jobs run **one at a time** (a Setting, 1 by default) in a **separate worker
         process** with ONNX Runtime limited to 2 threads, a lower CPU priority, a memory cap
         (1.5 GB) and a 60-second limit per receipt. The worker is restarted after a crash or
         a timeout, so a hostile or broken file cannot take down the server;
      3. Pillow's decompression-bomb limit and a cap of 40 million pixels refuse oversized
         images before decoding;
      4. a receipt that fails is marked *couldn't read it*, with the reason, and stays usable
         with fields typed by hand;
      5. expected speed, to be measured on the target hardware: about 1–3 s per receipt on a
         current x86 CPU, about 3–10 s on a Raspberry Pi 5. A batch of uploads works through
         the queue.
   5. **Stored**: the full text in the database, indexed with SQLite **FTS5**, so the Receipts
      screen searches it (`blue bottle`, `142.18`). Beside it: the suggested fields with their
      confidences, the method (text layer or OCR), and the engine and model versions. Text and
      fields follow the receipt's sharing (S9.6), never cross a link, and are never written
      to Activity or the log.
   6. **Re-reading**: a receipt's **Read again** button, and in Settings › Receipts **Re-read
      all receipts** (after a model update), queue the jobs again. Only empty or
      OCR-suggested fields are replaced.
   7. **Settings › Receipts**: **Read receipts** on or off (on by default; off for a host too
      small to run it), the number of jobs at a time, and the queue's state (waiting,
      failed, last run).
   8. **Not in this version**: line items, handwriting, multi-receipt photos, currencies
      other than USD, and non-Latin scripts. A receipt that the parser can't
      make sense of still has its searchable text.
