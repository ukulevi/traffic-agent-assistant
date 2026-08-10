"""Tests for the deterministic offline MVP demo smoke harness."""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from scripts.demo.run_mvp_smoke import run_smoke


class TestMvpSmoke(unittest.TestCase):
    def test_smoke_writes_safe_aggregate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "evidence.json"
            evidence = run_smoke(output)
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), evidence)

        self.assertEqual(evidence["schema_version"], "1.0")
        self.assertEqual(evidence["verdict"], "pass")
        self.assertFalse(evidence["live_services_contacted"])
        self.assertFalse(evidence["raw_video_retained"])
        self.assertEqual(len(evidence["capabilities"]), 13)
        self.assertEqual(
            [case["name"] for case in evidence["capabilities"]],
            [
                "safe_approval",
                "safe_rejection",
                "refinement_success",
                "unsafe_vc",
                "ood",
                "high_uncertainty",
                "missing_citation",
                "dependency_failure",
                "deadline_exceeded",
                "invalid_scenario",
                "tenant_scope_denied",
                "sse_reconnect",
                "static_preview",
            ],
        )
        for case in evidence["capabilities"]:
            self.assertEqual(case["status"], "pass")
            self.assertFalse(case["applied_by_system"])
            self.assertFalse(case["automatic_actuation"])


if __name__ == "__main__":
    unittest.main()
