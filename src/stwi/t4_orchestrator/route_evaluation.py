"""Evidence-based evaluation and ranking of local diversion candidates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from math import isfinite
from typing import Any

from stwi.contracts.incident import IncidentVector
from stwi.t1_pipeline.network_topology import NetworkTopology, validate_topology
from stwi.t4_orchestrator.contracts import (
    RouteCandidate,
    RouteEvaluation,
    RouteRecommendation,
)
from stwi.t4_orchestrator.interfaces import (
    RouteScenarioForecaster,
    ScenarioForecast,
)


class RouteEvaluationError(RuntimeError):
    """Raised when the evaluator itself cannot produce trustworthy evidence."""


class RouteImpactEvaluator:
    """Derive route metrics from candidate-specific incident forecasts."""

    def __init__(self, route_forecaster: RouteScenarioForecaster) -> None:
        if not callable(getattr(route_forecaster, "predict_route", None)):
            raise RouteEvaluationError("route-specific forecaster is required")
        self._route_forecaster = route_forecaster

    def evaluate_all(
        self,
        *,
        topology: NetworkTopology,
        candidates: tuple[RouteCandidate, ...],
        incident: IncidentVector,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
        model_version: str,
        data_version: str,
        expected_topology_version: str,
        vc_threshold: float,
        uncertainty_threshold: float,
        ood_threshold: float,
        has_evidence: bool,
    ) -> tuple[RouteEvaluation, ...]:
        topology = validate_topology(topology)
        evaluations: list[RouteEvaluation] = []
        for candidate in candidates:
            scenario_results = self._route_forecaster.predict_route(
                node_ids=node_ids,
                horizons_minutes=horizons_minutes,
                candidate_action=candidate_action,
                scenario_time=scenario_time,
                incident=incident,
                route_candidate=candidate,
            )
            evaluations.append(
                self._evaluate_one(
                    topology=topology,
                    candidate=candidate,
                    incident=incident,
                    scenario_results=scenario_results,
                    expected_horizons=horizons_minutes,
                    model_version=model_version,
                    data_version=data_version,
                    expected_topology_version=expected_topology_version,
                    vc_threshold=vc_threshold,
                    uncertainty_threshold=uncertainty_threshold,
                    ood_threshold=ood_threshold,
                    has_evidence=has_evidence,
                )
            )
        return tuple(evaluations)

    def _evaluate_one(
        self,
        *,
        topology: NetworkTopology,
        candidate: RouteCandidate,
        incident: IncidentVector,
        scenario_results: list[ScenarioForecast],
        expected_horizons: list[int],
        model_version: str,
        data_version: str,
        expected_topology_version: str,
        vc_threshold: float,
        uncertainty_threshold: float,
        ood_threshold: float,
        has_evidence: bool,
    ) -> RouteEvaluation:
        reasons: list[str] = []
        if (
            expected_topology_version != topology.routing_graph_version
            or candidate.topology_version != topology.routing_graph_version
        ):
            reasons.append("topology_version_mismatch")
        if not self._path_is_valid(topology, candidate, incident):
            reasons.append("invalid_path")

        by_node: dict[str, list[ScenarioForecast]] = defaultdict(list)
        for result in scenario_results:
            by_node[result.node_id].append(result)
        route_results = [
            result
            for node_id in candidate.node_sequence
            for result in by_node.get(node_id, ())
        ]
        expected_grid = {
            (node_id, horizon)
            for node_id in candidate.node_sequence
            for horizon in expected_horizons
        }
        actual_grid = [
            (result.node_id, result.horizon_minutes) for result in route_results
        ]
        exact_route_grid = (
            len(actual_grid) == len(expected_grid)
            and set(actual_grid) == expected_grid
        )
        versions_complete = bool(model_version and data_version) and all(
            getattr(result, "model_version", None) == model_version
            and getattr(result, "data_version", None) == data_version
            for result in route_results
        )
        metrics_are_finite = bool(route_results) and all(
            isfinite(float(value))
            for result in route_results
            for value in (
                result.vc_ratio,
                result.predicted_speed,
                result.uncertainty_score,
                result.ood_score,
            )
        )
        evidence_complete = (
            has_evidence
            and exact_route_grid
            and versions_complete
            and metrics_are_finite
            and "topology_version_mismatch" not in reasons
            and "invalid_path" not in reasons
        )
        if not evidence_complete:
            reasons.append("missing_evidence")

        max_vc_ratio = max(
            (float(result.vc_ratio) for result in route_results), default=0.0
        )
        avg_speed_kmh = (
            sum(float(result.predicted_speed) for result in route_results)
            / len(route_results)
            if route_results
            else 0.0
        )
        uncertainty_score = max(
            (float(result.uncertainty_score) for result in route_results),
            default=0.0,
        )
        ood_score = max(
            (float(result.ood_score) for result in route_results), default=0.0
        )
        delay_proxy_seconds = self._travel_time_proxy(
            topology,
            candidate,
            by_node,
        )

        if max_vc_ratio > vc_threshold:
            reasons.append("high_vc_ratio")
        if uncertainty_score > uncertainty_threshold:
            reasons.append("high_uncertainty")
        if ood_score > ood_threshold:
            reasons.append("out_of_distribution")

        rejection_reasons = tuple(dict.fromkeys(reasons))
        return RouteEvaluation(
            route=candidate,
            max_vc_ratio=max_vc_ratio,
            avg_speed_kmh=avg_speed_kmh,
            delay_proxy_seconds=delay_proxy_seconds,
            uncertainty_score=uncertainty_score,
            ood_score=ood_score,
            passed=not rejection_reasons,
            rejection_reasons=rejection_reasons,
            evidence_complete=evidence_complete,
            model_version=model_version,
            data_version=data_version,
            topology_version=candidate.topology_version,
        )

    @staticmethod
    def _path_is_valid(
        topology: NetworkTopology,
        candidate: RouteCandidate,
        incident: IncidentVector,
    ) -> bool:
        known_nodes = {node.node_id for node in topology.nodes}
        edge_by_id = {edge.edge_id: edge for edge in topology.directed_edges}
        incident_nodes = set(incident.affected_node_ids)
        if not set(candidate.node_sequence).issubset(known_nodes):
            return False
        if incident_nodes.intersection(candidate.node_sequence):
            return False
        for source, target, edge_id in zip(
            candidate.node_sequence[:-1],
            candidate.node_sequence[1:],
            candidate.edge_ids,
            strict=True,
        ):
            edge = edge_by_id.get(edge_id)
            if edge is None:
                return False
            if (edge.source_node_id, edge.target_node_id) != (source, target):
                return False
        return True

    @staticmethod
    def _travel_time_proxy(
        topology: NetworkTopology,
        candidate: RouteCandidate,
        by_node: dict[str, list[ScenarioForecast]],
    ) -> float:
        edge_by_id = {edge.edge_id: edge for edge in topology.directed_edges}
        total_seconds = 0.0
        for target_node, edge_id in zip(
            candidate.node_sequence[1:], candidate.edge_ids, strict=True
        ):
            results = by_node.get(target_node, ())
            edge = edge_by_id.get(edge_id)
            if not results or edge is None:
                return 0.0
            avg_speed_kmh = sum(
                max(float(result.predicted_speed), 0.0) for result in results
            ) / len(results)
            if avg_speed_kmh <= 0.0:
                return 0.0
            total_seconds += float(edge.distance_m) / (avg_speed_kmh / 3.6)
        return total_seconds


class RouteSafetyGate:
    """Filter failed evaluations and apply the approved lexicographic order."""

    def filter_and_rank(
        self,
        evaluations: Iterable[RouteEvaluation],
    ) -> tuple[RouteRecommendation, ...]:
        passing = [
            evaluation
            for evaluation in evaluations
            if evaluation.passed and evaluation.evidence_complete
        ]
        passing.sort(
            key=lambda item: (
                item.max_vc_ratio,
                item.uncertainty_score,
                item.ood_score,
                item.delay_proxy_seconds,
                item.route.base_cost,
                item.route.distance_m,
                item.route.route_id,
            )
        )
        return tuple(
            RouteRecommendation(
                route=evaluation.route,
                evaluation=evaluation,
                rank=rank,
            )
            for rank, evaluation in enumerate(passing[:3], start=1)
        )


__all__ = [
    "RouteEvaluationError",
    "RouteImpactEvaluator",
    "RouteSafetyGate",
]
