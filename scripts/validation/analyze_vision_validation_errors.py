"""Analyze YOLO validation errors by class, confusion, and object size."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

try:
    from scripts.data_prep.build_vision_error_review_pack import (
        Box,
        box_iou,
        iter_source_images,
        read_source_class_names,
        yolo_xywh_to_xyxy,
    )
except ModuleNotFoundError:
    from build_vision_error_review_pack import (
        Box,
        box_iou,
        iter_source_images,
        read_source_class_names,
        yolo_xywh_to_xyxy,
    )


AREA_BINS = [
    ("tiny", 0.0, 0.003),
    ("small", 0.003, 0.01),
    ("medium", 0.01, 0.05),
    ("large", 0.05, 1.01),
]


@dataclass(frozen=True)
class LabeledBox(Box):
    normalized_area: float = 0.0


def area_bin(area: float) -> str:
    for name, lower, upper in AREA_BINS:
        if lower <= area < upper:
            return name
    return "large"


def load_label_boxes(
    label_path: Path,
    source_classes: list[str],
    image_size: tuple[int, int],
) -> list[LabeledBox]:
    image_width, image_height = image_size
    boxes: list[LabeledBox] = []
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
        width = float(fields[3])
        height = float(fields[4])
        boxes.append(LabeledBox(
            class_name=source_classes[class_id],
            xyxy=yolo_xywh_to_xyxy(
                float(fields[1]),
                float(fields[2]),
                width,
                height,
                image_width,
                image_height,
            ),
            confidence=None,
            normalized_area=width * height,
        ))
    return boxes


def predict_boxes(
    *,
    model: Any,
    image_path: Path,
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
            x1, y1, x2, y2 = [float(value) for value in raw_box.xyxy[0].tolist()]
            predicted.append(Box(
                class_name=class_name,
                xyxy=(x1, y1, x2, y2),
                confidence=float(raw_box.conf[0].item()),
            ))
    return predicted


def greedy_match(
    targets: list[LabeledBox],
    predictions: list[Box],
    iou_threshold: float,
) -> list[tuple[int, int, float]]:
    candidates: list[tuple[float, int, int]] = []
    for target_index, target in enumerate(targets):
        for prediction_index, prediction in enumerate(predictions):
            iou = box_iou(target, prediction)
            if iou >= iou_threshold:
                candidates.append((iou, target_index, prediction_index))
    candidates.sort(reverse=True)
    used_targets: set[int] = set()
    used_predictions: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for iou, target_index, prediction_index in candidates:
        if target_index in used_targets or prediction_index in used_predictions:
            continue
        used_targets.add(target_index)
        used_predictions.add(prediction_index)
        matches.append((target_index, prediction_index, iou))
    return matches


def analyze_image(
    *,
    targets: list[LabeledBox],
    predictions: list[Box],
    iou_threshold: float,
) -> dict[str, Any]:
    matches = greedy_match(targets, predictions, iou_threshold)
    matched_targets = {target_index for target_index, _, _ in matches}
    matched_predictions = {prediction_index for _, prediction_index, _ in matches}
    true_positive: Counter[str] = Counter()
    false_negative: Counter[str] = Counter()
    false_positive: Counter[str] = Counter()
    fn_area_bins: Counter[str] = Counter()
    confusion: Counter[str] = Counter()
    wrong_class_matches: list[dict[str, Any]] = []

    for target_index, prediction_index, iou in matches:
        target = targets[target_index]
        prediction = predictions[prediction_index]
        if target.class_name == prediction.class_name:
            true_positive[target.class_name] += 1
        else:
            false_negative[target.class_name] += 1
            false_positive[prediction.class_name] += 1
            fn_area_bins[f"{target.class_name}:{area_bin(target.normalized_area)}"] += 1
            key = f"{target.class_name}->{prediction.class_name}"
            confusion[key] += 1
            wrong_class_matches.append({
                "target_class": target.class_name,
                "predicted_class": prediction.class_name,
                "iou": round(iou, 4),
                "confidence": prediction.confidence,
                "target_area": target.normalized_area,
                "area_bin": area_bin(target.normalized_area),
            })

    for target_index, target in enumerate(targets):
        if target_index not in matched_targets:
            false_negative[target.class_name] += 1
            fn_area_bins[f"{target.class_name}:{area_bin(target.normalized_area)}"] += 1
    for prediction_index, prediction in enumerate(predictions):
        if prediction_index not in matched_predictions:
            false_positive[prediction.class_name] += 1

    return {
        "true_positive": dict(true_positive),
        "false_negative": dict(false_negative),
        "false_positive": dict(false_positive),
        "fn_area_bins": dict(fn_area_bins),
        "confusion": dict(confusion),
        "wrong_class_matches": wrong_class_matches,
    }


def merge_counter(target: Counter[str], values: dict[str, int]) -> None:
    for key, value in values.items():
        target[key] += int(value)


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {
        key: counter[key]
        for key in sorted(counter, key=lambda item: (-counter[item], item))
    }


def summarize_error_rates(
    *,
    classes: Iterable[str],
    true_positive: Counter[str],
    false_negative: Counter[str],
    false_positive: Counter[str],
) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for class_name in classes:
        tp = true_positive[class_name]
        fn = false_negative[class_name]
        fp = false_positive[class_name]
        recall_denominator = tp + fn
        precision_denominator = tp + fp
        summary[class_name] = {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "recall_at_conf": tp / recall_denominator if recall_denominator else 0.0,
            "precision_at_conf": (
                tp / precision_denominator if precision_denominator else 0.0
            ),
        }
    return summary


def write_image_rows(output_path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "split",
        "image",
        "label",
        "tp",
        "fn",
        "fp",
        "confusion",
        "fn_area_bins",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "split": row["split"],
                "image": row["image"],
                "label": row["label"],
                "tp": json.dumps(row["true_positive"], sort_keys=True),
                "fn": json.dumps(row["false_negative"], sort_keys=True),
                "fp": json.dumps(row["false_positive"], sort_keys=True),
                "confusion": json.dumps(row["confusion"], sort_keys=True),
                "fn_area_bins": json.dumps(row["fn_area_bins"], sort_keys=True),
            })


def analyze_dataset(
    *,
    source_root: Path,
    model_path: Path,
    output_root: Path,
    splits: list[str],
    confidence: float,
    iou_threshold: float,
    image_size: int,
    device: str,
    max_images: int | None = None,
) -> dict[str, Any]:
    ultralytics_config_dir = Path("data/derived/private/ultralytics").resolve()
    ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ultralytics_config_dir))
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("WINDIR", os.environ.get("SystemRoot", "C:\\Windows"))

    from ultralytics import YOLO

    output_root.mkdir(parents=True, exist_ok=True)
    source_classes = read_source_class_names(source_root)
    model = YOLO(str(model_path))
    true_positive: Counter[str] = Counter()
    false_negative: Counter[str] = Counter()
    false_positive: Counter[str] = Counter()
    confusion: Counter[str] = Counter()
    fn_area_bins: Counter[str] = Counter()
    image_rows: list[dict[str, Any]] = []
    scanned_images = 0

    for split, image_path, label_path in iter_source_images(source_root, splits):
        if max_images is not None and scanned_images >= max_images:
            break
        scanned_images += 1
        with Image.open(image_path) as image:
            targets = load_label_boxes(label_path, source_classes, image.size)
        predictions = predict_boxes(
            model=model,
            image_path=image_path,
            confidence=confidence,
            image_size=image_size,
            device=device,
        )
        image_result = analyze_image(
            targets=targets,
            predictions=predictions,
            iou_threshold=iou_threshold,
        )
        merge_counter(true_positive, image_result["true_positive"])
        merge_counter(false_negative, image_result["false_negative"])
        merge_counter(false_positive, image_result["false_positive"])
        merge_counter(confusion, image_result["confusion"])
        merge_counter(fn_area_bins, image_result["fn_area_bins"])
        if (
            image_result["false_negative"]
            or image_result["false_positive"]
            or image_result["confusion"]
        ):
            image_rows.append({
                "split": split,
                "image": image_path.relative_to(source_root).as_posix(),
                "label": label_path.relative_to(source_root).as_posix(),
                **image_result,
            })

    summary = {
        "schema_version": "1.0",
        "task": "vision_validation_error_analysis",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(source_root),
        "model_path": str(model_path),
        "splits": splits,
        "confidence": confidence,
        "iou_threshold": iou_threshold,
        "image_size": image_size,
        "max_images": max_images,
        "scanned_images": scanned_images,
        "error_images": len(image_rows),
        "classes": source_classes,
        "per_class": summarize_error_rates(
            classes=source_classes,
            true_positive=true_positive,
            false_negative=false_negative,
            false_positive=false_positive,
        ),
        "false_negative": sorted_counter(false_negative),
        "false_positive": sorted_counter(false_positive),
        "confusion": sorted_counter(confusion),
        "fn_area_bins": sorted_counter(fn_area_bins),
        "image_error_csv": "image_errors.csv",
    }
    (output_root / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_image_rows(output_root / "image_errors.csv", image_rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=["train", "val", "test"],
        action="append",
        default=None,
    )
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-images", type=int, default=None)
    args = parser.parse_args()
    summary = analyze_dataset(
        source_root=args.source,
        model_path=args.model,
        output_root=args.output,
        splits=args.split or ["val"],
        confidence=args.conf,
        iou_threshold=args.iou_threshold,
        image_size=args.imgsz,
        device=args.device,
        max_images=args.max_images,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
