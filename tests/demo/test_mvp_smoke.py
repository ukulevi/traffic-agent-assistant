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
        self.assertEqual(len(evidence["capabilities"]), 17)
        self.assertEqual(
            [case["name"] for case in evidence["capabilities"]],
            [
                "normal_baseline",
                "safe_rejection",
                "route_recommendation",
                "accident_any_node",
                "flood_any_node",
                "lane_closure_any_node",
                "demand_surge_any_node",
                "route_needs_review",
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
        incident_cases = {
            case["name"]: case for case in evidence["capabilities"]
            if case["name"] in {
                "accident_any_node",
                "flood_any_node",
                "lane_closure_any_node",
                "demand_surge_any_node",
                "route_recommendation",
            }
        }
        self.assertEqual(
            {case["details"]["event_type"] for case in incident_cases.values()},
            {"accident", "flood", "lane_closure", "demand_surge", "signal_change"},
        )
        self.assertTrue(all("description" not in case["details"] for case in incident_cases.values()))


if __name__ == "__main__":
    unittest.main()
