"""Build a traceable STWI dataset from licensed public-proxy traffic data.

The public-proxy path is deliberately separate from the local deployment
dataset.  It can support an offline MVP demo while real local sensor/camera
inputs are unavailable, but it must never be labelled as representative of a
Vietnamese deployment or be used to calibrate field interventions.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from stwi.contracts.project import (
    feature_names,
    load_project_contract,
    scaled_feature_indices,
)
from stwi.t1_pipeline.tensor_builder import (
    StandardScaler,
    apply_quality_and_impute,
    build_tensor_windows,
    chronological_split_indices,
)


REQUIRED_COLUMNS = frozenset(
    {"timestamp", "source_node_id", "traffic_volume_5m", "avg_speed_kmh"}
)
PUBLIC_PROXY_CLASSIFICATION = "public_proxy_demo_only"


@dataclass(frozen=True)
class PublicProxySource:
    provider_name: str
    source_url: str
    license_reference: str
    access_confirmed_by: str
    downloaded_at_utc: str
    data_scope_notice: str


@dataclass(frozen=True)
class PublicProxyNetwork:
    network_version: str
    node_order: tuple[str, ...]
    source_node_order: tuple[str, ...]
    capacities_vph: np.ndarray
    free_flow_speed_kmh: np.ndarray
    adjacency: np.ndarray


def sha256_file(path: Path) -> str:
    """Return the content digest recorded in the provenance manifest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if timestamp.tzinfo is None:
        raise ValueError("timestamps must include an explicit UTC offset")
    return timestamp


def _require_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"spec field {field!r} must be a non-empty string")
    return value.strip()


