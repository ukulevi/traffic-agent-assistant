"""Promote a reviewed local detector artifact as the official MVP detector."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.training.train_vision_model import sha256_file
except ModuleNotFoundError:
    from train_vision_model import sha256_file


REQUIRED_STWI_CLASSES = {"car", "motorcycle", "bus", "truck"}


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/derived/private/vision_models/official"),
    )
    parser.add_argument("--min-map50", type=float, default=0.85)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--notes", required=True)
    args = parser.parse_args()
    promoted = promote_artifact(
        args.artifact,
        args.output_dir,
        min_map50=args.min_map50,
        approver=args.approver,
        notes=args.notes,
    )
    print(json.dumps({
        "model_version": promoted["model_version"],
        "promotion_status": promoted["promotion_status"],
        "weights": promoted["weights"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
