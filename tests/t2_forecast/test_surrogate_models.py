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
class SurrogateModelsTest(unittest.TestCase):
    def test_heterogeneous_models_share_contract(self) -> None:
        from stwi.t2_forecast.surrogate import build_surrogate

        values = torch.randn(2, 89)
        for name in ("mlp", "cnn1d", "transformer"):
            output = build_surrogate(name, 89, 363)(values)
            self.assertEqual(tuple(output.shape), (2, 363))


if __name__ == "__main__":
    unittest.main()
