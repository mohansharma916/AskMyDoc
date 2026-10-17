"""CI gate: runs the golden set once, writes eval/report.json, one test per threshold.

pytest eval/
"""

import pytest

from askdocs.config import get_settings

from .run_eval import has_llm_credentials, run, write_report
from .scoring import load_thresholds


@pytest.fixture(scope="session")
def report():
    if not has_llm_credentials(get_settings()):
        pytest.skip("No LLM credentials: set LLM_API_KEY (or ANTHROPIC_API_KEY) to run the eval gate.")
    result = run()
    write_report(result)
    return result


@pytest.mark.parametrize("metric", list(load_thresholds()))
def test_threshold(report, metric):
    r = report["results"][metric]
    assert r["passed"], f"{metric} = {r['value']} does not satisfy {r['op']} {r['threshold']}"
