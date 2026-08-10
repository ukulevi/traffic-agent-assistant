"""Versioned synthetic 4x5 topology and directed routing graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class NetworkTopologyError(ValueError):
    """Raised when a topology or registry entry violates its contract."""


@dataclass(frozen=True)
class NetworkNode:
    node_id: str
    display_name: str
    x: float
    y: float


@dataclass(frozen=True)
class DirectedEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    cost: float
    distance_m: float
    lane_count: int


@dataclass(frozen=True)
class NetworkTopology:
    network_version: str
    routing_graph_version: str
    gcn_adjacency_version: str
    capacity_version: str
    nodes: tuple[NetworkNode, ...]
    directed_edges: tuple[DirectedEdge, ...]


def _require_version(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise NetworkTopologyError(f"{name} must be a canonical non-empty string")


def _reachable(start: str, adjacency: dict[str, tuple[str, ...]]) -> set[str]:
    visited = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for target in adjacency[current]:
            if target not in visited:
                visited.add(target)
                pending.append(target)
    return visited


def validate_topology(topology: NetworkTopology) -> NetworkTopology:
    """Validate stable grid nodes, corridor edges, versions and reachability."""

    if not isinstance(topology, NetworkTopology):
        raise NetworkTopologyError("topology must be a NetworkTopology")
    for name in (
        "network_version",
        "routing_graph_version",
        "gcn_adjacency_version",
        "capacity_version",
    ):
        _require_version(name, getattr(topology, name))
    if len(
        {
            topology.network_version,
            topology.routing_graph_version,
            topology.gcn_adjacency_version,
        }
    ) != 3:
        raise NetworkTopologyError(
            "network, routing graph and GCN adjacency versions must be distinct"
        )

    expected_ids = tuple(f"node_{index:02d}" for index in range(20))
    node_ids = tuple(node.node_id for node in topology.nodes)
    if node_ids != expected_ids:
        raise NetworkTopologyError("nodes must use stable node_00..node_19 order")
    if len({(node.x, node.y) for node in topology.nodes}) != 20:
        raise NetworkTopologyError("node coordinates must be unique")
    for index, node in enumerate(topology.nodes):
        if not node.display_name or node.display_name.strip() != node.display_name:
            raise NetworkTopologyError("node display names must be canonical")
        if (node.x, node.y) != (float(index % 5), float(index // 5)):
            raise NetworkTopologyError("node coordinates must form a stable 5x4 grid")

    node_set = set(node_ids)
    edge_ids: set[str] = set()
    edge_pairs: set[tuple[str, str]] = set()
    adjacency_lists: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in topology.directed_edges:
        if not edge.edge_id or edge.edge_id.strip() != edge.edge_id:
            raise NetworkTopologyError("edge IDs must be canonical non-empty strings")
        if edge.edge_id in edge_ids:
            raise NetworkTopologyError("edge IDs must be unique")
        edge_ids.add(edge.edge_id)
        pair = (edge.source_node_id, edge.target_node_id)
        if pair in edge_pairs:
            raise NetworkTopologyError("directed endpoint pairs must be unique")
        edge_pairs.add(pair)
        if edge.source_node_id not in node_set or edge.target_node_id not in node_set:
            raise NetworkTopologyError("edge endpoints must reference known nodes")
        if edge.source_node_id == edge.target_node_id:
            raise NetworkTopologyError("self-loop routing edges are not allowed")
        source_index = int(edge.source_node_id.removeprefix("node_"))
        target_index = int(edge.target_node_id.removeprefix("node_"))
        source_xy = (source_index % 5, source_index // 5)
        target_xy = (target_index % 5, target_index // 5)
        if abs(source_xy[0] - target_xy[0]) + abs(source_xy[1] - target_xy[1]) != 1:
            raise NetworkTopologyError("routing edges must connect grid neighbours")
        if (
            not isinstance(edge.cost, (int, float))
            or isinstance(edge.cost, bool)
            or edge.cost <= 0
            or not isinstance(edge.distance_m, (int, float))
            or isinstance(edge.distance_m, bool)
            or edge.distance_m <= 0
            or not isinstance(edge.lane_count, int)
            or isinstance(edge.lane_count, bool)
            or edge.lane_count <= 0
        ):
            raise NetworkTopologyError("edge cost, distance and lane count must be positive")
        adjacency_lists[edge.source_node_id].append(edge.target_node_id)
    if any((target, source) not in edge_pairs for source, target in edge_pairs):
        raise NetworkTopologyError("every synthetic corridor must be bidirectional")

    adjacency = {
        node_id: tuple(sorted(targets))
        for node_id, targets in adjacency_lists.items()
    }
    if any(_reachable(node_id, adjacency) != node_set for node_id in node_ids):
        raise NetworkTopologyError("directed routing graph must be strongly connected")
    return topology


def _edge(source: str, target: str) -> DirectedEdge:
    return DirectedEdge(
        edge_id=f"edge-{source}-{target}",
        source_node_id=source,
        target_node_id=target,
        cost=1.0,
        distance_m=100.0,
        lane_count=2,
    )


def build_synthetic_topology() -> NetworkTopology:
    """Build the canonical, visibly synthetic 20-node routing topology."""

    nodes = tuple(
        NetworkNode(
            node_id=f"node_{index:02d}",
            display_name=f"Nút {index:02d}",
            x=float(index % 5),
            y=float(index // 5),
        )
        for index in range(20)
    )
    edges: list[DirectedEdge] = []
    for index in range(20):
        source = f"node_{index:02d}"
        if index % 5 < 4:
            target = f"node_{index + 1:02d}"
            edges.extend((_edge(source, target), _edge(target, source)))
        if index // 5 < 3:
            target = f"node_{index + 5:02d}"
            edges.extend((_edge(source, target), _edge(target, source)))
    return validate_topology(
        NetworkTopology(
            network_version="synthetic-grid-20-v1",
            routing_graph_version="synthetic-routing-20-v1",
            gcn_adjacency_version="mock-adjacency-20-v1",
            capacity_version="mock-capacity-20-v1",
            nodes=nodes,
            directed_edges=tuple(edges),
        )
    )


class NetworkTopologyRegistry:
    """Immutable fail-closed lookup of validated network versions."""

    def __init__(self, topologies: Iterable[NetworkTopology]) -> None:
        entries: dict[str, NetworkTopology] = {}
        for topology in topologies:
            validated = validate_topology(topology)
            if validated.network_version in entries:
                raise NetworkTopologyError("network version is registered more than once")
            entries[validated.network_version] = validated
        self._entries = entries

    def load(self, network_version: str) -> NetworkTopology:
        _require_version("network_version", network_version)
        try:
            topology = self._entries[network_version]
        except KeyError as exc:
            raise NetworkTopologyError("unknown network version") from exc
        return validate_topology(topology)


__all__ = [
    "DirectedEdge",
    "NetworkNode",
    "NetworkTopology",
    "NetworkTopologyError",
    "NetworkTopologyRegistry",
    "build_synthetic_topology",
    "validate_topology",
]
