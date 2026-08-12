from __future__ import annotations

import unittest

from pydantic import ValidationError

from stwi.contracts import IncidentVector, SignalPlanDelta


def valid_incident(event_type: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_type": event_type,
        "affected_node_ids": ["node_07"],
        "severity": "medium",
        "duration_minutes": 30,
        "description": "Giả định tổng hợp phục vụ đánh giá what-if.",
    }
    payload.update(overrides)
    return payload


class IncidentContractTest(unittest.TestCase):
    def test_each_approved_event_accepts_only_its_typed_parameters(self):
        cases = {
            "accident": {},
            "flood": {},
            "lane_closure": {"lane_closure_ratio": 0.5},
            "demand_surge": {"demand_multiplier": 1.5},
            "signal_change": {
                "signal_plan_delta": {"green_time_ratio_delta": -0.2}
            },
        }
        for event_type, parameters in cases.items():
            with self.subTest(event_type=event_type):
                incident = IncidentVector.model_validate(
                    valid_incident(event_type, **parameters)
                )
                self.assertEqual(incident.event_type.value, event_type)

    def test_event_specific_parameters_are_required_and_irrelevant_ones_rejected(self):
        invalid_payloads = [
            valid_incident("lane_closure"),
            valid_incident("demand_surge"),
            valid_incident("signal_change"),
            valid_incident("accident", lane_closure_ratio=0.5),
            valid_incident("flood", demand_multiplier=1.5),
            valid_incident(
                "lane_closure",
                lane_closure_ratio=0.5,
                signal_plan_delta={"green_time_ratio_delta": 0.1},
            ),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    IncidentVector.model_validate(payload)

    def test_unknown_fields_and_deferred_signal_offset_are_rejected(self):
        with self.assertRaises(ValidationError):
            IncidentVector.model_validate(
                valid_incident("accident", simulation_speed_multiplier=0.5)
            )
        with self.assertRaises(ValidationError):
            SignalPlanDelta.model_validate(
                {"green_time_ratio_delta": 0.1, "offset_seconds_delta": 15}
            )

    def test_contract_bounds_and_single_canonical_node_are_enforced(self):
        invalid_payloads = [
            valid_incident("accident", duration_minutes=0),
            valid_incident("accident", duration_minutes=181),
            valid_incident("lane_closure", lane_closure_ratio=-0.01),
            valid_incident("lane_closure", lane_closure_ratio=1.01),
            valid_incident("demand_surge", demand_multiplier=1.0),
            valid_incident("demand_surge", demand_multiplier=3.01),
            valid_incident("accident", affected_node_ids=[]),
            valid_incident("accident", affected_node_ids=["node_07", "node_08"]),
            valid_incident("accident", affected_node_ids=["   "]),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    IncidentVector.model_validate(payload)

    def test_numeric_fields_reject_booleans_and_numeric_strings(self):
        invalid_payloads = [
            valid_incident("accident", duration_minutes=True),
            valid_incident("lane_closure", lane_closure_ratio=True),
            valid_incident("demand_surge", demand_multiplier="1.5"),
            valid_incident(
                "signal_change",
                signal_plan_delta={"green_time_ratio_delta": "0.2"},
            ),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    IncidentVector.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
