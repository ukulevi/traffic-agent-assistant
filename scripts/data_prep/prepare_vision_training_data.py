"""Build a private YOLO dataset from synthetic scenes and RTSP quarantine.

Real frames receive conservative privacy redaction and auditable pseudo-labels.
Synthetic images have exact geometric labels and supply validation/test splits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


CLASS_NAMES = ["car", "motorcycle", "bus", "truck"]
COCO_TO_STWI = {2: 0, 3: 1, 5: 2, 7: 3}
PRIVACY_COCO_CLASSES = {0, 1, 2, 3, 5, 7}
ROAD_ROI = ((0.18, 1.0), (0.41, 0.0), (0.63, 0.0), (0.90, 1.0))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def yolo_line(class_id: int, box: tuple[int, int, int, int],
              width: int, height: int) -> str:
    left, top, right, bottom = box
    center_x = ((left + right) / 2) / width
    center_y = ((top + bottom) / 2) / height
    box_width = (right - left) / width
    box_height = (bottom - top) / height
    return (
        f"{class_id} {center_x:.6f} {center_y:.6f} "
        f"{box_width:.6f} {box_height:.6f}"
    )


def split_for_mock(index: int, total: int) -> str:
    ratio = index / total
    if ratio < 0.70:
        return "train"
    if ratio < 0.85:
        return "val"
    return "test"


def draw_vehicle(
    draw: ImageDraw.ImageDraw,
    rng: random.Random,
    class_id: int,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    colors = ["#2878b5", "#cc3d3d", "#e0a020", "#4b5563"]
    color = colors[class_id]
    if class_id == 1:
        radius = max(2, (right - left) // 6)
        draw.ellipse((left, bottom - radius * 2, left + radius * 2, bottom),
                     fill="#202020")
        draw.ellipse((right - radius * 2, bottom - radius * 2, right, bottom),
                     fill="#202020")
        draw.rectangle((left + radius, top, right - radius, bottom - radius),
                       fill=color)
    else:
        draw.rounded_rectangle(box, radius=max(2, (right - left) // 10),
                               fill=color, outline="#202020", width=2)
        window_top = top + max(2, (bottom - top) // 6)
        draw.rectangle(
            (left + (right - left) // 5, window_top,
             right - (right - left) // 5,
             top + (bottom - top) // 2),
            fill="#9ecae1",
        )
    if rng.random() < 0.5:
        draw.line((left, bottom, right, bottom), fill="#111111", width=2)


def generate_mock_dataset(root: Path, count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    width, height = 640, 384
    for index in range(count):
        split = split_for_mock(index, count)
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        stem = f"mock_{index:05d}"
        image_path = image_dir / f"{stem}.jpg"
        label_path = label_dir / f"{stem}.txt"

        sky = (125 + rng.randrange(25), 165 + rng.randrange(30),
               195 + rng.randrange(35))
        grass = (95 + rng.randrange(35), 145 + rng.randrange(35),
                 80 + rng.randrange(30))
        road = (70 + rng.randrange(25),) * 3
        image = Image.new("RGB", (width, height), sky)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, width, 95), fill=grass)
        draw.polygon([(115, height), (260, 90), (380, 90), (535, height)],
                     fill=road)
        for lane_x in (274, 366):
            draw.line((lane_x, height, 310 if lane_x < 320 else 330, 90),
                      fill="#f4d03f", width=5)

        labels: list[str] = []
        object_count = rng.randint(0, 5)
        for _ in range(object_count):
            class_id = rng.randrange(len(CLASS_NAMES))
            top = rng.randint(105, height - 45)
            perspective = (top - 90) / (height - 90)
            max_width = max(24, round(28 + perspective * 72))
            if class_id == 1:
                max_width = max(20, round(max_width * 0.65))
            box_width = rng.randint(max(16, max_width // 2), max_width)
            box_height = rng.randint(
                max(20, round(box_width * 0.65)),
                max(24, round(box_width * 1.20)),
            )
            box_height = min(box_height, height - top - 5)
            road_left = 260 + (115 - 260) * perspective
            road_right = 380 + (535 - 380) * perspective
            minimum_left = math.ceil(road_left + 4)
            maximum_left = math.floor(road_right - box_width - 4)
            if maximum_left < minimum_left:
                continue
            left = rng.randint(minimum_left, maximum_left)
            box = (left, top, left + box_width, top + box_height)
            draw_vehicle(draw, rng, class_id, box)
            labels.append(yolo_line(class_id, box, width, height))

        image.save(image_path, quality=88, optimize=True)
        label_path.write_text("\n".join(labels) + ("\n" if labels else ""),
                              encoding="utf-8")
        records.append({
            "image": image_path.relative_to(root).as_posix(),
            "label": label_path.relative_to(root).as_posix(),
            "split": split,
            "source_type": "synthetic_mock",
            "annotation_provenance": "exact_geometry",
            "object_count": len(labels),
            "sha256": sha256_file(image_path),
        })
    return records


def clamp_box(box: tuple[float, float, float, float], width: int,
              height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    return (
        max(0, min(width - 1, int(left))),
        max(0, min(height - 1, int(top))),
        max(1, min(width, int(math.ceil(right)))),
        max(1, min(height, int(math.ceil(bottom)))),
    )


def point_in_polygon(
    x: float, y: float, polygon: tuple[tuple[float, float], ...]
) -> bool:
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def box_center_in_road_roi(
    box: tuple[int, int, int, int], width: int, height: int
) -> bool:
    left, top, right, bottom = box
    return point_in_polygon(
        ((left + right) / 2) / width,
        ((top + bottom) / 2) / height,
        ROAD_ROI,
    )


def blur_region(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return
    crop = image.crop(box)
    radius = max(8, min(crop.size) // 4)
    image.paste(crop.filter(ImageFilter.GaussianBlur(radius=radius)), box)


def redact_detection(image: Image.Image, coco_class: int,
                     box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    if coco_class == 0:
        face_box = (
            left + int(width * 0.25), top,
            right - int(width * 0.25), top + int(height * 0.25),
        )
        blur_region(image, face_box)
        return
    plate_box = (
        left + int(width * 0.10), top + int(height * 0.30),
        right - int(width * 0.10), bottom,
    )
    blur_region(image, plate_box)


def prepare_real_dataset(
    root: Path,
    manifest_path: Path,
    model_path: str,
    label_confidence: float,
    privacy_confidence: float,
) -> list[dict[str, Any]]:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "Install the project vision extra before preparing real frames"
        ) from exc

    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("privacy_status") != "needs_review":
        raise ValueError("real source must be a quarantine manifest")
    source_root = manifest_path.parent
    model = YOLO(model_path)
    image_dir = root / "images" / "train"
    label_dir = root / "labels" / "train"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    frame_metadata = {
        frame["path"]: frame for frame in source_manifest["frames"]
    }
    records: list[dict[str, Any]] = []
    results = model.predict(
        source=[str(source_root / frame["path"])
                for frame in source_manifest["frames"]],
        imgsz=640,
        conf=privacy_confidence,
        device="cpu",
        verbose=False,
        stream=True,
    )
    for result in results:
        source_path = Path(result.path)
        metadata = frame_metadata[source_path.name]
        image = Image.open(source_path).convert("RGB")
        original_width, original_height = image.size
        labels: list[str] = []
        pseudo_labels: list[dict[str, Any]] = []
        for box, class_value, confidence_value in zip(
            result.boxes.xyxy.tolist(),
            result.boxes.cls.tolist(),
            result.boxes.conf.tolist(),
            strict=True,
        ):
            coco_class = int(class_value)
            confidence = float(confidence_value)
            pixel_box = clamp_box(tuple(box), original_width, original_height)
            if coco_class in PRIVACY_COCO_CLASSES:
                redact_detection(image, coco_class, pixel_box)
            if (
                coco_class in COCO_TO_STWI
                and confidence >= label_confidence
                and box_center_in_road_roi(
                    pixel_box, original_width, original_height
                )
            ):
                class_id = COCO_TO_STWI[coco_class]
                labels.append(
                    yolo_line(class_id, pixel_box,
                              original_width, original_height)
                )
                pseudo_labels.append({
                    "class_id": class_id,
                    "class_name": CLASS_NAMES[class_id],
                    "confidence": round(confidence, 6),
                    "xyxy": list(pixel_box),
                })

        if not labels:
            continue

        target_width = 640
        target_height = round(original_height * target_width / original_width)
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        stem = f"real_{source_manifest['session_id']}_{source_path.stem}"
        image_path = image_dir / f"{stem}.jpg"
        label_path = label_dir / f"{stem}.txt"
        image.save(image_path, quality=88, optimize=True)
        label_path.write_text("\n".join(labels) + ("\n" if labels else ""),
                              encoding="utf-8")
        records.append({
            "image": image_path.relative_to(root).as_posix(),
            "label": label_path.relative_to(root).as_posix(),
            "split": "train",
            "source_type": "real_rtsp_sanitized",
            "source_id": source_manifest["source_id"],
            "source_session_id": source_manifest["session_id"],
            "source_frame_sha256": metadata["sha256"],
            "recorded_at": metadata.get("recorded_at"),
            "timestamp_quality": metadata.get("timestamp_quality"),
            "annotation_provenance": f"pseudo_label:{Path(model_path).name}",
            "privacy_transform": "heuristic_face_and_plate_region_blur",
            "privacy_status": "automated_redaction_needs_spot_review",
            "pseudo_labels": pseudo_labels,
            "object_count": len(labels),
            "sha256": sha256_file(image_path),
        })
    return records


def write_dataset_files(root: Path, records: list[dict[str, Any]],
                        args: argparse.Namespace) -> None:
    class_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    for record in records:
        split_counts[record["split"]] += 1
        for label in record.get("pseudo_labels", []):
            class_counts[label["class_name"]] += 1
        if record["source_type"] == "synthetic_mock":
            label_path = root / record["label"]
            for line in label_path.read_text(encoding="utf-8").splitlines():
                if line:
                    class_counts[CLASS_NAMES[int(line.split()[0])]] += 1

    yaml_lines = [
        f"path: {root.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ] + [f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES)]
    (root / "dataset.yaml").write_text("\n".join(yaml_lines) + "\n",
                                       encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "classes": CLASS_NAMES,
        "split_policy": (
            "synthetic independent split; real session restricted to train"
        ),
        "label_confidence": args.label_confidence,
        "privacy_confidence": args.privacy_confidence,
        "privacy_status": "automated_redaction_needs_spot_review",
        "split_counts": dict(split_counts),
        "class_counts": dict(class_counts),
        "records": records,
    }
    (root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--real-manifest", type=Path, required=True)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--mock-count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20250530)
    parser.add_argument("--label-confidence", type=float, default=0.40)
    parser.add_argument("--privacy-confidence", type=float, default=0.20)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 30 <= args.mock_count <= 10_000:
        raise ValueError("mock-count must be between 30 and 10000")
    if args.output.exists():
        if not args.replace:
            raise FileExistsError("output exists; pass --replace to rebuild")
        marker = args.output / "dataset_manifest.json"
        if not marker.is_file():
            raise ValueError("refusing to replace a non-dataset directory")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)
    records = generate_mock_dataset(args.output, args.mock_count, args.seed)
    records.extend(prepare_real_dataset(
        args.output,
        args.real_manifest,
        args.model,
        args.label_confidence,
        args.privacy_confidence,
    ))
    write_dataset_files(args.output, records, args)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
