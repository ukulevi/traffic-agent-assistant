"""Fail-closed validation for a generated STWI YOLO dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from PIL import Image


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dataset(
    root: Path, require_privacy_review: bool = True
) -> dict[str, int]:
    manifest_path = root / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    classes = manifest["classes"]
    records = manifest["records"]
    errors: list[str] = []
    if (
        require_privacy_review
        and manifest.get("privacy_status") != "visual_spot_reviewed_agent"
    ):
        errors.append("privacy review has not been finalized")
    hashes_by_split: dict[str, set[str]] = {
        "train": set(), "val": set(), "test": set()
    }
    counts: Counter[str] = Counter()

    for record in records:
        image_path = root / record["image"]
        label_path = root / record["label"]
        split = record["split"]
        if not image_path.is_file() or not label_path.is_file():
            errors.append(f"missing pair: {record['image']}")
            continue
        try:
            with Image.open(image_path) as image:
                image.verify()
        except OSError:
            errors.append(f"invalid image: {record['image']}")
        image_hash = digest(image_path)
        if image_hash != record["sha256"]:
            errors.append(f"hash mismatch: {record['image']}")
        hashes_by_split[split].add(image_hash)
        counts[f"images_{split}"] += 1
        for line_number, line in enumerate(
            label_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            fields = line.split()
            if len(fields) != 5:
                errors.append(f"bad label fields: {label_path}:{line_number}")
                continue
            try:
                class_id = int(fields[0])
                coordinates = [float(value) for value in fields[1:]]
            except ValueError:
                errors.append(f"bad label value: {label_path}:{line_number}")
                continue
            if not 0 <= class_id < len(classes):
                errors.append(f"bad class: {label_path}:{line_number}")
                continue
            if not all(0 < value <= 1 for value in coordinates[2:]) or not all(
                0 <= value <= 1 for value in coordinates[:2]
            ):
                errors.append(f"bad box: {label_path}:{line_number}")
            counts[classes[class_id]] += 1

    split_names = list(hashes_by_split)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1:]:
            overlap = hashes_by_split[left] & hashes_by_split[right]
            if overlap:
                errors.append(f"{len(overlap)} duplicate images: {left}/{right}")
    for split in split_names:
        if not hashes_by_split[split]:
            errors.append(f"empty split: {split}")
    if errors:
        raise ValueError("dataset validation failed:\n- " + "\n- ".join(errors))
    return dict(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--allow-pending-review", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate_dataset(
        args.dataset,
        require_privacy_review=not args.allow_pending_review,
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