def load_source_spec(path: Path) -> tuple[PublicProxySource, PublicProxyNetwork]:
    """Load and validate the hand-authored provenance/network spec."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported public-proxy spec schema")
    if payload.get("data_classification") != PUBLIC_PROXY_CLASSIFICATION:
        raise ValueError("spec must declare public_proxy_demo_only classification")

    source_payload = payload.get("source")
    if not isinstance(source_payload, dict):
        raise ValueError("spec source must be an object")
    source = PublicProxySource(
        provider_name=_require_text(source_payload, "provider_name"),
        source_url=_require_text(source_payload, "source_url"),
        license_reference=_require_text(source_payload, "license_reference"),
        access_confirmed_by=_require_text(source_payload, "access_confirmed_by"),
        downloaded_at_utc=_require_text(source_payload, "downloaded_at_utc"),
        data_scope_notice=_require_text(source_payload, "data_scope_notice"),
    )
    _parse_timestamp(source.downloaded_at_utc)

    network_payload = payload.get("network")
    if not isinstance(network_payload, dict):
        raise ValueError("spec network must be an object")
    contract = load_project_contract()
    expected_nodes = contract["mvp_scope"]["functional_network_nodes"]
    nodes = network_payload.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != expected_nodes:
        raise ValueError(f"spec must contain exactly {expected_nodes} proxy nodes")

    node_order: list[str] = []
    source_node_order: list[str] = []
    capacities: list[float] = []
    free_flow_speeds: list[float] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"network node {index} must be an object")
        node_order.append(_require_text(node, "node_id"))
        source_node_order.append(_require_text(node, "source_node_id"))
        try:
            capacity = float(node["capacity_vph"])
            free_flow_speed = float(node["free_flow_speed_kmh"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"network node {index} needs numeric capacity_vph and "
                "free_flow_speed_kmh"
            ) from exc
        if capacity <= 0 or free_flow_speed <= 0:
            raise ValueError("capacity and free-flow speed must be positive")
        capacities.append(capacity)
        free_flow_speeds.append(free_flow_speed)
    if len(set(node_order)) != expected_nodes:
        raise ValueError("proxy node_id values must be unique")
    if len(set(source_node_order)) != expected_nodes:
        raise ValueError("source_node_id values must map one-to-one to proxy nodes")

    adjacency = np.asarray(network_payload.get("adjacency"), dtype=np.float32)
    if adjacency.shape != (expected_nodes, expected_nodes):
        raise ValueError("proxy adjacency must have shape [20,20]")
    if not np.all(np.isfinite(adjacency)) or np.any(adjacency < 0):
        raise ValueError("proxy adjacency must be finite and non-negative")
    if not np.allclose(adjacency, adjacency.T):
        raise ValueError("proxy adjacency must be symmetric")

    return source, PublicProxyNetwork(
        network_version=_require_text(network_payload, "network_version"),
        node_order=tuple(node_order),
        source_node_order=tuple(source_node_order),
        capacities_vph=np.asarray(capacities, dtype=np.float32),
        free_flow_speed_kmh=np.asarray(free_flow_speeds, dtype=np.float32),
        adjacency=adjacency,
    )


def _read_observations(
    path: Path, source_node_order: tuple[str, ...]
) -> tuple[list[datetime], np.ndarray, np.ndarray]:
    """Read a rectangular 5-minute CSV without silently resampling it."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(
                "CSV requires timestamp, source_node_id, traffic_volume_5m, "
                "and avg_speed_kmh columns"
            )
        rows = list(reader)
    if not rows:
        raise ValueError("CSV has no observations")

    source_positions = {node_id: index for index, node_id in enumerate(source_node_order)}
    records: dict[datetime, dict[int, tuple[float, float]]] = {}
    for line_number, row in enumerate(rows, start=2):
        timestamp = _parse_timestamp(row.get("timestamp", ""))
        source_node_id = row.get("source_node_id", "").strip()
        if source_node_id not in source_positions:
            raise ValueError(f"line {line_number} has unmapped source_node_id")
        try:
            volume = float(row.get("traffic_volume_5m", ""))
            speed = float(row.get("avg_speed_kmh", ""))
        except ValueError as exc:
            raise ValueError(f"line {line_number} has non-numeric traffic values") from exc
        if not np.isfinite(volume) or not np.isfinite(speed):
            raise ValueError(f"line {line_number} has non-finite traffic values")
        if volume < 0 or speed < 0:
            raise ValueError(f"line {line_number} has negative traffic values")
        by_node = records.setdefault(timestamp, {})
        position = source_positions[source_node_id]
        if position in by_node:
            raise ValueError(f"line {line_number} duplicates a timestamp/node observation")
        by_node[position] = (volume, speed)

    timestamps = sorted(records)
    expected_step_seconds = load_project_contract()["data_contract"]["time_step_minutes"] * 60
    for previous, current in zip(timestamps, timestamps[1:]):
        if (current - previous).total_seconds() != expected_step_seconds:
            raise ValueError("CSV timestamps must be contiguous at five-minute intervals")
    if len(timestamps) < 128:
        raise ValueError("at least 128 five-minute timestamps are required")
    for timestamp in timestamps:
        if len(records[timestamp]) != len(source_node_order):
            raise ValueError("CSV must contain every mapped source node at each timestamp")

    values = np.empty((len(timestamps), len(source_node_order), 2), dtype=np.float32)
    for row_index, timestamp in enumerate(timestamps):
        for node_index in range(len(source_node_order)):
            values[row_index, node_index] = records[timestamp][node_index]
    observed = np.ones_like(values, dtype=np.bool_)
    return timestamps, values, observed


