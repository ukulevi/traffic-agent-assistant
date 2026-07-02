"""Counterfactual Safety Loop — Phase 4 orchestrator.

Inspired by CF-VLA (not an end-to-end VLA model).

Contract (from project_contract.json):
- max_iterations: 3
- default_vc_threshold: 0.9 (configurable policy)
- fail_closed: true — any unresolved safety issue returns needs_review
- human_approval_required: true — succeeded jobs still require human sign-off

The loop evaluates a candidate action against four safety gates:
  1. vc_ratio     — volume/capacity ratio must stay below threshold (traffic safety)
  2. citations    — legal evidence must exist (legal grounding required)
  3. uncertainty  — model uncertainty must be within acceptable bounds
  4. ood          — input must be in-distribution for the surrogate

If any gate fails after MAX_ITERATIONS attempts, the job transitions to
needs_review with the candidate_action (NOT recommended_action). The human
operator receives the candidate_action and all evidence to make the final call.

Phase 4 provisional note: the loop runs MAX_ITERATIONS on non-convergence but
does not currently modify the candidate_action between iterations (no
optimizer). The repeated checks provide an audit-compatible placeholder for
Phase 5 action refinement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from stwi.t4_orchestrator.contracts import SafetyCheckResult
from stwi.t4_orchestrator.interfaces import ScenarioForecast, ScenarioForecaster

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
DEFAULT_VC_THRESHOLD = 0.9
DEFAULT_UNCERTAINTY_THRESHOLD = 0.7
DEFAULT_OOD_THRESHOLD = 0.5


@dataclass(frozen=True)
class SafetyLoopOutcome:
    """Final outcome of the Counterfactual Safety Loop."""

    passed: bool
    iterations_run: int
    checks: list[SafetyCheckResult]
    fail_reason: str | None = None


class CounterfactualSafetyLoop:
    """Counterfactual Safety Loop with configurable thresholds.

    Phase 4 provisional: runs up to max_iterations evaluations.
    Each iteration checks the same candidate_action (no optimizer yet).
    Passes iff ALL four safety gates pass in any single iteration.
    """

    def __init__(
        self,
        surrogate: ScenarioForecaster,
        vc_threshold: float = DEFAULT_VC_THRESHOLD,
        uncertainty_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD,
        ood_threshold: float = DEFAULT_OOD_THRESHOLD,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        self._surrogate = surrogate
        self._vc_threshold = vc_threshold
        self._uncertainty_threshold = uncertainty_threshold
        self._ood_threshold = ood_threshold
        self._max_iterations = max_iterations

    def run(
        self,
        scenario_results: list[ScenarioForecast],
        has_citations: bool,
    ) -> SafetyLoopOutcome:
        """Evaluate the scenario results against all safety gates.

        Args:
            scenario_results: Predictions from surrogate for this iteration.
            has_citations: Whether T3 returned valid legal evidence.

        Returns:
            SafetyLoopOutcome with pass/fail and per-gate details.
        """
        checks: list[SafetyCheckResult] = []

        for iteration in range(1, self._max_iterations + 1):
            check = self._evaluate_iteration(
                iteration=iteration,
                scenario_results=scenario_results,
                has_citations=has_citations,
            )
            checks.append(check)

            if check.passed:
                logger.info(
                    "Safety loop passed on iteration %d / %d",
                    iteration,
                    self._max_iterations,
                )
                return SafetyLoopOutcome(
                    passed=True,
                    iterations_run=iteration,
                    checks=checks,
                )

            logger.warning(
                "Safety loop iteration %d failed: %s",
                iteration,
                check.fail_reason,
            )

            # Phase 4 provisional: no action optimizer yet, so each iteration
            # re-evaluates the same candidate for audit-compatible CSL traces.

        final_reason = checks[-1].fail_reason if checks else "no_iterations_run"
        return SafetyLoopOutcome(
            passed=False,
            iterations_run=len(checks),
            checks=checks,
            fail_reason=final_reason,
        )

    def _evaluate_iteration(
        self,
        iteration: int,
        scenario_results: list[ScenarioForecast],
        has_citations: bool,
    ) -> SafetyCheckResult:
        """Run all four safety gates for one iteration."""
        max_vc = self._surrogate.max_vc_ratio(scenario_results)
        max_unc = self._surrogate.max_uncertainty(scenario_results)
        max_ood = self._surrogate.max_ood_score(scenario_results)

        vc_ok = max_vc <= self._vc_threshold
        citations_ok = has_citations
        uncertainty_ok = max_unc <= self._uncertainty_threshold
        ood_ok = max_ood <= self._ood_threshold

        passed = vc_ok and citations_ok and uncertainty_ok and ood_ok

        fail_reason: str | None = None
        if not passed:
            reasons = []
            if not vc_ok:
                reasons.append(
                    f"vc_ratio {max_vc:.3f} exceeds threshold {self._vc_threshold:.3f}"
                )
            if not citations_ok:
                reasons.append("missing_legal_evidence")
            if not ood_ok:
                reasons.append(
                    f"ood_score {max_ood:.3f} exceeds threshold {self._ood_threshold:.3f}"
                )
            if not uncertainty_ok:
                reasons.append(
                    f"uncertainty {max_unc:.3f} exceeds threshold {self._uncertainty_threshold:.3f}"
                )
            fail_reason = "; ".join(reasons)

        return SafetyCheckResult(
            passed=passed,
            iteration=iteration,
            vc_ratio_ok=vc_ok,
            citations_ok=citations_ok,
            uncertainty_ok=uncertainty_ok,
            ood_ok=ood_ok,
            fail_reason=fail_reason,
            max_vc_ratio=max_vc,
            vc_threshold=self._vc_threshold,
            uncertainty_score=max_unc,
            ood_score=max_ood,
        )


__all__ = [
    "CounterfactualSafetyLoop",
    "SafetyLoopOutcome",
    "MAX_ITERATIONS",
    "DEFAULT_VC_THRESHOLD",
    "DEFAULT_UNCERTAINTY_THRESHOLD",
    "DEFAULT_OOD_THRESHOLD",
]
