import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from validation.validate_surrogate_benchmark_evidence import _validate, check_benchmark_evidence  # noqa: E402


class SurrogateBenchmarkEvidenceValidationTest(unittest.TestCase):
    def _write_compliant_report(self) -> Path:
        path = ROOT / "data/derived/private/phase2_surrogate/v3/benchmark_report_compliant.json"
        path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "p99_ms": 14.12,
                    "cpu_cores": 8,
                    "ram_gb": 32,
                    "gpu_vram_gb_min": 12,
                    "gpu_vram_gb_max": 16,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _write_non_compliant_report(self) -> Path:
        path = ROOT / "data/derived/private/phase2_surrogate/v3/benchmark_report_non_compliant.json"
        path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "p99_ms": 14.12,
                    "cpu_threads": 8,
                    "device": "cpu",
                    "payload_nodes": 20,
                    "warmup_runs": 20,
                    "measured_runs": 300,
                    "surrogate_p99_target_ms": 500,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_missing_gpu_profile_fields_are_reported(self) -> None:
        path = self._write_non_compliant_report()
        try:
            benchmark = json.loads(path.read_text(encoding="utf-8"))
            profile = {"cpu_cores": 8, "ram_gb": 32, "gpu_vram_gb_min": 12, "gpu_vram_gb_max": 16}
            errors = _validate(benchmark, profile)
            self.assertFalse(errors == [])
            self.assertTrue(any("missing profile fields" in error for error in errors))
            self.assertFalse(any("benchmark profile does not match contract" in error for error in errors))
        finally:
            path.unlink(missing_ok=True)

    def test_p99_above_threshold_is_reported(self) -> None:
        benchmark = {
            "status": "pass",
            "p99_ms": 600,
            "cpu_cores": 8,
            "ram_gb": 32,
            "gpu_vram_gb_min": 12,
            "gpu_vram_gb_max": 16,
        }
        profile = {"cpu_cores": 8, "ram_gb": 32, "gpu_vram_gb_min": 12, "gpu_vram_gb_max": 16}
        errors = _validate(benchmark, profile)
        self.assertTrue(any("not below 500 ms" in error for error in errors))

    def test_pass_when_profile_matches(self) -> None:
        path = self._write_compliant_report()
        try:
            import validation.validate_surrogate_benchmark_evidence as module

            original_path = module.BENCHMARK_PATH
            module.BENCHMARK_PATH = path
            try:
                result = module.check_benchmark_evidence()
                self.assertEqual(result["status"], "pass")
                self.assertEqual(result["recorded_profile"]["gpu_vram_gb_min"], 12)
                self.assertEqual(result["recorded_profile"]["gpu_vram_gb_max"], 16)
            finally:
                module.BENCHMARK_PATH = original_path
        finally:
            path.unlink(missing_ok=True)

    def test_check_benchmark_evidence_fails_with_non_compliant_artifact(self) -> None:
        path = self._write_non_compliant_report()
        try:
            import validation.validate_surrogate_benchmark_evidence as module

            original_path = module.BENCHMARK_PATH
            module.BENCHMARK_PATH = path
            try:
                result = module.check_benchmark_evidence()
                self.assertEqual(result["status"], "fail")
                self.assertTrue(any("missing profile fields" in error for error in result["errors"]))
            finally:
                module.BENCHMARK_PATH = original_path
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
