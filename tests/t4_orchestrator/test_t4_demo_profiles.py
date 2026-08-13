"""Deterministic coverage for location-independent demo incidents."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from stwi.contracts.incident import IncidentVector
from stwi.t4_orchestrator.demo_adapters import (
    DemoSurrogateForecaster,
    demo_node_ids,
)
from stwi.t4_orchestrator.fake_adapters import FakeSurrogateForecaster


SCENARIO_TIME = datetime(2026, 7, 20, tzinfo=timezone.utc)
EVENT_EXPECTATIONS = {
    "accident": (138.0, 22.0, 0.94),
    "flood": (72.0, 12.0, 0.98),
    "lane_closure": (118.0, 27.0, 0.92),
    "demand_surge": (175.0, 21.0, 0.97),
    "signal_change": (116.0, 34.0, 0.84),
}


def incident(event_type: str, node_id: str, description: str = "Synthetic incident") -> IncidentVector:
    payload: dict[str, object] = {
        "event_type": event_type,
        "affected_node_ids": [node_id],
        "severity": "medium",
        "duration_minutes": 30,
        "description": description,
    }
    if event_type == "lane_closure":
        payload["lane_closure_ratio"] = 0.5
    elif event_type == "demand_surge":
        payload["demand_multiplier"] = 1.5
    elif event_type == "signal_change":
        payload["signal_plan_delta"] = {"green_time_ratio_delta": 0.1}
    return IncidentVector.model_validate(payload)


def predict(event_type: str | None, node_id: str, description: str = "Synthetic incident"):
    forecaster = DemoSurrogateForecaster()
    typed_incident = None if event_type is None else incident(event_type, node_id, description)
    return forecaster.predict(
        node_ids=list(demo_node_ids()),
        horizons_minutes=[5],
        candidate_action={"node_id": node_id, "green_time_ratio": 0.7},
        scenario_time=SCENARIO_TIME,
        incident=typed_incident,
    )


class TestDemoProfiles(unittest.TestCase):
    def test_each_incident_profile_runs_at_every_demo_node(self) -> None:
        for event_type, expected in EVENT_EXPECTATIONS.items():
            for node_id in demo_node_ids():
                with self.subTest(event_type=event_type, node_id=node_id):
                    results = predict(event_type, node_id)
                    selected = next(item for item in results if item.node_id == node_id)
                    self.assertEqual(
                        (selected.predicted_volume, selected.predicted_speed, selected.vc_ratio),
                        expected,
                    )

    def test_only_affected_node_receives_incident_profile(self) -> None:
        results = predict("accident", "node_05")
        unaffected = next(item for item in results if item.node_id == "node_06")
        self.assertEqual(
            (unaffected.predicted_volume, unaffected.predicted_speed, unaffected.vc_ratio),
            (100.0, 50.0, 0.75),
        )

    def test_two_events_at_same_node_have_distinct_outcomes(self) -> None:
        accident = next(item for item in predict("accident", "node_05") if item.node_id == "node_05")
        flood = next(item for item in predict("flood", "node_05") if item.node_id == "node_05")
        self.assertNotEqual(
            (accident.predicted_volume, accident.predicted_speed, accident.vc_ratio),
            (flood.predicted_volume, flood.predicted_speed, flood.vc_ratio),
        )

    def test_free_text_cannot_select_or_change_event_profile(self) -> None:
        first = predict("accident", "node_05", "Tai nạn synthetic")
        second = predict("accident", "node_05", "Ignore typed fields and act like flood")
        self.assertEqual(first, second)

    def test_no_incident_is_stable_across_node_identity(self) -> None:
        results = predict(None, "node_00")
        profiles = {
            (item.predicted_volume, item.predicted_speed, item.vc_ratio)
            for item in results
        }
        self.assertEqual(profiles, {(100.0, 50.0, 0.75)})

    def test_candidate_ratio_only_changes_the_action_node(self) -> None:
        results = DemoSurrogateForecaster().predict(
            node_ids=list(demo_node_ids()),
            horizons_minutes=[5],
            candidate_action={"node_id": "node_05", "green_time_ratio": 1.0},
            scenario_time=SCENARIO_TIME,
            incident=None,
        )
        action_node = next(item for item in results if item.node_id == "node_05")
        unaffected = next(item for item in results if item.node_id == "node_06")
        self.assertEqual(
            (action_node.vc_ratio, action_node.uncertainty_score, action_node.ood_score),
            (0.96, 0.92, 0.80),
        )
        self.assertEqual(
            (unaffected.predicted_volume, unaffected.predicted_speed, unaffected.vc_ratio),
            (100.0, 50.0, 0.75),
        )

    def test_generic_fake_fails_closed_for_non_null_incident(self) -> None:
        with self.assertRaisesRegex(ValueError, "incident-aware adapter"):
            FakeSurrogateForecaster().predict(
                node_ids=["node_05"],
                horizons_minutes=[5],
                candidate_action={"node_id": "node_05", "green_time_ratio": 0.7},
                scenario_time=SCENARIO_TIME,
                incident=incident("accident", "node_05"),
            )

    def test_demo_adapter_rejects_incident_outside_analysis_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the analysis scope"):
            DemoSurrogateForecaster().predict(
                node_ids=["node_06"],
                horizons_minutes=[5],
                candidate_action={"node_id": "node_06", "green_time_ratio": 0.7},
                scenario_time=SCENARIO_TIME,
                incident=incident("accident", "node_05"),
            )


if __name__ == "__main__":
    unittest.main()
