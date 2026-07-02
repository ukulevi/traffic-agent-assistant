"""Attach operator-confirmed video-time anchors to a quarantine manifest."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed


def frame_sequence(frame: dict[str, Any]) -> int:
    try:
        return int(Path(frame["path"]).stem.rsplit("_", maxsplit=1)[1])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("manifest contains an invalid frame path") from exc


def annotate_manifest(
    manifest_path: Path,
    recorded_start: datetime,
    recorded_end: datetime,
) -> dict[str, Any]:
    """Interpolate frame event times between two verified overlay anchors."""
    if recorded_start.utcoffset() is None or recorded_end.utcoffset() is None:
        raise ValueError("recorded timestamps must include UTC offsets")
    if recorded_end <= recorded_start:
        raise ValueError("recorded_end must be after recorded_start")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = payload.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("manifest must contain at least two frames")
    if payload.get("privacy_status") != "needs_review":
        raise ValueError("only a quarantine manifest can be annotated")

    sequences = [frame_sequence(frame) for frame in frames]
    first_sequence = min(sequences)
    last_sequence = max(sequences)
    if first_sequence == last_sequence:
        raise ValueError("frame sequence range is empty")

    duration = recorded_end - recorded_start
    for frame, sequence in zip(frames, sequences, strict=True):
        fraction = (sequence - first_sequence) / (
            last_sequence - first_sequence
        )
        frame["recorded_at"] = (
            recorded_start + duration * fraction
        ).isoformat()
        frame["timestamp_quality"] = (
            "operator_confirmed_overlay"
            if sequence in {first_sequence, last_sequence}
            else "interpolated_between_overlay_anchors"
        )

    payload["recorded_start"] = recorded_start.isoformat()
    payload["recorded_end"] = recorded_end.isoformat()
    payload["recorded_time_source"] = (
        "operator_confirmed_overlay_anchors_interpolated"
    )
    payload["recorded_time_anchors"] = [
        {"frame": frames[sequences.index(first_sequence)]["path"],
         "recorded_at": recorded_start.isoformat()},
        {"frame": frames[sequences.index(last_sequence)]["path"],
         "recorded_at": recorded_end.isoformat()},
    ]
    payload["split_group"] = (
        f"{payload['source_id']}:{recorded_start.date().isoformat()}"
    )

    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, manifest_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Annotate a quarantined RTSP manifest with video time."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--recorded-start", type=parse_aware_datetime,
                        required=True)
    parser.add_argument("--recorded-end", type=parse_aware_datetime,
                        required=True)
    args = parser.parse_args()
    annotate_manifest(args.manifest, args.recorded_start, args.recorded_end)
    print(args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
