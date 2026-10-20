"""The guides' acronyms (requirements S12.7.7): each one a guide uses is explained in
guides/terms.md, in a sentence or two with its official document where there is one. The IRS
forms they name (S12.7.8) are listed in guides/forms.md with their pages on irs.gov. The
hand-written mockup carries the same terms and forms."""

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
}
# Not guides: the lists the guides draw on.
LISTS = ("terms.md", "forms.md")


def glossary() -> dict[str, tuple[str, ...]]:
    """Each term's expansion and explanation, and its document's name and address if it has one."""
    out = {}
    for part in re.split(r"^## ", (GUIDES / "terms.md").read_text(), flags=re.M)[1:]:
        head, *body = part.strip().split("\n")
        m = re.fullmatch(r"([A-Z][A-Z0-9]*): (.+)", head)
        assert m, f"terms.md: '## {head}' isn't 'ACRONYM: What it stands for'"
        link = re.fullmatch(r"\[([^\]]+)\]\((\S+)\)", body[-1])
        if link:
            body.pop()
        out[m[1]] = (m[2], " ".join(" ".join(body).split()), *(link.groups() if link else ()))
    return out


def forms() -> dict[str, tuple[str, str]]:
    """Each form's title and the address of its page."""
    out = {}
    for part in re.split(r"^## ", (GUIDES / "forms.md").read_text(), flags=re.M)[1:]:
        head, *body = part.strip().split("\n")
        m = re.fullmatch(r"((?:Form|Schedule) [0-9A-Z-]+): (.+)", head)
        assert m, f"forms.md: '## {head}' isn't 'Form 8949: Its title'"
        link = re.fullmatch(r"\[[^\]]+\]\((\S+)\)", body[-1])
        assert link and len(body) == 2, f"forms.md: {m[1]} needs a line that is only its link"
        out[m[1]] = (m[2], link[1])
    return out


def guides() -> dict[str, str]:
    """Each guide's prose: no code blocks, code, link addresses or heading ids."""
    out = {}
    for path in sorted(GUIDES.glob("*.md")):
        if path.name not in LISTS:
            text = re.sub(r"^```.*?^```", "", path.read_text(), flags=re.M | re.S)
            out[path.stem] = re.sub(r"`[^`]*`|\]\([^)]*\)|\{#[^}]*\}", "", text)
    return out


def test_every_acronym_in_a_guide_is_explained():
    terms = glossary()
    named = "|".join(re.escape(f.removeprefix("Form ")) for f in forms())
    missing = {}
    for stem, text in guides().items():
        text = re.sub(rf"(?<![\w-])({named})(?![\w-])", "", text)
        for word in re.findall(r"\b([A-Z][A-Z0-9]{1,5}?)s?\b", text):
            if word not in terms and word not in PLAIN:
                missing.setdefault(word, stem)
    assert missing == {}, f"acronyms terms.md doesn't explain (first guide using each): {missing}"


def test_each_term_says_what_it_stands_for_in_a_sentence_or_two():
    terms = glossary()
    assert list(terms) == sorted(terms), "terms.md is kept in alphabetical order"
    for term, (title, text, *source) in terms.items():
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        assert text and len(sentences) <= 2, f"{term}: {len(sentences)} sentences"
        assert title[0].isupper() and not title.endswith("."), f"{term}: '{title}' is a name"
        assert term not in PLAIN, f"{term} is both a term and plain"
        assert "](" not in text, f"{term}: a link goes on its own last line, the document's"
        if source:
            assert source[1].startswith("https://"), f"{term}: {source[1]} isn't https"


def test_the_hand_written_mockup_carries_the_same_terms():
    page = MOCKUP.read_text()
    block = page[page.index("const TERMS = {\n") : page.index("\n};\nconst TERM_RE")]
    mock = {
        m[1]: tuple(g.replace("’", "'") for g in m.groups()[1:] if g is not None)
        for m in re.finditer(
            r"^  ([A-Z][A-Z0-9]*): \['(.*?)', '(.*?)'(?:, '(.*?)', '(.*?)')?\],$", block, re.M
        )
    }
    assert mock == glossary()


def test_every_form_a_guide_names_is_listed_with_its_page():
    listed = forms()
    assert list(listed) == sorted(listed), "forms.md is kept in alphabetical order"
    for name, (title, href) in listed.items():
        assert title[0].isupper() and not title.endswith("."), f"{name}: '{title}' is a title"
        assert href.startswith("https://www.irs.gov/forms-pubs/about-"), f"{name}: {href}"
    # "Form 8949", "Schedule D", and "1099-DIV" or "W-2" alone
    named = (
        r"\bForm (?:\d{3,4}(?:-[A-Z]+)?|W-\d)\b|\bSchedule [A-Z]\b"
        r"|(?<![\w-])(?:\d{4}-[A-Z]+|W-\d)\b"
    )
    missing = {}
    for stem, text in guides().items():
        for name in re.findall(named, text):
            if not name.startswith(("Form ", "Schedule ")):
                name = "Form " + name
            if name not in listed:
                missing.setdefault(name, stem)
    assert missing == {}, f"forms forms.md doesn't list (first guide naming each): {missing}"


def test_the_hand_written_mockup_carries_the_same_forms():
    page = MOCKUP.read_text()
    start = page.index("const FORMS = {\n")
    block = page[start : page.index("\n};\n", start)]
    mock = {
        m[1]: (m[2].replace("’", "'"), m[3])
        for m in re.finditer(r"^  '([^']+)': \['(.*?)', '(.*?)'\],$", block, re.M)
    }
    assert mock == forms()
