"""Finalize accepted motorcycle relabel candidates after visual review."""

from __future__ import annotations

import argparse
import csv
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


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def write_data_yaml(root: Path) -> None:
    lines = [
        f"path: {root.resolve().as_posix()}",
        "train: train/images",
        "val: train/images",
        "test: train/images",
        "names:",
        "  0: motorcycle",
    ]
    (root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_review_statuses(review_queue: Path) -> dict[str, str]:
    with review_queue.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            row["image"]: row["review_status"].strip().lower()
            for row in reader
            if row.get("image") and row.get("review_status")
        }


def finalize_review(
    *,
    relabel_root: Path,
    output_root: Path,
    reviewer: str,
    notes: str,
    accepted_status: str = "accepted",
) -> dict[str, Any]:
    manifest = json.loads(
        (relabel_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    review_queue = relabel_root / manifest["relabel_policy"]["review_queue"]
    statuses = read_review_statuses(review_queue)
    accepted = {
        image for image, status in statuses.items()
        if status == accepted_status
    }
    if not accepted:
        raise ValueError(f"no rows marked {accepted_status!r} in {review_queue}")

    output_root.mkdir(parents=True, exist_ok=True)
    write_data_yaml(output_root)
    records: list[dict[str, Any]] = []
    object_counts: Counter[str] = Counter()
    for index, record in enumerate(manifest["records"]):
        if record["image"] not in accepted:
            continue
        source_image = relabel_root / record["image"]
        source_label = relabel_root / record["label"]
        suffix = source_image.suffix.lower()
        stem = f"helmet_reviewed_{index:06d}"
        output_image = output_root / "train" / "images" / f"{stem}{suffix}"
        output_label = output_root / "train" / "labels" / f"{stem}.txt"
        link_or_copy(source_image, output_image)
        link_or_copy(source_label, output_label)
        object_count = sum(
            1 for line in output_label.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        object_counts["motorcycle"] += object_count
        finalized_record = {
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": "train",
            "source_type": "helmet_dataset_motorcycle_relabel_reviewed",
            "source_dataset": str(relabel_root),
            "source_image": record["source_image"],
            "source_split": record["source_split"],
            "annotation_provenance": record["annotation_provenance"],
            "review_status": accepted_status,
            "reviewer": reviewer,
            "object_count": object_count,
            "sha256": sha256_file(output_image),
        }
        records.append(finalized_record)

    finalized_manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{manifest['dataset_version']}_reviewed",
        "task": "motorcycle_object_detection_reviewed_supplement",
        "format": "YOLO normalized xywh",
        "source": "helmet_dataset_assisted_motorcycle_relabel_reviewed",
        "source_dataset": str(relabel_root),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": ["motorcycle"],
        "split_policy": "accepted relabel candidates are train-only supplements",
        "split_counts": {"train": len(records)},
        "object_counts": dict(object_counts),
        "privacy_status": "visual_spot_reviewed_agent",
        "privacy_review": {"reviewer": reviewer, "notes": notes},
        "records": records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(finalized_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return finalized_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relabel-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--accepted-status", default="accepted")
    args = parser.parse_args()
    manifest = finalize_review(
        relabel_root=args.relabel_root,
        output_root=args.output,
        reviewer=args.reviewer,
        notes=args.notes,
        accepted_status=args.accepted_status,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
