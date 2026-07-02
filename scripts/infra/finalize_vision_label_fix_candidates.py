"""Finalize accepted label-fix candidates into an STWI vehicle dataset."""

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
    from scripts.data_prep.prepare_roboflow_yolo_dataset import sha256_file
except ModuleNotFoundError:
    from augment_vehicle_dataset_with_yolo_sources import (
        TARGET_CLASSES,
        copy_base_dataset,
        link_or_copy,
        write_dataset_yaml,
    )
    from prepare_roboflow_yolo_dataset import sha256_file


def read_review_rows(review_csv: Path, statuses: set[str]) -> list[dict[str, str]]:
    with review_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    selected = [
        row for row in rows
        if row.get("review_status", "").strip().lower() in statuses
    ]
    if not selected:
        raise ValueError(
            "label-fix candidate review has no rows matching statuses: "
            + ", ".join(sorted(statuses))
        )
    return selected


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for line in (root / record["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def update_candidate_review_status(
    *,
    candidate_root: Path,
    status: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    review_csv = candidate_root / "review" / "review_queue.csv"
    with review_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if "review_status" not in fieldnames:
        raise ValueError(f"missing review_status column: {review_csv}")
    if "review_note" not in fieldnames:
        fieldnames.append("review_note")
    for row in rows:
        row["review_status"] = status
        row["review_note"] = notes
    with review_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    manifest_path = candidate_root / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in manifest["records"]:
        record["review_status"] = status
        record["reviewer"] = reviewer
        record["review_note"] = notes
    manifest["privacy_review"]["reviewer"] = reviewer
    manifest["privacy_review"]["reviewed_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["privacy_review"]["notes"] = notes
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def finalize_label_fix_candidates(
    *,
    base_root: Path,
    candidate_root: Path,
    output_root: Path,
    include_statuses: list[str],
    privacy_status: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    base_manifest, seen_hashes = copy_base_dataset(base_root, output_root)
    write_dataset_yaml(output_root)
    candidate_manifest = json.loads(
        (candidate_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if candidate_manifest.get("classes") != TARGET_CLASSES:
        raise ValueError("label-fix candidate classes do not match STWI target classes")
    statuses = {status.strip().lower() for status in include_statuses}
    rows = read_review_rows(candidate_root / "review" / "review_queue.csv", statuses)

    new_records: list[dict[str, Any]] = []
    skipped_duplicates = 0
    for index, row in enumerate(rows):
        image_path = candidate_root / row["image"]
        label_path = candidate_root / row["label"]
        if not image_path.is_file() or not label_path.is_file():
            raise ValueError(f"missing candidate pair: {row.get('image')}")
        image_hash = sha256_file(image_path)
        if image_hash in seen_hashes:
            skipped_duplicates += 1
            continue
        stem = f"label_fix_candidate_{index:06d}"
        output_image = output_root / "train" / "images" / (
            stem + image_path.suffix.lower()
        )
        output_label = output_root / "train" / "labels" / f"{stem}.txt"
        link_or_copy(image_path, output_image)
        output_label.parent.mkdir(parents=True, exist_ok=True)
        output_label.write_text(label_path.read_text(encoding="utf-8"), encoding="utf-8")
        new_records.append({
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": "train",
            "source_type": "accepted_label_fix_candidate",
            "source_dataset": str(candidate_root),
            "source_image": row.get("image", ""),
            "source_label": row.get("label", ""),
            "review_status": row.get("review_status", ""),
            "annotation_provenance": "human_accepted_label_fix_candidate",
            "object_count": sum(
                1 for line in output_label.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ),
            "sha256": sha256_file(output_image),
        })
        seen_hashes.add(image_hash)

    all_records = [*base_manifest["records"], *new_records]
    split_counts: Counter[str] = Counter(record["split"] for record in all_records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{base_manifest['dataset_version']}_label_fix_round1",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "derived_vehicle_dataset_with_human_accepted_label_fix_candidates",
        "base_dataset": str(base_root),
        "base_manifest_sha256": sha256_file(base_root / "dataset_manifest.json"),
        "candidate_dataset": str(candidate_root),
        "candidate_manifest_sha256": sha256_file(candidate_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": [],
        "split_policy": "base val/test preserved; accepted label-fix candidates added to train only",
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
            "candidate_dataset": str(candidate_root),
            "include_statuses": sorted(statuses),
            "source_rows": len(rows),
            "new_records": len(new_records),
            "skipped_duplicates": skipped_duplicates,
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
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-status", action="append", default=None)
    parser.add_argument(
        "--mark-all-accepted",
        action="store_true",
        help="Set all candidate review rows to accepted before finalizing.",
    )
    parser.add_argument(
        "--privacy-status",
        choices=["needs_review", "visual_spot_reviewed_agent"],
        default="needs_review",
    )
    parser.add_argument("--reviewer", default="pending")
    parser.add_argument("--notes", default="pending privacy review")
    args = parser.parse_args()
    if args.mark_all_accepted:
        update_candidate_review_status(
            candidate_root=args.candidate,
            status="accepted",
            reviewer=args.reviewer,
            notes=args.notes,
        )
    manifest = finalize_label_fix_candidates(
        base_root=args.base,
        candidate_root=args.candidate,
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
