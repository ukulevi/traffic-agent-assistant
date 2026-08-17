"""Builder and validator for typed network impact evidence."""

from __future__ import annotations

from typing import Iterable, Sequence

from stwi.t1_pipeline.network_topology import NetworkTopology
from stwi.t4_orchestrator.contracts import (
    IncidentVector,
    NetworkImpactEvidence,
    NetworkImpactPoint,
)
from stwi.t4_orchestrator.interfaces import ScenarioForecast


def build_network_impact(
    results: Sequence[ScenarioForecast],
    topology: NetworkTopology | None,
    incident: IncidentVector | None,
    horizons_minutes: Sequence[int],
    model_version: str,
    data_version: str,
) -> NetworkImpactEvidence:
    """Build a validated complete per-node NetworkImpactEvidence grid."""

    if topology is None:
        raise ValueError("Network topology is required to build network impact evidence")

    incident_nodes: set[str] = set()
    if incident is not None and incident.affected_node_ids:
        incident_nodes = set(incident.affected_node_ids)

    # Find adjacent neighbors in directed topology
    adjacent_nodes: set[str] = set()
    if incident_nodes:
        for edge in topology.directed_edges:
            if edge.source_node_id in incident_nodes and edge.target_node_id not in incident_nodes:
                adjacent_nodes.add(edge.target_node_id)
            if edge.target_node_id in incident_nodes and edge.source_node_id not in incident_nodes:
                adjacent_nodes.add(edge.source_node_id)

    # Map forecast results to impact points
    impact_points: list[NetworkImpactPoint] = []
    for r in results:
        if r.node_id in incident_nodes:
            role = "incident"
        elif r.node_id in adjacent_nodes:
            role = "adjacent"
        else:
            role = "network"

        impact_points.append(
            NetworkImpactPoint(
                node_id=r.node_id,
                horizon_minutes=r.horizon_minutes,
                traffic_volume_5m=float(r.predicted_volume),
                avg_speed_kmh=float(r.predicted_speed),
                vc_ratio=float(r.vc_ratio),
                uncertainty_score=float(r.uncertainty_score),
                ood_score=float(r.ood_score),
                impact_role=role,
            )
        )

    evidence = NetworkImpactEvidence(
        topology_version=topology.network_version,
        model_version=model_version,
        data_version=data_version,
        horizons_minutes=tuple(horizons_minutes),
        incident_node_ids=tuple(sorted(incident_nodes)),
        node_impacts=tuple(impact_points),
    )

    validate_network_impact(evidence, topology, expected_horizons=horizons_minutes)
    return evidence


def validate_network_impact(
    evidence: NetworkImpactEvidence | None,
    topology: NetworkTopology | None,
    expected_horizons: Sequence[int] | None = None,
) -> None:
    """Validate NetworkImpactEvidence against trusted topology and expected horizons."""

    if evidence is None:
        return

    if topology is None:
        raise ValueError("Network topology is required to validate network impact evidence")

    if evidence.topology_version != topology.network_version:
        raise ValueError(
            f"Topology version mismatch: evidence topology '{evidence.topology_version}' "
            f"!= expected '{topology.network_version}'"
        )

    if expected_horizons is not None and tuple(evidence.horizons_minutes) != tuple(expected_horizons):
        raise ValueError(
            f"Network impact horizons mismatch: evidence horizons {evidence.horizons_minutes} "
            f"!= expected {tuple(expected_horizons)}"
        )

    topology_node_ids = {node.node_id for node in topology.nodes}
    evidence_node_ids = {p.node_id for p in evidence.node_impacts}

    if not evidence_node_ids.issubset(topology_node_ids):
        unknown_nodes = evidence_node_ids - topology_node_ids
        raise ValueError(f"Network impact evidence references unknown nodes: {unknown_nodes}")

    if len(evidence_node_ids) != len(topology_node_ids):
        raise ValueError(
            f"Network impact evidence node count ({len(evidence_node_ids)}) "
            f"does not match topology node count ({len(topology_node_ids)})"
        )


__all__ = ["build_network_impact", "validate_network_impact"]
