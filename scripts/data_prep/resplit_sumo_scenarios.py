"""Migrate SUMO scenarios to event-node family holdout without rerunning SUMO."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np


EVENT_TYPES = (
    "accident", "flood", "lane_closure", "demand_surge", "signal_change"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_for_family(node_index: int, event_index: int) -> str:
    bucket = (node_index + event_index * 4) % 20
    if bucket < 14:
        return "train"
    if bucket < 17:
        return "val"
    return "test"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    scenarios_path = args.dataset / "scenarios.json"
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    for record in scenarios:
        event_index = EVENT_TYPES.index(record["event_type"])
        node_index = int(record["affected_node_id"].rsplit("_", 1)[1])
        record["split"] = split_for_family(node_index, event_index)
    temporary_scenarios = scenarios_path.with_suffix(".json.tmp")
    temporary_scenarios.write_text(
        json.dumps(scenarios, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_scenarios, scenarios_path)

    dataset_path = args.dataset / "scenario_dataset.npz"
    with np.load(dataset_path, allow_pickle=False) as data:
        arrays = {name: data[name] for name in data.files}
    split_names = np.array([record["split"] for record in scenarios])
    arrays["train_indices"] = np.flatnonzero(split_names == "train")
    arrays["val_indices"] = np.flatnonzero(split_names == "val")
    arrays["test_indices"] = np.flatnonzero(split_names == "test")
    temporary_dataset = dataset_path.with_suffix(".npz.tmp")
    with temporary_dataset.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary_dataset, dataset_path)

    coverage_path = args.dataset / "scenario_coverage_report.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["split_counts"] = {
        split: int(np.count_nonzero(split_names == split))
        for split in ("train", "val", "test")
    }
    coverage["split_policy"] = "event-node scenario family holdout"
    temporary_coverage = coverage_path.with_suffix(".json.tmp")
    temporary_coverage.write_text(
        json.dumps(coverage, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_coverage, coverage_path)

    manifest_path = args.dataset / "scenario_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["split_policy"] = "event-node scenario family holdout"
    manifest.pop("validation", None)
    for name in (
        "scenario_dataset.npz", "scenarios.json", "scenario_coverage_report.json"
    ):
        manifest["artifacts"][name] = sha256_file(args.dataset / name)
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_manifest.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_manifest, manifest_path)
    print(json.dumps(coverage["split_counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
