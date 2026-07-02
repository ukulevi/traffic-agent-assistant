"""Augment the STWI vehicle dataset with multi-class YOLO vehicle sources."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.data_prep.prepare_roboflow_yolo_dataset import (
        IMAGE_EXTENSIONS,
        STWI_CLASS_MAP,
        read_roboflow_yaml,
        sha256_file,
    )
except ModuleNotFoundError:
    from prepare_roboflow_yolo_dataset import (
        IMAGE_EXTENSIONS,
        STWI_CLASS_MAP,
        read_roboflow_yaml,
        sha256_file,
    )


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


def iter_images(source_root: Path, split: str) -> Iterable[Path]:
    image_dir = source_root / SPLIT_DIRS[split] / "images"
    if not image_dir.is_dir():
        return []
    return sorted(
        path for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def label_for_image(source_root: Path, split: str, image_path: Path) -> Path:
    return source_root / SPLIT_DIRS[split] / "labels" / f"{image_path.stem}.txt"


def copy_base_dataset(base_root: Path, output_root: Path) -> tuple[dict[str, Any], set[str]]:
    base_manifest = json.loads(
        (base_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if base_manifest["classes"] != TARGET_CLASSES:
        raise ValueError("base dataset must use STWI vehicle classes")
    output_root.mkdir(parents=True, exist_ok=True)
    write_dataset_yaml(output_root)
    seen_hashes: set[str] = set()
    for record in base_manifest["records"]:
        source_image = base_root / record["image"]
        source_label = base_root / record["label"]
        target_image = output_root / record["image"]
        target_label = output_root / record["label"]
        link_or_copy(source_image, target_image)
        link_or_copy(source_label, target_label)
        seen_hashes.add(record["sha256"])
    return base_manifest, seen_hashes


def remap_label_lines(
    label_path: Path,
    source_classes: list[str],
    class_map: dict[str, str | None],
) -> list[str]:
    target_index = {name: index for index, name in enumerate(TARGET_CLASSES)}
    output_lines: list[str] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split()
        try:
            source_class_id = int(fields[0])
        except ValueError as exc:
            raise ValueError(f"bad class id: {label_path}:{line_number}") from exc
        if not 0 <= source_class_id < len(source_classes):
            raise ValueError(f"bad class id: {label_path}:{line_number}")
        if len(fields) != 5:
            raise ValueError(f"expected YOLO xywh label: {label_path}:{line_number}")
        target_class = class_map.get(source_classes[source_class_id])
        if target_class not in target_index:
            continue
        output_lines.append(" ".join([str(target_index[target_class]), *fields[1:]]))
    return output_lines


def add_yolo_source(
    *,
    source_root: Path,
    output_root: Path,
    seen_hashes: set[str],
    start_index: int,
    source_splits: list[str],
    require_classes: set[str],
    max_records: int | None,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    source_yaml = read_roboflow_yaml(source_root / "data.yaml")
    source_classes = [str(name).lower().strip() for name in source_yaml["names"]]
    class_map = {name: STWI_CLASS_MAP.get(name) for name in source_classes}
    records: list[dict[str, Any]] = []
    index = start_index
    skipped_duplicates = 0
    skipped_without_vehicle = 0
    skipped_without_required_class = 0

    for source_split in source_splits:
        for image_path in iter_images(source_root, source_split):
            if max_records is not None and len(records) >= max_records:
                break
            label_path = label_for_image(source_root, source_split, image_path)
            if not label_path.is_file():
                continue
            image_hash = sha256_file(image_path)
            if image_hash in seen_hashes:
                skipped_duplicates += 1
                continue
            output_lines = remap_label_lines(label_path, source_classes, class_map)
            if not output_lines:
                skipped_without_vehicle += 1
                continue
            target_classes_in_image = {
                TARGET_CLASSES[int(line.split()[0])] for line in output_lines
            }
            if require_classes and not require_classes.issubset(target_classes_in_image):
                skipped_without_required_class += 1
                continue
            stem = f"vehicle_src_{index:06d}"
            output_image = output_root / "train" / "images" / (
                stem + image_path.suffix.lower()
            )
            output_label = output_root / "train" / "labels" / f"{stem}.txt"
            link_or_copy(image_path, output_image)
            output_label.parent.mkdir(parents=True, exist_ok=True)
            output_label.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
            records.append({
                "image": output_image.relative_to(output_root).as_posix(),
                "label": output_label.relative_to(output_root).as_posix(),
                "split": "train",
                "source_type": "yolo_vehicle_annotated_supplement",
                "source_dataset": str(source_root),
                "source_image": image_path.relative_to(source_root).as_posix(),
                "source_label": label_path.relative_to(source_root).as_posix(),
                "source_split": source_split,
                "annotation_provenance": "source_yolo_vehicle_class_remap",
                "object_count": len(output_lines),
                "sha256": sha256_file(output_image),
            })
            seen_hashes.add(image_hash)
            index += 1

    summary = {
        "source": str(source_root),
        "source_classes": source_classes,
        "source_splits": source_splits,
        "new_records": len(records),
        "skipped_duplicates": skipped_duplicates,
        "skipped_without_vehicle": skipped_without_vehicle,
        "skipped_without_required_class": skipped_without_required_class,
        "ignored_classes": sorted(
            name for name, target in class_map.items() if target not in TARGET_CLASSES
        ),
    }
    return records, index, summary


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for line in (root / record["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def augment_dataset(
    *,
    base_root: Path,
    output_root: Path,
    yolo_sources: list[Path],
    source_splits: list[str],
    require_classes: list[str],
    max_records_per_source: int | None,
    privacy_status: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    base_manifest, seen_hashes = copy_base_dataset(base_root, output_root)
    new_records: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    next_index = 0
    for source_root in yolo_sources:
        records, next_index, summary = add_yolo_source(
            source_root=source_root,
            output_root=output_root,
            seen_hashes=seen_hashes,
            start_index=next_index,
            source_splits=source_splits,
            require_classes=set(require_classes),
            max_records=max_records_per_source,
        )
        new_records.extend(records)
        source_summaries.append(summary)

    all_records = [*base_manifest["records"], *new_records]
    split_counts: Counter[str] = Counter(record["split"] for record in all_records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{base_manifest['dataset_version']}_vehicle_yolo_aug",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "derived_vehicle_dataset_with_yolo_vehicle_supplements",
        "base_dataset": str(base_root),
        "base_manifest_sha256": sha256_file(base_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": sorted({
            ignored
            for summary in source_summaries
            for ignored in summary["ignored_classes"]
        }),
        "split_policy": "base val/test preserved; YOLO vehicle supplements added to train only",
        "split_counts": dict(split_counts),
        "object_counts": count_objects(output_root, all_records),
        "privacy_status": privacy_status,
        "privacy_review": {
            "reviewer": reviewer,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "human_approval_required_for_external_release": True,
        },
        "supplement": {
            "yolo_sources": source_summaries,
            "new_records": len(new_records),
        },
        "records": all_records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--yolo-source", type=Path, action="append", required=True)
    parser.add_argument(
        "--source-split",
        choices=["train", "val", "test"],
        action="append",
        default=None,
        help="Source split to add as train supplement. Defaults to all splits.",
    )
    parser.add_argument(
        "--require-class",
        choices=TARGET_CLASSES,
        action="append",
        default=[],
        help="Keep only source images whose remapped labels include this class.",
    )
    parser.add_argument("--max-records-per-source", type=int, default=None)
    parser.add_argument(
        "--privacy-status",
        choices=["needs_review", "visual_spot_reviewed_agent"],
        default="needs_review",
    )
    parser.add_argument("--reviewer", default="pending")
    parser.add_argument("--notes", default="pending privacy review")
    args = parser.parse_args()
    manifest = augment_dataset(
        base_root=args.base,
        output_root=args.output,
        yolo_sources=args.yolo_source,
        source_splits=args.source_split or ["train", "val", "test"],
        require_classes=args.require_class,
        max_records_per_source=args.max_records_per_source,
        privacy_status=args.privacy_status,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "supplement": manifest["supplement"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
