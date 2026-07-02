"""Apply decisions from a vision review batch back to source review queues."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {"pending", "accepted", "rejected", "needs_fix"}


def read_batch_rows(batch_csv: Path) -> list[dict[str, str]]:
    if not batch_csv.is_file():
        raise ValueError(f"missing review batch CSV: {batch_csv}")
    with batch_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"source_review_csv", "source_row_index", "review_status"}
    missing = required.difference(rows[0].keys() if rows else set())
    if missing:
        raise ValueError(
            f"review batch missing required columns: {', '.join(sorted(missing))}"
        )
    return rows


def read_queue(csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not csv_path.is_file():
        raise ValueError(f"missing source review queue: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if "review_status" not in fieldnames:
        raise ValueError(f"source queue has no review_status column: {csv_path}")
    return rows, fieldnames


def write_queue(
    *,
    csv_path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def apply_review_batch(batch_csv: Path, dry_run: bool = False) -> dict[str, Any]:
    batch_rows = read_batch_rows(batch_csv)
    grouped: dict[Path, list[dict[str, str]]] = defaultdict(list)
    for row in batch_rows:
        status = row["review_status"].strip().lower()
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"unsupported review_status {status!r}; expected one of "
                + ", ".join(sorted(ALLOWED_STATUSES))
            )
        grouped[Path(row["source_review_csv"])].append(row)

    updated_by_queue: dict[str, int] = {}
    status_counts: dict[str, int] = defaultdict(int)
    for csv_path, decisions in grouped.items():
        rows, fieldnames = read_queue(csv_path)
        updates = 0
        for decision in decisions:
            row_index = int(decision["source_row_index"])
            if not 0 <= row_index < len(rows):
                raise ValueError(f"source row index out of range: {csv_path}:{row_index}")
            new_status = decision["review_status"].strip().lower()
            rows[row_index]["review_status"] = new_status
            if "review_note" in rows[row_index]:
                rows[row_index]["review_note"] = decision.get("review_note", "")
            updates += 1
            status_counts[new_status] += 1
        if not dry_run:
            write_queue(csv_path=csv_path, rows=rows, fieldnames=fieldnames)
        updated_by_queue[csv_path.as_posix()] = updates

    return {
        "schema_version": "1.0",
        "task": "apply_vision_review_batch",
        "batch_csv": batch_csv.as_posix(),
        "dry_run": dry_run,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "updated_by_queue": updated_by_queue,
        "status_counts": dict(sorted(status_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = apply_review_batch(args.batch, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
