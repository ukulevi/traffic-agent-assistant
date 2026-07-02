"""Augment the STWI vehicle dataset with extra motorcycle-focused images."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.data_prep.prepare_roboflow_yolo_dataset import read_roboflow_yaml, sha256_file
except ModuleNotFoundError:
    from prepare_roboflow_yolo_dataset import read_roboflow_yaml, sha256_file


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TARGET_CLASSES = ["bus", "car", "motorcycle", "truck"]
MOTORCYCLE_INDEX = TARGET_CLASSES.index("motorcycle")
SPLIT_DIRS = {"train": "train", "val": "valid", "test": "test"}


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


def iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def copy_base_dataset(base_root: Path, output_root: Path) -> tuple[dict[str, Any], set[str]]:
    base_manifest = json.loads(
        (base_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if base_manifest["classes"] != TARGET_CLASSES:
        raise ValueError("base dataset must use STWI vehicle classes")
    output_root.mkdir(parents=True, exist_ok=True)
    write_dataset_yaml(output_root)
    seen_hashes: set[str] = set()
    for record in base_manifest["records"]:
        source_image = base_root / record["image"]
        source_label = base_root / record["label"]
        target_image = output_root / record["image"]
        target_label = output_root / record["label"]
        link_or_copy(source_image, target_image)
        link_or_copy(source_label, target_label)
        seen_hashes.add(record["sha256"])
    return base_manifest, seen_hashes


def remap_annotated_source(
    *,
    source_root: Path,
    output_root: Path,
    seen_hashes: set[str],
    source_tag: str,
    start_index: int,
) -> tuple[list[dict[str, Any]], int]:
    source_yaml = read_roboflow_yaml(source_root / "data.yaml")
    names = [name.lower().strip() for name in source_yaml["names"]]
    motorcycle_ids = {
        index for index, name in enumerate(names)
        if name in {"motorcycle", "motorbike", "motorcycles", "motorbikes"}
    }
    if not motorcycle_ids:
        return [], start_index
    records: list[dict[str, Any]] = []
    index = start_index
    for image_path in iter_images(source_root):
        label_path = image_path.parent.parent / "labels" / f"{image_path.stem}.txt"
        if not label_path.is_file():
            continue
        image_hash = sha256_file(image_path)
        if image_hash in seen_hashes:
            continue
        output_lines: list[str] = []
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fields = line.split()
            if int(fields[0]) in motorcycle_ids:
                output_lines.append(" ".join([str(MOTORCYCLE_INDEX), *fields[1:5]]))
        if not output_lines:
            continue
        stem = f"moto_ann_{index:06d}"
        output_image = output_root / "train" / "images" / f"{stem}{image_path.suffix.lower()}"
        output_label = output_root / "train" / "labels" / f"{stem}.txt"
        link_or_copy(image_path, output_image)
        output_label.parent.mkdir(parents=True, exist_ok=True)
        output_label.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        records.append({
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": "train",
            "source_type": "motorcycle_annotated_supplement",
            "source_dataset": source_tag,
            "annotation_provenance": "source_yolo_motorcycle_remap",
            "object_count": len(output_lines),
            "sha256": sha256_file(output_image),
        })
        seen_hashes.add(image_hash)
        index += 1
    return records, index


def pseudo_label_sources(
    *,
    source_roots: list[Path],
    output_root: Path,
    seen_hashes: set[str],
    model_path: str,
    confidence: float,
    start_index: int,
) -> tuple[list[dict[str, Any]], int]:
    if not source_roots:
        return [], start_index
    os.environ.setdefault(
        "YOLO_CONFIG_DIR",
        str(Path("data/derived/private/ultralytics").resolve()),
    )
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    from ultralytics import YOLO

    model = YOLO(model_path)
    names = {
        int(index): str(name).lower()
        for index, name in dict(model.names).items()
    }
    model_motorcycle_ids = [
        index for index, name in names.items()
        if name in {"motorcycle", "motorbike"}
    ]
    if not model_motorcycle_ids:
        raise ValueError("pseudo-label model does not expose a motorcycle class")

    records: list[dict[str, Any]] = []
    index = start_index
    for source_root in source_roots:
        for image_path in iter_images(source_root):
            image_hash = sha256_file(image_path)
            if image_hash in seen_hashes:
                continue
            predictions = model.predict(
                source=str(image_path),
                imgsz=416,
                conf=confidence,
                classes=model_motorcycle_ids,
                verbose=False,
            )
            if not predictions:
                continue
            result = predictions[0]
            if result.boxes is None or len(result.boxes) == 0:
                continue
            output_lines = [
                (
                    f"{MOTORCYCLE_INDEX} {float(x):.6f} {float(y):.6f} "
                    f"{float(w):.6f} {float(h):.6f}"
                )
                for x, y, w, h in result.boxes.xywhn.tolist()
            ]
            stem = f"moto_pseudo_{index:06d}"
            output_image = output_root / "train" / "images" / (
                stem + image_path.suffix.lower()
            )
            output_label = output_root / "train" / "labels" / f"{stem}.txt"
            link_or_copy(image_path, output_image)
            output_label.parent.mkdir(parents=True, exist_ok=True)
            output_label.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
            records.append({
                "image": output_image.relative_to(output_root).as_posix(),
                "label": output_label.relative_to(output_root).as_posix(),
                "split": "train",
                "source_type": "motorcycle_pseudo_labeled_supplement",
                "source_dataset": str(source_root),
                "annotation_provenance": f"{model_path}:conf>={confidence}",
                "object_count": len(output_lines),
                "sha256": sha256_file(output_image),
            })
            seen_hashes.add(image_hash)
            index += 1
    return records, index


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for line in (root / record["label"]).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def augment_dataset(
    *,
    base_root: Path,
    output_root: Path,
    annotated_sources: list[Path],
    pseudo_sources: list[Path],
    pseudo_model: str,
    pseudo_conf: float,
) -> dict[str, Any]:
    base_manifest, seen_hashes = copy_base_dataset(base_root, output_root)
    new_records: list[dict[str, Any]] = []
    next_index = 0
    for source in annotated_sources:
        records, next_index = remap_annotated_source(
            source_root=source,
            output_root=output_root,
            seen_hashes=seen_hashes,
            source_tag=str(source),
            start_index=next_index,
        )
        new_records.extend(records)
    records, next_index = pseudo_label_sources(
        source_roots=pseudo_sources,
        output_root=output_root,
        seen_hashes=seen_hashes,
        model_path=pseudo_model,
        confidence=pseudo_conf,
        start_index=next_index,
    )
    new_records.extend(records)

    all_records = [*base_manifest["records"], *new_records]
    split_counts: Counter[str] = Counter(record["split"] for record in all_records)
    manifest = {
        "schema_version": "1.0",
        "dataset_version": f"{base_manifest['dataset_version']}_moto_aug",
        "task": "vehicle_object_detection",
        "format": "YOLO normalized xywh",
        "source": "derived_vehicle_dataset_with_motorcycle_supplement",
        "base_dataset": str(base_root),
        "base_manifest_sha256": sha256_file(base_root / "dataset_manifest.json"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classes": TARGET_CLASSES,
        "stwi_class_map": {name: name for name in TARGET_CLASSES},
        "ignored_classes": base_manifest.get("ignored_classes", []),
        "split_policy": "base val/test preserved; motorcycle supplements added to train only",
        "split_counts": dict(split_counts),
        "object_counts": count_objects(output_root, all_records),
        "privacy_status": base_manifest["privacy_status"],
        "privacy_review": base_manifest["privacy_review"],
        "supplement": {
            "annotated_sources": [str(path) for path in annotated_sources],
            "pseudo_sources": [str(path) for path in pseudo_sources],
            "pseudo_model": pseudo_model,
            "pseudo_confidence": pseudo_conf,
            "new_records": len(new_records),
        },
        "records": all_records,
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
    parser.add_argument("--annotated-source", type=Path, action="append", default=[])
    parser.add_argument("--pseudo-source", type=Path, action="append", default=[])
    parser.add_argument("--pseudo-model", default="yolov8n.pt")
    parser.add_argument("--pseudo-conf", type=float, default=0.3)
    args = parser.parse_args()
    manifest = augment_dataset(
        base_root=args.base,
        output_root=args.output,
        annotated_sources=args.annotated_source,
        pseudo_sources=args.pseudo_source,
        pseudo_model=args.pseudo_model,
        pseudo_conf=args.pseudo_conf,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "records": len(manifest["records"]),
        "split_counts": manifest["split_counts"],
        "object_counts": manifest["object_counts"],
        "supplement": manifest["supplement"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
