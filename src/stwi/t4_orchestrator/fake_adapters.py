"""Fake/in-memory adapters for Phase 4 contract tests.

These adapters replace real ML models and services so that contract tests
run without GPU, Qdrant, TimescaleDB, or Redis.

All fake adapters are labelled synthetic_mock and must never be used in
production or to claim benchmark accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# =============================================================================
# Forecast result shapes
# =============================================================================

@dataclass(frozen=True)
class BaselineForecastResult:
    """Aggregate-only baseline forecast (no raw frame data)."""

    node_id: str
    horizon_minutes: int
    predicted_volume: float    # vehicles/5min
    predicted_speed: float     # km/h
    model_version: str = "provisional_mock_v1"
    data_version: str = "synthetic_mock_phase4"
    warning: str = "Phase 2 uses synthetic/mock data. Not production-ready."


@dataclass(frozen=True)
class ScenarioForecastResult:
    """Aggregate-only surrogate forecast for a candidate action."""

    node_id: str
    horizon_minutes: int
    predicted_volume: float
    predicted_speed: float
    vc_ratio: float            # volume-capacity ratio (safety-critical)
    uncertainty_score: float   # 0.0 (certain) – 1.0 (max uncertain)
    ood_score: float           # 0.0 (in-dist) – 1.0 (out-of-dist)
    model_version: str = "provisional_mock_v1"
    data_version: str = "synthetic_mock_phase4"
    warning: str = "Phase 2 uses synthetic/mock data. Not production-ready."


# =============================================================================
# Fake baseline forecaster
# =============================================================================

class FakeBaselineForecaster:
    """In-memory baseline forecaster — no ML models required.

    Returns configurable synthetic predictions for each node/horizon pair.
    """

    def __init__(
        self,
        default_volume: float = 120.0,
        default_speed: float = 45.0,
    ) -> None:
        self._default_volume = default_volume
        self._default_speed = default_speed

    def predict(
        self,
        node_ids: list[str],
        horizons_minutes: list[int],
        scenario_time: datetime,
    ) -> list[BaselineForecastResult]:
        """Return synthetic baseline predictions."""
        results = []
        for node_id in node_ids:
            for h in horizons_minutes:
                # Simple synthetic decay: speed decreases at longer horizons
                speed = max(self._default_speed - h * 0.3, 10.0)
                results.append(
                    BaselineForecastResult(
                        node_id=node_id,
                        horizon_minutes=h,
                        predicted_volume=self._default_volume,
                        predicted_speed=speed,
                    )
                )
        return results


# =============================================================================
# Fake surrogate forecaster (configurable for test scenarios)
# =============================================================================

@dataclass
class SurrogateScenario:
    """Configurable per-node scenario for FakeSurrogateForecaster.

    Set vc_ratio > vc_threshold to simulate safety failure.
    Set ood_score > ood_threshold to simulate OOD rejection.
    Set uncertainty_score > uncertainty_threshold for high-uncertainty rejection.
    """

    vc_ratio: float = 0.75
    uncertainty_score: float = 0.1
    ood_score: float = 0.05
    predicted_volume: float = 100.0
    predicted_speed: float = 50.0


class FakeSurrogateForecaster:
    """In-memory surrogate forecaster with configurable scenario outcomes.

    Used to exercise all Safety Loop branches in contract tests:
    - Pass (vc_ratio ok, uncertainty ok, ood ok)
    - Fail on vc_ratio
    - Fail on OOD
    - Fail on uncertainty
    """

    def __init__(
        self,
        default_scenario: SurrogateScenario | None = None,
        node_overrides: dict[str, SurrogateScenario] | None = None,
    ) -> None:
        self._default = default_scenario or SurrogateScenario()
        self._node_overrides: dict[str, SurrogateScenario] = node_overrides or {}

    def predict(
        self,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
    ) -> list[ScenarioForecastResult]:
        """Return synthetic scenario predictions with safety metrics."""
        results = []
        for node_id in node_ids:
            scenario = self._node_overrides.get(node_id, self._default)
            for h in horizons_minutes:
                results.append(
                    ScenarioForecastResult(
                        node_id=node_id,
                        horizon_minutes=h,
                        predicted_volume=scenario.predicted_volume,
                        predicted_speed=scenario.predicted_speed,
                        vc_ratio=scenario.vc_ratio,
                        uncertainty_score=scenario.uncertainty_score,
                        ood_score=scenario.ood_score,
                    )
                )
        return results

    def max_vc_ratio(self, results: list[ScenarioForecastResult]) -> float:
        if not results:
            return 0.0
        return max(r.vc_ratio for r in results)

    def max_uncertainty(self, results: list[ScenarioForecastResult]) -> float:
        if not results:
            return 0.0
        return max(r.uncertainty_score for r in results)

    def max_ood_score(self, results: list[ScenarioForecastResult]) -> float:
        if not results:
            return 0.0
        return max(r.ood_score for r in results)


# =============================================================================
# Pre-built scenarios for standard test cases
# =============================================================================

def safe_scenario() -> SurrogateScenario:
    """Scenario that passes all safety checks (vc_ratio well below threshold)."""
    return SurrogateScenario(vc_ratio=0.70, uncertainty_score=0.05, ood_score=0.02)


def unsafe_vc_scenario(vc_ratio: float = 0.95) -> SurrogateScenario:
    """Scenario that fails vc_ratio check (congestion risk)."""
    return SurrogateScenario(vc_ratio=vc_ratio, uncertainty_score=0.05, ood_score=0.02)


def ood_scenario() -> SurrogateScenario:
    """Scenario that triggers OOD rejection."""
    return SurrogateScenario(vc_ratio=0.70, uncertainty_score=0.05, ood_score=0.85)


def high_uncertainty_scenario() -> SurrogateScenario:
    """Scenario that triggers high-uncertainty rejection."""
    return SurrogateScenario(vc_ratio=0.70, uncertainty_score=0.90, ood_score=0.02)


__all__ = [
    "BaselineForecastResult",
    "ScenarioForecastResult",
    "SurrogateScenario",
    "FakeBaselineForecaster",
    "FakeSurrogateForecaster",
    "safe_scenario",
    "unsafe_vc_scenario",
    "ood_scenario",
    "high_uncertainty_scenario",
]
