"""Validated Tier-1 ingestion records and fail-closed dead letters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping


SCHEMA_VERSION = "1.0"
QUALITY_FLAGS = frozenset({"valid", "late_event", "degraded", "outlier", "calibration_required"})


@dataclass(frozen=True)
class SensorRecord:
    schema_version: str
    source_id: str
    node_id: str
    feature: str
    value: float
    unit: str
    observed_at: datetime
    received_at: datetime
    quality_flag: str = "valid"


@dataclass(frozen=True)
class DeadLetter:
    reason: str
    source_id: str | None
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class CameraAggregate:
    source_id: str
    node_id: str
    window_start: datetime
    traffic_volume_5m: float
    avg_speed_kmh: float | None
    heavy_vehicle_ratio: float
    calibration_approved: bool
    quality_flag: str


def validate_sensor_record(
    payload: Mapping[str, Any],
    known_nodes: frozenset[str],
    expected_units: Mapping[str, str],
    late_tolerance: timedelta = timedelta(minutes=15),
) -> SensorRecord | DeadLetter:
    try:
        observed_at = payload["observed_at"]
        received_at = payload["received_at"]
        if not isinstance(observed_at, datetime) or not isinstance(
            received_at, datetime
        ):
            raise ValueError("timestamps must be datetime")
        if observed_at.utcoffset() is None or received_at.utcoffset() is None:
            raise ValueError("timestamps must include UTC offset")
        feature = str(payload["feature"])
        node_id = str(payload["node_id"])
        if payload["schema_version"] != SCHEMA_VERSION:
            raise ValueError("unsupported schema version")
        if node_id not in known_nodes:
            raise ValueError("unknown node")
        if feature not in expected_units:
            raise ValueError("unknown feature")
        if payload["unit"] != expected_units[feature]:
            raise ValueError("unit mismatch")
        quality_flag = str(payload.get("quality_flag", "valid"))
        if quality_flag not in QUALITY_FLAGS:
            raise ValueError("invalid quality flag")
        if received_at - observed_at > late_tolerance:
            quality_flag = "late_event"
        return SensorRecord(
            schema_version=SCHEMA_VERSION,
            source_id=str(payload["source_id"]),
            node_id=node_id,
            feature=feature,
            value=float(payload["value"]),
            unit=str(payload["unit"]),
            observed_at=observed_at,
            received_at=received_at,
            quality_flag=quality_flag,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return DeadLetter(
            reason=str(exc),
            source_id=(
                str(payload.get("source_id"))
                if payload.get("source_id") is not None
                else None
            ),
            payload=payload,
        )


def publish_camera_aggregate(
    *,
    source_id: str,
    node_id: str,
    window_start: datetime,
    traffic_volume_5m: float,
    avg_speed_kmh: float | None,
    heavy_vehicle_ratio: float,
    calibration_approved: bool,
) -> CameraAggregate:
    if traffic_volume_5m < 0 or not 0 <= heavy_vehicle_ratio <= 1:
        raise ValueError("invalid camera aggregate")
    if not calibration_approved:
        avg_speed_kmh = None
        quality_flag = "calibration_required"
    elif avg_speed_kmh is None or not 0 <= avg_speed_kmh <= 160:
        raise ValueError("approved calibration requires valid speed")
    else:
        quality_flag = "valid"
    return CameraAggregate(
        source_id=source_id,
        node_id=node_id,
        window_start=window_start,
        traffic_volume_5m=traffic_volume_5m,
        avg_speed_kmh=avg_speed_kmh,
        heavy_vehicle_ratio=heavy_vehicle_ratio,
        calibration_approved=calibration_approved,
        quality_flag=quality_flag,
    )


def camera_source_status(
    last_valid_aggregate_at: datetime | None,
    now: datetime,
    offline_after: timedelta = timedelta(minutes=15),
) -> str:
    if now.utcoffset() is None:
        raise ValueError("now must include UTC offset")
    if last_valid_aggregate_at is None:
        return "offline"
    if last_valid_aggregate_at.utcoffset() is None:
        raise ValueError("last aggregate timestamp must include UTC offset")
    return (
        "offline"
        if now - last_valid_aggregate_at > offline_after
        else "online"
    )
