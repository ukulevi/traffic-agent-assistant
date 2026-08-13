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

        for name in ("normal_baseline", "safe_rejection", "route_recommendation"):
            self.assertIsNotNone(by_name[name].recommended_action)
            self.assertIsNone(by_name[name].candidate_action)
        for name in (
            "accident_any_node",
            "flood_any_node",
            "lane_closure_any_node",
            "demand_surge_any_node",
            "route_needs_review",
            "ood",
            "high_uncertainty",
            "missing_citation",
        ):
            self.assertIsNone(by_name[name].recommended_action)
            self.assertIsNotNone(by_name[name].candidate_action)
        for name in ("dependency_failure", "deadline_exceeded"):
            self.assertIsNone(by_name[name].recommended_action)
            self.assertIsNone(by_name[name].candidate_action)

        refinement = by_name["route_recommendation"]
        self.assertGreaterEqual(refinement.details["safety_iterations"], 2)
        self.assertGreater(
            refinement.recommended_action["green_time_ratio"],
            0.7,
        )

    def test_catalog_covers_independent_incidents_and_route_branches(self) -> None:
        cases = {item.name: item for item in offline_scenarios()}
        self.assertTrue(
            {
                "normal_baseline",
                "accident_any_node",
                "route_recommendation",
                "route_needs_review",
            }.issubset(cases)
        )
        canonical_incidents = [
            cases["accident_any_node"],
            cases["flood_any_node"],
            cases["lane_closure_any_node"],
            cases["demand_surge_any_node"],
            cases["route_recommendation"],
        ]
        self.assertEqual(
            {item.event_type for item in canonical_incidents},
            {"accident", "flood", "lane_closure", "demand_surge", "signal_change"},
        )
        self.assertEqual(
            len({item.node_id for item in canonical_incidents}),
            len(canonical_incidents),
        )

    def test_job_evidence_records_bounded_privacy_safe_route_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            evidence = run_offline_profile(Path(temporary) / "offline.json")
        by_name = {item.name: item for item in evidence.capabilities}

        route = by_name["route_recommendation"]
        self.assertEqual(route.details["route_status"], "recommended")
        self.assertEqual(route.details["route_count"], 3)
        self.assertEqual(route.details["topology_version"], "synthetic-routing-20-v1")
        self.assertIsNone(route.details["safety_reason"])

        held = by_name["route_needs_review"]
        self.assertEqual(held.details["route_status"], "needs_review")
        self.assertEqual(held.details["route_count"], 0)
        self.assertIn("no_passing_route", held.details["safety_reason"])

        forbidden_keys = {
            "description",
            "scenario_query",
            "raw_image",
            "image_base64",
            "secret",
        }
        for item in evidence.capabilities:
            self.assertTrue(forbidden_keys.isdisjoint(item.details))
            if item.kind == "job":
                self.assertTrue(
                    {
                        "event_type",
                        "node_id",
                        "topology_version",
                        "route_count",
                        "route_status",
                        "safety_reason",
                        "policy_version",
                        "citation_present",
                    }.issubset(item.details)
                )


if __name__ == "__main__":
    unittest.main()
