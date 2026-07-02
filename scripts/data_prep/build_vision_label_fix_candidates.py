"""Build candidate fixed labels for reviewed train images with missing boxes."""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

try:
    from scripts.data_prep.augment_vehicle_dataset_with_yolo_sources import TARGET_CLASSES, link_or_copy
    from scripts.data_prep.build_vision_error_review_pack import box_iou, read_source_class_names
    from scripts.data_prep.prepare_roboflow_yolo_dataset import STWI_CLASS_MAP, sha256_file
except ModuleNotFoundError:
    from augment_vehicle_dataset_with_yolo_sources import TARGET_CLASSES, link_or_copy
    from build_vision_error_review_pack import box_iou, read_source_class_names
    from prepare_roboflow_yolo_dataset import STWI_CLASS_MAP, sha256_file


@dataclass(frozen=True)
class CandidateBox:
    class_name: str
    xyxy: tuple[float, float, float, float]
    confidence: float | None
    provenance: str


def yolo_xywh_to_xyxy(
    x_center: float,
    y_center: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    return (
        max(0.0, (x_center - width / 2) * image_width),
        max(0.0, (y_center - height / 2) * image_height),
        min(float(image_width), (x_center + width / 2) * image_width),
        min(float(image_height), (y_center + height / 2) * image_height),
    )


def xyxy_to_yolo_xywh(
    xyxy: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = xyxy
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    return (
        (x1 + width / 2) / image_width,
        (y1 + height / 2) / image_height,
        width / image_width,
        height / image_height,
    )


def read_existing_boxes(
    label_path: Path,
    source_classes: list[str],
    image_size: tuple[int, int],
) -> list[CandidateBox]:
    image_width, image_height = image_size
    boxes: list[CandidateBox] = []
    for line_number, line in enumerate(
        label_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"expected YOLO xywh label: {label_path}:{line_number}")
        source_class_id = int(fields[0])
        if not 0 <= source_class_id < len(source_classes):
            raise ValueError(f"bad class id: {label_path}:{line_number}")
        target_class = STWI_CLASS_MAP.get(source_classes[source_class_id])
        if target_class not in TARGET_CLASSES:
            continue
        coordinates = [float(value) for value in fields[1:]]
        boxes.append(CandidateBox(
            class_name=target_class,
            xyxy=yolo_xywh_to_xyxy(*coordinates, image_width, image_height),
            confidence=None,
            provenance="source_label",
        ))
    return boxes


def predict_boxes(
    *,
    model: Any,
    image_path: Path,
    image_size: int,
    confidence: float,
    device: str,
) -> list[CandidateBox]:
    results = model.predict(
        source=str(image_path),
        imgsz=image_size,
        conf=confidence,
        device=device,
        verbose=False,
    )
    boxes: list[CandidateBox] = []
    for result in results:
        names = result.names
        for raw_box in result.boxes:
            class_id = int(raw_box.cls[0].item())
            class_name = str(names[class_id]).lower().strip()
            if class_name not in TARGET_CLASSES:
                continue
            x1, y1, x2, y2 = [float(value) for value in raw_box.xyxy[0].tolist()]
            boxes.append(CandidateBox(
                class_name=class_name,
                xyxy=(x1, y1, x2, y2),
                confidence=float(raw_box.conf[0].item()),
                provenance="model_prediction",
            ))
    return boxes


def merge_boxes(
    *,
    source_boxes: list[CandidateBox],
    prediction_boxes: list[CandidateBox],
    add_iou_threshold: float,
    reclass_iou_threshold: float,
    reclass_confidence: float,
) -> tuple[list[CandidateBox], int, int]:
    output = list(source_boxes)
    reclassified = 0
    added = 0
    for prediction in prediction_boxes:
        best_index = -1
        best_iou = 0.0
        for index, source_box in enumerate(output):
            iou = box_iou(source_box, prediction)  # type: ignore[arg-type]
            if iou > best_iou:
                best_index = index
                best_iou = iou
        if best_iou >= reclass_iou_threshold and best_index >= 0:
            existing = output[best_index]
            if (
                existing.class_name != prediction.class_name
                and prediction.confidence is not None
                and prediction.confidence >= reclass_confidence
            ):
                output[best_index] = CandidateBox(
                    class_name=prediction.class_name,
                    xyxy=existing.xyxy,
                    confidence=prediction.confidence,
                    provenance=f"source_label_reclass_from_{existing.class_name}",
                )
                reclassified += 1
            continue
        if best_iou < add_iou_threshold:
            output.append(CandidateBox(
                class_name=prediction.class_name,
                xyxy=prediction.xyxy,
                confidence=prediction.confidence,
                provenance="model_added_missing_label",
            ))
            added += 1
    return output, added, reclassified


def write_yolo_label(
    *,
    label_path: Path,
    boxes: list[CandidateBox],
    image_size: tuple[int, int],
) -> None:
    image_width, image_height = image_size
    target_index = {class_name: index for index, class_name in enumerate(TARGET_CLASSES)}
    lines: list[str] = []
    for box in boxes:
        x_center, y_center, width, height = xyxy_to_yolo_xywh(
            box.xyxy,
            image_width,
            image_height,
        )
        lines.append(
            f"{target_index[box.class_name]} "
            f"{x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        )
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_objects(root: Path, records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        label_path = root / record["label"]
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[TARGET_CLASSES[int(line.split()[0])]] += 1
    return dict(counts)


def draw_preview(
    *,
    image_path: Path,
    output_path: Path,
    source_boxes: list[CandidateBox],
    final_boxes: list[CandidateBox],
) -> None:
    with Image.open(image_path) as image:
        preview = image.convert("RGB")
    draw = ImageDraw.Draw(preview)
    for box in source_boxes:
        draw.rectangle(box.xyxy, outline=(220, 40, 40), width=3)
    for box in final_boxes:
        color = (0, 170, 0) if box.provenance == "source_label" else (0, 110, 255)
        draw.rectangle(box.xyxy, outline=color, width=3)
        label = box.class_name
        if box.confidence is not None:
            label = f"{label} {box.confidence:.2f}"
        draw.text((box.xyxy[0] + 2, box.xyxy[1] + 2), label, fill=color)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output_path)


def write_review_html(output_root: Path, review_rows: list[dict[str, Any]]) -> None:
    cards: list[str] = []
    for index, row in enumerate(review_rows, start=1):
        preview_src = Path(row["preview"]).relative_to("review").as_posix()
        cards.append(
            "<article class=\"item\">"
            f"<h2>{index:03d}. {html.escape(row['source_image'])}</h2>"
            f"<img src=\"{html.escape(preview_src)}\" alt=\"label fix preview {index}\">"
            "<dl>"
            f"<dt>Status</dt><dd>{html.escape(row['review_status'])}</dd>"
            f"<dt>Source boxes</dt><dd>{row['source_box_count']}</dd>"
            f"<dt>Predictions</dt><dd>{row['prediction_box_count']}</dd>"
            f"<dt>Final boxes</dt><dd>{row['final_box_count']}</dd>"
            f"<dt>Added</dt><dd>{row['added_box_count']}</dd>"
            f"<dt>Reclass</dt><dd>{row['reclassified_box_count']}</dd>"
            f"<dt>Label</dt><dd>{html.escape(row['label'])}</dd>"
            "</dl>"
            "</article>"
        )
    content = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>STWI label-fix candidates</title>
  <style>
    body {{ margin: 24px; font-family: Arial, sans-serif; color: #172026; background: #f7f9fb; }}
    header {{ max-width: 1180px; margin: 0 auto 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ margin: 6px 0; line-height: 1.45; }}
    code {{ background: #eef3f7; padding: 2px 5px; border-radius: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }}
    .item {{ background: white; border: 1px solid #d9e2ea; border-radius: 8px; padding: 12px; }}
    .item h2 {{ font-size: 15px; margin: 0 0 10px; }}
    img {{ width: 100%; height: auto; border: 1px solid #c8d3dc; }}
    dl {{ display: grid; grid-template-columns: 100px 1fr; gap: 5px 10px; font-size: 13px; }}
    dt {{ font-weight: 700; color: #3b4b58; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>STWI label-fix candidates</h1>
    <p>Đỏ là nhãn nguồn ban đầu, xanh lá là nhãn giữ nguyên, xanh dương là nhãn model đề xuất thêm hoặc reclass. Chỉ đổi <code>review_status</code> sang <code>accepted</code> sau khi bạn kiểm tra preview và file label tương ứng.</p>
  </header>
  <main class="grid">
    {''.join(cards)}
  </main>
</body>
</html>
"""
    (output_root / "review" / "index.html").write_text(content, encoding="utf-8")


def write_change_summary(
    *,
    output_root: Path,
    manifest: dict[str, Any],
    review_rows: list[dict[str, Any]],
) -> None:
    top_rows = sorted(
        review_rows,
        key=lambda row: (
            int(row["added_box_count"]),
            int(row["reclassified_box_count"]),
        ),
        reverse=True,
    )[:20]
    lines = [
        "# STWI MVP Round 1 Label-Fix Candidate Summary",
        "",
        "This candidate set covers train-split `needs_fix` rows only.",
        "Validation rows are intentionally unchanged because their red FN boxes were confirmed as valid missed objects.",
        "",
        f"- Candidate images: {manifest['split_counts']['train']}",
        f"- Added candidate boxes: {manifest['total_added_box_count']}",
        f"- Reclassified candidate boxes: {manifest['total_reclassified_box_count']}",
        f"- Object counts: {json.dumps(manifest['object_counts'], ensure_ascii=False)}",
        "- Original source images and labels were not modified.",
        "- All candidate rows remain `review_status=pending` until human review.",
        "",
        "## Largest Changes",
        "",
        "| Source image | Added | Reclass | Final boxes | Preview |",
        "|---|---:|---:|---:|---|",
    ]
    for row in top_rows:
        lines.append(
            f"| `{row['source_image']}` | {row['added_box_count']} | "
            f"{row['reclassified_box_count']} | {row['final_box_count']} | "
            f"`{row['preview']}` |"
        )
    (output_root / "review" / "CHANGE_SUMMARY.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def load_review_rows(batch_csv: Path) -> list[dict[str, str]]:
    with batch_csv.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row for row in rows
        if row.get("split") == "train"
        and row.get("review_status", "").strip().lower() == "needs_fix"
    ]


def build_label_fix_candidates(
    *,
    batch_csv: Path,
    output_root: Path,
    model_path: Path,
    image_size: int,
    confidence: float,
    add_iou_threshold: float,
    reclass_iou_threshold: float,
    reclass_confidence: float,
    device: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    from ultralytics import YOLO

    if output_root.exists():
        shutil.rmtree(output_root)
    (output_root / "train" / "images").mkdir(parents=True)
    (output_root / "train" / "labels").mkdir(parents=True)
    model = YOLO(str(model_path))

    records: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    total_added = 0
    total_reclassified = 0
    for index, row in enumerate(load_review_rows(batch_csv)):
        source_root = Path(row["source_pack"])
        source_manifest = json.loads(
            (source_root / "review_manifest.json").read_text(encoding="utf-8")
        )
        source_dataset = Path(source_manifest["source_dataset"])
        source_classes = read_source_class_names(source_dataset)
        image_path = source_dataset / row["source_image"]
        label_path = source_dataset / row["source_label"]
        with Image.open(image_path) as image:
            source_image_size = image.size
        source_boxes = read_existing_boxes(label_path, source_classes, source_image_size)
        prediction_boxes = predict_boxes(
            model=model,
            image_path=image_path,
            image_size=image_size,
            confidence=confidence,
            device=device,
        )
        final_boxes, added, reclassified = merge_boxes(
            source_boxes=source_boxes,
            prediction_boxes=prediction_boxes,
            add_iou_threshold=add_iou_threshold,
            reclass_iou_threshold=reclass_iou_threshold,
            reclass_confidence=reclass_confidence,
        )
        total_added += added
        total_reclassified += reclassified
        stem = f"label_fix_{index:06d}"
        output_image = output_root / "train" / "images" / f"{stem}{image_path.suffix.lower()}"
        output_label = output_root / "train" / "labels" / f"{stem}.txt"
        link_or_copy(image_path, output_image)
        write_yolo_label(
            label_path=output_label,
            boxes=final_boxes,
            image_size=source_image_size,
        )
        preview_path = output_root / "review" / "previews" / f"{stem}.jpg"
        draw_preview(
            image_path=image_path,
            output_path=preview_path,
            source_boxes=source_boxes,
            final_boxes=final_boxes,
        )
        record = {
            "image": output_image.relative_to(output_root).as_posix(),
            "label": output_label.relative_to(output_root).as_posix(),
            "split": "train",
            "source_type": "label_fix_candidate",
            "source_dataset": str(source_dataset),
            "source_image": row["source_image"],
            "source_label": row["source_label"],
            "review_pack": row["source_pack"],
            "review_status": "pending",
            "annotation_provenance": "source_label_plus_model_candidate_fix",
            "source_box_count": len(source_boxes),
            "prediction_box_count": len(prediction_boxes),
            "final_box_count": len(final_boxes),
            "added_box_count": added,
            "reclassified_box_count": reclassified,
            "sha256": sha256_file(output_image),
        }
        records.append(record)
        review_rows.append({
            "review_status": "pending",
            "image": record["image"],
            "label": record["label"],
            "preview": preview_path.relative_to(output_root).as_posix(),
            "source_dataset": str(source_dataset),
            "source_image": row["source_image"],
            "source_label": row["source_label"],
            "source_box_count": len(source_boxes),
            "prediction_box_count": len(prediction_boxes),
            "final_box_count": len(final_boxes),
            "added_box_count": added,
            "reclassified_box_count": reclassified,
            "review_note": "",
        })

    manifest = {
        "schema_version": "1.0",
        "dataset_version": output_root.name,
        "task": "vehicle_object_detection_label_fix_candidates",
        "format": "YOLO normalized xywh",
        "classes": TARGET_CLASSES,
        "source_batch": str(batch_csv),
        "model_path": str(model_path),
        "image_size": image_size,
        "confidence": confidence,
        "add_iou_threshold": add_iou_threshold,
        "reclass_iou_threshold": reclass_iou_threshold,
        "reclass_confidence": reclass_confidence,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "privacy_status": "needs_review",
        "privacy_review": {
            "reviewer": reviewer,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "human_approval_required_for_external_release": True,
        },
        "split_counts": {"train": len(records)},
        "object_counts": count_objects(output_root, records),
        "total_added_box_count": total_added,
        "total_reclassified_box_count": total_reclassified,
        "records": records,
    }
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_root / "review" / "review_queue.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0].keys()))
        writer.writeheader()
        writer.writerows(review_rows)
    write_review_html(output_root, review_rows)
    write_change_summary(
        output_root=output_root,
        manifest=manifest,
        review_rows=review_rows,
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--add-iou-threshold", type=float, default=0.45)
    parser.add_argument("--reclass-iou-threshold", type=float, default=0.65)
    parser.add_argument("--reclass-confidence", type=float, default=0.55)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--reviewer", default="pending")
    parser.add_argument("--notes", default="label fix candidates require human review")
    args = parser.parse_args()
    manifest = build_label_fix_candidates(
        batch_csv=args.batch,
        output_root=args.output,
        model_path=args.model,
        image_size=args.imgsz,
        confidence=args.conf,
        add_iou_threshold=args.add_iou_threshold,
        reclass_iou_threshold=args.reclass_iou_threshold,
        reclass_confidence=args.reclass_confidence,
        device=args.device,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    print(json.dumps({
        "dataset": str(args.output),
        "split_counts": manifest["split_counts"],
        "total_added_box_count": manifest["total_added_box_count"],
        "total_reclassified_box_count": manifest["total_reclassified_box_count"],
        "privacy_status": manifest["privacy_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
