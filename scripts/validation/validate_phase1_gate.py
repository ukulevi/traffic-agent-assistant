"""Validate and optionally finalize the STWI Phase-1 integration gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stwi.contracts.project import (  # noqa: E402
    feature_names,
    load_project_contract,
    scaled_feature_indices,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_phase1_gate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    contract = load_project_contract()
    data_contract = contract["data_contract"]
    manifest_path = root / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("contract_version") != contract["contract_version"]:
        errors.append("contract version mismatch")
    if manifest.get("feature_order") != list(feature_names()):
        errors.append("feature order mismatch")

    for artifact_name, metadata in manifest.get("artifacts", {}).items():
        path = root / artifact_name
        if not path.is_file():
            errors.append(f"missing artifact: {artifact_name}")
        elif sha256_file(path) != metadata["sha256"]:
            errors.append(f"hash mismatch: {artifact_name}")

    registry = json.loads(
        (root / "node_registry.json").read_text(encoding="utf-8")
    )
    expected_nodes = contract["mvp_scope"]["functional_network_nodes"]
    if len(registry["node_order"]) != expected_nodes:
        errors.append("node registry does not contain 20 nodes")
    if len(set(registry["node_order"])) != expected_nodes:
        errors.append("node ids are not unique")
    if any(node["capacity_vph"] <= 0 for node in registry["nodes"]):
        errors.append("capacity table contains non-positive value")
    capacity = json.loads(
        (root / "capacity_table.json").read_text(encoding="utf-8")
    )
    if capacity["node_order"] != registry["node_order"]:
        errors.append("capacity table node order mismatch")
    if not np.allclose(
        capacity["values"],
        [node["capacity_vph"] for node in registry["nodes"]],
    ):
        errors.append("capacity values disagree with node registry")
    sensor_map = json.loads(
        (root / "sensor_node_map.json").read_text(encoding="utf-8")
    )
    mapped_nodes = [
        mapping["node_ids"][0] for mapping in sensor_map["mappings"]
    ]
    if mapped_nodes != registry["node_order"]:
        errors.append("sensor-node mapping/order mismatch")

    adjacency = np.load(root / "adjacency.npy", allow_pickle=False)
    if adjacency.shape != (expected_nodes, expected_nodes):
        errors.append("adjacency shape mismatch")
    if not np.allclose(adjacency, adjacency.T):
        errors.append("GCN adjacency is not symmetric")

    with np.load(root / "timeseries.npz", allow_pickle=False) as time_series:
        values = time_series["values"]
        observed_mask = time_series["observed_mask"]
        timestamps = time_series["timestamps"]
    if values.shape[1:] != (expected_nodes, len(feature_names())):
        errors.append("timeseries shape mismatch")
    if observed_mask.shape != values.shape:
        errors.append("timeseries mask shape mismatch")
    if not np.all(np.isfinite(values)):
        errors.append("timeseries contains non-finite values after imputation")
    if observed_mask.dtype != np.bool_ or np.all(observed_mask):
        errors.append("missing mask is invalid or contains no missing values")

    with np.load(root / "tensor_dataset.npz", allow_pickle=False) as tensors:
        X = tensors["X"]
        M = tensors["M"]
        A = tensors["A"]
        Y = tensors["Y"]
        starts = tensors["window_start_indices"]
        splits = {
            "train": tensors["train_indices"],
            "val": tensors["val_indices"],
            "test": tensors["test_indices"],
        }
    if X.shape[0] < 32 or X.shape[1:] != (12, 20, 16):
        errors.append("X does not satisfy Gate-P1 batch shape")
    if M.shape != X.shape or M.dtype != np.bool_:
        errors.append("M contract mismatch")
    if A.shape != (20, 20) or not np.array_equal(A, adjacency):
        errors.append("A contract/order mismatch")
    if Y.shape != (X.shape[0], 6, 20, 2):
        errors.append("Y contract mismatch")
    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(Y)):
        errors.append("tensor dataset contains non-finite values")

    all_split_indices = np.concatenate(list(splits.values()))
    if any(len(indices) == 0 for indices in splits.values()):
        errors.append("one or more chronological splits are empty")
    if len(np.unique(all_split_indices)) != len(all_split_indices):
        errors.append("window leakage across splits")
    if not (
        splits["train"][-1] < splits["val"][0]
        and splits["val"][-1] < splits["test"][0]
    ):
        errors.append("split order is not chronological")

    scaler = json.loads((root / "scaler.json").read_text(encoding="utf-8"))
    expected_scaled = list(scaled_feature_indices())
    if scaler["feature_indices"] != expected_scaled:
        errors.append("scaler feature selection does not match contract")
    train_cutoff = int(len(timestamps) * 0.70)
    recomputed = np.nanmean(
        np.where(
            observed_mask[:train_cutoff, :, expected_scaled],
            values[:train_cutoff, :, expected_scaled],
            np.nan,
        ),
        axis=(0, 1),
    )
    if not np.allclose(recomputed, np.array(scaler["mean"]), atol=1e-5):
        errors.append("scaler was not fit from the training split")

    target_indices = [
        feature_names().index(name)
        for name in data_contract["forecast_targets"]
    ]
    sample_count = min(8, len(starts))
    for window_index in range(sample_count):
        target_start = int(starts[window_index]) + data_contract["history_steps"]
        expected_y = values[
            target_start:target_start + data_contract["forecast_steps"],
            :,
            target_indices,
        ]
        if not np.allclose(Y[window_index], expected_y):
            errors.append("Y is not stored in physical target units")
            break

    producers = json.loads(
        (root / "load_producers_1000.json").read_text(encoding="utf-8")
    )
    expected_producers = contract["mvp_scope"]["synthetic_camera_producers"]
    if len(producers) != expected_producers:
        errors.append("load producer count mismatch")
    if any("frame" in record or not record.get("synthetic") for record in producers):
        errors.append("load test includes non-aggregate or non-synthetic data")
    if manifest.get("privacy") != {
        "contains_video_or_frames": False,
        "aggregate_only": True,
    }:
        errors.append("privacy manifest is not aggregate-only")

    if errors:
        raise ValueError("Gate P1 failed:\n- " + "\n- ".join(errors))
    return {
        "status": "pass",
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_version": contract["contract_version"],
        "batch_shape": list(X[:32].shape),
        "mask_shape": list(M[:32].shape),
        "adjacency_shape": list(A.shape),
        "forecast_shape": list(Y[:32].shape),
        "split_windows": {name: int(len(indices)) for name, indices in splits.items()},
        "missing_ratio": float(1 - observed_mask.mean()),
        "scaled_feature_count": len(expected_scaled),
        "synthetic_aggregate_producers": len(producers),
        "privacy": "aggregate_only_no_video_or_frames",
    }


def finalize(root: Path, report: dict[str, Any]) -> None:
    report_path = root / "gate_p1_report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    manifest_path = root / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["gate_p1"] = report
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    report = validate_phase1_gate(args.dataset)
    if args.finalize:
        finalize(args.dataset, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
