"""Benchmark a registered external detector candidate on the STWI dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stwi.tooling.vision_training.benchmark import run_external_benchmark

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
    return run_external_benchmark(
        manifest_path=manifest_path,
        source_root=source_root,
        output_root=output_root,
        splits=splits,
        confidence=confidence,
        iou_threshold=iou_threshold,
        image_size=image_size,
        device=device,
        min_box_area=min_box_area,
        max_images=max_images,
        baseline_map50=baseline_map50,
        evaluator=evaluate_roi_ap,
    )


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
