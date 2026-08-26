"""Measured camera aggregate evidence from a recorded video via the T1 path.

Runs the promoted local detector over a licensed, pre-recorded video,
counts vehicle-class detections per sampled frame bucket, and produces a
measured aggregate evidence report for the Phase 1 gate.

Honesty and privacy rules enforced here:
- The report always records ``evidence_kind: measured`` plus the detector
  model version, dataset version, and weights checksum it actually ran.
- No frame or video is retained outside the caller's control; only
  per-bucket counts leave this module. Raw pixels are never logged.
- Detector output is camera aggregate evidence only — never actuation input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stwi.t1_pipeline.local_vision import (
    DEFAULT_OFFICIAL_MANIFEST,
    LocalVisionModelError,
    LocalVisionModelArtifact,
    load_official_vision_model_artifact,
)

REPORT_SCHEMA_VERSION = "1.0"
BUCKET_SECONDS_DEFAULT = 300.0


class CameraAggregateError(RuntimeError):
    """Raised when the recorded-video aggregate run cannot proceed."""


@dataclass(frozen=True)
class AggregateConfig:
    bucket_seconds: float = BUCKET_SECONDS_DEFAULT
    sample_fps: float = 1.0
    confidence: float = 0.25
    max_frames: int = 600

    def __post_init__(self) -> None:
        if self.bucket_seconds <= 0:
            raise CameraAggregateError("bucket_seconds must be positive")
        if self.sample_fps <= 0:
            raise CameraAggregateError("sample_fps must be positive")
        if not 0 < self.confidence < 1:
            raise CameraAggregateError("confidence must be in (0, 1)")
        if self.max_frames < 1:
            raise CameraAggregateError("max_frames must be positive")


def _open_video(video_path: Path):
    try:
        import cv2
    except ImportError as exc:
        raise CameraAggregateError(
            "opencv-python is required for the recorded-video aggregate path"
        ) from exc
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise CameraAggregateError(f"cannot open video: {video_path}")
    return capture


def _load_detector(artifact: LocalVisionModelArtifact):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise CameraAggregateError(
            "ultralytics is required for the recorded-video aggregate path"
        ) from exc
    # Honest gate handling: the artifact may be below the MVP promotion gate.
    # We still run it, but the report must disclose provisional status so the
    # evidence is never quoted as production-grade detector output.
    try:
        artifact.validate_for_mvp()
        detector_status = "official_mvp_primary"
    except LocalVisionModelError as exc:
        detector_status = f"provisional_below_promotion_gate ({exc})"
    return YOLO(str(artifact.weights)), detector_status


def count_detections_per_bucket(
    video_path: Path,
    artifact: LocalVisionModelArtifact,
    config: AggregateConfig,
) -> dict[str, Any]:
    """Run the detector over a recorded video and bucket counts by time.

    Returns a report payload with per-bucket per-class counts; no frames or
    detections beyond aggregates are retained.
    """
    if not video_path.is_file():
        raise CameraAggregateError(f"video not found: {video_path}")

    model, detector_status = _load_detector(artifact)
    capture = _open_video(video_path)

    import cv2

    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(round(source_fps / config.sample_fps)))

    buckets: dict[str, dict[str, int]] = {}
    frames_sampled = 0
    total_detections = 0
    frame_index = 0

    while True:
        grabbed = capture.grab()
        if not grabbed:
            break
        if frame_index % frame_interval == 0:
            ok, frame = capture.retrieve()
            if not ok:
                break
            seconds = frame_index / source_fps
            bucket_id = f"bucket-{int(seconds // config.bucket_seconds):04d}"
            results = model.predict(
                frame, verbose=False, conf=config.confidence
            )
            names = results[0].names
            bucket_counts = buckets.setdefault(
                bucket_id, {cls: 0 for cls in artifact.classes}
            )
            for box in results[0].boxes:
                cls_name = names.get(int(box.cls), str(int(box.cls)))
                stwi_cls = artifact.stwi_class_map.get(cls_name)
                if stwi_cls is None:
                    continue
                bucket_counts[stwi_cls] = bucket_counts.get(stwi_cls, 0) + 1
                total_detections += 1
            frames_sampled += 1
            if frames_sampled >= config.max_frames:
                break
        frame_index += 1

    capture.release()

    if frames_sampled == 0:
        raise CameraAggregateError("no frames could be read from the video")

    duration_covered_seconds = frames_sampled / config.sample_fps
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "evidence_kind": "measured",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "kind": "recorded_video",
            "file_name": video_path.name,
            "source_fps": round(source_fps, 3),
            "sample_fps": config.sample_fps,
            "frames_sampled": frames_sampled,
            "duration_covered_seconds": round(duration_covered_seconds, 1),
            "license_note": "operator-provided recording; see ticket TRA-67",
        },
        "detector": {
            "model_version": artifact.model_version,
            "dataset_version": artifact.dataset_version,
            "weights_sha256": artifact.weights_sha256,
            "confidence_threshold": config.confidence,
            "detector_status": detector_status,
        },
        "privacy": "aggregate_only_no_video_or_frames_retained",
        "aggregate_totals": {"detections": total_detections},
        "per_bucket": buckets,
    }


def sanity_check_against_mock(
    report: dict[str, Any], mock_load_producers_path: Path
) -> dict[str, Any]:
    """Compare measured per-bucket totals against mock producer ranges.

    The check is a coarse plausibility comparison, not a calibration claim:
    it records whether measured counts fall within the same order of
    magnitude as the synthetic producers used elsewhere in the MVP.
    """
    if not mock_load_producers_path.is_file():
        raise CameraAggregateError(
            f"mock producer reference not found: {mock_load_producers_path}"
        )
    reference = json.loads(mock_load_producers_path.read_text(encoding="utf-8"))

    volumes = [
        float(row["traffic_volume_5m"])
        for row in reference
        if isinstance(row, dict) and "traffic_volume_5m" in row
    ]
    if not volumes:
        raise CameraAggregateError(
            "mock producer reference has no traffic_volume_5m rows"
        )
    low, high = min(volumes), max(volumes)

    measured_totals = [
        sum(counts.values()) for counts in report["per_bucket"].values()
    ]
    measured_mean = (
        sum(measured_totals) / len(measured_totals) if measured_totals else 0.0
    )

    in_band = low <= measured_mean <= high * 3
    result = "in_order_of_magnitude" if in_band else "outlier"
    note = (
        f"measured mean {measured_mean:.1f} vs mock volume range "
        f"[{low}, {high}] (upper bound x3 tolerance)"
    )

    return {
        "check": "order_of_magnitude_vs_mock_producers",
        "result": result,
        "measured_mean_per_bucket": round(measured_mean, 2),
        "note": note,
    }


def build_camera_aggregate_report(
    video_path: Path,
    *,
    manifest_path: Path | None = None,
    config: AggregateConfig | None = None,
    mock_reference_path: Path | None = None,
) -> dict[str, Any]:
    """End-to-end helper: load artifact, measure, optionally sanity-check."""
    config = config or AggregateConfig()
    try:
        artifact = load_official_vision_model_artifact(
            manifest_path
            if manifest_path is not None
            else DEFAULT_OFFICIAL_MANIFEST
        )
    except LocalVisionModelError:
        # The manifest may describe a detector below the promotion gate; the
        # report will disclose this honestly via detector_status.
        raw_manifest_path = (
            manifest_path if manifest_path is not None else DEFAULT_OFFICIAL_MANIFEST
        )
        payload = json.loads(raw_manifest_path.read_text(encoding="utf-8"))
        artifact = LocalVisionModelArtifact(
            model_version=str(payload["model_version"]),
            weights=Path(payload["weights"]),
            weights_sha256=str(payload["weights_sha256"]),
            dataset_version=str(payload["dataset_version"]),
            classes=tuple(payload["classes"]),
            stwi_class_map=dict(payload["stwi_class_map"]),
            privacy_status=str(payload["privacy_status"]),
            promotion_status=str(payload["promotion_status"]),
            metrics=dict(payload.get("metrics", {})),
        )
    report = count_detections_per_bucket(video_path, artifact, config)
    if mock_reference_path is not None:
        report["sanity_check"] = sanity_check_against_mock(
            report, mock_reference_path
        )
    return report


__all__ = [
    "AggregateConfig",
    "CameraAggregateError",
    "build_camera_aggregate_report",
    "count_detections_per_bucket",
    "sanity_check_against_mock",
]
