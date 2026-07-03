"""Fetch an external detector weight file with SHA256 verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stwi.tooling.vision_training.external_models import (
    fetch_external_weight,
    normalize_sha256,
    require_https_url,
    write_stream_with_sha256,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    manifest = fetch_external_weight(
        url=args.url,
        output_path=args.output,
        expected_sha256=args.expected_sha256,
        overwrite=args.overwrite,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({
        "status": manifest["result"]["status"],
        "path": manifest["result"]["path"],
        "sha256": manifest["result"]["sha256"],
        "manifest": str(args.output.with_name(args.output.name + ".fetch_manifest.json")),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
