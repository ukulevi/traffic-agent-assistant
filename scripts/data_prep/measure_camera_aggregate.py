"""CLI: measure camera aggregate evidence from a recorded video (TRA-67)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stwi.t1_pipeline.camera_aggregate import (  # noqa: E402
    AggregateConfig,
    build_camera_aggregate_report,
)

DEFAULT_OUTPUT = (
    ROOT / "data/derived/private/phase1_mock/camera_aggregate_measured/report.json"
)
DEFAULT_MOCK_REFERENCE = ROOT / "data/derived/private/phase1_mock/load_producers_1000.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path,
                        help="Licensed, pre-recorded video file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bucket-seconds", type=float, default=300.0)
    parser.add_argument("--sample-fps", type=float, default=1.0)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--max-frames", type=int, default=600)
    args = parser.parse_args()

    config = AggregateConfig(
        bucket_seconds=args.bucket_seconds,
        sample_fps=args.sample_fps,
        confidence=args.confidence,
        max_frames=args.max_frames,
    )
    report = build_camera_aggregate_report(
        args.video,
        config=config,
        mock_reference_path=DEFAULT_MOCK_REFERENCE
        if DEFAULT_MOCK_REFERENCE.is_file()
        else None,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)

    summary = {
        "status": "measured",
        "report": str(args.output),
        "frames_sampled": report["source"]["frames_sampled"],
        "buckets": len(report["per_bucket"]),
        "total_detections": report["aggregate_totals"]["detections"],
        "model_version": report["detector"]["model_version"],
        "privacy": report["privacy"],
    }
    if "sanity_check" in report:
        summary["sanity_check"] = report["sanity_check"]["result"]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
