"""Pure metric aggregation for evaluation reports (no model calls)."""

import math
from pathlib import Path

import yaml

from askdocs.generate.citations import answer_sentences, cited_numbers

THRESHOLDS = Path(__file__).parent / "thresholds.yaml"


def load_thresholds(path: Path = THRESHOLDS) -> dict[str, dict[str, float]]:
    return yaml.safe_load(path.read_text())


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct in 0-100)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)]


def abstention_rates(rows: list[dict]) -> dict[str, float]:
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    return {
        "correct_abstention": sum(r["abstained"] for r in unanswerable) / max(len(unanswerable), 1),
        "false_abstention": sum(r["abstained"] for r in answerable) / max(len(answerable), 1),
    }


def citation_pairs(answer: str) -> list[tuple[str, int]]:
    """(sentence, cited excerpt number) pairs to be judged for citation precision."""
    return [(s, n) for s in answer_sentences(answer) for n in dict.fromkeys(cited_numbers(s))]


def mean_or_none(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None and not math.isnan(v)]
    return sum(present) / len(present) if present else None


def check_thresholds(metrics: dict[str, float | None], thresholds: dict) -> dict[str, dict]:
    results = {}
    for name, bound in thresholds.items():
        value = metrics.get(name)
        if "min" in bound:
            passed = value is not None and value >= bound["min"]
            results[name] = {"value": value, "op": ">=", "threshold": bound["min"], "passed": passed}
        else:
            passed = value is not None and value <= bound["max"]
            results[name] = {"value": value, "op": "<=", "threshold": bound["max"], "passed": passed}
    return results


def report_markdown(report: dict) -> str:
    status = "✅ All eval thresholds passed" if report["passed"] else "❌ Eval thresholds failed"
    lines = [
        f"### {status}",
        "",
        f"{report['n_items']} golden questions · model `{report['model']}` · judge `{report['judge_model']}` · "
        f"prompt `{report['prompt_version']}`",
        "",
        "| Metric | Value | Threshold | Result |",
        "| --- | --- | --- | --- |",
    ]
    for name, r in report["results"].items():
        value = "n/a" if r["value"] is None else (f"{r['value']:.0f}" if name.endswith("_ms") else f"{r['value']:.3f}")
        lines.append(f"| {name} | {value} | {r['op']} {r['threshold']} | {'pass' if r['passed'] else '**FAIL**'} |")
    usage = report.get("usage", {})
    if usage:
        cost = usage.get("cost_usd")
        lines += [
            "",
            f"Pipeline usage: {usage['input_tokens']} input / {usage['output_tokens']} output tokens"
            + (f", ${cost:.4f}" if cost is not None else ""),
        ]
    return "\n".join(lines) + "\n"
