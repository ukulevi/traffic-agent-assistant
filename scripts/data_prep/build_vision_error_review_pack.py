"""Build a review pack for detector misses on a YOLO dataset."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

try:
    from scripts.data_prep.prepare_roboflow_yolo_dataset import IMAGE_EXTENSIONS, read_roboflow_yaml
except ModuleNotFoundError:
    from prepare_roboflow_yolo_dataset import IMAGE_EXTENSIONS, read_roboflow_yaml


SPLIT_DIRS = {"train": "train", "val": "valid", "test": "test"}


@dataclass(frozen=True)
class Box:
    class_name: str
    xyxy: tuple[float, float, float, float]
    confidence: float | None = None


def read_source_class_names(source_root: Path) -> list[str]:
    data_yaml = source_root / "data.yaml"
    if data_yaml.is_file():
        return [
            str(name).lower().strip()
            for name in read_roboflow_yaml(data_yaml)["names"]
        ]
    manifest_path = source_root / "dataset_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        classes = manifest.get("classes")
        if isinstance(classes, list) and classes:
            return [str(name).lower().strip() for name in classes]
    dataset_yaml = source_root / "dataset.yaml"
    if dataset_yaml.is_file():
        names: dict[int, str] = {}
        in_names = False
        for raw_line in dataset_yaml.read_text(encoding="utf-8").splitlines():
            if raw_line.strip() == "names:":
                in_names = True
                continue
            if not in_names:
                continue
            if raw_line.startswith(" ") and ":" in raw_line:
                key, _, value = raw_line.strip().partition(":")
                names[int(key)] = value.strip()
                continue
            if raw_line.strip():
                break
        if names:
            return [names[index].lower().strip() for index in sorted(names)]
    raise ValueError(f"could not read class names from {source_root}")


def yolo_xywh_to_xyxy(
    x_center: float,
    y_center: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    x1 = (x_center - width / 2) * image_width
    y1 = (y_center - height / 2) * image_height
    x2 = (x_center + width / 2) * image_width
    y2 = (y_center + height / 2) * image_height
    return (
        max(0.0, x1),
        max(0.0, y1),
        min(float(image_width), x2),
        min(float(image_height), y2),
    )


def box_iou(left: Box, right: Box) -> float:
    lx1, ly1, lx2, ly2 = left.xyxy
    rx1, ry1, rx2, ry2 = right.xyxy
    ix1 = max(lx1, rx1)
    iy1 = max(ly1, ry1)
    ix2 = min(lx2, rx2)
    iy2 = min(ly2, ry2)
    inter_width = max(0.0, ix2 - ix1)
    inter_height = max(0.0, iy2 - iy1)
    intersection = inter_width * inter_height
    left_area = max(0.0, lx2 - lx1) * max(0.0, ly2 - ly1)
    right_area = max(0.0, rx2 - rx1) * max(0.0, ry2 - ry1)
    union = left_area + right_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def load_target_label_boxes(
    label_path: Path,
    source_classes: list[str],
    target_class: str,
    image_size: tuple[int, int],
) -> list[Box]:
    image_width, image_height = image_size
    boxes: list[Box] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"expected YOLO xywh label: {label_path}:{line_number}")
        class_id = int(fields[0])
        if not 0 <= class_id < len(source_classes):
            raise ValueError(f"bad class id: {label_path}:{line_number}")
        class_name = source_classes[class_id]
        if class_name != target_class:
            continue
        coordinates = [float(value) for value in fields[1:]]
        boxes.append(Box(
            class_name=class_name,
            xyxy=yolo_xywh_to_xyxy(*coordinates, image_width, image_height),
        ))
    return boxes


def unmatched_boxes(
    target_boxes: Iterable[Box],
    predicted_boxes: Iterable[Box],
    iou_threshold: float,
) -> list[Box]:
    predictions = list(predicted_boxes)
    misses: list[Box] = []
    for target_box in target_boxes:
        best_iou = max(
            (box_iou(target_box, prediction) for prediction in predictions),
            default=0.0,
        )
        if best_iou < iou_threshold:
            misses.append(target_box)
    return misses


def unmatched_predictions(
    predicted_boxes: Iterable[Box],
    target_boxes: Iterable[Box],
    iou_threshold: float,
) -> list[Box]:
    targets = list(target_boxes)
    false_positives: list[Box] = []
    for predicted_box in predicted_boxes:
        best_iou = max(
            (box_iou(predicted_box, target_box) for target_box in targets),
            default=0.0,
        )
        if best_iou < iou_threshold:
            false_positives.append(predicted_box)
    return false_positives


def iter_source_images(source_root: Path, splits: Iterable[str]) -> Iterable[tuple[str, Path, Path]]:
    for split in splits:
        image_dir = source_root / SPLIT_DIRS[split] / "images"
        label_dir = source_root / SPLIT_DIRS[split] / "labels"
        if not image_dir.is_dir():
            continue
        for image_path in sorted(image_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label_path = label_dir / f"{image_path.stem}.txt"
            if label_path.is_file():
                yield split, image_path, label_path


def draw_preview(
    image_path: Path,
    output_path: Path,
    target_boxes: list[Box],
    predicted_boxes: list[Box],
    misses: list[Box],
) -> None:
    with Image.open(image_path) as image:
        preview = image.convert("RGB")
    draw = ImageDraw.Draw(preview)
    for box in target_boxes:
        draw.rectangle(box.xyxy, outline=(0, 170, 0), width=3)
    for box in predicted_boxes:
        draw.rectangle(box.xyxy, outline=(0, 110, 255), width=2)
    for box in misses:
        draw.rectangle(box.xyxy, outline=(220, 40, 40), width=4)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output_path)


def predict_target_boxes(
    *,
    model: Any,
    image_path: Path,
    target_class: str,
    confidence: float,
    image_size: int,
    device: str,
) -> list[Box]:
    results = model.predict(
        source=str(image_path),
        imgsz=image_size,
        conf=confidence,
        device=device,
        verbose=False,
    )
    predicted: list[Box] = []
    names = results[0].names
    for result in results:
        for raw_box in result.boxes:
            class_id = int(raw_box.cls[0].item())
            class_name = str(names[class_id]).lower().strip()
            if class_name != target_class:
                continue
            x1, y1, x2, y2 = [float(value) for value in raw_box.xyxy[0].tolist()]
            predicted.append(Box(
                class_name=class_name,
                xyxy=(x1, y1, x2, y2),
                confidence=float(raw_box.conf[0].item()),
            ))
    return predicted


def build_review_pack(
    *,
    source_root: Path,
    output_root: Path,
    model_path: Path,
    target_class: str,
    splits: list[str],
    max_images: int,
    confidence: float,
    iou_threshold: float,
    image_size: int,
    device: str,
    reviewer: str,
    notes: str,
    review_mode: str,
) -> dict[str, Any]:
    ultralytics_config_dir = Path("data/derived/private/ultralytics").resolve()
    ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ultralytics_config_dir))
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("WINDIR", os.environ.get("SystemRoot", "C:\\Windows"))

    from ultralytics import YOLO

    source_classes = read_source_class_names(source_root)
    if target_class not in source_classes:
        raise ValueError(f"target class {target_class!r} is not in source data.yaml")

    if output_root.exists():
        shutil.rmtree(output_root)
    (output_root / "previews").mkdir(parents=True)
    model = YOLO(str(model_path))
    review_rows: list[dict[str, Any]] = []
    scanned_images = 0

    for split, image_path, label_path in iter_source_images(source_root, splits):
        if len(review_rows) >= max_images:
            break
        scanned_images += 1
        with Image.open(image_path) as image:
            image_size_px = image.size
        target_boxes = load_target_label_boxes(
            label_path,
            source_classes,
            target_class,
            image_size_px,
        )
        if not target_boxes:
            continue
        predicted_boxes = predict_target_boxes(
            model=model,
            image_path=image_path,
            target_class=target_class,
            confidence=confidence,
            image_size=image_size,
            device=device,
        )
        if review_mode == "false_negative":
            review_boxes = unmatched_boxes(target_boxes, predicted_boxes, iou_threshold)
        elif review_mode == "false_positive":
            review_boxes = unmatched_predictions(
                predicted_boxes,
                target_boxes,
                iou_threshold,
            )
        else:
            raise ValueError(f"unsupported review mode: {review_mode}")
        if not review_boxes:
            continue
        preview_name = f"{len(review_rows):04d}_{split}_{image_path.stem}.jpg"
        preview_path = output_root / "previews" / preview_name
        draw_preview(image_path, preview_path, target_boxes, predicted_boxes, review_boxes)
        review_rows.append({
            "review_status": "pending",
            "split": split,
            "source_image": image_path.relative_to(source_root).as_posix(),
            "source_label": label_path.relative_to(source_root).as_posix(),
            "preview": preview_path.relative_to(output_root).as_posix(),
            "target_class": target_class,
            "target_boxes": len(target_boxes),
            "predicted_boxes": len(predicted_boxes),
            "missed_boxes": len(review_boxes) if review_mode == "false_negative" else 0,
            "false_positive_boxes": (
                len(review_boxes) if review_mode == "false_positive" else 0
            ),
            "review_note": "",
        })

    review_csv = output_root / "review_queue.csv"
    with review_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "review_status",
                "split",
                "source_image",
                "source_label",
                "preview",
                "target_class",
                "target_boxes",
                "predicted_boxes",
                "missed_boxes",
                "false_positive_boxes",
                "review_note",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    manifest = {
        "schema_version": "1.0",
        "review_pack_version": output_root.name,
        "task": "vision_error_review",
        "source_dataset": str(source_root),
        "model_path": str(model_path),
        "target_class": target_class,
        "review_mode": review_mode,
        "splits": splits,
        "confidence": confidence,
        "iou_threshold": iou_threshold,
        "image_size": image_size,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer": reviewer,
        "notes": notes,
        "scanned_images": scanned_images,
        "review_images": len(review_rows),
        "review_csv": review_csv.relative_to(output_root).as_posix(),
    }
    (output_root / "review_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--target-class", default="motorcycle")
    parser.add_argument(
        "--review-mode",
        choices=["false_negative", "false_positive"],
        default="false_negative",
    )
    parser.add_argument(
        "--split",
        choices=["train", "val", "test"],
        action="append",
        default=None,
    )
    parser.add_argument("--max-images", type=int, default=80)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--reviewer", default="pending")
    parser.add_argument("--notes", default="pending human review")
    args = parser.parse_args()

    manifest = build_review_pack(
        source_root=args.source,
        output_root=args.output,
        model_path=args.model,
        target_class=args.target_class,
        splits=args.split or ["train", "val", "test"],
        max_images=args.max_images,
        confidence=args.conf,
        iou_threshold=args.iou_threshold,
        image_size=args.imgsz,
        device=args.device,
        reviewer=args.reviewer,
        notes=args.notes,
        review_mode=args.review_mode,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
