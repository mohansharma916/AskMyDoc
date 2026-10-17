import pytest

from eval.build_golden import GOLDEN, build, load_golden, main, to_jsonl


def test_golden_file_is_in_sync_with_corpus_and_chunker():
    # Fails when the corpus or chunking changes without `python -m eval.build_golden`.
    assert GOLDEN.read_text() == to_jsonl(build())


def test_golden_mix_and_schema():
    items = load_golden()
    assert len(items) >= 50
    tags = [t for i in items for t in i["tags"]]
    assert tags.count("unanswerable") >= 0.15 * len(items)
    assert tags.count("multi-chunk") >= 0.15 * len(items)
    for item in items:
        assert {"id", "question", "expected_answer", "supporting_chunk_ids", "answerable", "tags"} <= item.keys()
        assert bool(item["supporting_chunk_ids"]) == item["answerable"]


def test_missing_evidence_is_an_error(tmp_path):
    src = tmp_path / "src.yaml"
    src.write_text("- id: x\n  question: q\n  evidence: ['this quote is not in the corpus']\n")
    with pytest.raises(ValueError, match="evidence not found"):
        build(src)
    src.write_text("- id: x\n  question: q\n")
    with pytest.raises(ValueError, match="need evidence"):
        build(src)


def test_check_mode(capsys):
    assert main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out
