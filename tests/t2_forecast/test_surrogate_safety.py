import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t2_forecast.safety import gate_surrogate_result  # noqa: E402


class SurrogateSafetyTest(unittest.TestCase):
    def test_ood_and_uncertainty_fail_closed(self) -> None:
        ood = gate_surrogate_result(
            uncertainty_score=0.1,
            uncertainty_threshold=1.0,
            ood_score=3.0,
            ood_threshold=2.0,
        )
        uncertain = gate_surrogate_result(
            uncertainty_score=2.0,
            uncertainty_threshold=1.0,
            ood_score=0.1,
            ood_threshold=2.0,
        )
        self.assertEqual(ood.status, "needs_review")
        self.assertEqual(uncertain.status, "needs_review")
        self.assertFalse(ood.recommended_action_allowed)
        self.assertFalse(uncertain.recommended_action_allowed)


class SurrogateSafetyPassingTest(unittest.TestCase):
    """Tests for the passing / eligible path."""

    def test_both_below_threshold_passes(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=0.5,
            uncertainty_threshold=1.0,
            ood_score=1.0,
            ood_threshold=2.0,
        )
        self.assertEqual(result.status, "eligible_for_safety_loop")
        self.assertFalse(result.recommended_action_allowed)  # gate defers to safety loop

    def test_zero_scores_pass(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=0.0,
            uncertainty_threshold=1.0,
            ood_score=0.0,
            ood_threshold=1.0,
        )
        self.assertEqual(result.status, "eligible_for_safety_loop")
        self.assertFalse(result.recommended_action_allowed)  # gate defers to safety loop

    def test_negative_scores_pass(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=-5.0,
            uncertainty_threshold=1.0,
            ood_score=-3.0,
            ood_threshold=1.0,
        )
        self.assertEqual(result.status, "eligible_for_safety_loop")
        self.assertFalse(result.recommended_action_allowed)  # gate defers to safety loop


class SurrogateSafetyBoundaryTest(unittest.TestCase):
    """Boundary tests: exactly AT threshold should pass (strict > comparison)."""

    def test_ood_exactly_at_threshold_passes(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=0.1,
            uncertainty_threshold=1.0,
            ood_score=2.0,
            ood_threshold=2.0,
        )
        self.assertEqual(result.status, "eligible_for_safety_loop")
        self.assertFalse(result.recommended_action_allowed)  # gate defers to safety loop

    def test_uncertainty_exactly_at_threshold_passes(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=1.0,
            uncertainty_threshold=1.0,
            ood_score=0.1,
            ood_threshold=2.0,
        )
        self.assertEqual(result.status, "eligible_for_safety_loop")
        self.assertFalse(result.recommended_action_allowed)  # gate defers to safety loop


class SurrogateSafetyReasonStringsTest(unittest.TestCase):
    """Tests for the specific reason strings on failure."""

    def test_ood_failure_reason(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=0.1,
            uncertainty_threshold=1.0,
            ood_score=3.0,
            ood_threshold=2.0,
        )
        self.assertEqual(result.reason, "out_of_distribution")

    def test_uncertainty_failure_reason(self) -> None:
        result = gate_surrogate_result(
            uncertainty_score=5.0,
            uncertainty_threshold=1.0,
            ood_score=0.1,
            ood_threshold=2.0,
        )
        self.assertEqual(result.reason, "high_uncertainty")

    def test_ood_checked_before_uncertainty(self) -> None:
        """When both scores exceed thresholds, OOD reason takes precedence."""
        result = gate_surrogate_result(
            uncertainty_score=5.0,
            uncertainty_threshold=1.0,
            ood_score=5.0,
            ood_threshold=1.0,
        )
        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.reason, "out_of_distribution")


if __name__ == "__main__":
    unittest.main()
