import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, "forecast extra is not installed")
class GCNLSTMTest(unittest.TestCase):
    def test_contract_shapes(self) -> None:
        from stwi.t2_forecast.gcn_lstm import GCNLSTM

        model = GCNLSTM()
        X = torch.randn(2, 12, 20, 16)
        M = torch.ones_like(X, dtype=torch.bool)
        A = torch.eye(20)
        output = model(X, M, A)
        self.assertEqual(tuple(output.shape), (2, 6, 20, 2))


if __name__ == "__main__":
    unittest.main()
