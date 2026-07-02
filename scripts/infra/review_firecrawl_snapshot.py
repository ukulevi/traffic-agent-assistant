"""Apply legal/SOP owner review decisions to a Firecrawl snapshot manifest.

This script never indexes content into Qdrant. It only writes a reviewed
manifest that downstream ingestion may consume after checking
``approved_for_index``.

Usage:
    python scripts/infra/review_firecrawl_snapshot.py snapshot.json \
        --reviewer legal@example.org \
        --approve fc_123 \
        --output reviewed_snapshot.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t3_knowledge.firecrawl_review import (  # noqa: E402
    FirecrawlReviewError,
    write_reviewed_firecrawl_snapshot,
)


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}.reviewed{input_path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Firecrawl candidate snapshot manifest.")
    parser.add_argument("input", type=Path, help="Candidate snapshot manifest JSON.")
    parser.add_argument("--output", type=Path, default=None, help="Reviewed manifest output path.")
    parser.add_argument("--reviewer", required=True, help="Legal/SOP owner identity.")
    parser.add_argument(
        "--approve",
        action="append",
        default=[],
        metavar="SNAPSHOT_ID",
        help="Snapshot ID to approve for downstream indexing. Can be repeated.",
    )
    parser.add_argument(
        "--reject",
        action="append",
        default=[],
        metavar="SNAPSHOT_ID",
        help="Snapshot ID to reject. Can be repeated.",
    )
    parser.add_argument("--reason", default="", help="Optional reason attached to rejected documents.")
    args = parser.parse_args()

    output_path = args.output or default_output_path(args.input)
    try:
        reviewed_manifest = write_reviewed_firecrawl_snapshot(
            args.input,
            output_path,
            reviewer=args.reviewer,
            approved_snapshot_ids=args.approve,
            rejected_snapshot_ids=args.reject,
            rejection_reason=args.reason,
        )
    except FirecrawlReviewError as exc:
        print(f"Review rejected: {exc}", file=sys.stderr)
        return 2

    counts = reviewed_manifest["counts"]
    print(f"Reviewed snapshot written: {output_path}")
    print(f"Approved for index: {counts.get('approved_for_index', 0)}")
    print(f"Rejected by reviewer: {counts.get('rejected_by_reviewer', 0)}")
    print("Qdrant indexing performed: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
