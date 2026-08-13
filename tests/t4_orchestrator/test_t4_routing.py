"""Contract tests for bounded local diversion generation."""

from __future__ import annotations

import unittest

from stwi.t1_pipeline.network_topology import build_synthetic_topology
from stwi.t4_orchestrator.routing import RoutingError


class TestLocalDiversionGenerator(unittest.TestCase):
    def setUp(self) -> None:
        from stwi.t4_orchestrator.routing import LocalDiversionGenerator

        self.topology = build_synthetic_topology()
        self.generator = LocalDiversionGenerator()

    def test_candidates_are_directed_simple_incident_avoiding_and_bounded(self):
        candidates = self.generator.generate(
            self.topology,
            incident_node_id="node_07",
            expected_topology_version=self.topology.routing_graph_version,
        )
        valid_edges = {edge.edge_id for edge in self.topology.directed_edges}

        self.assertGreaterEqual(len(candidates), 1)
        self.assertLessEqual(len(candidates), 3)
        for candidate in candidates:
            self.assertNotIn("node_07", candidate.node_sequence)
            self.assertEqual(
                len(candidate.node_sequence), len(set(candidate.node_sequence))
            )
            self.assertTrue(set(candidate.edge_ids).issubset(valid_edges))
            self.assertEqual(
                len(candidate.edge_ids), len(candidate.node_sequence) - 1
            )

    def test_generation_is_deterministic_with_stable_route_ids(self):
        first = self.generator.generate(self.topology, incident_node_id="node_07")
        second = self.generator.generate(self.topology, incident_node_id="node_07")

        self.assertEqual(first, second)
        self.assertEqual(
            [candidate.route_id for candidate in first],
            ["route-node_02-node_06-01", "route-node_02-node_08-02", "route-node_06-node_02-03"],
        )

    def test_closed_edges_are_never_used(self):
        closed = {
            "edge-node_02-node_01",
            "edge-node_01-node_06",
        }
        candidates = self.generator.generate(
            self.topology,
            incident_node_id="node_07",
            closed_edge_ids=closed,
        )

        self.assertTrue(candidates)
        self.assertTrue(
            all(closed.isdisjoint(candidate.edge_ids) for candidate in candidates)
        )

    def test_no_boundaries_or_disconnected_candidate_graph_returns_empty(self):
        incident_edges = {
            edge.edge_id
            for edge in self.topology.directed_edges
            if "node_07" in (edge.source_node_id, edge.target_node_id)
        }

        self.assertEqual(
            self.generator.generate(
                self.topology,
                incident_node_id="node_07",
                closed_edge_ids=incident_edges,
            ),
            (),
        )

    def test_unknown_incident_and_version_mismatch_fail_closed(self):
        with self.assertRaisesRegex(RoutingError, "unknown incident node"):
            self.generator.generate(self.topology, incident_node_id="node_99")
        with self.assertRaisesRegex(RoutingError, "topology version mismatch"):
            self.generator.generate(
                self.topology,
                incident_node_id="node_07",
                expected_topology_version="stale-routing-v0",
            )

    def test_path_search_has_a_hard_expansion_budget(self):
        from stwi.t4_orchestrator.routing import LocalDiversionGenerator

        constrained = LocalDiversionGenerator(max_path_expansions=1)
        with self.assertRaisesRegex(RoutingError, "path search budget exceeded"):
            constrained.generate(self.topology, incident_node_id="node_07")


if __name__ == "__main__":
    unittest.main()
