"""Tests for the versioned synthetic routing topology."""

from __future__ import annotations

import unittest
from dataclasses import replace

from stwi.t1_pipeline.network_topology import (
    DirectedEdge,
    NetworkNode,
    NetworkTopology,
    NetworkTopologyError,
    NetworkTopologyRegistry,
    build_synthetic_topology,
    validate_topology,
)


class SyntheticTopologyTests(unittest.TestCase):
    def test_grid_has_stable_nodes_coordinates_and_bidirectional_corridors(self) -> None:
        topology = build_synthetic_topology()

        self.assertEqual(
            [node.node_id for node in topology.nodes],
            [f"node_{index:02d}" for index in range(20)],
        )
        self.assertEqual(
            {(node.x, node.y) for node in topology.nodes},
            {(float(x), float(y)) for y in range(4) for x in range(5)},
        )
        self.assertEqual(len(topology.directed_edges), 62)
        edge_pairs = {
            (edge.source_node_id, edge.target_node_id)
            for edge in topology.directed_edges
        }
        self.assertIn(("node_00", "node_01"), edge_pairs)
        self.assertIn(("node_01", "node_00"), edge_pairs)
        self.assertIn(("node_00", "node_05"), edge_pairs)
        self.assertIn(("node_05", "node_00"), edge_pairs)
        self.assertEqual(
            len({edge.edge_id for edge in topology.directed_edges}),
            len(topology.directed_edges),
        )
        self.assertTrue(
            all(
                edge.cost > 0 and edge.distance_m > 0 and edge.lane_count > 0
                for edge in topology.directed_edges
            )
        )

    def test_routing_and_gcn_versions_are_distinct_artifact_identifiers(self) -> None:
        topology = build_synthetic_topology()

        self.assertEqual(topology.network_version, "synthetic-grid-20-v1")
        self.assertEqual(topology.routing_graph_version, "synthetic-routing-20-v1")
        self.assertEqual(topology.gcn_adjacency_version, "mock-adjacency-20-v1")
        self.assertNotEqual(
            topology.routing_graph_version,
            topology.gcn_adjacency_version,
        )
        self.assertEqual(topology.capacity_version, "mock-capacity-20-v1")


class TopologyValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = build_synthetic_topology()

    def test_rejects_duplicate_node_id_and_coordinate(self) -> None:
        duplicate_id = replace(
            self.topology,
            nodes=self.topology.nodes[:-1] + (replace(self.topology.nodes[-1], node_id="node_00"),),
        )
        duplicate_coordinate = replace(
            self.topology,
            nodes=self.topology.nodes[:-1] + (replace(self.topology.nodes[-1], x=0.0, y=0.0),),
        )

        with self.assertRaises(NetworkTopologyError):
            validate_topology(duplicate_id)
        with self.assertRaises(NetworkTopologyError):
            validate_topology(duplicate_coordinate)

    def test_rejects_unknown_endpoint_duplicate_edge_and_non_positive_fields(self) -> None:
        first = self.topology.directed_edges[0]
        unknown = replace(first, target_node_id="node_99")
        duplicate = replace(first, source_node_id="node_02", target_node_id="node_03")

        for invalid in (
            replace(self.topology, directed_edges=(unknown,) + self.topology.directed_edges[1:]),
            replace(self.topology, directed_edges=self.topology.directed_edges + (duplicate,)),
            replace(self.topology, directed_edges=(replace(first, cost=0.0),) + self.topology.directed_edges[1:]),
            replace(self.topology, directed_edges=(replace(first, distance_m=0.0),) + self.topology.directed_edges[1:]),
            replace(self.topology, directed_edges=(replace(first, lane_count=0),) + self.topology.directed_edges[1:]),
        ):
            with self.subTest(invalid=invalid.directed_edges[-1].edge_id):
                with self.assertRaises(NetworkTopologyError):
                    validate_topology(invalid)

    def test_rejects_duplicate_pair_non_corridor_and_missing_reverse_edge(self) -> None:
        first = self.topology.directed_edges[0]
        duplicate_pair = replace(first, edge_id="edge-duplicate-pair")
        diagonal = DirectedEdge(
            edge_id="edge-node_00-node_06",
            source_node_id="node_00",
            target_node_id="node_06",
            cost=1.0,
            distance_m=100.0,
            lane_count=2,
        )
        without_reverse = replace(
            self.topology,
            directed_edges=tuple(
                edge
                for edge in self.topology.directed_edges
                if not (
                    edge.source_node_id == first.target_node_id
                    and edge.target_node_id == first.source_node_id
                )
            ),
        )

        for invalid in (
            replace(
                self.topology,
                directed_edges=self.topology.directed_edges + (duplicate_pair,),
            ),
            replace(
                self.topology,
                directed_edges=self.topology.directed_edges + (diagonal,),
            ),
            without_reverse,
        ):
            with self.assertRaises(NetworkTopologyError):
                validate_topology(invalid)

    def test_rejects_unstable_order_disconnected_graph_and_invalid_versions(self) -> None:
        unstable = replace(
            self.topology,
            nodes=(self.topology.nodes[1], self.topology.nodes[0]) + self.topology.nodes[2:],
        )
        disconnected = replace(
            self.topology,
            directed_edges=tuple(
                edge
                for edge in self.topology.directed_edges
                if "node_19" not in (edge.source_node_id, edge.target_node_id)
            ),
        )
        same_versions = replace(
            self.topology,
            gcn_adjacency_version=self.topology.routing_graph_version,
        )

        for invalid in (unstable, disconnected, same_versions):
            with self.assertRaises(NetworkTopologyError):
                validate_topology(invalid)


class TopologyRegistryTests(unittest.TestCase):
    def test_loads_registered_validated_version_and_unknown_fails_closed(self) -> None:
        topology = build_synthetic_topology()
        registry = NetworkTopologyRegistry((topology,))

        self.assertIs(registry.load(topology.network_version), topology)
        with self.assertRaises(NetworkTopologyError):
            registry.load("unknown-version")

    def test_rejects_duplicate_or_invalid_registration(self) -> None:
        topology = build_synthetic_topology()
        with self.assertRaises(NetworkTopologyError):
            NetworkTopologyRegistry((topology, topology))

        invalid = NetworkTopology(
            network_version="synthetic-grid-20-v1",
            routing_graph_version="same",
            gcn_adjacency_version="same",
            capacity_version="mock-capacity-20-v1",
            nodes=topology.nodes,
            directed_edges=topology.directed_edges,
        )
        with self.assertRaises(NetworkTopologyError):
            NetworkTopologyRegistry((invalid,))


if __name__ == "__main__":
    unittest.main()
