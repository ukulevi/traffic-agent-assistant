"""Deterministic synthetic adapters used only by ``STWI_RUNTIME_MODE=demo``.

The values exercise safety branches and make the operator UI reproducible.
They are not calibrated forecasts and must never be wired in production.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from stwi.t1_pipeline.mock_data import generate_mock_network
from stwi.t4_orchestrator.fake_adapters import (
    ScenarioForecastResult,
    SurrogateScenario,
)


def demo_node_ids() -> tuple[str, ...]:
    """Return the canonical node order of the versioned synthetic network."""

    return generate_mock_network().node_ids


class DemoSurrogateForecaster:
    """Ratio-sensitive synthetic surrogate with deterministic safety profiles."""

    is_provisional_adapter = True

    _PROFILE_OVERRIDES = {
        "node_01": SurrogateScenario(
            vc_ratio=0.95,
            uncertainty_score=0.10,
            ood_score=0.05,
            predicted_volume=145.0,
            predicted_speed=24.0,
        ),
        "node_02": SurrogateScenario(
            vc_ratio=0.72,
            uncertainty_score=0.10,
            ood_score=0.85,
            predicted_volume=108.0,
            predicted_speed=43.0,
        ),
        "node_03": SurrogateScenario(
            vc_ratio=0.73,
            uncertainty_score=0.90,
            ood_score=0.05,
            predicted_volume=110.0,
            predicted_speed=41.0,
        ),
    }

    def predict(
        self,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
    ) -> list[ScenarioForecastResult]:
        """Return aggregate-only scenario estimates for the selected profile."""

        del scenario_time
        ratio = float(candidate_action["green_time_ratio"])
        results: list[ScenarioForecastResult] = []
        for node_id in node_ids:
            profile = self._scenario_for(node_id, ratio)
            for horizon in horizons_minutes:
                horizon_pressure = max(horizon - 5, 0) / 25
                results.append(
                    ScenarioForecastResult(
                        node_id=node_id,
                        horizon_minutes=horizon,
                        predicted_volume=profile.predicted_volume * (1 + 0.03 * horizon_pressure),
                        predicted_speed=max(profile.predicted_speed * (1 - 0.04 * horizon_pressure), 5.0),
                        vc_ratio=min(profile.vc_ratio + 0.01 * horizon_pressure, 1.5),
                        uncertainty_score=profile.uncertainty_score,
                        ood_score=profile.ood_score,
                    )
                )
        return results

    def _scenario_for(self, node_id: str, ratio: float) -> SurrogateScenario:
        if ratio <= 0.05 or ratio >= 0.95:
            return SurrogateScenario(
                vc_ratio=0.96,
                uncertainty_score=0.92,
                ood_score=0.80,
                predicted_volume=155.0,
                predicted_speed=18.0,
            )
        if node_id in self._PROFILE_OVERRIDES:
            return self._PROFILE_OVERRIDES[node_id]

        ratio_delta = ratio - 0.70
        return SurrogateScenario(
            vc_ratio=max(0.10, min(0.89, 0.75 - ratio_delta * 0.30)),
            uncertainty_score=0.10,
            ood_score=0.05,
            predicted_volume=max(20.0, 100.0 - ratio_delta * 60.0),
            predicted_speed=max(8.0, 50.0 + ratio_delta * 20.0),
        )

    @staticmethod
    def max_vc_ratio(results: list[ScenarioForecastResult]) -> float:
        return max((result.vc_ratio for result in results), default=0.0)

    @staticmethod
    def max_uncertainty(results: list[ScenarioForecastResult]) -> float:
        return max((result.uncertainty_score for result in results), default=1.0)

    @staticmethod
    def max_ood_score(results: list[ScenarioForecastResult]) -> float:
        return max((result.ood_score for result in results), default=1.0)


__all__ = ["DemoSurrogateForecaster", "demo_node_ids"]
