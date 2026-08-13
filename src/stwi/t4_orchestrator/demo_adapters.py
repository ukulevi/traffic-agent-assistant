"""Deterministic synthetic adapters used only by ``STWI_RUNTIME_MODE=demo``.

The values exercise safety branches and make the operator UI reproducible.
They are not calibrated forecasts and must never be wired in production.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from stwi.contracts.incident import IncidentType, IncidentVector
from stwi.t1_pipeline.mock_data import generate_mock_network
from stwi.t4_orchestrator.contracts import RouteCandidate
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

    _EVENT_PROFILES = {
        IncidentType.ACCIDENT: SurrogateScenario(
            vc_ratio=0.94,
            uncertainty_score=0.18,
            ood_score=0.15,
            predicted_volume=138.0,
            predicted_speed=22.0,
        ),
        IncidentType.FLOOD: SurrogateScenario(
            vc_ratio=0.98,
            uncertainty_score=0.25,
            ood_score=0.30,
            predicted_volume=72.0,
            predicted_speed=12.0,
        ),
        IncidentType.LANE_CLOSURE: SurrogateScenario(
            vc_ratio=0.92,
            uncertainty_score=0.15,
            ood_score=0.10,
            predicted_volume=118.0,
            predicted_speed=27.0,
        ),
        IncidentType.DEMAND_SURGE: SurrogateScenario(
            vc_ratio=0.97,
            uncertainty_score=0.20,
            ood_score=0.15,
            predicted_volume=175.0,
            predicted_speed=21.0,
        ),
        IncidentType.SIGNAL_CHANGE: SurrogateScenario(
            vc_ratio=0.84,
            uncertainty_score=0.10,
            ood_score=0.05,
            predicted_volume=116.0,
            predicted_speed=34.0,
        ),
    }

    def predict(
        self,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
        incident: IncidentVector | None,
    ) -> list[ScenarioForecastResult]:
        """Return aggregate-only scenario estimates for the selected profile."""

        del scenario_time
        if incident is not None:
            incident_node = incident.affected_node_ids[0]
            if incident_node not in demo_node_ids():
                raise ValueError("incident node is outside the demo registry")
            if incident_node not in node_ids:
                raise ValueError("incident node is outside the analysis scope")
        action_node_id = str(candidate_action["node_id"])
        if action_node_id not in node_ids:
            raise ValueError("candidate action node is outside the analysis scope")
        ratio = float(candidate_action["green_time_ratio"])
        results: list[ScenarioForecastResult] = []
        for node_id in node_ids:
            node_ratio = ratio if node_id == action_node_id else 0.70
            profile = self._scenario_for(node_id, node_ratio, incident)
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

    def predict_route(
        self,
        *,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
        incident: IncidentVector,
        route_candidate: RouteCandidate,
    ) -> list[ScenarioForecastResult]:
        """Return synthetic route-specific evidence without actuation claims."""

        base_results = self.predict(
            node_ids=node_ids,
            horizons_minutes=horizons_minutes,
            candidate_action=candidate_action,
            scenario_time=scenario_time,
            incident=incident,
        )
        try:
            route_index = int(route_candidate.route_id.rsplit("-", 1)[-1])
        except ValueError:
            route_index = 1
        pressure = min(max(route_index, 1), 3) * 0.015
        route_nodes = set(route_candidate.node_sequence)
        return [
            replace(
                result,
                predicted_volume=result.predicted_volume * (1.0 + pressure),
                predicted_speed=result.predicted_speed * (1.0 - pressure),
                vc_ratio=min(result.vc_ratio + pressure, 1.5),
            )
            if result.node_id in route_nodes
            else result
            for result in base_results
        ]

    def _scenario_for(
        self,
        node_id: str,
        ratio: float,
        incident: IncidentVector | None,
    ) -> SurrogateScenario:
        if incident is not None:
            incident_node = incident.affected_node_ids[0]
            if incident_node == node_id:
                return self._EVENT_PROFILES[incident.event_type]
        return self._normal_scenario(ratio)

    @staticmethod
    def _normal_scenario(ratio: float) -> SurrogateScenario:
        if ratio <= 0.05 or ratio >= 0.95:
            return SurrogateScenario(
                vc_ratio=0.96,
                uncertainty_score=0.92,
                ood_score=0.80,
                predicted_volume=155.0,
                predicted_speed=18.0,
            )
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


class RefinementDemoSurrogateForecaster(DemoSurrogateForecaster):
    """Synthetic response curve that proves bounded candidate refinement."""

    def _scenario_for(
        self,
        node_id: str,
        ratio: float,
        incident: IncidentVector | None,
    ) -> SurrogateScenario:
        if (
            incident is None
            or incident.event_type is not IncidentType.SIGNAL_CHANGE
            or incident.affected_node_ids[0] != node_id
        ):
            return super()._scenario_for(node_id, ratio, incident)
        return SurrogateScenario(
            vc_ratio=0.94 if ratio < 0.85 else 0.84,
            uncertainty_score=0.10,
            ood_score=0.05,
            predicted_volume=132.0 if ratio < 0.85 else 116.0,
            predicted_speed=26.0 if ratio < 0.85 else 34.0,
        )


__all__ = [
    "DemoSurrogateForecaster",
    "RefinementDemoSurrogateForecaster",
    "demo_node_ids",
]
