"""Promotion gate for reviewed local vision detector artifacts."""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stwi.utils.file_hash import sha256_file


REQUIRED_STWI_CLASSES = {"car", "motorcycle", "bus", "truck"}
DEFAULT_MVP_MAP50 = 0.85


def is_finite_number(value: Any, *, minimum: float = 0.0, maximum: float | None = None) -> bool:
    """Return whether an artifact number is usable as promotion evidence."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return math.isfinite(number) and number >= minimum and (
        maximum is None or number <= maximum
    )


def has_value(value: Any) -> bool:
    """Reject blank scalar metadata and empty structured metadata."""
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def metric_value(metrics: dict[str, Any], preferred_names: tuple[str, ...]) -> float | None:
    for name in preferred_names:
        value = metrics.get(name)
        if isinstance(value, (int, float)):
            return float(value)
    for key, value in metrics.items():
        normalized = key.lower().replace("_", "").replace("-", "")
        if "map50" in normalized and isinstance(value, (int, float)):
            return float(value)
    return None


def validate_artifact_for_promotion(
    artifact: dict[str, Any],
    *,
    min_map50: float,
) -> None:
    errors: list[str] = []
    if artifact.get("privacy_status") != "visual_spot_reviewed_agent":
        errors.append("privacy review is not finalized")
    weights = Path(str(artifact.get("weights", "")))
    if not weights.is_file():
        errors.append(f"weights file is missing: {weights}")
    elif artifact.get("weights_sha256") != sha256_file(weights):
        errors.append("weights sha256 does not match artifact")
    class_map = artifact.get("stwi_class_map")
    if not isinstance(class_map, dict):
        errors.append("missing stwi_class_map")
    else:
        mapped = {value for value in class_map.values() if value}
        missing = REQUIRED_STWI_CLASSES - mapped
        if missing:
            errors.append("missing STWI class mapping: " + ", ".join(sorted(missing)))
    metrics = artifact.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("missing training metrics")
    else:
        map50 = metric_value(metrics, ("metrics/mAP50(B)", "metrics/mAP50"))
        if map50 is None:
            errors.append("could not find mAP50 metric")
        elif map50 < min_map50:
            errors.append(f"mAP50 {map50:.4f} is below threshold {min_map50:.4f}")
    calibration = artifact.get("calibration")
    if not isinstance(calibration, dict):
        errors.append("missing calibration evidence")
    else:
        for field in ("confidence_threshold", "iou_threshold"):
            if not is_finite_number(calibration.get(field), maximum=1.0):
                errors.append(f"invalid calibration.{field}")
        if not is_finite_number(calibration.get("image_size"), minimum=1.0):
            errors.append("invalid calibration.image_size")
        if not has_value(calibration.get("roi_policy")):
            errors.append("invalid calibration.roi_policy")
    benchmark = artifact.get("benchmark")
    if not isinstance(benchmark, dict):
        errors.append("missing benchmark evidence")
    else:
        if not has_value(benchmark.get("profile")):
            errors.append("invalid benchmark.profile")
        p50 = benchmark.get("seconds_per_image_p50")
        p99 = benchmark.get("seconds_per_image_p99")
        if not is_finite_number(p50):
            errors.append("invalid benchmark.seconds_per_image_p50")
        if not is_finite_number(p99):
            errors.append("invalid benchmark.seconds_per_image_p99")
        elif is_finite_number(p50) and float(p99) < float(p50):
            errors.append("benchmark.seconds_per_image_p99 is below p50")
    legal_and_privacy = artifact.get("legal_and_privacy")
    if not isinstance(legal_and_privacy, dict):
        errors.append("missing legal_and_privacy evidence")
    else:
        for field in ("source_license", "privacy_status"):
            if not has_value(legal_and_privacy.get(field)):
                errors.append(f"invalid legal_and_privacy.{field}")
    if errors:
        raise ValueError("model promotion failed:\n- " + "\n- ".join(errors))


def promote_artifact(
    artifact_path: Path,
    output_dir: Path,
    *,
    min_map50: float,
    approver: str,
    notes: str,
) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    validate_artifact_for_promotion(artifact, min_map50=min_map50)
    output_dir.mkdir(parents=True, exist_ok=True)
    weights_source = Path(artifact["weights"])
    weights_target = output_dir / weights_source.name
    shutil.copy2(weights_source, weights_target)
    promoted = dict(artifact)
    promoted["weights"] = str(weights_target)
    promoted["weights_sha256"] = sha256_file(weights_target)
    promoted["promotion_status"] = "official_mvp_primary"
    promoted["promoted_at_utc"] = datetime.now(timezone.utc).isoformat()
    promoted["promotion_approval"] = {
        "approver": approver,
        "notes": notes,
        "scope": "Tier 1 local vehicle detector for aggregate evidence",
    }
    target_manifest = output_dir / "model_artifact.json"
    target_manifest.write_text(
        json.dumps(promoted, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return promoted
