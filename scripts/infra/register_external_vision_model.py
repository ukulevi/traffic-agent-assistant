"""Register a downloaded open-source detector candidate for local STWI tests."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.validation.evaluate_vision_roi_ap import (
        normalize_class_aliases,
        normalize_prompt_classes,
    )
    from scripts.training.promote_vision_model import REQUIRED_STWI_CLASSES
    from scripts.training.train_vision_model import sha256_file
except ModuleNotFoundError:
    from evaluate_vision_roi_ap import normalize_class_aliases, normalize_prompt_classes
    from promote_vision_model import REQUIRED_STWI_CLASSES
    from train_vision_model import sha256_file


def slugify_model_id(model_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_id.strip())
    slug = slug.strip("._-").lower()
    if not slug:
        raise ValueError("model id must contain at least one safe character")
    return slug


def normalize_source_classes(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        class_name = value.strip().lower()
        if not class_name or class_name in seen:
            continue
        normalized.append(class_name)
        seen.add(class_name)
    return normalized


def build_class_map(values: list[str] | None) -> dict[str, str]:
    return normalize_class_aliases(values)


def copy_candidate_weights(
    *,
    weights_path: Path,
    candidate_dir: Path,
    overwrite: bool,
) -> Path:
    if not weights_path.is_file():
        raise FileNotFoundError(f"weights file is missing: {weights_path}")
    target = candidate_dir / weights_path.name
    if target.exists() and not overwrite:
        if sha256_file(target) == sha256_file(weights_path):
            return target
        raise FileExistsError(
            f"target weights already exist with different content: {target}"
        )
    shutil.copy2(weights_path, target)
    return target


def register_external_model(
    *,
    model_id: str,
    source_url: str,
    source_license: str,
    weights_path: Path,
    output_root: Path,
    model_family: str,
    source_classes: list[str] | None,
    class_map_values: list[str] | None,
    class_alias_values: list[str] | None,
    prompt_classes: list[str] | None,
    reviewer: str,
    notes: str,
    copy_weights: bool,
    overwrite: bool,
) -> dict[str, Any]:
    if not source_url.startswith("https://"):
        raise ValueError("source-url must be an https URL")
    if not source_license.strip():
        raise ValueError("source-license is required")
    candidate_dir = output_root / slugify_model_id(model_id)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    registered_weights = (
        copy_candidate_weights(
            weights_path=weights_path,
            candidate_dir=candidate_dir,
            overwrite=overwrite,
        )
        if copy_weights
        else weights_path
    )
    if not registered_weights.is_file():
        raise FileNotFoundError(f"weights file is missing: {registered_weights}")

    class_map = build_class_map(class_map_values)
    aliases = normalize_class_aliases(class_alias_values)
    mapped_classes = {target for target in class_map.values() if target}
    missing_classes = sorted(REQUIRED_STWI_CLASSES - mapped_classes)
    status = (
        "ready_for_local_benchmark"
        if not missing_classes
        else "needs_class_map_review"
    )
    manifest_path = candidate_dir / "external_model_manifest.json"
    manifest = {
        "schema_version": "1.0",
        "task": "external_vision_model_candidate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "source_url": source_url,
        "source_license": source_license.strip(),
        "model_family": model_family,
        "runtime_format": registered_weights.suffix.lower().lstrip(".") or "unknown",
        "weights": str(registered_weights),
        "weights_sha256": sha256_file(registered_weights),
        "weights_size_bytes": registered_weights.stat().st_size,
        "manifest_path": str(manifest_path),
        "source_classes": normalize_source_classes(source_classes),
        "stwi_class_map": class_map,
        "class_aliases": aliases,
        "prompt_classes": normalize_prompt_classes(prompt_classes),
        "missing_stwi_classes": missing_classes,
        "candidate_status": status,
        "promotion_gate": {
            "min_map50": 0.85,
            "requires_validation_split": True,
            "requires_test_split": True,
            "requires_latency_record": True,
            "requires_privacy_review": True,
            "requires_human_approval": True,
        },
        "review": {
            "reviewer": reviewer,
            "notes": notes,
            "license_is_self_reported": True,
            "not_promotable_without_local_metrics": True,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-license", required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/derived/private/vision_external_models"),
    )
    parser.add_argument(
        "--model-family",
        choices=["yolo", "yolo_world", "rtdetr"],
        default="yolo",
    )
    parser.add_argument("--source-class", action="append", default=None)
    parser.add_argument(
        "--class-map",
        action="append",
        default=None,
        help="Map source class to STWI class using SOURCE:TARGET.",
    )
    parser.add_argument(
        "--class-alias",
        action="append",
        default=None,
        help="Map predicted class name during evaluation using SOURCE:TARGET.",
    )
    parser.add_argument("--prompt-class", action="append", default=None)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--copy-weights", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest = register_external_model(
        model_id=args.model_id,
        source_url=args.source_url,
        source_license=args.source_license,
        weights_path=args.weights,
        output_root=args.output_root,
        model_family=args.model_family,
        source_classes=args.source_class,
        class_map_values=args.class_map,
        class_alias_values=args.class_alias,
        prompt_classes=args.prompt_class,
        reviewer=args.reviewer,
        notes=args.notes,
        copy_weights=args.copy_weights,
        overwrite=args.overwrite,
    )
    print(json.dumps({
        "candidate_status": manifest["candidate_status"],
        "manifest": manifest["manifest_path"],
        "weights": manifest["weights"],
        "missing_stwi_classes": manifest["missing_stwi_classes"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
