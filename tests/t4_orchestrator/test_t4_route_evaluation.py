"""Safety and ranking tests for typed local diversion evidence."""

from __future__ import annotations

import unittest
from datetime import datetime

from stwi.contracts.incident import IncidentVector
from stwi.t1_pipeline.network_topology import build_synthetic_topology
from stwi.t4_orchestrator.contracts import RouteCandidate, RouteEvaluation
from stwi.t4_orchestrator.demo_adapters import DemoSurrogateForecaster, demo_node_ids
from stwi.t4_orchestrator.route_evaluation import (
    RouteImpactEvaluator,
    RouteSafetyGate,
)
from stwi.t4_orchestrator.routing import LocalDiversionGenerator


class TestRouteImpactEvaluator(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = build_synthetic_topology()
        self.incident = IncidentVector.model_validate(
            {
                "event_type": "signal_change",
                "affected_node_ids": ["node_07"],
                "severity": "medium",
                "duration_minutes": 30,
                "description": "Synthetic signal hypothesis",
                "signal_plan_delta": {"green_time_ratio_delta": 0.15},
            }
        )
        self.candidates = LocalDiversionGenerator().generate(
            self.topology,
            incident_node_id="node_07",
        )
        self.evaluator = RouteImpactEvaluator(
            route_forecaster=DemoSurrogateForecaster()
        )

    def _evaluate(self, candidates=None, **overrides):
        values = {
            "topology": self.topology,
            "candidates": candidates or self.candidates,
            "incident": self.incident,
            "node_ids": list(demo_node_ids()),
            "horizons_minutes": [5, 10],
            "candidate_action": {"node_id": "node_07", "green_time_ratio": 0.85},
            "scenario_time": datetime(2025, 6, 1, 8, 0),
            "model_version": "provisional_mock_v1",
            "data_version": "synthetic_mock_phase4",
            "expected_topology_version": self.topology.routing_graph_version,
            "vc_threshold": 0.9,
            "uncertainty_threshold": 0.7,
            "ood_threshold": 0.5,
            "has_evidence": True,
        }
        values.update(overrides)
        return self.evaluator.evaluate_all(**values)

    def test_only_evidence_backed_routes_are_recommended(self):
        evaluations = self._evaluate()
        recommendations = RouteSafetyGate().filter_and_rank(evaluations)

        self.assertEqual(len(evaluations), 3)
        self.assertTrue(all(item.passed for item in evaluations))
        self.assertEqual(
            [item.rank for item in recommendations],
            [1, 2, 3],
        )
        self.assertTrue(
            all(item.evaluation.evidence_complete for item in recommendations)
        )
        self.assertGreater(len({item.max_vc_ratio for item in evaluations}), 1)

    def test_high_vc_uncertainty_ood_and_missing_evidence_are_rejected(self):
        class UnsafeRouteForecaster(DemoSurrogateForecaster):
            def predict_route(self, **kwargs):
                return [
                    item.__class__(
                        **{
                            **item.__dict__,
                            "vc_ratio": 0.95,
                            "uncertainty_score": 0.8,
                            "ood_score": 0.6,
                        }
                    )
                    for item in super().predict_route(**kwargs)
                ]

        self.evaluator = RouteImpactEvaluator(
            route_forecaster=UnsafeRouteForecaster()
        )
        evaluations = self._evaluate(has_evidence=False)

        self.assertFalse(any(item.passed for item in evaluations))
        for item in evaluations:
            self.assertEqual(
                item.rejection_reasons,
                (
                    "missing_evidence",
                    "high_vc_ratio",
                    "high_uncertainty",
                    "out_of_distribution",
                ),
            )
        self.assertEqual(RouteSafetyGate().filter_and_rank(evaluations), ())

    def test_invalid_path_and_topology_version_mismatch_are_rejected(self):
        original = self.candidates[0]
        invalid_edge = RouteCandidate(
            **{
                **original.model_dump(),
                "edge_ids": ["edge-unknown", *original.edge_ids[1:]],
            }
        )
        stale = RouteCandidate(
            **{
                **self.candidates[1].model_dump(),
                "topology_version": "stale-routing-v0",
            }
        )
        evaluations = self._evaluate(candidates=(invalid_edge, stale))

        self.assertIn("invalid_path", evaluations[0].rejection_reasons)
        self.assertIn(
            "topology_version_mismatch", evaluations[1].rejection_reasons
        )
        self.assertEqual(RouteSafetyGate().filter_and_rank(evaluations), ())

    def test_missing_or_duplicate_route_horizons_are_rejected(self):
        class IncompleteRouteForecaster(DemoSurrogateForecaster):
            def predict_route(self, **kwargs):
                results = super().predict_route(**kwargs)
                route_node = kwargs["route_candidate"].node_sequence[0]
                filtered = [
                    item
                    for item in results
                    if not (item.node_id == route_node and item.horizon_minutes == 10)
                ]
                return [filtered[0], *filtered]

        self.evaluator = RouteImpactEvaluator(
            route_forecaster=IncompleteRouteForecaster()
        )
        evaluation = self._evaluate(candidates=(self.candidates[0],))[0]

        self.assertFalse(evaluation.passed)
        self.assertIn("missing_evidence", evaluation.rejection_reasons)

    def test_generic_incident_forecast_cannot_promote_route(self):
        class GenericOnlyForecaster:
            def predict(self, **kwargs):
                return []

        with self.assertRaisesRegex(RuntimeError, "route-specific forecaster"):
            RouteImpactEvaluator(route_forecaster=GenericOnlyForecaster())


class TestRouteSafetyGate(unittest.TestCase):
    def _evaluation(
        self,
        route_id: str,
        *,
        max_vc_ratio: float,
        uncertainty_score: float,
        ood_score: float,
        delay_proxy_seconds: float,
        base_cost: float,
        distance_m: float,
    ) -> RouteEvaluation:
        route = RouteCandidate(
            route_id=route_id,
            topology_version="synthetic-routing-20-v1",
            boundary_entry_node="node_01",
            boundary_exit_node="node_02",
            node_sequence=["node_01", "node_02"],
            edge_ids=["edge-node_01-node_02"],
            base_cost=base_cost,
            distance_m=distance_m,
        )
        return RouteEvaluation(
            route=route,
            max_vc_ratio=max_vc_ratio,
            avg_speed_kmh=30.0,
            delay_proxy_seconds=delay_proxy_seconds,
            uncertainty_score=uncertainty_score,
            ood_score=ood_score,
            passed=True,
            rejection_reasons=[],
            evidence_complete=True,
            model_version="model-v1",
            data_version="data-v1",
            topology_version="synthetic-routing-20-v1",
        )

    def test_ranking_is_lexicographic_and_stably_bounded(self):
        evaluations = (
            self._evaluation(
                "route-b",
                max_vc_ratio=0.82,
                uncertainty_score=0.10,
                ood_score=0.05,
                delay_proxy_seconds=10.0,
                base_cost=1.0,
                distance_m=100.0,
            ),
            self._evaluation(
                "route-a",
                max_vc_ratio=0.80,
                uncertainty_score=0.20,
                ood_score=0.05,
                delay_proxy_seconds=30.0,
                base_cost=3.0,
                distance_m=300.0,
            ),
            self._evaluation(
                "route-d",
                max_vc_ratio=0.82,
                uncertainty_score=0.10,
                ood_score=0.04,
                delay_proxy_seconds=20.0,
                base_cost=2.0,
                distance_m=200.0,
            ),
            self._evaluation(
                "route-c",
                max_vc_ratio=0.82,
                uncertainty_score=0.10,
                ood_score=0.04,
                delay_proxy_seconds=15.0,
                base_cost=2.0,
                distance_m=200.0,
            ),
        )

        recommendations = RouteSafetyGate().filter_and_rank(evaluations)

        self.assertEqual(
            [item.route.route_id for item in recommendations],
            ["route-a", "route-c", "route-d"],
        )
        self.assertEqual([item.rank for item in recommendations], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
