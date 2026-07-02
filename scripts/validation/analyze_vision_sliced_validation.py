"""Analyze validation errors with full-frame plus sliced YOLO inference."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

try:
    from scripts.validation.analyze_vision_validation_errors import (
        analyze_image,
        load_label_boxes,
        merge_counter,
        sorted_counter,
        summarize_error_rates,
        write_image_rows,
    )
    from scripts.data_prep.build_vision_error_review_pack import (
        Box,
        box_iou,
        iter_source_images,
        read_source_class_names,
    )
except ModuleNotFoundError:
    from analyze_vision_validation_errors import (
        analyze_image,
        load_label_boxes,
        merge_counter,
        sorted_counter,
        summarize_error_rates,
        write_image_rows,
    )
    from build_vision_error_review_pack import (
        Box,
        box_iou,
        iter_source_images,
        read_source_class_names,
    )


def tile_origins(length: int, tile_size: int, overlap: float) -> list[int]:
    if length <= tile_size:
        return [0]
    stride = max(1, int(round(tile_size * (1.0 - overlap))))
    origins = list(range(0, max(1, length - tile_size + 1), stride))
    last = length - tile_size
    if origins[-1] != last:
        origins.append(last)
    return origins


def image_tiles(
    image: Image.Image,
    tile_size: int,
    overlap: float,
) -> Iterable[tuple[Image.Image, int, int]]:
    width, height = image.size
    for y_offset in tile_origins(height, tile_size, overlap):
        for x_offset in tile_origins(width, tile_size, overlap):
            yield image.crop((
                x_offset,
                y_offset,
                min(width, x_offset + tile_size),
                min(height, y_offset + tile_size),
            )), x_offset, y_offset


def predict_on_image(
    *,
    model: Any,
    image: Image.Image,
    confidence: float,
    image_size: int,
    device: str,
    x_offset: int = 0,
    y_offset: int = 0,
) -> list[Box]:
    results = model.predict(
        source=image,
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
                xyxy=(
                    x1 + x_offset,
                    y1 + y_offset,
                    x2 + x_offset,
                    y2 + y_offset,
                ),
                confidence=float(raw_box.conf[0].item()),
            ))
    return predicted


def class_aware_nms(boxes: list[Box], iou_threshold: float) -> list[Box]:
    kept: list[Box] = []
    by_class: dict[str, list[Box]] = {}
    for box in boxes:
        by_class.setdefault(box.class_name, []).append(box)
    for class_boxes in by_class.values():
        remaining = sorted(
            class_boxes,
            key=lambda box: float(box.confidence or 0.0),
            reverse=True,
        )
        while remaining:
            current = remaining.pop(0)
            kept.append(current)
            remaining = [
                candidate
                for candidate in remaining
                if box_iou(current, candidate) < iou_threshold
            ]
    return kept


def predict_sliced_boxes(
    *,
    model: Any,
    image_path: Path,
    confidence: float,
    image_size: int,
    device: str,
    tile_size: int,
    overlap: float,
    nms_iou: float,
    include_full_frame: bool,
) -> list[Box]:
    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")
    predictions: list[Box] = []
    if include_full_frame:
        predictions.extend(predict_on_image(
            model=model,
            image=image,
            confidence=confidence,
            image_size=image_size,
            device=device,
        ))
    for tile, x_offset, y_offset in image_tiles(image, tile_size, overlap):
        predictions.extend(predict_on_image(
            model=model,
            image=tile,
            confidence=confidence,
            image_size=image_size,
            device=device,
            x_offset=x_offset,
            y_offset=y_offset,
        ))
    return class_aware_nms(predictions, nms_iou)


def analyze_sliced_dataset(
    *,
    source_root: Path,
    model_path: Path,
    output_root: Path,
    splits: list[str],
    confidence: float,
    iou_threshold: float,
    image_size: int,
    device: str,
    tile_size: int,
    overlap: float,
    nms_iou: float,
    include_full_frame: bool,
    max_images: int | None,
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
        predictions = predict_sliced_boxes(
            model=model,
            image_path=image_path,
            confidence=confidence,
            image_size=image_size,
            device=device,
            tile_size=tile_size,
            overlap=overlap,
            nms_iou=nms_iou,
            include_full_frame=include_full_frame,
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
        "task": "vision_sliced_validation_error_analysis",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(source_root),
        "model_path": str(model_path),
        "splits": splits,
        "confidence": confidence,
        "iou_threshold": iou_threshold,
        "image_size": image_size,
        "tile_size": tile_size,
        "overlap": overlap,
        "nms_iou": nms_iou,
        "include_full_frame": include_full_frame,
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
    parser.add_argument("--tile-size", type=int, default=640)
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument("--nms-iou", type=float, default=0.55)
    parser.add_argument("--no-full-frame", action="store_true")
    parser.add_argument("--max-images", type=int, default=None)
    args = parser.parse_args()
    if not 0 <= args.overlap < 1:
        raise ValueError("overlap must be in [0, 1)")
    if args.tile_size < 160:
        raise ValueError("tile-size must be at least 160")

    summary = analyze_sliced_dataset(
        source_root=args.source,
        model_path=args.model,
        output_root=args.output,
        splits=args.split or ["val"],
        confidence=args.conf,
        iou_threshold=args.iou_threshold,
        image_size=args.imgsz,
        device=args.device,
        tile_size=args.tile_size,
        overlap=args.overlap,
        nms_iou=args.nms_iou,
        include_full_frame=not args.no_full_frame,
        max_images=args.max_images,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
