"""Finalize an audited visual spot review of promoted real RTSP frames."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def finalize_review(dataset_root: Path, reviewer: str, notes: str) -> dict:
    if not reviewer.strip() or not notes.strip():
        raise ValueError("reviewer and notes are required")
    manifest_path = dataset_root / "dataset_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    real_records = [
        record for record in payload["records"]
        if record["source_type"] == "real_rtsp_sanitized"
    ]
    if not real_records:
        raise ValueError("dataset contains no promoted real frames")
    for record in real_records:
        if not record.get("pseudo_labels"):
            raise ValueError("a promoted real frame has no pseudo-label")
        if record.get("privacy_transform") != (
            "heuristic_face_and_plate_region_blur"
        ):
            raise ValueError("unexpected privacy transform")
        record["privacy_status"] = "visual_spot_reviewed_agent"

    reviewed_at = datetime.now(timezone.utc).isoformat()
    payload["privacy_status"] = "visual_spot_reviewed_agent"
    payload["privacy_review"] = {
        "reviewer": reviewer,
        "reviewed_at_utc": reviewed_at,
        "scope": "all promoted real-positive frames",
        "reviewed_frame_count": len(real_records),
        "notes": notes,
        "human_approval_required_for_external_release": True,
    }
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, manifest_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", required=True)
    args = parser.parse_args()
    payload = finalize_review(args.dataset, args.reviewer, args.notes)
    print(json.dumps(payload["privacy_review"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
