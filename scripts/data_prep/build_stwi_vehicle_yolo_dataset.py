"""Build a vehicle-only YOLO dataset from a prepared Roboflow export."""

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
SPLIT_DIRS = {"train": "train", "val": "valid", "test": "test"}


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


def remap_label(
    label_path: Path,
    output_label_path: Path,
    source_classes: list[str],
    class_map: dict[str, str | None],
) -> int:
    target_index = {name: index for index, name in enumerate(TARGET_CLASSES)}
    output_lines: list[str] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        source_class = source_classes[int(fields[0])]
        target_class = class_map.get(source_class)
        if target_class not in target_index:
            continue
        output_lines.append(" ".join([str(target_index[target_class]), *fields[1:]]))
    if output_lines:
        output_label_path.parent.mkdir(parents=True, exist_ok=True)
        output_label_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return len(output_lines)


def build_vehicle_dataset(source_root: Path, output_root: Path) -> dict[str, Any]:
    source_manifest = json.loads(
        (source_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    source_classes = list(source_manifest["classes"])
    class_map = dict(source_manifest["stwi_class_map"])
    if source_manifest.get("privacy_status") != "visual_spot_reviewed_agent":
        raise ValueError("source dataset must pass privacy review before vehicle export")

    output_root.mkdir(parents=True, exist_ok=True)
    write_dataset_yaml(output_root)
    records: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    object_counts: Counter[str] = Counter()

    for record_index, record in enumerate(source_manifest["records"]):
        source_image = source_root / record["image"]
        source_label = source_root / record["label"]
        split = record["split"]
        split_dir = SPLIT_DIRS[split]
        short_stem = f"{split}_{record_index:06d}"
        output_image = output_root / split_dir / "images" / (
            short_stem + source_image.suffix.lower()
        )
        output_label = output_root / split_dir / "labels" / f"{short_stem}.txt"
        kept = remap_label(source_label, output_label, source_classes, class_map)
        if kept == 0:
            continue
        link_or_copy(source_image, output_image)
        for line in output_label.read_text(encoding="utf-8").splitlines():
            target_class = TARGET_CLASSES[int(line.split()[0])]
            object_counts[target_class] += 1
        records.append({
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": split,
            "source_type": "roboflow_export_vehicle_filtered",
            "annotation_provenance": "stwi_vehicle_class_remap",
            "source_image": record["image"],
            "source_label": record["label"],
            "object_count": kept,
            "sha256": sha256_file(output_image),
        })
        split_counts[split] += 1

    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{source_manifest['dataset_version']}_stwi_vehicles",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "derived_from_roboflow_export",
        "source_dataset": str(source_root),
        "source_manifest_sha256": sha256_file(source_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": [
            name for name, mapped in class_map.items() if mapped not in TARGET_CLASSES
        ],
        "split_policy": "Roboflow split preserved; non-vehicle-only images omitted",
        "split_counts": dict(split_counts),
        "object_counts": dict(object_counts),
        "privacy_status": source_manifest["privacy_status"],
        "privacy_review": source_manifest["privacy_review"],
        "records": records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = build_vehicle_dataset(args.source, args.output)
    print(json.dumps({
        "dataset": str(args.output),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
