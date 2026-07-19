"""Regression tests for bounded GCN-LSTM training CLI inputs."""

from __future__ import annotations

import unittest

import numpy as np

from scripts.training.train_gcn_lstm_smoke import limit_indices


class TrainingCliLimitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.indices = np.asarray([2, 4, 6, 8], dtype=np.int64)

    def test_zero_uses_complete_split(self) -> None:
        selected = limit_indices(self.indices, 0, name="train")
        np.testing.assert_array_equal(selected, self.indices)

    def test_positive_limit_is_applied(self) -> None:
        selected = limit_indices(self.indices, 2, name="train")
        np.testing.assert_array_equal(selected, [2, 4])

    def test_negative_limit_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "zero or a positive integer"):
            limit_indices(self.indices, -1, name="train")

    def test_empty_split_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty split"):
            limit_indices(np.asarray([], dtype=np.int64), 0, name="train")


if __name__ == "__main__":
    unittest.main()
