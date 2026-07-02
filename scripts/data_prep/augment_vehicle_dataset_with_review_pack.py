"""Augment an STWI vehicle dataset with rows selected from an error review pack."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.data_prep.augment_vehicle_dataset_with_yolo_sources import (
        TARGET_CLASSES,
        copy_base_dataset,
        link_or_copy,
        write_dataset_yaml,
    )
    from scripts.data_prep.prepare_roboflow_yolo_dataset import (
        STWI_CLASS_MAP,
        read_roboflow_yaml,
        sha256_file,
    )
except ModuleNotFoundError:
    from augment_vehicle_dataset_with_yolo_sources import (
        TARGET_CLASSES,
        copy_base_dataset,
        link_or_copy,
        write_dataset_yaml,
    )
    from prepare_roboflow_yolo_dataset import (
        STWI_CLASS_MAP,
        read_roboflow_yaml,
        sha256_file,
    )


def remap_source_label(label_path: Path, source_classes: list[str]) -> list[str]:
    target_index = {name: index for index, name in enumerate(TARGET_CLASSES)}
    output_lines: list[str] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"expected YOLO xywh label: {label_path}:{line_number}")
        source_class_id = int(fields[0])
        if not 0 <= source_class_id < len(source_classes):
            raise ValueError(f"bad class id: {label_path}:{line_number}")
        target_class = STWI_CLASS_MAP.get(source_classes[source_class_id])
        if target_class not in target_index:
            continue
        output_lines.append(" ".join([str(target_index[target_class]), *fields[1:]]))
    return output_lines


def selected_review_rows(review_csv: Path, statuses: set[str]) -> list[dict[str, str]]:
    with review_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selected = [
        row for row in rows
        if row.get("review_status", "").strip().lower() in statuses
    ]
    if not selected:
        raise ValueError(
            "review pack has no rows matching statuses: "
            + ", ".join(sorted(statuses))
        )
    return selected


def safe_stem(value: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else "_"
        for character in value
    ).strip("_") or "review_pack"


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for line in (root / record["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def augment_with_review_pack(
    *,
    base_root: Path,
    source_root: Path,
    review_pack_root: Path,
    output_root: Path,
    include_statuses: list[str],
    privacy_status: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    base_manifest, seen_hashes = copy_base_dataset(base_root, output_root)
    write_dataset_yaml(output_root)
    source_yaml = read_roboflow_yaml(source_root / "data.yaml")
    source_classes = [str(name).lower().strip() for name in source_yaml["names"]]
    statuses = {status.strip().lower() for status in include_statuses}
    rows = selected_review_rows(review_pack_root / "review_queue.csv", statuses)

    new_records: list[dict[str, Any]] = []
    skipped_duplicates = 0
    skipped_without_vehicle = 0
    record_prefix = safe_stem(review_pack_root.name)
    for index, row in enumerate(rows):
        image_path = source_root / row["source_image"]
        label_path = source_root / row["source_label"]
        if not image_path.is_file() or not label_path.is_file():
            raise ValueError(f"missing review source pair: {row['source_image']}")
        image_hash = sha256_file(image_path)
        if image_hash in seen_hashes:
            skipped_duplicates += 1
            continue
        output_lines = remap_source_label(label_path, source_classes)
        if not output_lines:
            skipped_without_vehicle += 1
            continue
        stem = f"review_src_{record_prefix}_{index:06d}"
        output_image = output_root / "train" / "images" / (
            stem + image_path.suffix.lower()
        )
        output_label = output_root / "train" / "labels" / f"{stem}.txt"
        link_or_copy(image_path, output_image)
        output_label.parent.mkdir(parents=True, exist_ok=True)
        output_label.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        new_records.append({
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": "train",
            "source_type": "review_pack_vehicle_supplement",
            "source_dataset": str(source_root),
            "source_image": row["source_image"],
            "source_label": row["source_label"],
            "review_pack": str(review_pack_root),
            "review_status": row.get("review_status", ""),
            "annotation_provenance": "source_yolo_label_selected_by_error_review",
            "object_count": len(output_lines),
            "sha256": sha256_file(output_image),
        })
        seen_hashes.add(image_hash)

    all_records = [*base_manifest["records"], *new_records]
    split_counts: Counter[str] = Counter(record["split"] for record in all_records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{base_manifest['dataset_version']}_review_pack_aug",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "derived_vehicle_dataset_with_error_review_supplement",
        "base_dataset": str(base_root),
        "base_manifest_sha256": sha256_file(base_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": sorted(
            name for name in source_classes
            if STWI_CLASS_MAP.get(name) not in TARGET_CLASSES
        ),
        "split_policy": "base val/test preserved; review pack rows added to train only",
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
            "review_pack": str(review_pack_root),
            "include_statuses": sorted(statuses),
            "source_rows": len(rows),
            "new_records": len(new_records),
            "skipped_duplicates": skipped_duplicates,
            "skipped_without_vehicle": skipped_without_vehicle,
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
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--review-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-status",
        action="append",
        default=None,
        help="Review status to include. Repeat for multiple statuses.",
    )
    parser.add_argument(
        "--privacy-status",
        choices=["needs_review", "visual_spot_reviewed_agent"],
        default="needs_review",
    )
    parser.add_argument("--reviewer", default="pending")
    parser.add_argument("--notes", default="pending privacy review")
    args = parser.parse_args()
    manifest = augment_with_review_pack(
        base_root=args.base,
        source_root=args.source,
        review_pack_root=args.review_pack,
        output_root=args.output,
        include_statuses=args.include_status or ["accepted"],
        privacy_status=args.privacy_status,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "supplement": manifest["supplement"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
