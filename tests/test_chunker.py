import pytest

from askdocs.ingest.chunker import chunk_blocks, count_tokens, split_sentences
from askdocs.ingest.parsers import Block


def sentences(n: int, prefix: str = "Sentence") -> str:
    return " ".join(f"{prefix} number {i} talks about leave policy details." for i in range(n))


def test_split_sentences():
    assert split_sentences("One. Two! Three? four") == ["One.", "Two!", "Three? four"]
    assert split_sentences("See e.g. the portal. Then go.") == ["See e.g. the portal.", "Then go."]
    assert split_sentences("Price is 1.5 USD. Next.") == ["Price is 1.5 USD.", "Next."]
    assert split_sentences("code\n  block. Here") == ["code\n  block. Here"]
    assert split_sentences("a | b. C | d") == ["a | b. C | d"]


def test_small_section_is_one_chunk():
    blocks = [Block("Short one.", 1, ("A",)), Block("Short two.", 1, ("A",))]
    [chunk] = chunk_blocks(blocks)
    assert chunk.text == "Short one.\nShort two."
    assert (chunk.page, chunk.section_path, chunk.position) == (1, ("A",), 0)
    assert chunk.token_count == count_tokens(chunk.text)


def test_sections_never_share_a_chunk():
    blocks = [Block("In A.", None, ("A",)), Block("In B.", None, ("B",)), Block("A again.", None, ("A",))]
    chunks = chunk_blocks(blocks)
    assert [c.text for c in chunks] == ["In A.", "In B.", "A again."]
    assert [c.position for c in chunks] == [0, 1, 2]


def test_long_section_respects_size_overlap_and_sentence_boundaries():
    text = sentences(200)
    chunks = chunk_blocks([Block(text, 3, ("S",))], chunk_size=100, overlap=20)
    assert len(chunks) > 5
    for chunk in chunks:
        assert chunk.token_count <= 100
        assert chunk.text.endswith(".")  # never cut mid-sentence
        assert chunk.text.startswith("Sentence")
    # Consecutive chunks overlap by whole trailing sentences.
    prev = split_sentences(chunks[0].text)
    nxt = split_sentences(chunks[1].text)
    carried = [s for s in nxt if s in prev]
    assert carried and carried == prev[-len(carried) :]
    assert sum(count_tokens(s) for s in carried) <= 20


def test_zero_overlap():
    chunks = chunk_blocks([Block(sentences(60), None, ())], chunk_size=80, overlap=0)
    joined = " ".join(c.text for c in chunks)
    assert joined == sentences(60)


def test_oversize_sentence_is_split_by_tokens():
    giant = "word " * 300
    chunks = chunk_blocks([Block(giant.strip(), 1, ())], chunk_size=100, overlap=10)
    assert all(c.token_count <= 101 for c in chunks)
    assert len(chunks) >= 3


def test_page_is_first_page_of_chunk():
    blocks = [Block(sentences(3), 4, ("S",)), Block(sentences(3, "Other"), 5, ("S",))]
    [chunk] = chunk_blocks(blocks)
    assert chunk.page == 4


def test_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_blocks([], chunk_size=10, overlap=10)
