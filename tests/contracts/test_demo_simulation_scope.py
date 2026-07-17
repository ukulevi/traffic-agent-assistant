"""Contract tests for the approved simulation-first demo boundary."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.validation.validate_demo_simulation_scope import validate_demo_scope
from scripts.validation.validate_provisional_phase2_gate import (
    _validate_demo_policy,
)


ROOT = Path(__file__).resolve().parents[2]


class DemoSimulationScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(
            (ROOT / "data/manifests/phase2_temporary_data_policy.json").read_text(
                encoding="utf-8"
            )
        )
        cls.handoff = json.loads(
            (ROOT / "data/manifests/phase3_temporary_handoff.json").read_text(
                encoding="utf-8"
            )
        )
        cls.contract = json.loads(
            (ROOT / "project_contract.json").read_text(encoding="utf-8")
        )

    def test_approved_scope_passes_without_production_claim(self) -> None:
        report = validate_demo_scope(self.policy, self.handoff, self.contract)
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["frame_derived_forecast_allowed"])
        self.assertFalse(report["production_ready"])
        self.assertFalse(report["automatic_actuation_allowed"])

    def test_frame_forecast_policy_fails_closed(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["prohibited_forecast_inputs"] = []
        with self.assertRaisesRegex(ValueError, "frame-derived"):
            validate_demo_scope(policy, self.handoff, self.contract)

    def test_production_claim_fails_closed(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["prohibited_claims"] = []
        with self.assertRaisesRegex(ValueError, "production claims"):
            validate_demo_scope(policy, self.handoff, self.contract)

    def test_demo_gate_policy_is_explicitly_approved(self) -> None:
        self.assertEqual(_validate_demo_policy(self.policy), [])

    def test_demo_gate_rejects_production_scope_drift(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["production_scope_deferred"] = False
        self.assertIn(
            "production scope must remain deferred",
            _validate_demo_policy(policy),
        )


if __name__ == "__main__":
    unittest.main()
