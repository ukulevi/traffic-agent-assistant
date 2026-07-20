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

        self.assertFalse(evidence["live_services_contacted"])
        self.assertFalse(evidence["raw_video_retained"])
        self.assertEqual(len(evidence["cases"]), 4)
        self.assertEqual(evidence["cases"][0]["terminal_status"], "succeeded")
        self.assertTrue(
            all(case["terminal_status"] == "needs_review" for case in evidence["cases"][1:])
        )
        for case in evidence["cases"]:
            self.assertTrue(case["provisional"])
            self.assertFalse(case["applied_by_system"])
            self.assertFalse(case["automatic_actuation"])
            self.assertTrue(all(case["invariants"].values()))


if __name__ == "__main__":
    unittest.main()
