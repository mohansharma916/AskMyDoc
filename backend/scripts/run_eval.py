"""CI entry point: run the Ragas evaluation and exit non-zero if a quality gate fails.

    python -m scripts.run_eval --phase 2 [--limit 20]
"""

import argparse
import sys

from app import evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", type=int, choices=[1, 2], default=2, help="Pipeline to evaluate")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N golden pairs")
    args = parser.parse_args()

    job = evaluation.create_job(args.phase, args.limit)
    evaluation.run_job(job["id"])
    if job["status"] == "failed":
        print(f"Evaluation failed: {job['error']}", file=sys.stderr)
        return 2

    build = job["result"]
    for name, m in build["metrics"].items():
        value = "n/a" if m["value"] is None else f"{m['value']:.3f}"
        print(f"{'PASS' if m['passed'] else 'FAIL'}  {name:<18} {value}  (threshold {m['threshold']})")
    print(f"\nBuild #{build['build_number']}: {'PASSED' if build['passed'] else 'FAILED'}")
    return 0 if build["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
