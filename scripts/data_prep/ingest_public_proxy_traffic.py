"""Ingest a human-authorized, licensed 5-minute public traffic CSV for demo use."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stwi.t2_forecast.public_proxy import build_public_proxy_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    manifest = build_public_proxy_dataset(
        args.input_csv, args.spec, args.output, replace=args.replace
    )
    print(json.dumps({
        "dataset_id": manifest["dataset_id"],
        "data_classification": manifest["data_classification"],
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
