import json
import tempfile
import unittest
from pathlib import Path

from scripts.infra.finalize_vision_privacy_review import finalize_review


class FinalizeVisionPrivacyReviewTest(unittest.TestCase):
    def test_finalizes_promoted_real_records(self) -> None:
        payload = {
            "records": [{
                "source_type": "real_rtsp_sanitized",
                "pseudo_labels": [{"class_name": "car"}],
                "privacy_transform": "heuristic_face_and_plate_region_blur",
                "privacy_status": "automated_redaction_needs_spot_review",
            }]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dataset_manifest.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            result = finalize_review(root, "reviewer", "all real frames checked")
            self.assertEqual(
                result["privacy_status"], "visual_spot_reviewed_agent"
            )
            self.assertTrue(
                result["privacy_review"][
                    "human_approval_required_for_external_release"
                ]
            )


if __name__ == "__main__":
    unittest.main()
