"""Duplicate train records selected from detector error analysis."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.training.rebalance_vehicle_training_dataset import (
        TARGET_CLASSES,
        copy_record,
        count_objects,
        write_dataset_yaml,
    )
    from scripts.data_prep.prepare_roboflow_yolo_dataset import sha256_file
except ModuleNotFoundError:
    from rebalance_vehicle_training_dataset import (
        TARGET_CLASSES,
        copy_record,
        count_objects,
        write_dataset_yaml,
    )
    from prepare_roboflow_yolo_dataset import sha256_file


def load_error_rows(error_csv: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with error_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({
                "split": row["split"],
                "image": row["image"],
                "fn": json.loads(row["fn"]),
                "fp": json.loads(row["fp"]),
                "confusion": json.loads(row["confusion"]),
                "fn_area_bins": json.loads(row["fn_area_bins"]),
            })
    return rows


def row_score(row: dict[str, Any], class_weights: dict[str, float]) -> float:
    score = 0.0
    for class_name, count in row["fn"].items():
        score += class_weights.get(class_name, 1.0) * float(count)
    for key, count in row["confusion"].items():
        target_class, _, _ = key.partition("->")
        score += 0.75 * class_weights.get(target_class, 1.0) * float(count)
    for key, count in row["fn_area_bins"].items():
        class_name, _, area_bin = key.partition(":")
        if area_bin == "tiny":
            score += 0.5 * class_weights.get(class_name, 1.0) * float(count)
    return score


def select_error_rows(
    rows: list[dict[str, Any]],
    *,
    class_weights: dict[str, float],
    max_records: int,
    min_score: float,
) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if row["split"] == "train" and row_score(row, class_weights) >= min_score
    ]
    candidates.sort(
        key=lambda row: (-row_score(row, class_weights), row["image"]),
    )
    return candidates[:max_records]


def record_by_image(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        record["image"]: record
        for record in manifest["records"]
        if record["split"] == "train"
    }


def rebalance_from_errors(
    *,
    source_root: Path,
    output_root: Path,
    error_csv: Path,
    repeat: int,
    max_records: int,
    min_score: float,
    class_weights: dict[str, float],
) -> dict[str, Any]:
    if repeat < 1:
        raise ValueError("repeat must be >= 1")
    source_manifest = json.loads(
        (source_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if source_manifest["classes"] != TARGET_CLASSES:
        raise ValueError("source dataset must use STWI vehicle classes")
    output_root.mkdir(parents=True, exist_ok=True)
    write_dataset_yaml(output_root)

    records: list[dict[str, Any]] = []
    for record in source_manifest["records"]:
        records.append(copy_record(
            source_root=source_root,
            output_root=output_root,
            record=record,
        ))

    lookup = record_by_image(source_manifest)
    selected_rows = select_error_rows(
        load_error_rows(error_csv),
        class_weights=class_weights,
        max_records=max_records,
        min_score=min_score,
    )
    skipped_missing = 0
    duplicate_count = 0
    selected_images: list[str] = []
    for pass_index in range(repeat):
        for row_index, row in enumerate(selected_rows):
            source_record = lookup.get(row["image"])
            if source_record is None:
                skipped_missing += 1
                continue
            selected_images.append(row["image"])
            output_stem = f"hardcase_{pass_index:02d}_{row_index:06d}"
            copied = copy_record(
                source_root=source_root,
                output_root=output_root,
                record=source_record,
                output_stem=output_stem,
                source_type="hardcase_error_replay",
            )
            copied["hardcase_score"] = row_score(row, class_weights)
            copied["hardcase_fn"] = row["fn"]
            copied["hardcase_confusion"] = row["confusion"]
            copied["hardcase_fn_area_bins"] = row["fn_area_bins"]
            records.append(copied)
            duplicate_count += 1

    split_counts: Counter[str] = Counter(record["split"] for record in records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{source_manifest['dataset_version']}_hardcase_replay",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "hardcase_error_replay_training_dataset",
        "source_dataset": str(source_root),
        "source_manifest_sha256": sha256_file(source_root / "dataset_manifest.json"),
        "error_csv": str(error_csv),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": source_manifest.get("ignored_classes", []),
        "split_policy": "val/test preserved; train records with model errors duplicated",
        "split_counts": dict(split_counts),
        "object_counts": count_objects(output_root, records),
        "privacy_status": source_manifest["privacy_status"],
        "privacy_review": source_manifest["privacy_review"],
        "hardcase_replay": {
            "repeat": repeat,
            "max_records": max_records,
            "min_score": min_score,
            "class_weights": class_weights,
            "selected_rows": len(selected_rows),
            "duplicate_records": duplicate_count,
            "skipped_missing": skipped_missing,
            "selected_images_preview": selected_images[:20],
        },
        "records": records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_class_weights(values: list[str] | None) -> dict[str, float]:
    weights = {name: 1.0 for name in TARGET_CLASSES}
    for value in values or []:
        class_name, separator, raw_weight = value.partition(":")
        if separator != ":" or class_name not in TARGET_CLASSES:
            raise ValueError(f"expected CLASS:WEIGHT for {TARGET_CLASSES}: {value}")
        weights[class_name] = float(raw_weight)
    return weights


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--error-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-records", type=int, default=1800)
    parser.add_argument("--min-score", type=float, default=1.0)
    parser.add_argument(
        "--class-weight",
        action="append",
        default=None,
        help="Class replay weight as CLASS:WEIGHT. Repeat for multiple classes.",
    )
    args = parser.parse_args()
    manifest = rebalance_from_errors(
        source_root=args.source,
        output_root=args.output,
        error_csv=args.error_csv,
        repeat=args.repeat,
        max_records=args.max_records,
        min_score=args.min_score,
        class_weights=parse_class_weights(args.class_weight),
    )
    print(json.dumps({
        "dataset": str(args.output),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "hardcase_replay": manifest["hardcase_replay"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
