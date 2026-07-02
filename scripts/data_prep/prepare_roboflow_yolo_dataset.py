"""Prepare a downloaded Roboflow YOLO export for local STWI training."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_DIRS = {"train": "train", "val": "valid", "test": "test"}
STWI_CLASS_MAP = {
    "bicycle": None,
    "bus": "bus",
    "car": "car",
    "motorbike": "motorcycle",
    "motorcycle": "motorcycle",
    "pedestrian": None,
    "traffic_light": None,
    "truck": "truck",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value


def read_roboflow_yaml(path: Path) -> dict[str, Any]:
    """Read the simple Roboflow data.yaml shape without adding PyYAML."""

    payload: dict[str, Any] = {}
    current_section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith(" ") and current_section:
            key, _, value = raw_line.strip().partition(":")
            payload.setdefault(current_section, {})[key] = _parse_scalar(value)
            continue
        key, _, value = raw_line.partition(":")
        key = key.strip()
        if value.strip():
            payload[key] = _parse_scalar(value)
            current_section = None
        else:
            payload[key] = {}
            current_section = key
    names = payload.get("names")
    if not isinstance(names, list) or not names:
        raise ValueError("data.yaml must declare a non-empty names list")
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("all class names in data.yaml must be non-empty strings")
    return payload


def write_ultralytics_dataset_yaml(root: Path, names: list[str]) -> None:
    lines = [
        f"path: {root.resolve().as_posix()}",
        "train: train/images",
        "val: valid/images",
        "test: test/images",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(names))
    (root / "dataset.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def label_for_image(image: Path, split_dir: Path) -> Path:
    return split_dir / "labels" / f"{image.stem}.txt"


def iter_images(root: Path, split_name: str) -> list[Path]:
    image_dir = root / SPLIT_DIRS[split_name] / "images"
    if not image_dir.is_dir():
        raise ValueError(f"missing image directory: {image_dir}")
    return sorted(
        path for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def bbox_from_polygon(class_id: int, coordinates: list[float]) -> str:
    if len(coordinates) < 6 or len(coordinates) % 2:
        raise ValueError("polygon labels must contain x/y coordinate pairs")
    xs = coordinates[0::2]
    ys = coordinates[1::2]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    width = right - left
    height = bottom - top
    return (
        f"{class_id} {center_x:.6f} {center_y:.6f} "
        f"{width:.6f} {height:.6f}"
    )


def validate_label_file(label_path: Path, class_count: int) -> tuple[int, int]:
    object_count = 0
    converted_count = 0
    output_lines: list[str] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split()
        try:
            class_id = int(fields[0])
            coordinates = [float(value) for value in fields[1:]]
        except ValueError as exc:
            raise ValueError(f"bad label value: {label_path}:{line_number}") from exc
        if not 0 <= class_id < class_count:
            raise ValueError(f"bad class id: {label_path}:{line_number}")
        if len(fields) == 5:
            if not all(0 <= value <= 1 for value in coordinates[:2]):
                raise ValueError(f"bad box center: {label_path}:{line_number}")
            if not all(0 < value <= 1 for value in coordinates[2:]):
                raise ValueError(f"bad box size: {label_path}:{line_number}")
            output_lines.append(line)
        else:
            if not all(0 <= value <= 1 for value in coordinates):
                raise ValueError(f"bad polygon coordinate: {label_path}:{line_number}")
            output_lines.append(bbox_from_polygon(class_id, coordinates))
            converted_count += 1
        object_count += 1
    if converted_count:
        label_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return object_count, converted_count


def build_records(
    root: Path, class_count: int
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    records: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    converted_total = 0
    for split_name in ("train", "val", "test"):
        split_dir = root / SPLIT_DIRS[split_name]
        for image_path in iter_images(root, split_name):
            label_path = label_for_image(image_path, split_dir)
            if not label_path.is_file():
                raise ValueError(f"missing label for image: {image_path}")
            object_count, converted_count = validate_label_file(label_path, class_count)
            converted_total += converted_count
            records.append({
                "image": image_path.relative_to(root).as_posix(),
                "label": label_path.relative_to(root).as_posix(),
                "split": split_name,
                "source_type": "roboflow_export",
                "annotation_provenance": "roboflow_yolo_export",
                "object_count": object_count,
                "sha256": sha256_file(image_path),
            })
            split_counts[split_name] += 1
    return records, dict(split_counts), converted_total


def build_manifest(
    root: Path,
    *,
    dataset_version: str,
    privacy_status: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    source = read_roboflow_yaml(root / "data.yaml")
    names = list(source["names"])
    write_ultralytics_dataset_yaml(root, names)
    records, split_counts, converted_labels = build_records(root, len(names))
    roboflow = source.get("roboflow", {})
    class_map = {name: STWI_CLASS_MAP.get(name) for name in names}
    ignored = sorted(name for name, mapped in class_map.items() if mapped is None)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": dataset_version,
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "roboflow_export",
        "source_metadata": roboflow,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": names,
        "stwi_class_map": class_map,
        "ignored_classes": ignored,
        "split_policy": "Roboflow provided train/valid/test split",
        "split_counts": split_counts,
        "label_transform": {
            "segmentation_polygons_to_bbox": True,
            "converted_label_count": converted_labels,
        },
        "privacy_status": privacy_status,
        "privacy_review": {
            "reviewer": reviewer,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "human_approval_required_for_external_release": True,
        },
        "records": records,
    }
    (root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset",
        type=Path,
        help="Roboflow YOLO export root containing data.yaml and train/valid/test.",
    )
    parser.add_argument("--dataset-version", default="roboflow_v001")
    parser.add_argument(
        "--privacy-status",
        choices=["needs_review", "visual_spot_reviewed_agent"],
        default="needs_review",
    )
    parser.add_argument("--reviewer", default="pending")
    parser.add_argument("--notes", default="pending privacy review")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(
        args.dataset,
        dataset_version=args.dataset_version,
        privacy_status=args.privacy_status,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(json.dumps({
        "dataset": str(args.dataset),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "privacy_status": manifest["privacy_status"],
        "ignored_classes": manifest["ignored_classes"],
        "converted_label_count": manifest["label_transform"]["converted_label_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