def build_public_proxy_timeseries(
    timestamps: list[datetime], observations: np.ndarray, observed: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Project observed targets into the fixed 16-feature STWI input contract."""
    features = feature_names()
    values = np.zeros(
        (len(timestamps), observations.shape[1], len(features)), dtype=np.float32
    )
    mask = np.zeros_like(values, dtype=np.bool_)
    # These are neutral imputation seeds within the quality bounds.  Their
    # false mask is the provenance: no public-proxy source observation exists.
    values[:, :, 4] = 400.0  # co2_ppm
    values[:, :, 8] = 20.0   # temperature_c
    values[:, :, 9] = 50.0   # humidity_pct
    values[:, :, 15] = 0.5   # green_time_ratio
    values[:, :, 0:2] = observations
    mask[:, :, 0:2] = observed

    for index, timestamp in enumerate(timestamps):
        minutes = timestamp.hour * 60 + timestamp.minute
        angle = 2 * np.pi * minutes / (24 * 60)
        day_angle = 2 * np.pi * timestamp.weekday() / 7
        values[index, :, 11] = np.sin(angle)
        values[index, :, 12] = np.cos(angle)
        values[index, :, 13] = np.sin(day_angle)
        values[index, :, 14] = np.cos(day_angle)
    mask[:, :, 11:15] = True
    return values, mask


def _prepare_output(output: Path, replace: bool) -> None:
    if output.exists():
        marker = output / "dataset_manifest.json"
        if not replace:
            raise FileExistsError("output exists; pass --replace to rebuild")
        if not marker.is_file():
            raise ValueError("refusing to replace a non-dataset directory")
        shutil.rmtree(output)
    output.mkdir(parents=True)


def _fit_public_proxy_scaler(
    values: np.ndarray, observed_mask: np.ndarray, train_end_step: int
) -> StandardScaler:
    """Fit the contract scaler without treating unavailable inputs as observed.

    Public sources usually provide volume and speed only.  A feature with no
    source observations gets the neutral scale ``mean=0, std=1`` while its mask
    remains false; this avoids NaNs without manufacturing an observation.
    """
    feature_indices = scaled_feature_indices()
    mean = np.zeros(len(feature_indices), dtype=np.float32)
    std = np.ones(len(feature_indices), dtype=np.float32)
    for position, feature_index in enumerate(feature_indices):
        training_values = values[:train_end_step, :, feature_index]
        training_mask = observed_mask[:train_end_step, :, feature_index]
        observed_values = training_values[training_mask]
        if observed_values.size:
            mean[position] = np.mean(observed_values, dtype=np.float64)
            feature_std = float(np.std(observed_values, dtype=np.float64))
            std[position] = feature_std if feature_std >= 1e-6 else 1.0
    return StandardScaler(
        feature_indices=feature_indices,
        mean=mean,
        std=std,
    )


def build_public_proxy_dataset(
    csv_path: Path, spec_path: Path, output: Path, *, replace: bool = False
) -> dict[str, Any]:
    """Build a private aggregate-only dataset and return its manifest."""
    source, network = load_source_spec(spec_path)
    timestamps, observed_targets, observed_target_mask = _read_observations(
        csv_path, network.source_node_order
    )
    raw_values, raw_observed_mask = build_public_proxy_timeseries(
        timestamps, observed_targets, observed_target_mask
    )
    quality = apply_quality_and_impute(raw_values, raw_observed_mask, network.adjacency)
    train_end_step = int(len(timestamps) * 0.70)
    scaler = _fit_public_proxy_scaler(
        quality.values, quality.observed_mask, train_end_step
    )
    tensors = build_tensor_windows(
        scaler.transform(quality.values),
        quality.observed_mask,
        network.adjacency,
        target_values=quality.values,
    )
    splits = chronological_split_indices(tensors, len(timestamps))
    if any(len(indices) == 0 for indices in splits.values()):
        raise ValueError("dataset is too short for chronological train/val/test splits")

    _prepare_output(output, replace)
    contract = load_project_contract()
    node_registry = {
        "schema_version": "1.0",
        "network_version": network.network_version,
        "node_order": list(network.node_order),
        "nodes": [
            {
                "node_id": node_id,
                "capacity_vph": float(network.capacities_vph[index]),
                "free_flow_speed_kmh": float(network.free_flow_speed_kmh[index]),
                "source_node_id": network.source_node_order[index],
            }
            for index, node_id in enumerate(network.node_order)
        ],
    }
    capacity_table = {
        "schema_version": "1.0",
        "capacity_version": f"{network.network_version}-declared-capacity-v1",
        "unit": "vehicles/hour",
        "node_order": list(network.node_order),
        "values": network.capacities_vph.tolist(),
        "provenance": "declared in public-proxy source spec; not local field capacity",
    }
    source_node_map = {
        "schema_version": "1.0",
        "mapping_version": f"{network.network_version}-public-proxy-v1",
        "mappings": [
            {"source_id": source_node_id, "node_ids": [node_id]}
            for node_id, source_node_id in zip(network.node_order, network.source_node_order)
        ],
    }
    scaler_payload = {
        "schema_version": "1.0",
        "fit_scope": "training_split_only",
        "feature_indices": list(scaler.feature_indices),
        "feature_names": [feature_names()[index] for index in scaler.feature_indices],
        "mean": scaler.mean.tolist(),
        "std": scaler.std.tolist(),
    }
    (output / "node_registry.json").write_text(json.dumps(node_registry, indent=2) + "\n", encoding="utf-8")
    (output / "capacity_table.json").write_text(json.dumps(capacity_table, indent=2) + "\n", encoding="utf-8")
    (output / "source_node_map.json").write_text(json.dumps(source_node_map, indent=2) + "\n", encoding="utf-8")
    np.save(output / "adjacency.npy", network.adjacency)
    np.savez_compressed(
        output / "timeseries.npz",
        timestamps=np.asarray([timestamp.isoformat() for timestamp in timestamps]),
        values=quality.values,
        observed_mask=quality.observed_mask,
        raw_observed_mask=raw_observed_mask,
    )
    np.savez_compressed(
        output / "tensor_dataset.npz",
        X=tensors.X,
        M=tensors.M,
        A=tensors.A,
        Y=tensors.Y,
        train_indices=splits["train"],
        val_indices=splits["val"],
        test_indices=splits["test"],
        window_start_indices=tensors.window_start_indices,
    )
    (output / "scaler.json").write_text(json.dumps(scaler_payload, indent=2) + "\n", encoding="utf-8")

    artifacts = {
        path.name: {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "dataset_manifest.json"
    }
    manifest = {
        "schema_version": "1.0",
        "dataset_id": f"stwi_public_proxy_{network.network_version}",
        "contract_version": contract["contract_version"],
        "data_classification": PUBLIC_PROXY_CLASSIFICATION,
        "production_representativeness": "not_claimed",
        "intervention_calibration_eligible": False,
        "source": {
            "provider_name": source.provider_name,
            "source_url": source.source_url,
            "license_reference": source.license_reference,
            "access_confirmed_by": source.access_confirmed_by,
            "downloaded_at_utc": source.downloaded_at_utc,
            "data_scope_notice": source.data_scope_notice,
            "input_csv_sha256": sha256_file(csv_path),
        },
        "network_version": network.network_version,
        "time_range": {
            "start": timestamps[0].isoformat(),
            "end": timestamps[-1].isoformat(),
            "step_minutes": contract["data_contract"]["time_step_minutes"],
        },
        "feature_order": list(feature_names()),
        "shapes": {
            "timeseries": list(quality.values.shape),
            "X": list(tensors.X.shape),
            "M": list(tensors.M.shape),
            "A": list(tensors.A.shape),
            "Y": list(tensors.Y.shape),
        },
        "splits": {name: int(len(indices)) for name, indices in splits.items()},
        "quality": {
            "missing_ratio_after_source_projection": quality.missing_ratio,
            "source_observed_features": ["traffic_volume_5m", "avg_speed_kmh"],
            "deterministic_time_features": [
                "time_of_day_sin", "time_of_day_cos", "day_of_week_sin", "day_of_week_cos"
            ],
            "unavailable_features_remain_masked": True,
            "all_imputed_values_finite": bool(np.all(np.isfinite(quality.values))),
        },
        "normalization": {
            "fit_on_training_split_only": True,
            "targets_stored_in_physical_units": True,
        },
        "privacy": {"contains_video_or_frames": False, "aggregate_only": True},
        "gate_p1": {"status": "candidate", "required_batch_shape": [32, 12, 20, 16]},
        "artifacts": artifacts,
    }
    manifest_path = output / "dataset_manifest.json"
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, manifest_path)
    return manifest
