"""CLI: bind GCN-LSTM training evidence into a verifiable manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stwi.t2_forecast.evidence_binding import (  # noqa: E402
    bind_training_run,
    verify_evidence_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training", type=Path,
        default=Path("data/derived/private/phase2_forecast/gcn_lstm_mock_v2"),
    )
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("data/derived/private/phase1_mock"),
    )
    parser.add_argument(
        "--readiness", type=Path,
        default=None,
        help="Optional phase2 readiness report to cross-check dataset/KPI",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only re-verify the existing evidence manifest",
    )
    args = parser.parse_args()

    if args.verify_only:
        manifest_path = args.training / "evidence_manifest.json"
        manifest = verify_evidence_manifest(
            manifest_path,
            dataset_dir=args.dataset,
            readiness_report_path=args.readiness,
        )
    else:
        bind_training_run(args.training, args.dataset)
        # Re-verify immediately so binding + cross-check run as one step.
        manifest = verify_evidence_manifest(
            args.training / "evidence_manifest.json",
            dataset_dir=args.dataset,
            readiness_report_path=args.readiness,
        )

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
