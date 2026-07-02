"""Create a reviewed relabel pack from a helmet dataset for motorcycle training."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

try:
    from scripts.data_prep.prepare_roboflow_yolo_dataset import read_roboflow_yaml, sha256_file
except ModuleNotFoundError:
    from prepare_roboflow_yolo_dataset import read_roboflow_yaml, sha256_file


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TARGET_CLASS = "motorcycle"


@dataclass(frozen=True)
class RelabelDetection:
    """Normalized YOLO box proposed for a motorcycle in a helmet-source image."""

    x: float
    y: float
    w: float
    h: float
    confidence: float


@dataclass(frozen=True)
class SourceImage:
    image: Path
    label: Path | None
    split: str


def iter_source_images(source_root: Path) -> Iterable[SourceImage]:
    for split, split_dir in (("train", "train"), ("val", "valid"), ("test", "test")):
        image_dir = source_root / split_dir / "images"
        if not image_dir.is_dir():
            continue
        for image_path in image_dir.rglob("*"):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label_path = source_root / split_dir / "labels" / f"{image_path.stem}.txt"
            yield SourceImage(
                image=image_path,
                label=label_path if label_path.is_file() else None,
                split=split,
            )


def count_yolo_objects(label_path: Path | None) -> int:
    if label_path is None:
        return 0
    return sum(1 for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip())


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def yolo_to_pixel_box(detection: RelabelDetection, width: int, height: int) -> tuple[int, int, int, int]:
    left = int((detection.x - detection.w / 2) * width)
    top = int((detection.y - detection.h / 2) * height)
    right = int((detection.x + detection.w / 2) * width)
    bottom = int((detection.y + detection.h / 2) * height)
    return (
        max(0, left),
        max(0, top),
        min(width - 1, right),
        min(height - 1, bottom),
    )


def write_preview(image_path: Path, detections: list[RelabelDetection], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        preview = image.convert("RGB")
    draw = ImageDraw.Draw(preview)
    width, height = preview.size
    for detection in detections:
        box = yolo_to_pixel_box(detection, width, height)
        draw.rectangle(box, outline=(0, 153, 153), width=3)
        draw.text((box[0] + 2, max(0, box[1] - 12)), f"{detection.confidence:.2f}", fill=(0, 153, 153))
    preview.save(target)


def write_data_yaml(output_root: Path) -> None:
    lines = [
        f"path: {output_root.resolve().as_posix()}",
        "train: train/images",
        "val: train/images",
        "test: train/images",
        "names:",
        f"  0: {TARGET_CLASS}",
    ]
    (output_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_relabel_dataset_from_detections(
    *,
    source_root: Path,
    output_root: Path,
    detections_by_image: dict[Path, list[RelabelDetection]],
    dataset_version: str,
    model_path: str,
    min_confidence: float,
    max_images: int,
    reviewer: str,
) -> dict[str, object]:
    source_yaml = read_roboflow_yaml(source_root / "data.yaml")
    source_names = [str(name).lower() for name in source_yaml["names"]]
    if "helmet" not in source_names:
        raise ValueError("source dataset must expose a helmet class")

    output_root.mkdir(parents=True, exist_ok=True)
    write_data_yaml(output_root)
    review_image_dir = output_root / "review" / "images"
    review_queue = output_root / "review" / "review_queue.csv"
    records: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    seen_hashes: set[str] = set()

    candidates: list[tuple[float, SourceImage, list[RelabelDetection]]] = []
    for source_image in iter_source_images(source_root):
        detections = [
            detection for detection in detections_by_image.get(source_image.image, [])
            if detection.confidence >= min_confidence
        ]
        if not detections:
            continue
        score = max(detection.confidence for detection in detections)
        candidates.append((score, source_image, detections))
    candidates.sort(key=lambda item: item[0], reverse=True)

    for index, (_, source_image, detections) in enumerate(candidates[:max_images]):
        image_hash = sha256_file(source_image.image)
        if image_hash in seen_hashes:
            continue
        stem = f"helmet_relabel_{index:06d}"
        output_image = output_root / "train" / "images" / f"{stem}{source_image.image.suffix.lower()}"
        output_label = output_root / "train" / "labels" / f"{stem}.txt"
        preview_image = review_image_dir / f"{stem}.jpg"
        link_or_copy(source_image.image, output_image)
        output_label.parent.mkdir(parents=True, exist_ok=True)
        output_label.write_text(
            "\n".join(
                f"0 {det.x:.6f} {det.y:.6f} {det.w:.6f} {det.h:.6f}"
                for det in detections
            ) + "\n",
            encoding="utf-8",
        )
        write_preview(source_image.image, detections, preview_image)
        record = {
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": "train",
            "source_type": "helmet_dataset_motorcycle_relabel_candidate",
            "source_dataset": str(source_root),
            "source_image": str(source_image.image),
            "source_split": source_image.split,
            "annotation_provenance": f"{model_path}:assisted_relabel_conf>={min_confidence}",
            "review_status": "needs_human_spot_review",
            "helmet_source_objects": count_yolo_objects(source_image.label),
            "object_count": len(detections),
            "max_confidence": max(det.confidence for det in detections),
            "sha256": sha256_file(output_image),
        }
        records.append(record)
        review_rows.append({
            "review_status": "pending",
            "preview": preview_image.relative_to(output_root).as_posix(),
            "image": record["image"],
            "label": record["label"],
            "source_image": record["source_image"],
            "source_split": record["source_split"],
            "helmet_source_objects": record["helmet_source_objects"],
            "motorcycle_boxes": record["object_count"],
            "max_confidence": f"{record['max_confidence']:.6f}",
        })
        seen_hashes.add(image_hash)

    if not records:
        raise ValueError("no relabel candidates matched the requested confidence threshold")

    review_queue.parent.mkdir(parents=True, exist_ok=True)
    with review_queue.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0]))
        writer.writeheader()
        writer.writerows(review_rows)

    manifest = {
        "schema_version": "1.0",
        "dataset_version": dataset_version,
        "task": "motorcycle_object_detection_relabel_candidate",
        "format": "YOLO normalized xywh",
        "source": "helmet_dataset_assisted_motorcycle_relabel",
        "source_dataset": str(source_root),
        "source_class_names": source_yaml["names"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": [TARGET_CLASS],
        "split_policy": "selected relabel candidates are train-only until reviewed",
        "split_counts": {"train": len(records)},
        "object_counts": {TARGET_CLASS: sum(int(record["object_count"]) for record in records)},
        "privacy_status": "needs_review",
        "privacy_review": {
            "reviewer": reviewer,
            "notes": "Helmet-source images relabeled as motorcycle candidates; review previews before use in official training.",
        },
        "relabel_policy": {
            "model": model_path,
            "min_confidence": min_confidence,
            "max_images": max_images,
            "review_queue": review_queue.relative_to(output_root).as_posix(),
        },
        "records": records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def predict_motorcycle_boxes(
    *,
    source_root: Path,
    model_path: str,
    confidence: float,
    imgsz: int,
    device: str,
) -> dict[Path, list[RelabelDetection]]:
    os.environ.setdefault(
        "YOLO_CONFIG_DIR",
        str(Path("data/derived/private/ultralytics").resolve()),
    )
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    from ultralytics import YOLO

    model = YOLO(model_path)
    names = {int(index): str(name).lower() for index, name in dict(model.names).items()}
    motorcycle_class_ids = [
        index for index, name in names.items()
        if name in {"motorcycle", "motorbike"}
    ]
    if not motorcycle_class_ids:
        raise ValueError("model does not expose a motorcycle/motorbike class")

    detections_by_image: dict[Path, list[RelabelDetection]] = {}
    for source_image in iter_source_images(source_root):
        try:
            predictions = model.predict(
                source=str(source_image.image),
                imgsz=imgsz,
                conf=confidence,
                classes=motorcycle_class_ids,
                device=device,
                verbose=False,
            )
        except OSError:
            continue
        if not predictions or predictions[0].boxes is None:
            continue
        boxes = predictions[0].boxes
        detections = [
            RelabelDetection(
                x=float(x),
                y=float(y),
                w=float(w),
                h=float(h),
                confidence=float(conf),
            )
            for (x, y, w, h), conf in zip(boxes.xywhn.tolist(), boxes.conf.tolist())
        ]
        if detections:
            detections_by_image[source_image.image] = detections
    return detections_by_image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset-version", default="helmet_motorcycle_relabel_v001")
    parser.add_argument("--min-conf", type=float, default=0.55)
    parser.add_argument("--max-images", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--device", default="0")
    parser.add_argument("--reviewer", default="pending")
    args = parser.parse_args()

    detections = predict_motorcycle_boxes(
        source_root=args.source,
        model_path=args.model,
        confidence=args.min_conf,
        imgsz=args.imgsz,
        device=args.device,
    )
    manifest = build_relabel_dataset_from_detections(
        source_root=args.source,
        output_root=args.output,
        detections_by_image=detections,
        dataset_version=args.dataset_version,
        model_path=args.model,
        min_confidence=args.min_conf,
        max_images=args.max_images,
        reviewer=args.reviewer,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "review_queue": manifest["relabel_policy"]["review_queue"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
