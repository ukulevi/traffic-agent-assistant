"""Fail-closed policy boundary for provisional surrogate inference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurrogateGateDecision:
    status: str
    reason: str
    recommended_action_allowed: bool = False


def gate_surrogate_result(
    *,
    uncertainty_score: float,
    uncertainty_threshold: float,
    ood_score: float,
    ood_threshold: float,
) -> SurrogateGateDecision:
    if ood_score > ood_threshold:
        return SurrogateGateDecision("needs_review", "out_of_distribution")
    if uncertainty_score > uncertainty_threshold:
        return SurrogateGateDecision("needs_review", "high_uncertainty")
    return SurrogateGateDecision(
        "eligible_for_safety_loop", "within_provisional_policy"
    )
