"""Evaluate YOLO AP50 after applying an explicit ROI/min-object-area policy."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from PIL import Image
from stwi.tooling.vision_training.external_models import (
    normalize_class_aliases,
    normalize_prompt_classes,
)

try:
    from scripts.validation.analyze_vision_validation_errors import (
        LabeledBox,
        load_label_boxes,
        predict_boxes,
    )
    from scripts.data_prep.build_vision_error_review_pack import (
        Box,
        box_iou,
        iter_source_images,
        read_source_class_names,
    )
except ModuleNotFoundError:
    from analyze_vision_validation_errors import (
        LabeledBox,
        load_label_boxes,
        predict_boxes,
    )
    from build_vision_error_review_pack import (
        Box,
        box_iou,
        iter_source_images,
        read_source_class_names,
    )


@dataclass(frozen=True)
class PredictionRecord:
    class_name: str
    image_id: str
    box: Box
    confidence: float
    normalized_area: float


def load_ultralytics_detector(
    model_reference: str,
    *,
    model_family: str,
    prompt_classes: list[str] | None = None,
) -> Any:
    if model_family == "yolo":
        from ultralytics import YOLO

        return YOLO(model_reference)
    if model_family == "yolo_world":
        from ultralytics import YOLOWorld

        model = YOLOWorld(model_reference)
        classes = normalize_prompt_classes(prompt_classes)
        if classes:
            model.set_classes(classes)
        return model
    if model_family == "rtdetr":
        from ultralytics import RTDETR

        return RTDETR(model_reference)
    raise ValueError(f"unsupported model family: {model_family}")


def normalized_box_area(box: Box, image_size: tuple[int, int]) -> float:
    width, height = image_size
    x1, y1, x2, y2 = box.xyxy
    area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    denominator = max(1, width * height)
    return area / denominator


def filter_targets(
    boxes: list[LabeledBox],
    min_box_area: float,
) -> list[LabeledBox]:
    return [box for box in boxes if box.normalized_area >= min_box_area]


def filter_predictions(
    boxes: list[Box],
    *,
    image_id: str,
    image_size: tuple[int, int],
    min_box_area: float,
    class_aliases: Mapping[str, str] | None = None,
) -> list[PredictionRecord]:
    aliases = class_aliases or {}
    records: list[PredictionRecord] = []
    for box in boxes:
        area = normalized_box_area(box, image_size)
        if area < min_box_area:
            continue
        records.append(PredictionRecord(
            class_name=aliases.get(box.class_name, box.class_name),
            image_id=image_id,
            box=box,
            confidence=float(box.confidence or 0.0),
            normalized_area=area,
        ))
    return records


def average_precision(recall: list[float], precision: list[float]) -> float:
    if not recall:
        return 0.0
    mrec = [0.0, *recall, 1.0]
    mpre = [0.0, *precision, 0.0]
    for index in range(len(mpre) - 2, -1, -1):
        mpre[index] = max(mpre[index], mpre[index + 1])
    area = 0.0
    for index in range(1, len(mrec)):
        if mrec[index] != mrec[index - 1]:
            area += (mrec[index] - mrec[index - 1]) * mpre[index]
    return area


def evaluate_class_ap50(
    *,
    class_name: str,
    targets_by_image: dict[str, list[LabeledBox]],
    predictions: list[PredictionRecord],
    iou_threshold: float,
) -> dict[str, float | int]:
    class_targets = {
        image_id: [
            target for target in targets
            if target.class_name == class_name
        ]
        for image_id, targets in targets_by_image.items()
    }
    total_targets = sum(len(targets) for targets in class_targets.values())
    class_predictions = [
        prediction for prediction in predictions
        if prediction.class_name == class_name
    ]
    class_predictions.sort(key=lambda item: item.confidence, reverse=True)
    matched: dict[str, set[int]] = defaultdict(set)
    true_positive: list[int] = []
    false_positive: list[int] = []

    for prediction in class_predictions:
        targets = class_targets.get(prediction.image_id, [])
        best_iou = 0.0
        best_index: int | None = None
        for target_index, target in enumerate(targets):
            if target_index in matched[prediction.image_id]:
                continue
            iou = box_iou(target, prediction.box)
            if iou > best_iou:
                best_iou = iou
                best_index = target_index
        if best_index is not None and best_iou >= iou_threshold:
            matched[prediction.image_id].add(best_index)
            true_positive.append(1)
            false_positive.append(0)
        else:
            true_positive.append(0)
            false_positive.append(1)

    cumulative_tp: list[int] = []
    cumulative_fp: list[int] = []
    tp_sum = 0
    fp_sum = 0
    for tp, fp in zip(true_positive, false_positive):
        tp_sum += tp
        fp_sum += fp
        cumulative_tp.append(tp_sum)
        cumulative_fp.append(fp_sum)

    recall = [
        tp / total_targets if total_targets else 0.0
        for tp in cumulative_tp
    ]
    precision = [
        tp / max(1, tp + fp)
        for tp, fp in zip(cumulative_tp, cumulative_fp)
    ]
    ap50 = average_precision(recall, precision) if total_targets else 0.0
    return {
        "targets": total_targets,
        "predictions": len(class_predictions),
        "tp": tp_sum,
        "fp": fp_sum,
        "recall": recall[-1] if recall else 0.0,
        "precision": precision[-1] if precision else 0.0,
        "ap50": ap50,
    }


def evaluate_roi_ap(
    *,
    source_root: Path,
    model_path: Path | str,
    output_root: Path,
    splits: list[str],
    confidence: float,
    iou_threshold: float,
    image_size: int,
    device: str,
    min_box_area: float,
    max_images: int | None,
    model_family: str = "yolo",
    prompt_classes: list[str] | None = None,
    class_aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    ultralytics_config_dir = Path("data/derived/private/ultralytics").resolve()
    ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ultralytics_config_dir))
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("WINDIR", os.environ.get("SystemRoot", "C:\\Windows"))

    output_root.mkdir(parents=True, exist_ok=True)
    source_classes = read_source_class_names(source_root)
    normalized_aliases = dict(class_aliases or {})
    model = load_ultralytics_detector(
        str(model_path),
        model_family=model_family,
        prompt_classes=prompt_classes,
    )
    targets_by_image: dict[str, list[LabeledBox]] = {}
    predictions: list[PredictionRecord] = []
    scanned_images = 0
    original_targets = 0
    kept_targets = 0
    original_predictions = 0
    started_at = time.perf_counter()

    for split, image_path, label_path in iter_source_images(source_root, splits):
        if max_images is not None and scanned_images >= max_images:
            break
        scanned_images += 1
        image_id = image_path.relative_to(source_root).as_posix()
        with Image.open(image_path) as image:
            current_image_size = image.size
            targets = load_label_boxes(label_path, source_classes, image.size)
        original_targets += len(targets)
        filtered_targets = filter_targets(targets, min_box_area)
        kept_targets += len(filtered_targets)
        targets_by_image[image_id] = filtered_targets
        raw_predictions = predict_boxes(
            model=model,
            image_path=image_path,
            confidence=confidence,
            image_size=image_size,
            device=device,
        )
        original_predictions += len(raw_predictions)
        predictions.extend(filter_predictions(
            raw_predictions,
            image_id=image_id,
            image_size=current_image_size,
            min_box_area=min_box_area,
            class_aliases=normalized_aliases,
        ))

    per_class = {
        class_name: evaluate_class_ap50(
            class_name=class_name,
            targets_by_image=targets_by_image,
            predictions=predictions,
            iou_threshold=iou_threshold,
        )
        for class_name in source_classes
    }
    classes_with_targets = [
        metrics["ap50"]
        for metrics in per_class.values()
        if int(metrics["targets"]) > 0
    ]
    mean_ap50 = (
        sum(float(value) for value in classes_with_targets) / len(classes_with_targets)
        if classes_with_targets else 0.0
    )
    elapsed_seconds = time.perf_counter() - started_at
    summary = {
        "schema_version": "1.0",
        "task": "vision_roi_ap50_evaluation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(source_root),
        "model_path": str(model_path),
        "model_family": model_family,
        "prompt_classes": normalize_prompt_classes(prompt_classes),
        "class_aliases": normalized_aliases,
        "splits": splits,
        "confidence": confidence,
        "iou_threshold": iou_threshold,
        "image_size": image_size,
        "min_box_area": min_box_area,
        "max_images": max_images,
        "scanned_images": scanned_images,
        "original_targets": original_targets,
        "kept_targets": kept_targets,
        "removed_targets": original_targets - kept_targets,
        "original_predictions": original_predictions,
        "kept_predictions": len(predictions),
        "removed_predictions": original_predictions - len(predictions),
        "elapsed_seconds": elapsed_seconds,
        "seconds_per_image": elapsed_seconds / scanned_images if scanned_images else 0.0,
        "classes": source_classes,
        "per_class": per_class,
        "metrics": {"mAP50_roi": mean_ap50},
    }
    (output_root / "roi_ap50_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--model-family",
        choices=["yolo", "yolo_world", "rtdetr"],
        default="yolo",
    )
    parser.add_argument(
        "--prompt-class",
        action="append",
        default=None,
        help="Class prompt for yolo_world models. Repeat for multiple classes.",
    )
    parser.add_argument(
        "--class-alias",
        action="append",
        default=None,
        help=(
            "Map a predicted class name to an STWI class using SOURCE:TARGET. "
            "Repeat for multiple aliases, for example motor:motorcycle."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=["train", "val", "test"],
        action="append",
        default=None,
    )
    parser.add_argument("--conf", type=float, default=0.001)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-box-area", type=float, default=0.0)
    parser.add_argument("--max-images", type=int, default=None)
    args = parser.parse_args()
    if not 0 <= args.min_box_area < 1:
        raise ValueError("min-box-area must be in [0, 1)")
    summary = evaluate_roi_ap(
        source_root=args.source,
        model_path=args.model,
        output_root=args.output,
        splits=args.split or ["val"],
        confidence=args.conf,
        iou_threshold=args.iou_threshold,
        image_size=args.imgsz,
        device=args.device,
        min_box_area=args.min_box_area,
        max_images=args.max_images,
        model_family=args.model_family,
        prompt_classes=args.prompt_class,
        class_aliases=normalize_class_aliases(args.class_alias),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
