"""Promote a reviewed local detector artifact as the official MVP detector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stwi.tooling.vision_training.promotion import (
    DEFAULT_MVP_MAP50,
    REQUIRED_STWI_CLASSES,
    metric_value,
    promote_artifact,
    validate_artifact_for_promotion,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/derived/private/vision_models/official"),
    )
    parser.add_argument("--min-map50", type=float, default=DEFAULT_MVP_MAP50)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--notes", required=True)
    args = parser.parse_args()
    promoted = promote_artifact(
        args.artifact,
        args.output_dir,
        min_map50=args.min_map50,
        approver=args.approver,
        notes=args.notes,
    )
    print(json.dumps({
        "model_version": promoted["model_version"],
        "promotion_status": promoted["promotion_status"],
        "weights": promoted["weights"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
