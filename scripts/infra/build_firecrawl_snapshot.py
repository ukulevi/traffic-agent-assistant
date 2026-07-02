"""Build a Tier 3 corpus-candidate snapshot from Firecrawl JSON.

The input is a JSON response exported from Firecrawl search/crawl/scrape. The
output is a private manifest under data/derived/private by default. Documents in
the manifest are candidates only; they are not approved for Qdrant indexing
until legal/SOP owner review promotes them.

Usage:
    python scripts/infra/build_firecrawl_snapshot.py firecrawl_response.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t3_knowledge.firecrawl_snapshot import write_firecrawl_snapshot_manifest  # noqa: E402


def default_output_dir() -> Path:
    return ROOT / "data" / "derived" / "private" / "phase3_knowledge" / "firecrawl_snapshots"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Firecrawl candidate snapshot manifest.")
    parser.add_argument("input", type=Path, help="Firecrawl JSON response/export.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory for the snapshot manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Explicit output path. Overrides --output-dir.",
    )
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if args.output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = args.output_dir / f"firecrawl_snapshot_{stamp}.json"
    else:
        output_path = args.output

    manifest = write_firecrawl_snapshot_manifest(payload, output_path)

    counts = manifest["counts"]
    print(f"Snapshot written: {output_path}")
    print(f"Records seen: {counts['records_seen']}")
    print(f"Accepted: {counts['accepted']}")
    print(f"Rejected: {counts['rejected']}")
    print(f"Eligible after owner review: {counts['eligible_for_promotion']}")
    return 0 if counts["accepted"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
