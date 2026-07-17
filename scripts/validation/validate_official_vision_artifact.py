"""Fail-closed readiness report for the local official vision artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t1_pipeline.local_vision import (  # noqa: E402
    DEFAULT_OFFICIAL_MANIFEST,
    LocalVisionModelError,
    load_official_vision_model_artifact,
)
from stwi.tooling.vision_training.promotion import DEFAULT_MVP_MAP50  # noqa: E402


def validate_official_artifact(manifest_path: Path) -> dict[str, object]:
    """Return a redacted readiness result without loading images or weights."""
    try:
        artifact = load_official_vision_model_artifact(manifest_path)
    except LocalVisionModelError:
        return {
            "status": "blocked",
            "reason": "official detector evidence does not satisfy the MVP promotion gate",
            "minimum_map50": DEFAULT_MVP_MAP50,
            "raw_video_or_frames_read": False,
        }
    return {
        "status": "pass",
        "model_version": artifact.model_version,
        "minimum_map50": DEFAULT_MVP_MAP50,
        "raw_video_or_frames_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_OFFICIAL_MANIFEST)
    args = parser.parse_args()
    report = validate_official_artifact(args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
