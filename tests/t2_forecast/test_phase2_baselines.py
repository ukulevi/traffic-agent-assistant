import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t2_forecast.baselines import (  # noqa: E402
    fit_seasonal_ridge,
    persistence_forecast,
    regression_metrics,
    seasonal_ridge_forecast,
)


class Phase2BaselinesTest(unittest.TestCase):
    def test_persistence_shape_and_metrics(self) -> None:
        last = np.array([[[10.0, 40.0], [20.0, 30.0]]], dtype=np.float32)
        prediction = persistence_forecast(last, 6)
        self.assertEqual(prediction.shape, (1, 6, 2, 2))
        metrics = regression_metrics(prediction, prediction.copy())
        self.assertEqual(metrics["mae"], 0.0)
        self.assertEqual(metrics["rmse"], 0.0)

    def test_seasonal_ridge_shapes(self) -> None:
        rng = np.random.default_rng(3)
        X = rng.normal(size=(12, 12, 2, 16)).astype(np.float32)
        Y = rng.normal(size=(12, 6, 2, 2)).astype(np.float32)
        coefficients = fit_seasonal_ridge(X, Y)
        prediction = seasonal_ridge_forecast(X, coefficients, 6, 2)
        self.assertEqual(prediction.shape, Y.shape)


class PersistenceForecastValidationTest(unittest.TestCase):
    """Tests for persistence_forecast input validation and value correctness."""

    def test_invalid_ndim_raises(self) -> None:
        bad_2d = np.zeros((3, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            persistence_forecast(bad_2d, 4)

    def test_invalid_last_dim_raises(self) -> None:
        bad_last = np.zeros((1, 3, 5), dtype=np.float32)
        with self.assertRaises(ValueError):
            persistence_forecast(bad_last, 4)

    def test_values_are_repeated(self) -> None:
        last = np.array([[[1.0, 2.0], [3.0, 4.0]]], dtype=np.float32)
        prediction = persistence_forecast(last, 5)
        for step in range(5):
            np.testing.assert_array_equal(prediction[0, step], last[0])


class RegressionMetricsMathTest(unittest.TestCase):
    """Tests for regression_metrics numerical correctness."""

    def test_known_mae_and_rmse(self) -> None:
        # prediction = 3, target = 1 everywhere => error = 2
        # MAE = 2.0, RMSE = 2.0
        prediction = np.full((1, 2, 3, 2), 3.0, dtype=np.float32)
        target = np.full((1, 2, 3, 2), 1.0, dtype=np.float32)
        m = regression_metrics(prediction, target)
        self.assertAlmostEqual(m["mae"], 2.0, places=5)
        self.assertAlmostEqual(m["rmse"], 2.0, places=5)

    def test_mixed_errors_mae_rmse(self) -> None:
        # Single element per slice to make math trivial:
        # errors: +1, -3  =>  MAE = (1+3)/2 = 2.0,  RMSE = sqrt((1+9)/2) = sqrt(5)
        prediction = np.array([[[[1.0, 0.0]]]], dtype=np.float32)
        target = np.array([[[[0.0, 3.0]]]], dtype=np.float32)
        m = regression_metrics(prediction, target)
        self.assertAlmostEqual(m["mae"], 2.0, places=5)
        self.assertAlmostEqual(m["rmse"], float(np.sqrt(5.0)), places=5)

    def test_mismatched_shapes_raises(self) -> None:
        a = np.zeros((1, 2, 3, 2), dtype=np.float32)
        b = np.zeros((1, 2, 3, 4), dtype=np.float32)
        with self.assertRaises(ValueError):
            regression_metrics(a, b)

    def test_wrong_ndim_raises(self) -> None:
        a = np.zeros((2, 3, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            regression_metrics(a, a)

    def test_mae_by_target_length(self) -> None:
        prediction = np.ones((2, 4, 3, 2), dtype=np.float32)
        target = np.zeros((2, 4, 3, 2), dtype=np.float32)
        m = regression_metrics(prediction, target)
        self.assertEqual(len(m["mae_by_target"]), 2)

    def test_mae_by_horizon_length(self) -> None:
        prediction = np.ones((2, 6, 3, 2), dtype=np.float32)
        target = np.zeros((2, 6, 3, 2), dtype=np.float32)
        m = regression_metrics(prediction, target)
        self.assertEqual(len(m["mae_by_horizon"]), 6)


class SeasonalRidgeValidationTest(unittest.TestCase):
    """Tests for fit_seasonal_ridge input validation and determinism."""

    def test_invalid_X_ndim_raises(self) -> None:
        X = np.zeros((12, 12, 16), dtype=np.float32)  # 3-D, needs 4-D
        Y = np.zeros((12, 6, 2, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            fit_seasonal_ridge(X, Y)

    def test_invalid_Y_ndim_raises(self) -> None:
        X = np.zeros((12, 12, 2, 16), dtype=np.float32)
        Y = np.zeros((12, 6, 2), dtype=np.float32)  # 3-D, needs 4-D
        with self.assertRaises(ValueError):
            fit_seasonal_ridge(X, Y)

    def test_batch_mismatch_raises(self) -> None:
        X = np.zeros((10, 12, 2, 16), dtype=np.float32)
        Y = np.zeros((12, 6, 2, 2), dtype=np.float32)
        with self.assertRaises(ValueError):
            fit_seasonal_ridge(X, Y)

    def test_ridge_forecast_deterministic(self) -> None:
        rng = np.random.default_rng(42)
        X = rng.normal(size=(8, 12, 2, 16)).astype(np.float32)
        Y = rng.normal(size=(8, 6, 2, 2)).astype(np.float32)
        coeff = fit_seasonal_ridge(X, Y)
        pred1 = seasonal_ridge_forecast(X, coeff, 6, 2)
        pred2 = seasonal_ridge_forecast(X, coeff, 6, 2)
        np.testing.assert_array_equal(pred1, pred2)


if __name__ == "__main__":
    unittest.main()
