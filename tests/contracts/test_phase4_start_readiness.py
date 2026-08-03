import json
from pathlib import Path
import tempfile
import unittest

from scripts.validation.validate_phase4_start import validate_phase4_start


ROOT = Path(__file__).resolve().parents[2]


class Phase4StartReadinessTest(unittest.TestCase):
    def test_phase4_start_readiness_is_provisional_not_production(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture_root = Path(temp_dir)
            gate_paths = {
                "p1": fixture_root / "gate_p1_report.json",
                "p2": fixture_root / "gate_p2_report.json",
                "p3": fixture_root / "gate_p3_report.json",
            }
            fixtures = {
                "p1": {
                    "status": "pass",
                    "privacy": "aggregate_only_no_video_or_frames",
                },
                "p2": {
                    "status": "provisional_pass_for_phase3",
                    "production_ready": False,
                    "safety_gate": {"recommended_action_allowed": False},
                    "surrogate_gate": {"p99_ms": 499},
                    "mandatory_rework": ["replace mock inputs with real aggregates"],
                },
                "p3": {
                    "status": "pass",
                    "gate_criteria": {
                        "corpus_ok": True,
                        "retrieval_questions_ok": True,
                        "citation_precision_ok": True,
                        "unsupported_claim_ok": True,
                        "false_positive_ok": True,
                        "no_raw_sql_path": True,
                    },
                    "retrieval": {
                        "total_questions": 50,
                        "citation_precision": 0.95,
                        "unsupported_claim_rate": 0.0,
                        "false_positive_rate": 0.0,
                    },
                    "known_limitations": ["fixture-only readiness evidence"],
                },
            }
            for gate, path in gate_paths.items():
                path.write_text(
                    json.dumps(fixtures[gate]) + "\n",
                    encoding="utf-8",
                )

            report = validate_phase4_start(
                contract_path=ROOT / "project_contract.json",
                gate_p1_path=gate_paths["p1"],
                gate_p2_path=gate_paths["p2"],
                gate_p3_path=gate_paths["p3"],
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
