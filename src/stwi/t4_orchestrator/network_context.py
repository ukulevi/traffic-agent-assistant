"""Authorized read-only projection of the synthetic routing topology."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from stwi.t1_pipeline.network_topology import (
    NetworkTopologyError,
    NetworkTopologyRegistry,
)
from stwi.t4_orchestrator.auth import ServerPrincipal
from stwi.t4_orchestrator.ui_context import (
    UiContextProvider,
    UiContextResolutionError,
    UiContextScope,
)

SYNTHETIC_GEOGRAPHIC_CLAIM = (
    "Mạng 4x5 hoàn toàn synthetic, không đại diện địa lý thực."
)


class NetworkContextUnavailable(RuntimeError):
    """Raised when trusted network context cannot be returned safely."""


class NetworkContextNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    display_name: str
    x: float
    y: float


class NetworkContextEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_node_id: str
    target_node_id: str
    cost: float
    distance_m: float
    lane_count: int


class NetworkContextResponse(BaseModel):
    """Wire-safe topology projection for the operator dashboard."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["production"] = "production"
    synthetic: Literal[True] = True
    geographic_claim: Literal[
        "Mạng 4x5 hoàn toàn synthetic, không đại diện địa lý thực."
    ]
    network_version: str
    routing_graph_version: str
    gcn_adjacency_version: str
    capacity_version: str
    nodes: list[NetworkContextNode]
    directed_edges: list[NetworkContextEdge]


class NetworkContextProvider(Protocol):
    def resolve(self, *, principal: ServerPrincipal) -> NetworkContextResponse:
        ...


class AuthorizedNetworkContextProvider:
    """Combine a validated registry with the trusted UI node allowlist."""

    def __init__(
        self,
        *,
        registry: NetworkTopologyRegistry,
        network_version: str,
        ui_context_provider: UiContextProvider,
    ) -> None:
        self._registry = registry
        self._network_version = network_version
        self._ui_context_provider = ui_context_provider

    @property
    def ui_context_provider(self) -> UiContextProvider:
        """Expose identity for composition validation without duplicating scope."""

        return self._ui_context_provider

    def resolve(self, *, principal: ServerPrincipal) -> NetworkContextResponse:
        try:
            topology = self._registry.load(self._network_version)
            scope = self._ui_context_provider.resolve(principal=principal)
            if not isinstance(scope, UiContextScope):
                raise UiContextResolutionError("invalid trusted UI context scope")
            known_nodes = {node.node_id for node in topology.nodes}
            if not set(scope.node_ids).issubset(known_nodes):
                raise NetworkTopologyError("authorized scope references unknown nodes")
            allowed = set(scope.node_ids)
            nodes = [
                NetworkContextNode.model_validate(node.__dict__)
                for node in topology.nodes
                if node.node_id in allowed
            ]
            edges = [
                NetworkContextEdge.model_validate(edge.__dict__)
                for edge in topology.directed_edges
                if edge.source_node_id in allowed and edge.target_node_id in allowed
            ]
            return NetworkContextResponse(
                geographic_claim=SYNTHETIC_GEOGRAPHIC_CLAIM,
                network_version=topology.network_version,
                routing_graph_version=topology.routing_graph_version,
                gcn_adjacency_version=topology.gcn_adjacency_version,
                capacity_version=topology.capacity_version,
                nodes=nodes,
                directed_edges=edges,
            )
        except (NetworkTopologyError, UiContextResolutionError, ValueError) as exc:
            raise NetworkContextUnavailable(
                "Trusted network context is unavailable"
            ) from exc


__all__ = [
    "AuthorizedNetworkContextProvider",
    "NetworkContextEdge",
    "NetworkContextNode",
    "NetworkContextProvider",
    "NetworkContextResponse",
    "NetworkContextUnavailable",
    "SYNTHETIC_GEOGRAPHIC_CLAIM",
]
