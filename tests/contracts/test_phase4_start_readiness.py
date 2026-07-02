from pathlib import Path
import unittest

from scripts.validation.validate_phase4_start import validate_phase4_start


ROOT = Path(__file__).resolve().parents[2]


class Phase4StartReadinessTest(unittest.TestCase):
    def test_phase4_start_readiness_is_provisional_not_production(self) -> None:
        report = validate_phase4_start(
            contract_path=ROOT / "project_contract.json",
            gate_p1_path=ROOT / "data/derived/private/phase1_mock/gate_p1_report.json",
            gate_p2_path=ROOT
            / "data/derived/private/phase2_surrogate/provisional_gate_p2_report.json",
            gate_p3_path=ROOT / "data/derived/private/phase3_knowledge/gate_p3_report.json",
            pyproject_path=ROOT / "pyproject.toml",
            t4_package=ROOT / "src/stwi/t4_orchestrator/__init__.py",
        )

        self.assertEqual(report["status"], "ready_for_phase4_provisional")
        self.assertEqual(report["errors"], [])
        self.assertIs(report["production_ready"], False)
        self.assertIs(report["real_data_rework_required"], True)
        self.assertIs(report["human_approval_required"], True)
        self.assertIs(report["automatic_actuation_allowed"], False)
        self.assertIn(
            "execute candidate_action automatically",
            report["phase4_scope"]["prohibited"],
        )
        self.assertIn(
            "connect to field devices or traffic signal controllers",
            report["phase4_scope"]["prohibited"],
        )


if __name__ == "__main__":
    unittest.main()
