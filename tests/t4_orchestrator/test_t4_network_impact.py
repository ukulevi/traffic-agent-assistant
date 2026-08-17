"""Unit tests for building and validating network-impact evidence."""

import unittest

from stwi.contracts.incident import IncidentSeverity, IncidentType, IncidentVector
from stwi.t1_pipeline.network_topology import build_synthetic_topology
from stwi.t4_orchestrator.fake_adapters import ScenarioForecastResult
from stwi.t4_orchestrator.network_impact import (
    build_network_impact,
    validate_network_impact,
)


class TestNetworkImpactBuilder(unittest.TestCase):

    def setUp(self):
        self.topology = build_synthetic_topology()
        self.node_ids = [node.node_id for node in self.topology.nodes]
        self.horizons = [5, 10, 15, 20, 25, 30]

    def _make_scenario_results(self, node_ids=None, horizons=None):
        node_ids = node_ids or self.node_ids
        horizons = horizons or self.horizons
        results = []
        for n_id in node_ids:
            for h in horizons:
                results.append(
                    ScenarioForecastResult(
                        node_id=n_id,
                        horizon_minutes=h,
                        predicted_volume=100.0,
                        predicted_speed=30.0,
                        vc_ratio=0.75,
                        uncertainty_score=0.1,
                        ood_score=0.05,
                    )
                )
        return results

    def _make_incident(self, node_id: str) -> IncidentVector:
        return IncidentVector(
            event_type=IncidentType.LANE_CLOSURE,
            affected_node_ids=(node_id,),
            severity=IncidentSeverity.MEDIUM,
            duration_minutes=30,
            description=f"Test incident on {node_id}",
            lane_closure_ratio=0.5,
        )

    def test_builds_complete_20x6_grid_with_correct_roles_for_node_05(self):
        incident = self._make_incident("node_05")
        results = self._make_scenario_results()
        evidence = build_network_impact(
            results=results,
            topology=self.topology,
            incident=incident,
            horizons_minutes=self.horizons,
            model_version="demo-model-v1",
            data_version="synthetic-data-v1",
        )

        self.assertEqual(len(evidence.node_impacts), 20 * 6)
        self.assertEqual(evidence.topology_version, self.topology.network_version)
        self.assertEqual(evidence.incident_node_ids, ("node_05",))

        # node_05 impacts should have role 'incident'
        node_05_impacts = [p for p in evidence.node_impacts if p.node_id == "node_05"]
        self.assertEqual(len(node_05_impacts), 6)
        for p in node_05_impacts:
            self.assertEqual(p.impact_role, "incident")

        # Adjacent nodes for node_05 (grid neighbors in 5x4: node_00, node_06, node_10)
        adj_ids = {"node_00", "node_06", "node_10"}
        for p in evidence.node_impacts:
            if p.node_id in adj_ids:
                self.assertEqual(p.impact_role, "adjacent")
            elif p.node_id != "node_05":
                self.assertEqual(p.impact_role, "network")

    def test_handles_incident_relocation_to_node_14(self):
        incident = self._make_incident("node_14")
        results = self._make_scenario_results()
        evidence = build_network_impact(
            results=results,
            topology=self.topology,
            incident=incident,
            horizons_minutes=self.horizons,
            model_version="demo-model-v1",
            data_version="synthetic-data-v1",
        )

        node_14_impacts = [p for p in evidence.node_impacts if p.node_id == "node_14"]
        self.assertEqual(len(node_14_impacts), 6)
        for p in node_14_impacts:
            self.assertEqual(p.impact_role, "incident")

    def test_validate_network_impact_rejects_horizon_mismatch(self):
        incident = self._make_incident("node_05")
        results = self._make_scenario_results()
        evidence = build_network_impact(
            results=results,
            topology=self.topology,
            incident=incident,
            horizons_minutes=self.horizons,
            model_version="demo-model-v1",
            data_version="synthetic-data-v1",
        )

        with self.assertRaises(ValueError):
            validate_network_impact(evidence, self.topology, expected_horizons=[5, 10])


if __name__ == "__main__":
    unittest.main()
