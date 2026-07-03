"""Benchmark a registered external detector candidate on the STWI dataset."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stwi.tooling.vision_training.external_models import (
    build_external_verdict,
    load_external_manifest,
)

try:
    from scripts.validation.evaluate_vision_roi_ap import evaluate_roi_ap
except ModuleNotFoundError:
    from evaluate_vision_roi_ap import evaluate_roi_ap


def benchmark_external_model(
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
) -> dict[str, Any]:
    manifest = load_external_manifest(manifest_path)
    output_root.mkdir(parents=True, exist_ok=True)
    evaluation = evaluate_roi_ap(
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
    min_map50 = float(gate.get("min_map50", 0.85))
    map50 = float(evaluation["metrics"]["mAP50_roi"])
    seconds_per_image = float(evaluation.get("seconds_per_image", 0.0))
    verdict = build_external_verdict(
        map50=map50,
        seconds_per_image=seconds_per_image,
        min_map50=min_map50,
        splits=splits,
        max_images=max_images,
        baseline_map50=baseline_map50,
    )
    summary = {
        "schema_version": "1.0",
        "task": "external_vision_model_benchmark",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "external_model": {
            "model_id": manifest["model_id"],
            "source_url": manifest["source_url"],
            "source_license": manifest["source_license"],
            "manifest_path": str(manifest_path),
            "weights": manifest["weights"],
            "weights_sha256": manifest["weights_sha256"],
            "stwi_class_map": manifest["stwi_class_map"],
            "class_aliases": manifest.get("class_aliases", {}),
        },
        "evaluation": evaluation,
        "verdict": verdict,
        "promotion_boundary": {
            "not_promoted_by_this_script": True,
            "requires_promote_vision_model_gate": True,
            "requires_privacy_review": True,
            "requires_human_approval": True,
        },
    }
    (output_root / "external_benchmark_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split",
        choices=["train", "val", "test"],
        action="append",
        default=None,
    )
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--min-box-area", type=float, default=0.0)
    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--baseline-map50", type=float, default=None)
    args = parser.parse_args()
    if not 0 <= args.min_box_area < 1:
        raise ValueError("min-box-area must be in [0, 1)")
    summary = benchmark_external_model(
        manifest_path=args.manifest,
        source_root=args.source,
        output_root=args.output,
        splits=args.split or ["val"],
        confidence=args.conf,
        iou_threshold=args.iou_threshold,
        image_size=args.imgsz,
        device=args.device,
        min_box_area=args.min_box_area,
        max_images=args.max_images,
        baseline_map50=args.baseline_map50,
    )
    print(json.dumps({
        "model_id": summary["external_model"]["model_id"],
        "status": summary["verdict"]["status"],
        "map50": summary["verdict"]["map50"],
        "seconds_per_image": summary["verdict"]["seconds_per_image"],
        "summary": str(args.output / "external_benchmark_summary.json"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
