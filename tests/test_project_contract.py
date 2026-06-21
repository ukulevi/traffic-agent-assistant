import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "project_contract.json").read_text(encoding="utf-8"))


class ProjectContractTest(unittest.TestCase):
    def test_tensor_contract(self):
        data = CONTRACT["data_contract"]
        self.assertEqual(data["input_shape"], "X[B,12,N,16]")
        self.assertEqual(data["adjacency_shape"], "A[N,N]")
        self.assertEqual(data["missing_mask_shape"], "M[B,12,N,16]")
        self.assertEqual(data["forecast_shape"], "Y[B,6,N,2]")
        self.assertEqual(len(data["features"]), 16)
        self.assertEqual(data["features"][-1]["name"], "green_time_ratio")

    def test_runtime_contract(self):
        runtime = CONTRACT["runtime"]
        self.assertEqual(runtime["surrogate_p99_ms"], 500)
        self.assertEqual(runtime["e2e_p95_ms"], 30000)
        self.assertEqual(runtime["hard_deadline_p99_ms"], 180000)

    def test_fail_closed_api_contract(self):
        self.assertTrue(CONTRACT["safety"]["fail_closed"])
        self.assertTrue(CONTRACT["safety"]["human_approval_required"])
        self.assertEqual(CONTRACT["api"]["create_status"], 202)
        self.assertIn("needs_review", CONTRACT["api"]["statuses"])
        self.assertEqual(CONTRACT["api"]["legal_evidence_field"], "citations")

    def test_legal_sources_are_versioned(self):
        sources = {item["number"]: item for item in CONTRACT["legal_corpus"]}
        self.assertEqual(sources["35/2024/QH15"]["effective_from"], "2025-01-01")
        self.assertEqual(sources["36/2024/QH15"]["effective_from"], "2025-01-01")
        self.assertTrue(all(item["source_url"].startswith("https://") for item in sources.values()))


if __name__ == "__main__":
    unittest.main()
