"""Generate the versioned Gate-P1 mock dataset and Phase-2 handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stwi.contracts.project import feature_names, load_project_contract  # noqa: E402
from stwi.t1_pipeline.mock_data import (  # noqa: E402
    generate_load_aggregates,
    generate_mock_network,
    generate_mock_timeseries,
)
from stwi.t1_pipeline.tensor_builder import (  # noqa: E402
    apply_quality_and_impute,
    build_tensor_windows,
    chronological_split_indices,
    fit_train_scaler,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_output(output: Path, replace: bool) -> None:
    if output.exists():
        marker = output / "dataset_manifest.json"
        if not replace:
            raise FileExistsError("output exists; pass --replace to rebuild")
        if not marker.is_file():
            raise ValueError("refusing to replace a non-dataset directory")
        shutil.rmtree(output)
    output.mkdir(parents=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/derived/private/phase1_mock"),
    )
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seed", type=int, default=20250530)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not 7 <= args.days <= 365:
        raise ValueError("days must be between 7 and 365")
    prepare_output(args.output, args.replace)

    contract = load_project_contract()
    start = datetime.fromisoformat("2025-05-01T00:00:00+07:00")
    network = generate_mock_network(seed=args.seed)
    raw = generate_mock_timeseries(
        network, start=start, days=args.days, seed=args.seed
    )
    quality = apply_quality_and_impute(
        raw.values, raw.observed_mask, network.adjacency
    )
    train_end_step = int(len(raw.timestamps) * 0.70)
    scaler = fit_train_scaler(
        quality.values, quality.observed_mask, train_end_step
    )
    scaled_values = scaler.transform(quality.values)
    tensors = build_tensor_windows(
        scaled_values,
        quality.observed_mask,
        network.adjacency,
        target_values=quality.values,
    )
    splits = chronological_split_indices(tensors, len(raw.timestamps))

    node_registry = {
        "schema_version": "1.0",
        "network_version": network.version,
        "node_order": list(network.node_ids),
        "nodes": [
            {
                "node_id": node_id,
                "capacity_vph": float(network.capacities_vph[index]),
                "free_flow_speed_kmh": float(
                    network.free_flow_speed_kmh[index]
                ),
                "camera_source_id": f"camera_{index:02d}",
                "sensor_source_id": f"sensor_{index:02d}",
            }
            for index, node_id in enumerate(network.node_ids)
        ],
    }
    (args.output / "node_registry.json").write_text(
        json.dumps(node_registry, indent=2) + "\n", encoding="utf-8"
    )
    capacity_table = {
        "schema_version": "1.0",
        "capacity_version": "mock-capacity-v1",
        "unit": "vehicles/hour",
        "node_order": list(network.node_ids),
        "values": network.capacities_vph.tolist(),
    }
    (args.output / "capacity_table.json").write_text(
        json.dumps(capacity_table, indent=2) + "\n", encoding="utf-8"
    )
    sensor_node_map = {
        "schema_version": "1.0",
        "mapping_version": "mock-sensor-node-map-v1",
        "mappings": [
            {
                "source_id": f"sensor_{index:02d}",
                "node_ids": [node_id],
            }
            for index, node_id in enumerate(network.node_ids)
        ],
    }
    (args.output / "sensor_node_map.json").write_text(
        json.dumps(sensor_node_map, indent=2) + "\n", encoding="utf-8"
    )
    np.save(args.output / "adjacency.npy", network.adjacency)
    np.savez_compressed(
        args.output / "timeseries.npz",
        timestamps=np.array(
            [timestamp.isoformat() for timestamp in raw.timestamps]
        ),
        values=quality.values,
        observed_mask=quality.observed_mask,
        quality_flags=raw.quality_flags,
    )
    np.savez_compressed(
        args.output / "tensor_dataset.npz",
        X=tensors.X,
        M=tensors.M,
        A=tensors.A,
        Y=tensors.Y,
        train_indices=splits["train"],
        val_indices=splits["val"],
        test_indices=splits["test"],
        window_start_indices=tensors.window_start_indices,
    )
    scaler_payload = {
        "schema_version": "1.0",
        "fit_scope": "training_split_only",
        "feature_indices": list(scaler.feature_indices),
        "feature_names": [feature_names()[index] for index in scaler.feature_indices],
        "mean": scaler.mean.tolist(),
        "std": scaler.std.tolist(),
    }
    (args.output / "scaler.json").write_text(
        json.dumps(scaler_payload, indent=2) + "\n", encoding="utf-8"
    )
    load_records = generate_load_aggregates(network, start)
    (args.output / "load_producers_1000.json").write_text(
        json.dumps(load_records, indent=2) + "\n", encoding="utf-8"
    )

    artifacts = {}
    for path in sorted(args.output.iterdir()):
        if path.is_file() and path.name != "dataset_manifest.json":
            artifacts[path.name] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    manifest = {
        "schema_version": "1.0",
        "dataset_id": "stwi_phase1_mock_v1",
        "data_policy": "phase2-simulation-first-demo-v1",
        "data_classification": "synthetic_simulation_demo_only",
        "source_provenance": {
            "kind": "deterministic_analytical_traffic_simulation",
            "camera_frames_used": False,
            "field_sensor_observations_used": False,
        },
        "demo_scope_approved": True,
        "production_representativeness": "not_claimed",
        "production_ready": False,
        "contract_version": contract["contract_version"],
        "network_version": network.version,
        "seed": args.seed,
        "time_range": {
            "start": raw.timestamps[0].isoformat(),
            "end": raw.timestamps[-1].isoformat(),
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
            "missing_ratio": quality.missing_ratio,
            "outlier_count": quality.outlier_count,
            "all_imputed_values_finite": bool(np.all(np.isfinite(quality.values))),
        },
        "normalization": {
            "fit_on_training_split_only": True,
            "scaled_feature_count": len(scaler.feature_indices),
            "targets_stored_in_physical_units": True,
        },
        "privacy": {
            "contains_video_or_frames": False,
            "aggregate_only": True,
        },
        "load_test": {
            "synthetic_aggregate_producers": len(load_records),
            "video_streams": 0,
        },
        "gate_p1": {
            "status": "candidate",
            "required_batch_shape": [32, 12, 20, 16],
        },
        "artifacts": artifacts,
    }
    (args.output / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
