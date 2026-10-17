import pymupdf

from askdocs.ingest.parsers import parse_bytes


def make_pdf(pages: list[list[tuple[str, float]]], title: str = "") -> bytes:
    """Build a PDF where each page is a list of (text, font size) lines."""
    doc = pymupdf.open()
    for n, lines in enumerate(pages, start=1):
        page = doc.new_page()
        page.insert_text((72, 40), "ACME Corp - Confidential", fontsize=8)
        y = 90
        for text, size in lines:
            page.insert_text((72, y), text, fontsize=size)
            y += size * 2.2
        page.insert_text((72, 800), f"Page {n} of {len(pages)}", fontsize=8)
    if title:
        doc.set_metadata({"title": title})
    data = doc.tobytes()
    doc.close()
    return data


BODY = 11


def test_pdf_pages_headings_and_header_footer_removal():
    data = make_pdf(
        [
            [("Employee Handbook", 20), ("Leave", 15), ("Everyone gets 21 days of paid leave.", BODY)],
            [("Parental leave is 20 weeks for primary carers.", BODY), ("Expenses", 15)],
            [("Receipts are due within 30 days.", BODY), ("Managers approve claims.", BODY)],
        ]
    )
    doc = parse_bytes("handbook.pdf", data)
    assert doc.title == "Employee Handbook"
    texts = [b.text for b in doc.blocks]
    assert not any("Confidential" in t or "Page " in t for t in texts)

    leave = next(b for b in doc.blocks if b.text.startswith("Everyone"))
    assert (leave.page, leave.section_path) == (1, ("Employee Handbook", "Leave"))
    parental = next(b for b in doc.blocks if b.text.startswith("Parental"))
    assert parental.page == 2
    assert parental.section_path == ("Employee Handbook", "Leave")  # section continues across pages
    receipts = next(b for b in doc.blocks if "Receipts" in b.text)
    assert receipts.section_path == ("Employee Handbook", "Expenses")
    assert receipts.page == 3


def test_pdf_metadata_title_wins_and_short_docs_keep_edge_lines():
    data = make_pdf([[("Some body text here.", BODY)]], title="Official Title")
    doc = parse_bytes("x.pdf", data)
    assert doc.title == "Official Title"
    # With a single page nothing counts as a repeated header/footer.
    assert any("Confidential" in b.text for b in doc.blocks)


def test_sentences_wrapped_over_lines_and_pages_are_joined():
    data = make_pdf(
        [
            [("Policy", 15), ("Employees get twenty-one days of", BODY), ("paid leave per year.", BODY)],
            [("Unused days expire at the", BODY)],
            [("end of January.", BODY)],
        ]
    )
    texts = [(b.page, b.text) for b in parse_bytes("p.pdf", data).blocks]
    assert (1, "Employees get twenty-one days of paid leave per year.") in texts
    assert (2, "Unused days expire at the end of January.") in texts
