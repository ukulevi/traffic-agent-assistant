"""Deterministic 20-node mock data required by the Phase-1 gate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from stwi.contracts.project import feature_names, load_project_contract


QUALITY_MISSING = np.uint8(1)
QUALITY_OUTLIER = np.uint8(2)
QUALITY_LATE = np.uint8(4)
QUALITY_INCIDENT = np.uint8(8)


@dataclass(frozen=True)
class MockNetwork:
    version: str
    node_ids: tuple[str, ...]
    adjacency: np.ndarray
    capacities_vph: np.ndarray
    free_flow_speed_kmh: np.ndarray


@dataclass(frozen=True)
class MockTimeSeries:
    timestamps: tuple[datetime, ...]
    values: np.ndarray
    observed_mask: np.ndarray
    quality_flags: np.ndarray


def generate_mock_network(seed: int = 20250621) -> MockNetwork:
    contract = load_project_contract()
    node_count = contract["mvp_scope"]["functional_network_nodes"]
    rng = np.random.default_rng(seed)
    node_ids = tuple(f"node_{index:02d}" for index in range(node_count))
    adjacency = np.zeros((node_count, node_count), dtype=np.float32)
    for index in range(node_count):
        adjacency[index, index] = 1.0
        adjacency[index, (index - 1) % node_count] = 0.7
        adjacency[index, (index + 1) % node_count] = 0.7
        if index + 5 < node_count:
            adjacency[index, index + 5] = 0.35
            adjacency[index + 5, index] = 0.35
    capacities = rng.integers(1200, 2401, size=node_count).astype(np.float32)
    free_flow = rng.uniform(45, 70, size=node_count).astype(np.float32)
    return MockNetwork(
        version="mock-network-20-v1",
        node_ids=node_ids,
        adjacency=adjacency,
        capacities_vph=capacities,
        free_flow_speed_kmh=free_flow,
    )


def _daily_peak(hour: np.ndarray, center: float, width: float) -> np.ndarray:
    distance = np.minimum(np.abs(hour - center), 24 - np.abs(hour - center))
    return np.exp(-0.5 * (distance / width) ** 2)


def generate_mock_timeseries(
    network: MockNetwork,
    *,
    start: datetime,
    days: int = 14,
    seed: int = 20250530,
    missing_rate: float = 0.02,
    outlier_rate: float = 0.001,
) -> MockTimeSeries:
    if start.utcoffset() is None:
        raise ValueError("start must include UTC offset")
    if days < 2 or not 0 <= missing_rate < 0.5:
        raise ValueError("invalid mock generation settings")
    contract = load_project_contract()["data_contract"]
    step_minutes = contract["time_step_minutes"]
    steps = days * 24 * 60 // step_minutes
    nodes = len(network.node_ids)
    features = len(feature_names())
    timestamps = tuple(
        start + timedelta(minutes=step_minutes * index) for index in range(steps)
    )
    rng = np.random.default_rng(seed)
    values = np.zeros((steps, nodes, features), dtype=np.float32)
    observed = np.ones_like(values, dtype=np.bool_)
    quality = np.zeros_like(values, dtype=np.uint8)

    minutes = np.arange(steps) * step_minutes
    hour = (minutes % (24 * 60)) / 60.0
    day_index = minutes // (24 * 60)
    weekday = np.array(
        [(start.weekday() + int(day)) % 7 for day in day_index],
        dtype=np.float32,
    )
    morning = _daily_peak(hour, 7.5, 1.4)
    evening = _daily_peak(hour, 17.5, 1.8)
    daytime = np.clip(np.sin((hour - 5.5) / 14 * math.pi), 0, 1)
    weekend_factor = np.where(weekday >= 5, 0.72, 1.0)
    node_factor = rng.uniform(0.75, 1.25, size=nodes)
    demand = (
        0.16 + 0.48 * morning[:, None] + 0.55 * evening[:, None]
    ) * weekend_factor[:, None] * node_factor[None, :]
    volume = (
        network.capacities_vph[None, :] / 12 * demand
        + rng.normal(0, 3.0, size=(steps, nodes))
    )
    volume = np.clip(volume, 0, None)
    volume_to_capacity = volume * 12 / network.capacities_vph[None, :]
    speed = network.free_flow_speed_kmh[None, :] * (
        1 - 0.68 * np.clip(volume_to_capacity, 0, 1.25) ** 1.55
    ) + rng.normal(0, 2.0, size=(steps, nodes))
    speed = np.clip(speed, 5, 90)
    heavy_ratio = np.clip(
        0.08 + 0.05 * (np.arange(nodes)[None, :] % 5 == 0)
        + rng.normal(0, 0.015, size=(steps, nodes)),
        0.02,
        0.35,
    )

    values[:, :, 0] = volume
    values[:, :, 1] = speed
    values[:, :, 2] = heavy_ratio
    values[:, :, 3] = np.clip(0.25 + volume * 0.004 + rng.normal(0, 0.03, (steps, nodes)), 0, None)
    values[:, :, 4] = 410 + volume * 0.55 + rng.normal(0, 6, (steps, nodes))
    values[:, :, 5] = np.clip(12 + volume * 0.9 + rng.normal(0, 4, (steps, nodes)), 0, None)
    values[:, :, 6] = np.clip(8 + volume * 0.12 + rng.normal(0, 2, (steps, nodes)), 0, None)
    values[:, :, 7] = np.clip(values[:, :, 6] * 1.55 + rng.normal(0, 2, (steps, nodes)), 0, None)
    temperature = 27 + 5 * np.sin((hour - 8) / 24 * 2 * math.pi)
    values[:, :, 8] = temperature[:, None] + rng.normal(0, 0.5, (steps, nodes))
    values[:, :, 9] = np.clip(78 - (temperature[:, None] - 27) * 2.4 + rng.normal(0, 2, (steps, nodes)), 25, 100)
    values[:, :, 10] = np.clip(1.8 + 1.2 * daytime[:, None] + rng.normal(0, 0.4, (steps, nodes)), 0, None)
    values[:, :, 11] = np.sin(2 * math.pi * minutes[:, None] / (24 * 60))
    values[:, :, 12] = np.cos(2 * math.pi * minutes[:, None] / (24 * 60))
    values[:, :, 13] = np.sin(2 * math.pi * weekday[:, None] / 7)
    values[:, :, 14] = np.cos(2 * math.pi * weekday[:, None] / 7)
    values[:, :, 15] = np.clip(
        0.42 + 0.16 * (morning[:, None] + evening[:, None])
        + rng.normal(0, 0.025, (steps, nodes)),
        0.25,
        0.85,
    )

    incident_start = min(steps - 1, 5 * 24 * 12 + 17 * 12)
    incident_end = min(steps, incident_start + 12)
    if incident_end > incident_start:
        incident_node = 7 % nodes
        values[incident_start:incident_end, incident_node, 0] *= 1.45
        values[incident_start:incident_end, incident_node, 1] *= 0.35
        quality[incident_start:incident_end, incident_node, :] |= QUALITY_INCIDENT

    mutable_features = np.array(list(range(11)) + [15])
    missing_draw = rng.random((steps, nodes, len(mutable_features))) < missing_rate
    for local_index, feature_index in enumerate(mutable_features):
        missing = missing_draw[:, :, local_index]
        observed[:, :, feature_index][missing] = False
        quality[:, :, feature_index][missing] |= QUALITY_MISSING
        values[:, :, feature_index][missing] = np.nan

    for node in (2, 11):
        outage_start = min(steps - 8, (node + 2) * 37)
        outage = slice(outage_start, outage_start + 8)
        observed[outage, node, :11] = False
        quality[outage, node, :11] |= QUALITY_MISSING
        values[outage, node, :11] = np.nan

    candidate_count = steps * nodes * len(mutable_features)
    outlier_count = max(1, int(candidate_count * outlier_rate))
    flat_steps = rng.integers(0, steps, size=outlier_count)
    flat_nodes = rng.integers(0, nodes, size=outlier_count)
    flat_features = rng.choice(mutable_features, size=outlier_count)
    values[flat_steps, flat_nodes, flat_features] = 1_000_000.0
    quality[flat_steps, flat_nodes, flat_features] |= QUALITY_OUTLIER
    late_count = max(1, steps // 100)
    late_steps = rng.integers(0, steps, size=late_count)
    late_nodes = rng.integers(0, nodes, size=late_count)
    quality[late_steps, late_nodes, :] |= QUALITY_LATE
    return MockTimeSeries(timestamps, values, observed, quality)


def generate_load_aggregates(
    network: MockNetwork,
    observed_at: datetime,
    producer_count: int = 1000,
) -> list[dict[str, object]]:
    if producer_count != load_project_contract()["mvp_scope"][
        "synthetic_camera_producers"
    ]:
        raise ValueError("load producer count must match project contract")
    return [
        {
            "source_id": f"synthetic_camera_{index:04d}",
            "node_id": network.node_ids[index % len(network.node_ids)],
            "observed_at": observed_at.isoformat(),
            "traffic_volume_5m": float(10 + index % 70),
            "avg_speed_kmh": float(25 + index % 35),
            "heavy_vehicle_ratio": float(0.05 + (index % 10) / 100),
            "synthetic": True,
        }
        for index in range(producer_count)
    ]
