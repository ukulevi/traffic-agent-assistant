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

The loop may refine only an isolated V/C policy failure. Legal evidence,
uncertainty, OOD, validation and dependency failures stop immediately for
human review. Every recorded iteration therefore represents a distinct, typed
candidate evaluation rather than a repeated placeholder check.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from stwi.contracts.incident import IncidentVector
from stwi.t4_orchestrator.contracts import CandidateAction, SafetyCheckResult
from stwi.t4_orchestrator.interfaces import (
    CandidateRefiner,
    ScenarioForecast,
    ScenarioForecaster,
)

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
DEFAULT_VC_THRESHOLD = 0.9
DEFAULT_UNCERTAINTY_THRESHOLD = 0.7
DEFAULT_OOD_THRESHOLD = 0.5


@dataclass(frozen=True)
class SafetyIteration:
    """One immutable candidate evaluation in the safety loop."""

    action: dict[str, Any]
    results: tuple[ScenarioForecast, ...]
    check: SafetyCheckResult


@dataclass(frozen=True)
class SafetyLoopOutcome:
    """Final outcome plus the candidate history used to reach it."""

    passed: bool
    iterations_run: int
    iterations: tuple[SafetyIteration, ...]
    selected_action: dict[str, Any]
    fail_reason: str | None = None

    @property
    def checks(self) -> tuple[SafetyCheckResult, ...]:
        return tuple(item.check for item in self.iterations)


class GreenTimeRatioRefiner:
    """Increase one node's green-time hypothesis after an isolated V/C failure."""

    def __init__(self, step: float = 0.15) -> None:
        if not 0 < step <= 1:
            raise ValueError("refinement step must be in (0, 1]")
        self._step = step

    def refine(
        self,
        current_action: dict[str, Any],
        check: SafetyCheckResult,
        iteration: int,
    ) -> dict[str, Any] | None:
        del iteration
        adjustable_vc_only = (
            not check.vc_ratio_ok
            and check.citations_ok
            and check.uncertainty_ok
            and check.ood_ok
        )
        if not adjustable_vc_only:
            return None
        current_ratio = float(current_action["green_time_ratio"])
        next_ratio = min(1.0, round(current_ratio + self._step, 10))
        if next_ratio <= current_ratio:
            return None
        return {**current_action, "green_time_ratio": next_ratio}


class CounterfactualSafetyLoop:
    """Counterfactual Safety Loop with configurable thresholds.

    Runs up to max_iterations distinct candidate evaluations. Only an isolated
    V/C policy failure may trigger the bounded green-time-ratio refiner;
    evidence, OOD, uncertainty and validation failures stop immediately.
    Passes iff ALL four safety gates pass in any single iteration.
    """

    def __init__(
        self,
        surrogate: ScenarioForecaster,
        vc_threshold: float = DEFAULT_VC_THRESHOLD,
        uncertainty_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD,
        ood_threshold: float = DEFAULT_OOD_THRESHOLD,
        max_iterations: int = MAX_ITERATIONS,
        refiner: CandidateRefiner | None = None,
    ) -> None:
        self._surrogate = surrogate
        self._vc_threshold = vc_threshold
        self._uncertainty_threshold = uncertainty_threshold
        self._ood_threshold = ood_threshold
        self._max_iterations = max_iterations
        self._refiner = refiner or GreenTimeRatioRefiner()

    def run(
        self,
        *,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
        incident: IncidentVector | None,
        has_citations: bool,
        initial_results: list[ScenarioForecast] | None = None,
    ) -> SafetyLoopOutcome:
        """Evaluate and, for isolated V/C failure, refine distinct candidates."""
        current_action = self._validate_action(candidate_action, node_ids)
        iterations: list[SafetyIteration] = []

        for iteration in range(1, self._max_iterations + 1):
            scenario_results = (
                initial_results
                if iteration == 1 and initial_results is not None
                else self._surrogate.predict(
                    node_ids=node_ids,
                    horizons_minutes=horizons_minutes,
                    candidate_action=current_action,
                    scenario_time=scenario_time,
                    incident=incident,
                )
            )
            check = self._evaluate_iteration(
                iteration=iteration,
                scenario_results=scenario_results,
                has_citations=has_citations,
            )
            iterations.append(
                SafetyIteration(
                    action=dict(current_action),
                    results=tuple(scenario_results),
                    check=check,
                )
            )

            if check.passed:
                logger.info(
                    "Safety loop passed on iteration %d / %d",
                    iteration,
                    self._max_iterations,
                )
                return SafetyLoopOutcome(
                    passed=True,
                    iterations_run=iteration,
                    iterations=tuple(iterations),
                    selected_action=dict(current_action),
                )

            logger.warning(
                "Safety loop iteration %d failed: %s",
                iteration,
                check.fail_reason,
            )

            # The final bounded iteration has evidence only for current_action.
            # Do not expose a newly refined, unevaluated hypothesis downstream.
            if iteration == self._max_iterations:
                break

            next_action = self._refiner.refine(current_action, check, iteration)
            if next_action is None:
                return SafetyLoopOutcome(
                    passed=False,
                    iterations_run=len(iterations),
                    iterations=tuple(iterations),
                    selected_action=dict(current_action),
                    fail_reason=check.fail_reason or "refinement_unavailable",
                )
            try:
                validated_next = self._validate_action(next_action, node_ids)
            except (ValueError, ValidationError):
                return SafetyLoopOutcome(
                    passed=False,
                    iterations_run=len(iterations),
                    iterations=tuple(iterations),
                    selected_action=dict(current_action),
                    fail_reason="invalid_refined_candidate",
                )
            if validated_next == current_action:
                return SafetyLoopOutcome(
                    passed=False,
                    iterations_run=len(iterations),
                    iterations=tuple(iterations),
                    selected_action=dict(current_action),
                    fail_reason="duplicate_refined_candidate",
                )
            current_action = validated_next

        final_reason = (
            iterations[-1].check.fail_reason if iterations else "no_iterations_run"
        )
        return SafetyLoopOutcome(
            passed=False,
            iterations_run=len(iterations),
            iterations=tuple(iterations),
            selected_action=dict(current_action),
            fail_reason=final_reason,
        )

    @staticmethod
    def _validate_action(
        action: dict[str, Any], node_ids: list[str]
    ) -> dict[str, Any]:
        validated = CandidateAction.model_validate(action)
        if validated.node_id not in node_ids:
            raise ValueError("refined candidate node_id is outside request scope")
        return validated.model_dump()

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
    "GreenTimeRatioRefiner",
    "SafetyIteration",
    "SafetyLoopOutcome",
    "MAX_ITERATIONS",
    "DEFAULT_VC_THRESHOLD",
    "DEFAULT_UNCERTAINTY_THRESHOLD",
    "DEFAULT_OOD_THRESHOLD",
]
