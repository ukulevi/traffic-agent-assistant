import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validation.validate_provisional_phase2_gate import _check_benchmark_profile  # noqa: E402


class ValidateProvisionalPhase2GateOfflineTest(unittest.TestCase):
    def _write_report(self, report):  # type: ignore[no-untyped-def]
        path = Path("data/derived/private/phase2_surrogate/v3/benchmark_report.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return path

    def test_profile_mismatch_is_reported(self) -> None:
        report_path = self._write_report(
            {
                "status": "pass",
                "p99_ms": 14.12,
                "cpu_threads": 4,
                "device": "cpu",
                "payload_nodes": 20,
                "warmup_runs": 20,
                "measured_runs": 300,
                "surrogate_p99_target_ms": 500,
            }
        )
        try:
            errors = _check_benchmark_profile(json.loads(report_path.read_text(encoding="utf-8")))
            self.assertFalse(errors == [])
            self.assertTrue(any("benchmark profile does not match contract" in error for error in errors))
            self.assertTrue(any("missing profile fields" in error for error in errors))
        finally:
            report_path.unlink(missing_ok=True)

    def test_pass_when_profile_matches(self) -> None:
        report_path = self._write_report(
            {
                "status": "pass",
                "p99_ms": 14.12,
                "cpu_threads": 8,
                "device": "cpu",
                "payload_nodes": 20,
                "warmup_runs": 20,
                "measured_runs": 300,
                "surrogate_p99_target_ms": 500,
                "ram_gb": 32,
                "gpu_vram_gb_min": 12,
                "gpu_vram_gb_max": 16,
            }
        )
        try:
            errors = _check_benchmark_profile(json.loads(report_path.read_text(encoding="utf-8")))
            self.assertEqual(errors, [])
        finally:
            report_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
