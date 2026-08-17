"""Reusable orchestration for external detector benchmarks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from stwi.tooling.vision_training.external_models import (
    build_external_verdict,
    load_external_manifest,
)


def run_external_benchmark(
    *,
    manifest_path: Path,
    source_root: Path,
    output_root: Path,
    splits: list[str],
    confidence: float,
    iou_threshold: float,
    image_size: int,
    device: str,
    min_box_area: float,
    max_images: int | None,
    baseline_map50: float | None,
    evaluator: Callable[..., dict[str, Any]],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a registered candidate without promoting it."""

    manifest = load_external_manifest(manifest_path)
    output_root.mkdir(parents=True, exist_ok=True)
    evaluation = evaluator(
        source_root=source_root,
        model_path=manifest["weights"],
        output_root=output_root,
        splits=splits,
        confidence=confidence,
        iou_threshold=iou_threshold,
        image_size=image_size,
        device=device,
        min_box_area=min_box_area,
        max_images=max_images,
        model_family=manifest.get("model_family", "yolo"),
        prompt_classes=manifest.get("prompt_classes", []),
        class_aliases=manifest.get("class_aliases", {}),
    )
    gate = manifest.get("promotion_gate", {})
    map50 = float(evaluation["metrics"]["mAP50_roi"])
    seconds_per_image = float(evaluation.get("seconds_per_image", 0.0))
    summary = {
        "schema_version": "1.0",
        "task": "external_vision_model_benchmark",
        "created_at_utc": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "external_model": {
            "model_id": manifest["model_id"], "source_url": manifest["source_url"],
            "source_license": manifest["source_license"], "manifest_path": str(manifest_path),
            "weights": manifest["weights"], "weights_sha256": manifest["weights_sha256"],
            "stwi_class_map": manifest["stwi_class_map"],
            "class_aliases": manifest.get("class_aliases", {}),
        },
        "evaluation": evaluation,
        "verdict": build_external_verdict(
            map50=map50, seconds_per_image=seconds_per_image,
            min_map50=float(gate.get("min_map50", 0.85)), splits=splits,
            max_images=max_images, baseline_map50=baseline_map50,
        ),
        "promotion_boundary": {
            "not_promoted_by_this_script": True,
            "requires_promote_vision_model_gate": True,
            "requires_privacy_review": True,
            "requires_human_approval": True,
        },
    }
    (output_root / "external_benchmark_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary
