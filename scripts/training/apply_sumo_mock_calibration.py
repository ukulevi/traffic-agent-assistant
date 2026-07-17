"""Apply train-side detector expansion calibration to existing SUMO outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--phase1", type=Path, required=True)
    args = parser.parse_args()
    calibration_path = args.dataset / "calibration_report.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    if calibration.get("volume_expansion_factor_applied"):
        raise ValueError("volume expansion calibration is already applied")
    observed = np.asarray(
        calibration["observed_mean_volume_speed"], dtype=np.float64
    )
    for run in calibration["candidate_runs"]:
        simulated = np.asarray(
            run["simulated_mean_volume_speed"], dtype=np.float64
        )
        factor = float(observed[0] / max(simulated[0], 1e-6))
        calibrated = simulated.copy()
        calibrated[0] *= factor
        run["volume_expansion_factor"] = factor
        run["calibrated_mean_volume_speed"] = calibrated.tolist()
        run["normalized_error"] = float(np.mean(np.abs(
            (calibrated - observed) / np.maximum(observed, 1)
        )))
    selected = min(
        calibration["candidate_runs"], key=lambda run: run["normalized_error"]
    )
    factor = float(selected["volume_expansion_factor"])
    calibration["selected_vehicle_count_30m"] = selected[
        "vehicle_count_30m"
    ]
    calibration["selected_normalized_error"] = selected["normalized_error"]
    calibration["selected_volume_expansion_factor"] = factor
    calibration["volume_expansion_factor_applied"] = True

    capacity = json.loads(
        (args.phase1 / "capacity_table.json").read_text(encoding="utf-8")
    )
    capacities = np.asarray(capacity["values"], dtype=np.float32)
    dataset_path = args.dataset / "scenario_dataset.npz"
    with np.load(dataset_path, allow_pickle=False) as data:
        arrays = {name: data[name] for name in data.files}
    outputs = arrays["outputs"].copy()
    outputs[:, :, :, 0] *= factor
    outputs[:, :, :, 2] = outputs[:, :, :, 0] * 12 / capacities[None, None, :]
    summaries = arrays["summaries"].copy()
    summaries[:, 2] = outputs[:, :, :, 2].max(axis=(1, 2))
    arrays["outputs"] = outputs
    arrays["summaries"] = summaries
    temporary_dataset = dataset_path.with_suffix(".npz.tmp")
    with temporary_dataset.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary_dataset, dataset_path)

    temporary_calibration = calibration_path.with_suffix(".json.tmp")
    temporary_calibration.write_text(
        json.dumps(calibration, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_calibration, calibration_path)
    manifest_path = args.dataset / "scenario_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["calibration"] = {
        "volume_expansion_factor": factor,
        "normalized_error": selected["normalized_error"],
        "scope": "synthetic_simulation_demo_only",
    }
    manifest["artifacts"]["scenario_dataset.npz"] = sha256_file(dataset_path)
    manifest["artifacts"]["calibration_report.json"] = sha256_file(
        calibration_path
    )
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_manifest, manifest_path)
    print(json.dumps(manifest["calibration"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
