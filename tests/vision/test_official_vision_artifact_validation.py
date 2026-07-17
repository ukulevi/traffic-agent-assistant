"""Tests for the redacted official-vision readiness report."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validation.validate_official_vision_artifact import (
    validate_official_artifact,
)
from stwi.tooling.vision_training.promotion import DEFAULT_MVP_MAP50
from stwi.utils.file_hash import sha256_file


class OfficialVisionArtifactValidationTest(unittest.TestCase):
    def test_below_gate_artifact_is_reported_blocked_without_frames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"weights")
            manifest_path = root / "model_artifact.json"
            manifest_path.write_text(json.dumps({
                "model_version": "below-gate",
                "weights": str(weights),
                "weights_sha256": sha256_file(weights),
                "dataset_version": "unit",
                "classes": ["car", "motorcycle", "bus", "truck"],
                "stwi_class_map": {
                    "car": "car", "motorcycle": "motorcycle",
                    "bus": "bus", "truck": "truck",
                },
                "privacy_status": "visual_spot_reviewed_agent",
                "promotion_status": "official_mvp_primary",
                "metrics": {"metrics/mAP50(B)": DEFAULT_MVP_MAP50 - 0.01},
            }), encoding="utf-8")

            report = validate_official_artifact(manifest_path)

            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["raw_video_or_frames_read"])


if __name__ == "__main__":
    unittest.main()
