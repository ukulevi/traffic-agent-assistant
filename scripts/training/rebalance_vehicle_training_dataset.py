"""Rebalance STWI vehicle training data without changing validation/test splits."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.data_prep.prepare_roboflow_yolo_dataset import sha256_file
except ModuleNotFoundError:
    from prepare_roboflow_yolo_dataset import sha256_file


TARGET_CLASSES = ["bus", "car", "motorcycle", "truck"]


def write_dataset_yaml(root: Path) -> None:
    lines = [
        f"path: {root.resolve().as_posix()}",
        "train: train/images",
        "val: valid/images",
        "test: test/images",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(TARGET_CLASSES))
    (root / "dataset.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def classes_in_label(label_path: Path) -> set[str]:
    classes: set[str] = set()
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            classes.add(TARGET_CLASSES[int(line.split()[0])])
    return classes


def class_box_areas(label_path: Path, target_class: str) -> list[float]:
    target_index = TARGET_CLASSES.index(target_class)
    areas: list[float] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"expected YOLO xywh label: {label_path}:{line_number}")
        class_id = int(fields[0])
        if class_id == target_index:
            width = float(fields[3])
            height = float(fields[4])
            areas.append(width * height)
    return areas


def matches_boost_filter(
    label_path: Path,
    boost_class: str,
    min_box_area: float | None,
    max_box_area: float | None,
) -> bool:
    areas = class_box_areas(label_path, boost_class)
    if not areas:
        return False
    for area in areas:
        if min_box_area is not None and area < min_box_area:
            continue
        if max_box_area is not None and area > max_box_area:
            continue
        return True
    return False


def copy_record(
    *,
    source_root: Path,
    output_root: Path,
    record: dict[str, Any],
    output_stem: str | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    source_image = source_root / record["image"]
    source_label = source_root / record["label"]
    if output_stem is None:
        target_image = output_root / record["image"]
        target_label = output_root / record["label"]
    else:
        split_dir = "valid" if record["split"] == "val" else record["split"]
        target_image = output_root / split_dir / "images" / f"{output_stem}{source_image.suffix.lower()}"
        target_label = output_root / split_dir / "labels" / f"{output_stem}.txt"
    link_or_copy(source_image, target_image)
    link_or_copy(source_label, target_label)
    copied = dict(record)
    copied["image"] = target_image.relative_to(output_root).as_posix()
    copied["label"] = target_label.relative_to(output_root).as_posix()
    copied["sha256"] = sha256_file(target_image)
    if source_type:
        copied["source_type"] = source_type
        copied["rebalance_source_image"] = record["image"]
    return copied


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for line in (root / record["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def rebalance_dataset(
    *,
    source_root: Path,
    output_root: Path,
    boost_class: str,
    repeat: int,
    max_boost_records: int | None,
    min_box_area: float | None = None,
    max_box_area: float | None = None,
) -> dict[str, Any]:
    if boost_class not in TARGET_CLASSES:
        raise ValueError(f"unsupported boost class: {boost_class}")
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
    boost_candidates: list[dict[str, Any]] = []
    for record in source_manifest["records"]:
        copied = copy_record(
            source_root=source_root,
            output_root=output_root,
            record=record,
        )
        records.append(copied)
        if (
            record["split"] == "train"
            and matches_boost_filter(
                source_root / record["label"],
                boost_class,
                min_box_area,
                max_box_area,
            )
        ):
            boost_candidates.append(record)

    if max_boost_records is not None:
        boost_candidates = boost_candidates[:max_boost_records]

    duplicate_count = 0
    for pass_index in range(repeat):
        for candidate_index, record in enumerate(boost_candidates):
            output_stem = f"rebalance_{boost_class}_{pass_index:02d}_{candidate_index:06d}"
            records.append(copy_record(
                source_root=source_root,
                output_root=output_root,
                record=record,
                output_stem=output_stem,
                source_type=f"rebalance_boost_{boost_class}",
            ))
            duplicate_count += 1

    split_counts: Counter[str] = Counter(record["split"] for record in records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{source_manifest['dataset_version']}_rebalanced_{boost_class}",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "rebalanced_vehicle_training_dataset",
        "source_dataset": str(source_root),
        "source_manifest_sha256": sha256_file(source_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": source_manifest.get("ignored_classes", []),
        "split_policy": "val/test preserved; train records containing boost class duplicated",
        "split_counts": dict(split_counts),
        "object_counts": count_objects(output_root, records),
        "privacy_status": source_manifest["privacy_status"],
        "privacy_review": source_manifest["privacy_review"],
        "rebalance": {
            "boost_class": boost_class,
            "repeat": repeat,
            "min_box_area": min_box_area,
            "max_box_area": max_box_area,
            "boost_candidates": len(boost_candidates),
            "duplicate_records": duplicate_count,
        },
        "records": records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boost-class", choices=TARGET_CLASSES, default="motorcycle")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--max-boost-records", type=int, default=None)
    parser.add_argument("--min-box-area", type=float, default=None)
    parser.add_argument("--max-box-area", type=float, default=None)
    args = parser.parse_args()
    manifest = rebalance_dataset(
        source_root=args.source,
        output_root=args.output,
        boost_class=args.boost_class,
        repeat=args.repeat,
        max_boost_records=args.max_boost_records,
        min_box_area=args.min_box_area,
        max_box_area=args.max_box_area,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "rebalance": manifest["rebalance"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
