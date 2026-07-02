"""Add train-only object-centric crops for weak STWI vehicle classes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from scripts.data_prep.prepare_roboflow_yolo_dataset import sha256_file
except ModuleNotFoundError:
    from prepare_roboflow_yolo_dataset import sha256_file


TARGET_CLASSES = ["bus", "car", "motorcycle", "truck"]


@dataclass(frozen=True)
class LabelBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    def xyxy_pixels(self, image_width: int, image_height: int) -> tuple[float, float, float, float]:
        x_center = self.x_center * image_width
        y_center = self.y_center * image_height
        width = self.width * image_width
        height = self.height * image_height
        return (
            x_center - width / 2,
            y_center - height / 2,
            x_center + width / 2,
            y_center + height / 2,
        )


@dataclass(frozen=True)
class CropSpec:
    class_name: str
    max_box_area: float
    max_crops: int


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


def parse_label_file(label_path: Path) -> list[LabelBox]:
    boxes: list[LabelBox] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"expected YOLO xywh label: {label_path}:{line_number}")
        class_id = int(fields[0])
        if not 0 <= class_id < len(TARGET_CLASSES):
            raise ValueError(f"bad class id: {label_path}:{line_number}")
        boxes.append(LabelBox(class_id, *map(float, fields[1:])))
    return boxes


def parse_crop_spec(value: str) -> CropSpec:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "crop spec must be class:max_box_area:max_crops"
        )
    class_name, max_area_raw, max_crops_raw = parts
    if class_name not in TARGET_CLASSES:
        raise argparse.ArgumentTypeError(f"unsupported class: {class_name}")
    max_box_area = float(max_area_raw)
    max_crops = int(max_crops_raw)
    if max_box_area <= 0 or max_crops < 1:
        raise argparse.ArgumentTypeError("max_box_area and max_crops must be positive")
    return CropSpec(class_name, max_box_area, max_crops)


def copy_base_dataset(base_root: Path, output_root: Path) -> dict[str, Any]:
    base_manifest = json.loads(
        (base_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if base_manifest.get("classes") != TARGET_CLASSES:
        raise ValueError("base dataset must use STWI vehicle classes")
    output_root.mkdir(parents=True, exist_ok=True)
    write_dataset_yaml(output_root)
    for record in base_manifest["records"]:
        link_or_copy(base_root / record["image"], output_root / record["image"])
        link_or_copy(base_root / record["label"], output_root / record["label"])
    return base_manifest


def crop_bounds_for_box(
    box: LabelBox,
    image_width: int,
    image_height: int,
    context_scale: float,
    min_crop_size: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box.xyxy_pixels(image_width, image_height)
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    side = max(box_width, box_height) * context_scale
    side = max(float(min_crop_size), side)
    side = min(side, float(max(image_width, image_height)))
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    crop_x1 = int(round(center_x - side / 2))
    crop_y1 = int(round(center_y - side / 2))
    crop_x2 = int(round(center_x + side / 2))
    crop_y2 = int(round(center_y + side / 2))
    if crop_x1 < 0:
        crop_x2 -= crop_x1
        crop_x1 = 0
    if crop_y1 < 0:
        crop_y2 -= crop_y1
        crop_y1 = 0
    if crop_x2 > image_width:
        crop_x1 -= crop_x2 - image_width
        crop_x2 = image_width
    if crop_y2 > image_height:
        crop_y1 -= crop_y2 - image_height
        crop_y2 = image_height
    crop_x1 = max(0, crop_x1)
    crop_y1 = max(0, crop_y1)
    return crop_x1, crop_y1, crop_x2, crop_y2


def clipped_box_to_yolo(
    box: LabelBox,
    image_width: int,
    image_height: int,
    crop: tuple[int, int, int, int],
    min_visibility: float,
) -> str | None:
    crop_x1, crop_y1, crop_x2, crop_y2 = crop
    x1, y1, x2, y2 = box.xyxy_pixels(image_width, image_height)
    inter_x1 = max(x1, crop_x1)
    inter_y1 = max(y1, crop_y1)
    inter_x2 = min(x2, crop_x2)
    inter_y2 = min(y2, crop_y2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return None
    original_area = max(1.0, (x2 - x1) * (y2 - y1))
    visible_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    if visible_area / original_area < min_visibility:
        return None
    crop_width = crop_x2 - crop_x1
    crop_height = crop_y2 - crop_y1
    out_x1 = inter_x1 - crop_x1
    out_y1 = inter_y1 - crop_y1
    out_x2 = inter_x2 - crop_x1
    out_y2 = inter_y2 - crop_y1
    x_center = ((out_x1 + out_x2) / 2) / crop_width
    y_center = ((out_y1 + out_y2) / 2) / crop_height
    width = (out_x2 - out_x1) / crop_width
    height = (out_y2 - out_y1) / crop_height
    return (
        f"{box.class_id} {x_center:.6f} {y_center:.6f} "
        f"{width:.6f} {height:.6f}"
    )


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for line in (root / record["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def build_crop_candidates(
    base_root: Path,
    records: list[dict[str, Any]],
    specs: list[CropSpec],
) -> list[tuple[float, dict[str, Any], LabelBox, CropSpec]]:
    spec_by_class = {spec.class_name: spec for spec in specs}
    candidates: list[tuple[float, dict[str, Any], LabelBox, CropSpec]] = []
    for record in records:
        if record["split"] != "train":
            continue
        boxes = parse_label_file(base_root / record["label"])
        for box in boxes:
            class_name = TARGET_CLASSES[box.class_id]
            spec = spec_by_class.get(class_name)
            if spec is None or box.area > spec.max_box_area:
                continue
            candidates.append((box.area, record, box, spec))
    candidates.sort(key=lambda item: item[0])
    selected: list[tuple[float, dict[str, Any], LabelBox, CropSpec]] = []
    per_class_count: Counter[str] = Counter()
    for item in candidates:
        spec = item[3]
        if per_class_count[spec.class_name] >= spec.max_crops:
            continue
        selected.append(item)
        per_class_count[spec.class_name] += 1
    return selected


def augment_with_object_crops(
    *,
    base_root: Path,
    output_root: Path,
    specs: list[CropSpec],
    context_scale: float,
    min_crop_size: int,
    min_visibility: float,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    if context_scale <= 1.0:
        raise ValueError("context_scale must be > 1.0")
    if not 0 < min_visibility <= 1:
        raise ValueError("min_visibility must be in (0, 1]")
    base_manifest = copy_base_dataset(base_root, output_root)
    records = [dict(record) for record in base_manifest["records"]]
    selected = build_crop_candidates(base_root, base_manifest["records"], specs)
    crop_counts: Counter[str] = Counter()
    skipped_empty = 0

    for crop_index, (_, record, target_box, spec) in enumerate(selected):
        source_image = base_root / record["image"]
        with Image.open(source_image) as image:
            image = image.convert("RGB")
            crop = crop_bounds_for_box(
                target_box,
                image.width,
                image.height,
                context_scale,
                min_crop_size,
            )
            label_lines: list[str] = []
            for box in parse_label_file(base_root / record["label"]):
                line = clipped_box_to_yolo(
                    box,
                    image.width,
                    image.height,
                    crop,
                    min_visibility,
                )
                if line is not None:
                    label_lines.append(line)
            if not label_lines:
                skipped_empty += 1
                continue
            stem = f"object_crop_{spec.class_name}_{crop_index:06d}"
            output_image = output_root / "train" / "images" / f"{stem}.jpg"
            output_label = output_root / "train" / "labels" / f"{stem}.txt"
            output_image.parent.mkdir(parents=True, exist_ok=True)
            output_label.parent.mkdir(parents=True, exist_ok=True)
            image.crop(crop).save(output_image, quality=95)
            output_label.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
            records.append({
                "image": output_image.relative_to(output_root).as_posix(),
                "label": output_label.relative_to(output_root).as_posix(),
                "split": "train",
                "source_type": "object_crop_training_supplement",
                "source_dataset": str(base_root),
                "source_image": record["image"],
                "source_label": record["label"],
                "annotation_provenance": "train_label_object_crop",
                "crop_target_class": spec.class_name,
                "crop_bounds_xyxy": list(crop),
                "object_count": len(label_lines),
                "sha256": sha256_file(output_image),
            })
            crop_counts[spec.class_name] += 1

    split_counts: Counter[str] = Counter(record["split"] for record in records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{base_manifest['dataset_version']}_object_crop_aug",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "derived_vehicle_dataset_with_train_object_crops",
        "base_dataset": str(base_root),
        "base_manifest_sha256": sha256_file(base_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": base_manifest.get("ignored_classes", []),
        "split_policy": "base val/test preserved; object-centric crops added to train only",
        "split_counts": dict(split_counts),
        "object_counts": count_objects(output_root, records),
        "privacy_status": base_manifest["privacy_status"],
        "privacy_review": {
            **base_manifest["privacy_review"],
            "object_crop_reviewer": reviewer,
            "object_crop_notes": notes,
            "object_crop_created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "object_crop_augmentation": {
            "specs": [spec.__dict__ for spec in specs],
            "context_scale": context_scale,
            "min_crop_size": min_crop_size,
            "min_visibility": min_visibility,
            "selected_candidates": len(selected),
            "created_crops": dict(crop_counts),
            "skipped_empty": skipped_empty,
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
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--class-spec",
        type=parse_crop_spec,
        action="append",
        required=True,
        help="Class crop rule formatted as class:max_box_area:max_crops.",
    )
    parser.add_argument("--context-scale", type=float, default=4.0)
    parser.add_argument("--min-crop-size", type=int, default=160)
    parser.add_argument("--min-visibility", type=float, default=0.35)
    parser.add_argument("--reviewer", default="codex-object-crop-augmentation")
    parser.add_argument("--notes", default="train-only object crop augmentation")
    args = parser.parse_args()
    manifest = augment_with_object_crops(
        base_root=args.base,
        output_root=args.output,
        specs=args.class_spec,
        context_scale=args.context_scale,
        min_crop_size=args.min_crop_size,
        min_visibility=args.min_visibility,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "object_crop_augmentation": manifest["object_crop_augmentation"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
