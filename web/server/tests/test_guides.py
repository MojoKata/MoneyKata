"""The guides' acronyms (requirements S12.7.7): each one a guide uses is explained in
guides/terms.md, in a sentence or two, and the hand-written mockup carries the same terms."""

import re

from moolakata import paths

GUIDES = paths.ROOT / "web" / "ui" / "guides"
MOCKUP = paths.ROOT / "docs" / "mockups" / "MoolaKata-mock.html"

# Capitals in the guides that aren't acronyms to explain.
PLAIN = {
    # words everyone knows
    *("AI", "GB", "ID", "JPEG", "MB", "PDF", "PM", "PNG", "QR", "URL", "US"),
    # tickers and a bank in the examples
    *("ABC", "AMZN", "BND", "MSFT", "SPY", "UMB", "VT", "XYZ"),
    # the forms 1099-DIV and 1099-INT
    *("DIV", "INT"),
}


def glossary() -> dict[str, tuple[str, str]]:
    out = {}
    for part in re.split(r"^## ", (GUIDES / "terms.md").read_text(), flags=re.M)[1:]:
        head, _, body = part.partition("\n")
        m = re.fullmatch(r"([A-Z][A-Z0-9]*): (.+)", head)
        assert m, f"terms.md: '## {head}' isn't 'ACRONYM: What it stands for'"
        out[m[1]] = (m[2], " ".join(body.split()))
    return out


def test_every_acronym_in_a_guide_is_explained():
    terms = glossary()
    missing = {}
    for path in sorted(GUIDES.glob("*.md")):
        if path.name == "terms.md":
            continue
        text = re.sub(r"^```.*?^```", "", path.read_text(), flags=re.M | re.S)
        text = re.sub(r"`[^`]*`|\]\([^)]*\)|\{#[^}]*\}", "", text)
        for word in re.findall(r"\b([A-Z][A-Z0-9]{1,5}?)s?\b", text):
            if word not in terms and word not in PLAIN:
                missing.setdefault(word, path.stem)
    assert missing == {}, f"acronyms terms.md doesn't explain (first guide using each): {missing}"


def test_each_term_says_what_it_stands_for_in_a_sentence_or_two():
    terms = glossary()
    assert list(terms) == sorted(terms), "terms.md is kept in alphabetical order"
    for term, (title, text) in terms.items():
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        assert text and len(sentences) <= 2, f"{term}: {len(sentences)} sentences"
        assert title[0].isupper() and not title.endswith("."), f"{term}: '{title}' is a name"
        assert term not in PLAIN, f"{term} is both a term and plain"


def test_the_hand_written_mockup_carries_the_same_terms():
    page = MOCKUP.read_text()
    block = page[page.index("const TERMS = {\n") : page.index("\n};\nconst TERM_RE")]
    mock = {
        m[1]: (m[2].replace("’", "'"), m[3].replace("’", "'"))
        for m in re.finditer(r"^  ([A-Z][A-Z0-9]*): \['(.*)', '(.*)'\],$", block, re.M)
    }
    assert mock == glossary()
