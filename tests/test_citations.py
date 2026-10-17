import pytest

from askdocs.generate.citations import answer_sentences, check_citations, cited_numbers, is_not_found


def test_cited_numbers():
    assert cited_numbers("A [1]. B [2][3].") == [1, 2, 3]


@pytest.mark.parametrize(
    "answer",
    [
        "Employees get 26 weeks of paid parental leave [1], which can be split into two blocks [2].",
        "Primary caregivers get 20 weeks [1]. Secondary caregivers get 8 weeks [1][2].",
        "Primary caregivers get 20 weeks. [1] Secondary caregivers get 8 weeks. [2]",
        "Leave rules:\n- Primary caregivers get 20 weeks [1].\n- Secondary carers get 8 weeks [2].",
        "## Summary\nThe stipend is 400 USD per week [3].",
    ],
)
def test_valid_answers(answer):
    check = check_citations(answer, n_chunks=5)
    assert check.ok, check.issues


def test_uncited_sentence_is_flagged():
    check = check_citations("The stipend is 400 USD [1]. It is paid monthly by payroll.", 5)
    assert not check.ok
    assert check.uncited == ["It is paid monthly by payroll."]
    assert "Sentence without a citation" in check.issues[0]


def test_out_of_range_citation_is_flagged():
    check = check_citations("The stipend is 400 USD per week [6].", 5)
    assert not check.ok and check.out_of_range == [6]
    assert "do not exist: [6]" in check.issues[0]
    assert not check_citations("Zero is not a valid excerpt [0].", 5).ok


def test_empty_answer_fails():
    assert not check_citations("", 5).ok
    check = check_citations("OK [1].", 5)  # too short to count as a sentence
    assert not check.ok and check.issues == ["The answer has no complete, cited sentence."]


def test_sentence_splitting_skips_fragments_and_keeps_decimals():
    assert answer_sentences("**Note**\nThe rate is 0.55 USD per km [1]. Done.") == ["The rate is 0.55 USD per km [1]."]


def test_not_found_detection():
    assert is_not_found("NOT_FOUND")
    assert is_not_found("  **NOT_FOUND**")
    assert not is_not_found("The answer was not found in section 2 [1].")
