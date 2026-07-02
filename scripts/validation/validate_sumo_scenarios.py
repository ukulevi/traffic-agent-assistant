"""Strict validation for the provisional offline SUMO scenario dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--phase1", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    manifest_path = args.dataset / "scenario_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source") != "offline_eclipse_sumo_runs":
        errors.append("scenario source is not offline Eclipse SUMO")
    network = args.dataset / "mock_20_node.net.xml"
    if sha256_file(network) != manifest.get("network_sha256"):
        errors.append("SUMO network hash mismatch")
    for name, expected_hash in manifest.get("artifacts", {}).items():
        path = args.dataset / name
        if not path.is_file() or sha256_file(path) != expected_hash:
            errors.append(f"artifact hash mismatch: {name}")

    scenarios = json.loads(
        (args.dataset / "scenarios.json").read_text(encoding="utf-8")
    )
    with np.load(
        args.dataset / "scenario_dataset.npz", allow_pickle=False
    ) as dataset:
        inputs = dataset["inputs"]
        outputs = dataset["outputs"]
        summaries = dataset["summaries"]
        splits = {
            "train": dataset["train_indices"],
            "val": dataset["val_indices"],
            "test": dataset["test_indices"],
        }
    if inputs.shape != (len(scenarios), 89):
        errors.append("scenario input shape mismatch")
    if outputs.shape != (len(scenarios), 6, 20, 3):
        errors.append("scenario output shape mismatch")
    if summaries.shape != (len(scenarios), 3):
        errors.append("scenario summary shape mismatch")
    if not all(np.all(np.isfinite(array)) for array in (inputs, outputs, summaries)):
        errors.append("scenario dataset contains non-finite values")
    if np.any(outputs < 0) or np.std(outputs[:, :, :, 0]) < 1e-3:
        errors.append("scenario outputs are invalid or constant")

    capacity = json.loads(
        (args.phase1 / "capacity_table.json").read_text(encoding="utf-8")
    )
    capacities = np.asarray(capacity["values"], dtype=np.float32)
    expected_vc = outputs[:, :, :, 0] * 12 / capacities[None, None, :]
    if not np.allclose(outputs[:, :, :, 2], expected_vc, atol=1e-6):
        errors.append("V/C does not match calibrated volume/capacity")

    all_indices = np.concatenate(list(splits.values()))
    if len(np.unique(all_indices)) != len(scenarios):
        errors.append("scenario split indices overlap or omit rows")
    family_sets = {
        split: {scenarios[index]["family_id"] for index in indices}
        for split, indices in splits.items()
    }
    if any(
        family_sets[left] & family_sets[right]
        for left, right in (("train", "val"), ("train", "test"), ("val", "test"))
    ):
        errors.append("scenario-family leakage detected")
    required_events = {
        "accident", "flood", "lane_closure", "demand_surge", "signal_change"
    }
    for split, indices in splits.items():
        events = {scenarios[index]["event_type"] for index in indices}
        if events != required_events:
            errors.append(f"event coverage incomplete in {split}")

    calibration = json.loads(
        (args.dataset / "calibration_report.json").read_text(encoding="utf-8")
    )
    if not calibration.get("volume_expansion_factor_applied"):
        errors.append("detector expansion calibration was not applied")
    if calibration.get("production_calibration") is not False:
        errors.append("mock calibration is incorrectly marked production")
    if calibration.get("selected_normalized_error", 1.0) > 0.15:
        errors.append("mock calibration error exceeds provisional 15% policy")
    if errors:
        raise ValueError("SUMO scenario validation failed:\n- " + "\n- ".join(errors))

    report = {
        "schema_version": "1.0",
        "status": "provisional_pass",
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sumo_version": manifest["sumo_version"],
        "scenario_count": len(scenarios),
        "family_count": len({row["family_id"] for row in scenarios}),
        "split_counts": {name: int(len(indices)) for name, indices in splits.items()},
        "event_coverage_each_split": True,
        "family_leakage": False,
        "calibration_scope": "synthetic_mock_only",
        "calibration_normalized_error": calibration["selected_normalized_error"],
        "production_ready": False,
    }
    if args.finalize:
        report_path = args.dataset / "sumo_validation_report.json"
        report_path.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        manifest["validation"] = report
        temporary = manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, manifest_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
