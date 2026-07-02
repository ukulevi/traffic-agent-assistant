import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.infra.annotate_rtsp_manifest import annotate_manifest


class AnnotateRtspManifestTest(unittest.TestCase):
    def test_interpolates_between_verified_anchors(self) -> None:
        payload = {
            "source_id": "camera_1",
            "privacy_status": "needs_review",
            "frames": [
                {"path": "frame_000001.jpg"},
                {"path": "frame_000002.jpg"},
                {"path": "frame_000003.jpg"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            result = annotate_manifest(
                manifest,
                datetime.fromisoformat("2025-05-30T10:15:20+07:00"),
                datetime.fromisoformat("2025-05-30T10:15:30+07:00"),
            )

            self.assertEqual(
                result["frames"][1]["recorded_at"],
                "2025-05-30T10:15:25+07:00",
            )
            self.assertEqual(result["split_group"], "camera_1:2025-05-30")
            self.assertEqual(
                result["frames"][1]["timestamp_quality"],
                "interpolated_between_overlay_anchors",
            )

    def test_rejects_non_quarantine_manifest(self) -> None:
        payload = {
            "source_id": "camera_1",
            "privacy_status": "approved",
            "frames": [
                {"path": "frame_000001.jpg"},
                {"path": "frame_000002.jpg"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                annotate_manifest(
                    manifest,
                    datetime.fromisoformat("2025-05-30T10:15:20+07:00"),
                    datetime.fromisoformat("2025-05-30T10:15:25+07:00"),
                )


if __name__ == "__main__":
    unittest.main()
