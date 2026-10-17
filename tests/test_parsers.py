import pytest

from askdocs.ingest.parsers import (
    Block,
    UnsupportedFileType,
    normalize,
    parse_bytes,
    parse_html,
    parse_markdown,
    parse_text,
    title_from_filename,
)

MARKDOWN = """# Employee Handbook

Intro paragraph.

## Leave

### Parental leave

Primary caregivers get **20 weeks**.

- Can be split
- Into two blocks

## Expenses

| Amount | Approver |
| --- | --- |
| < 75 | None |

```
code   block
  indented
```
"""


def test_markdown_tracks_heading_path_and_title():
    doc = parse_markdown(MARKDOWN, "fallback")
    assert doc.title == "Employee Handbook"
    by_text = {b.text: b.section_path for b in doc.blocks}
    assert by_text["Intro paragraph."] == ("Employee Handbook",)
    assert by_text["Primary caregivers get **20 weeks**."] == ("Employee Handbook", "Leave", "Parental leave")
    assert by_text["- Can be split"] == ("Employee Handbook", "Leave", "Parental leave")
    # A new h2 pops the h3 off the stack.
    assert by_text["Amount | Approver"] == ("Employee Handbook", "Expenses")
    assert "< 75 | None" in by_text
    assert "code   block\n  indented" in by_text  # code keeps its spacing


def test_markdown_without_h1_uses_fallback_title():
    assert parse_markdown("Just text.", "My File").title == "My File"


HTML = """<html><head><title>Travel Policy</title><style>.x{}</style></head><body>
<nav>Home | About</nav>
<h1>Travel</h1><p>Book via the   portal.</p>
<h2>Flights</h2>
<ul><li><p>Economy under 6h</p></li><li>Premium economy otherwise</li></ul>
<table><tr><th>Class</th><th>Hours</th></tr><tr><td>Economy</td><td>&lt;6</td></tr></table>
<pre>line 1
line 2</pre>
<script>alert(1)</script>
<footer>Copyright</footer>
</body></html>"""


def test_html_blocks_sections_and_noise_removal():
    doc = parse_html(HTML, "fallback")
    assert doc.title == "Travel Policy"
    texts = [b.text for b in doc.blocks]
    assert "Book via the portal." in texts
    assert "- Economy under 6h" in texts  # <p> inside <li> appears once
    assert texts.count("- Economy under 6h") == 1
    assert "Class | Hours" in texts
    assert "line 1\nline 2" in texts
    assert not any("Home" in t or "Copyright" in t or "alert" in t for t in texts)
    flights = next(b for b in doc.blocks if b.text == "- Premium economy otherwise")
    assert flights.section_path == ("Travel", "Flights")


def test_html_falls_back_to_text_when_no_block_tags():
    doc = parse_html("<div>First para</div>\n\n<div>Second</div>", "Fallback")
    assert doc.title == "Fallback"
    assert [b.text for b in doc.blocks] == ["First para", "Second"]


def test_text_splits_paragraphs():
    doc = parse_text("One\nline.\n\n\nTwo.\n", "Notes")
    assert doc.blocks == [Block("One line."), Block("Two.")]


def test_normalize():
    assert normalize("  a \t b\n c ") == "a b c"
    assert normalize("a  \n\n\n\nb", keep_newlines=True) == "a\n\nb"


def test_dispatch_and_unsupported():
    assert parse_bytes("notes.txt", b"hello").blocks[0].text == "hello"
    assert parse_bytes("a.md", b"# T\n\nx").title == "T"
    assert parse_bytes("a.htm", b"<p>x</p>").blocks[0].text == "x"
    with pytest.raises(UnsupportedFileType):
        parse_bytes("image.png", b"")


def test_title_from_filename():
    assert title_from_filename("hr_handbook-2026.md") == "Hr Handbook 2026"
