"""Index a file or folder:  python -m askdocs.ingest --path data/docs"""

import argparse
import logging
import sys
from pathlib import Path

from ..services import Services


def main(argv: list[str] | None = None, services: Services | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m askdocs.ingest", description=__doc__)
    parser.add_argument("--path", required=True, type=Path, help="File or folder to index")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")
    if not args.path.exists():
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 2

    summary = (services or Services()).indexer.ingest_path(args.path)
    for r in summary.results:
        detail = r.error if r.status == "failed" else f"{r.chunks} chunks"
        print(f"{r.status:<9} {r.file_name}  ({detail})")
    print(
        f"\n{len(summary.results)} files: {summary.count('indexed')} indexed, "
        f"{summary.count('updated')} updated, {summary.count('unchanged')} unchanged, "
        f"{summary.count('failed')} failed; {summary.chunks} chunks written."
    )
    return 1 if summary.count("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
