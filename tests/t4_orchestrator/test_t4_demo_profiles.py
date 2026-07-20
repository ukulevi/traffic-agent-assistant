"""Deterministic coverage for the simulation-only demo composition."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from stwi.config.runtime import RuntimeMode, RuntimeSettings
from stwi.t4_orchestrator.contracts import JobStatus, WhatIfJobRequest
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator


DEMO_SETTINGS = RuntimeSettings(mode=RuntimeMode.DEMO, job_concurrency=1)


def request(
    node_id: str,
    ratio: float,
    query: str = "quyền nghĩa vụ người sử dụng đường",
) -> WhatIfJobRequest:
    return WhatIfJobRequest(
        tenant_id="demo-operator",
        scenario_time=datetime(2026, 7, 20, tzinfo=timezone.utc),
        candidate_action={"node_id": node_id, "green_time_ratio": ratio},
        node_ids=[node_id],
        scenario_query=query,
    )


class TestDemoProfiles(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = WhatIfOrchestrator(settings=DEMO_SETTINGS)

    def test_safe_profile_responds_to_green_time_ratio(self) -> None:
        low = self.orchestrator.run("low", request("node_00", 0.4))
        high = self.orchestrator.run("high", request("node_00", 0.7))

        self.assertEqual(low.status, JobStatus.SUCCEEDED)
        self.assertEqual(high.status, JobStatus.SUCCEEDED)
        self.assertNotEqual(
            low.scenario_summary["avg_volume"],
            high.scenario_summary["avg_volume"],
        )

    def test_extreme_green_time_fails_closed(self) -> None:
        for ratio in (0.0, 1.0):
            with self.subTest(ratio=ratio):
                result = self.orchestrator.run(
                    f"extreme-{ratio}", request("node_00", ratio)
                )
                self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
                self.assertIsNone(result.recommended_action)
                self.assertIsNotNone(result.candidate_action)

    def test_named_nodes_cover_vc_ood_and_uncertainty(self) -> None:
        expected_reasons = {
            "node_01": "vc_ratio",
            "node_02": "out_of_distribution",
            "node_03": "high_uncertainty",
        }
        for node_id, reason in expected_reasons.items():
            with self.subTest(node_id=node_id):
                result = self.orchestrator.run(
                    node_id, request(node_id, 0.7)
                )
                self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
                self.assertIn(reason, result.needs_review_reason)
                self.assertIsNone(result.recommended_action)


if __name__ == "__main__":
    unittest.main()
