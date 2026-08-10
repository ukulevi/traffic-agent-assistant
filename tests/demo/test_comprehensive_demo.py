from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.demo.run_mvp_smoke import run_offline_profile
from stwi.demo.evidence import CapabilityStatus, DemoEvidence
from stwi.demo.scenarios import offline_scenarios


class ComprehensiveOfflineDemoTest(unittest.TestCase):
    def test_every_catalog_capability_passes_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "offline.json"
            evidence = run_offline_profile(output)
            persisted = DemoEvidence.model_validate_json(
                output.read_text(encoding="utf-8")
            )

        self.assertEqual(evidence, persisted)
        self.assertEqual(evidence.verdict, "pass")
        self.assertEqual(
            [item.name for item in evidence.capabilities],
            [item.name for item in offline_scenarios()],
        )
        self.assertTrue(
            all(item.status == CapabilityStatus.PASS for item in evidence.capabilities)
        )
        self.assertFalse(evidence.live_services_contacted)
        self.assertFalse(evidence.raw_video_retained)
        self.assertFalse(evidence.automatic_actuation)

    def test_action_semantics_cover_all_terminal_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            evidence = run_offline_profile(Path(temporary) / "offline.json")
        by_name = {item.name: item for item in evidence.capabilities}

        for name in ("safe_approval", "safe_rejection", "refinement_success"):
            self.assertIsNotNone(by_name[name].recommended_action)
            self.assertIsNone(by_name[name].candidate_action)
        for name in ("unsafe_vc", "ood", "high_uncertainty", "missing_citation"):
            self.assertIsNone(by_name[name].recommended_action)
            self.assertIsNotNone(by_name[name].candidate_action)
        for name in ("dependency_failure", "deadline_exceeded"):
            self.assertIsNone(by_name[name].recommended_action)
            self.assertIsNone(by_name[name].candidate_action)

        refinement = by_name["refinement_success"]
        self.assertGreaterEqual(refinement.details["safety_iterations"], 2)
        self.assertGreater(
            refinement.recommended_action["green_time_ratio"],
            0.7,
        )


if __name__ == "__main__":
    unittest.main()
