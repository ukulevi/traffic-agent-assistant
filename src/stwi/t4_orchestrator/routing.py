"""Deterministic bounded routing over the trusted synthetic directed graph."""

from __future__ import annotations

import heapq
from typing import AbstractSet

from stwi.t1_pipeline.network_topology import (
    DirectedEdge,
    NetworkTopology,
    NetworkTopologyError,
    validate_topology,
)
from stwi.t4_orchestrator.contracts import RouteCandidate


class RoutingError(ValueError):
    """Raised when route generation cannot trust its inputs."""


class LocalDiversionGenerator:
    """Generate at most three local simple paths around one incident node."""

    def __init__(self, *, max_path_expansions: int = 4096) -> None:
        if (
            not isinstance(max_path_expansions, int)
            or isinstance(max_path_expansions, bool)
            or max_path_expansions < 1
        ):
            raise RoutingError("max_path_expansions must be a positive integer")
        self._max_path_expansions = max_path_expansions

    def generate(
        self,
        topology: NetworkTopology,
        incident_node_id: str,
        *,
        expected_topology_version: str | None = None,
        closed_edge_ids: AbstractSet[str] = frozenset(),
        limit: int = 3,
    ) -> tuple[RouteCandidate, ...]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 3:
            raise RoutingError("route limit must be between 1 and 3")
        try:
            topology = validate_topology(topology)
        except NetworkTopologyError as exc:
            raise RoutingError("invalid routing topology") from exc
        if (
            expected_topology_version is not None
            and expected_topology_version != topology.routing_graph_version
        ):
            raise RoutingError("topology version mismatch")

        node_ids = {node.node_id for node in topology.nodes}
        if incident_node_id not in node_ids:
            raise RoutingError("unknown incident node")
        known_edge_ids = {edge.edge_id for edge in topology.directed_edges}
        unknown_closed_edges = set(closed_edge_ids) - known_edge_ids
        if unknown_closed_edges:
            raise RoutingError("closed edge set contains unknown identifiers")

        active_edges = tuple(
            edge
            for edge in topology.directed_edges
            if edge.edge_id not in closed_edge_ids
        )
        predecessors = sorted(
            {
                edge.source_node_id
                for edge in active_edges
                if edge.target_node_id == incident_node_id
            }
        )
        successors = sorted(
            {
                edge.target_node_id
                for edge in active_edges
                if edge.source_node_id == incident_node_id
            }
        )
        if not predecessors or not successors:
            return ()

        adjacency: dict[str, list[DirectedEdge]] = {
            node_id: [] for node_id in node_ids if node_id != incident_node_id
        }
        for edge in active_edges:
            if incident_node_id in (edge.source_node_id, edge.target_node_id):
                continue
            adjacency[edge.source_node_id].append(edge)
        for outgoing in adjacency.values():
            outgoing.sort(key=lambda edge: (edge.cost, edge.edge_id))

        paths: list[tuple[float, float, tuple[str, ...], tuple[str, ...], str, str]] = []
        seen_sequences: set[tuple[str, ...]] = set()
        for entry_node in predecessors:
            for exit_node in successors:
                if entry_node == exit_node:
                    continue
                path = self._shortest_simple_path(adjacency, entry_node, exit_node)
                if path is None:
                    continue
                base_cost, distance_m, node_sequence, edge_ids = path
                if node_sequence in seen_sequences:
                    continue
                seen_sequences.add(node_sequence)
                paths.append(
                    (
                        base_cost,
                        distance_m,
                        node_sequence,
                        edge_ids,
                        entry_node,
                        exit_node,
                    )
                )

        paths.sort(
            key=lambda item: (
                item[0],
                item[1],
                len(item[2]),
                item[4],
                item[5],
                item[2],
                item[3],
            )
        )
        return tuple(
            RouteCandidate(
                route_id=f"route-{entry_node}-{exit_node}-{rank:02d}",
                topology_version=topology.routing_graph_version,
                boundary_entry_node=entry_node,
                boundary_exit_node=exit_node,
                node_sequence=node_sequence,
                edge_ids=edge_ids,
                base_cost=base_cost,
                distance_m=distance_m,
            )
            for rank, (
                base_cost,
                distance_m,
                node_sequence,
                edge_ids,
                entry_node,
                exit_node,
            ) in enumerate(paths[:limit], start=1)
        )

    def _shortest_simple_path(
        self,
        adjacency: dict[str, list[DirectedEdge]],
        start: str,
        target: str,
    ) -> tuple[float, float, tuple[str, ...], tuple[str, ...]] | None:
        pending: list[
            tuple[float, tuple[str, ...], float, tuple[str, ...]]
        ] = [(0.0, (start,), 0.0, ())]
        expansions = 0
        while pending:
            expansions += 1
            if expansions > self._max_path_expansions:
                raise RoutingError("path search budget exceeded")
            cost, nodes, distance_m, edge_ids = heapq.heappop(pending)
            current = nodes[-1]
            if current == target:
                return cost, distance_m, nodes, edge_ids
            for edge in adjacency.get(current, ()):
                if edge.target_node_id in nodes:
                    continue
                heapq.heappush(
                    pending,
                    (
                        cost + float(edge.cost),
                        (*nodes, edge.target_node_id),
                        distance_m + float(edge.distance_m),
                        (*edge_ids, edge.edge_id),
                    ),
                )
        return None


__all__ = ["LocalDiversionGenerator", "RoutingError"]
