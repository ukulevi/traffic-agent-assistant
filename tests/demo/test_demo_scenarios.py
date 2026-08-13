from __future__ import annotations

import unittest

from stwi.demo.scenarios import DemoScenario, offline_scenarios


EXPECTED_CASES = {
    "safe_approval",
    "safe_rejection",
    "refinement_success",
    "unsafe_vc",
    "flood_any_node",
    "lane_closure_any_node",
    "demand_surge_any_node",
    "ood",
    "high_uncertainty",
    "missing_citation",
    "dependency_failure",
    "deadline_exceeded",
    "invalid_scenario",
    "tenant_scope_denied",
    "sse_reconnect",
    "static_preview",
}


class DemoScenarioCatalogTest(unittest.TestCase):
    def test_catalog_is_complete_and_unique(self) -> None:
        scenarios = offline_scenarios()
        self.assertEqual({item.name for item in scenarios}, EXPECTED_CASES)
        self.assertEqual(len(scenarios), len(EXPECTED_CASES))

    def test_job_cases_use_canonical_terminal_statuses_and_demo_nodes(self) -> None:
        for scenario in offline_scenarios():
            with self.subTest(case=scenario.name):
                if scenario.kind == "job":
                    self.assertIn(
                        scenario.expected_terminal_status,
                        {"succeeded", "needs_review", "failed", "expired"},
                    )
                    self.assertRegex(scenario.node_id or "", r"^node_(0[0-9]|1[0-9])$")

    def test_catalog_keeps_event_type_independent_from_node(self) -> None:
        cases = {item.name: item for item in offline_scenarios()}
        self.assertEqual(cases["unsafe_vc"].event_type, "accident")
        self.assertEqual(cases["flood_any_node"].event_type, "flood")
        self.assertEqual(cases["lane_closure_any_node"].event_type, "lane_closure")
        self.assertEqual(cases["demand_surge_any_node"].event_type, "demand_surge")
        self.assertEqual(cases["refinement_success"].event_type, "signal_change")
        self.assertEqual(cases["safe_approval"].event_type, None)
        self.assertEqual(
            len({cases[name].node_id for name in (
                "unsafe_vc",
                "flood_any_node",
                "lane_closure_any_node",
                "demand_surge_any_node",
                "refinement_success",
            )}),
            5,
        )

    def test_catalog_records_are_immutable(self) -> None:
        scenario = offline_scenarios()[0]
        with self.assertRaises(AttributeError):
            scenario.name = "changed"  # type: ignore[misc]

    def test_invalid_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DemoScenario(
                name="invalid",
                kind="unknown",  # type: ignore[arg-type]
                expected_http_status=200,
            )


if __name__ == "__main__":
    unittest.main()
