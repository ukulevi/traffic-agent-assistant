"""Prepare a compact HTML/CSV batch for vision label review."""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATUSES = {"pending", "needs_fix"}


def read_manifest(pack_root: Path) -> dict[str, Any]:
    manifest_path = pack_root / "review_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing review manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def read_review_rows(pack_root: Path) -> list[dict[str, str]]:
    csv_path = pack_root / "review_queue.csv"
    if not csv_path.is_file():
        raise ValueError(f"missing review queue: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row_number, row in enumerate(rows, start=2):
        if not row.get("preview"):
            raise ValueError(f"missing preview path in {csv_path}:{row_number}")
    return rows


def select_rows(
    *,
    pack_root: Path,
    statuses: set[str],
    limit: int | None,
) -> list[dict[str, str]]:
    manifest = read_manifest(pack_root)
    rows = read_review_rows(pack_root)
    selected: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        status = row.get("review_status", "").strip().lower()
        if status not in statuses:
            continue
        selected.append({
            "batch_status": status,
            "review_status": status,
            "source_pack": pack_root.as_posix(),
            "source_review_csv": (pack_root / "review_queue.csv").as_posix(),
            "source_row_index": str(index),
            "review_pack_version": str(manifest.get("review_pack_version", pack_root.name)),
            "review_mode": str(manifest.get("review_mode", "false_negative")),
            "target_class": row.get("target_class", str(manifest.get("target_class", ""))),
            "split": row.get("split", ""),
            "source_image": row.get("source_image", ""),
            "source_label": row.get("source_label", ""),
            "preview": row["preview"],
            "target_boxes": row.get("target_boxes", ""),
            "predicted_boxes": row.get("predicted_boxes", ""),
            "missed_boxes": row.get("missed_boxes", ""),
            "false_positive_boxes": row.get("false_positive_boxes", ""),
            "review_note": row.get("review_note", ""),
        })
        if limit is not None and len(selected) >= limit:
            break
    return selected


def copy_previews(output_root: Path, rows: list[dict[str, str]]) -> None:
    preview_dir = output_root / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for batch_index, row in enumerate(rows):
        pack_root = Path(row["source_pack"])
        source_preview = pack_root / row["preview"]
        if not source_preview.is_file():
            raise ValueError(f"missing preview image: {source_preview}")
        suffix = source_preview.suffix.lower() or ".jpg"
        preview_name = f"{batch_index:04d}_{pack_root.name}_{source_preview.stem}{suffix}"
        destination = preview_dir / preview_name
        shutil.copy2(source_preview, destination)
        row["batch_preview"] = destination.relative_to(output_root).as_posix()


def write_batch_csv(output_root: Path, rows: list[dict[str, str]]) -> Path:
    fieldnames = [
        "batch_status",
        "review_status",
        "source_pack",
        "source_review_csv",
        "source_row_index",
        "review_pack_version",
        "review_mode",
        "target_class",
        "split",
        "source_image",
        "source_label",
        "preview",
        "batch_preview",
        "target_boxes",
        "predicted_boxes",
        "missed_boxes",
        "false_positive_boxes",
        "review_note",
    ]
    csv_path = output_root / "review_batch.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def write_html(output_root: Path, rows: list[dict[str, str]], title: str) -> Path:
    cards: list[str] = []
    for index, row in enumerate(rows, start=1):
        note = html.escape(row.get("review_note", ""))
        cards.append(
            "<article class=\"item\">"
            f"<h2>{index:03d}. {html.escape(row['review_pack_version'])}</h2>"
            f"<img src=\"{html.escape(row['batch_preview'])}\" alt=\"review preview {index}\">"
            "<dl>"
            f"<dt>Status</dt><dd>{html.escape(row['review_status'])}</dd>"
            f"<dt>Class</dt><dd>{html.escape(row['target_class'])}</dd>"
            f"<dt>Split</dt><dd>{html.escape(row['split'])}</dd>"
            f"<dt>Mode</dt><dd>{html.escape(row['review_mode'])}</dd>"
            f"<dt>Source image</dt><dd>{html.escape(row['source_image'])}</dd>"
            f"<dt>Row</dt><dd>{html.escape(row['source_row_index'])}</dd>"
            f"<dt>Note</dt><dd>{note}</dd>"
            "</dl>"
            "</article>"
        )
    content = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin: 24px; font-family: Arial, sans-serif; color: #172026; background: #f7f9fb; }}
    header {{ max-width: 1180px; margin: 0 auto 20px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ margin: 6px 0; line-height: 1.45; }}
    code {{ background: #eef3f7; padding: 2px 5px; border-radius: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .item {{ background: white; border: 1px solid #d9e2ea; border-radius: 8px; padding: 12px; }}
    .item h2 {{ font-size: 15px; margin: 0 0 10px; }}
    img {{ width: 100%; height: auto; border: 1px solid #c8d3dc; }}
    dl {{ display: grid; grid-template-columns: 96px 1fr; gap: 5px 10px; font-size: 13px; }}
    dt {{ font-weight: 700; color: #3b4b58; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <p>Review nhanh preview, sau đó sửa cột <code>review_status</code> trong <code>review_batch.csv</code>: <code>accepted</code>, <code>rejected</code>, <code>needs_fix</code> hoặc giữ <code>pending</code>.</p>
    <p>Quy ước màu preview: xanh lá là label gốc, xanh dương là prediction, đỏ là lỗi cần kiểm tra.</p>
  </header>
  <main class="grid">
    {''.join(cards)}
  </main>
</body>
</html>
"""
    html_path = output_root / "index.html"
    html_path.write_text(content, encoding="utf-8")
    return html_path


def write_manifest(
    *,
    output_root: Path,
    rows: list[dict[str, str]],
    packs: list[Path],
    statuses: set[str],
    title: str,
) -> dict[str, Any]:
    counts_by_pack = Counter(row["review_pack_version"] for row in rows)
    counts_by_class = Counter(row["target_class"] for row in rows)
    manifest = {
        "schema_version": "1.0",
        "task": "vision_review_batch",
        "title": title,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_packs": [pack.as_posix() for pack in packs],
        "selected_statuses": sorted(statuses),
        "review_images": len(rows),
        "counts_by_pack": dict(counts_by_pack),
        "counts_by_class": dict(counts_by_class),
        "review_batch_csv": "review_batch.csv",
        "html_index": "index.html",
    }
    (output_root / "review_batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def prepare_review_batch(
    *,
    packs: list[Path],
    output_root: Path,
    statuses: set[str],
    limit_per_pack: int | None,
    title: str,
) -> dict[str, Any]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    rows: list[dict[str, str]] = []
    for pack in packs:
        rows.extend(select_rows(
            pack_root=pack,
            statuses=statuses,
            limit=limit_per_pack,
        ))
    copy_previews(output_root, rows)
    write_batch_csv(output_root, rows)
    write_html(output_root, rows, title)
    return write_manifest(
        output_root=output_root,
        rows=rows,
        packs=packs,
        statuses=statuses,
        title=title,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--status", action="append", default=None)
    parser.add_argument("--limit-per-pack", type=int, default=None)
    parser.add_argument("--title", default="STWI Vision Label Review Batch")
    args = parser.parse_args()

    statuses = {
        status.strip().lower()
        for status in (args.status or sorted(DEFAULT_STATUSES))
    }
    manifest = prepare_review_batch(
        packs=args.pack,
        output_root=args.output,
        statuses=statuses,
        limit_per_pack=args.limit_per_pack,
        title=args.title,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
