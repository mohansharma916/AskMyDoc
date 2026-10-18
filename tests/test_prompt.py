import pytest

from askdocs.config import PROJECT_ROOT
from askdocs.generate.prompt import (
    NOT_FOUND,
    build_retry_message,
    build_user_message,
    format_excerpt,
    load_prompt,
)
from askdocs.retrieve.types import Candidate


def test_load_shipped_prompt():
    prompt = load_prompt(PROJECT_ROOT / "prompts", "answer_v1")
    assert prompt.version == "answer_v1"
    assert NOT_FOUND in prompt.system and "[1]" in prompt.system


def test_v2_prompt_allows_partial_answers_with_the_exact_gap_phrase():
    from askdocs.generate.prompt import NOT_COVERED

    prompt = load_prompt(PROJECT_ROOT / "prompts", "answer_v2")
    assert f'"{NOT_COVERED}"' in prompt.system and NOT_FOUND in prompt.system


def test_missing_prompt(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompt(tmp_path, "nope")


def test_numbered_excerpts_with_sources():
    chunks = [
        Candidate("c1", "hr", "Twenty weeks.", file_name="hr.pdf", page=14, section_path=("Leave", "Parental")),
        Candidate("c2", "it", "Report in 24h.", file_name="it.txt"),
    ]
    msg = build_user_message("How long?", chunks)
    assert "[1] (hr.pdf, page 14, section: Leave > Parental)\nTwenty weeks." in msg
    assert "[2] (it.txt)\nReport in 24h." in msg
    assert msg.endswith("Question: How long?")
    assert format_excerpt(3, Candidate("c", "doc", "t")) == "[3] (doc)\nt"


def test_retry_message():
    msg = build_retry_message(["Sentence without a citation: 'X.'"], 5)
    assert "'X.'" in msg and "[1] to [5]" in msg and NOT_FOUND in msg
