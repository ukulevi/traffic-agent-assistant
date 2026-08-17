from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import benchmark_external_vision_model as cli
from stwi.tooling.vision_training import benchmark


class ExternalVisionBenchmarkTest(unittest.TestCase):
    def test_runs_and_persists_external_benchmark_summary(self) -> None:
        manifest = {
            "model_id": "owner/traffic-yolo",
            "source_url": "https://example.com/model",
            "source_license": "mit",
            "weights": "C:/private/best.pt",
            "weights_sha256": "a" * 64,
            "stwi_class_map": {"car": "car"},
            "class_aliases": {"motor": "motorcycle"},
            "promotion_gate": {"min_map50": 0.85},
        }
        evaluator = mock.Mock(
            return_value={"metrics": {"mAP50_roi": 0.90}, "seconds_per_image": 0.05}
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "benchmark"
            with mock.patch.object(benchmark, "load_external_manifest", return_value=manifest):
                summary = benchmark.run_external_benchmark(
                    manifest_path=Path("manifest.json"), source_root=Path("source"),
                    output_root=output, splits=["val"], confidence=0.05,
                    iou_threshold=0.5, image_size=640, device="cpu",
                    min_box_area=0.0, max_images=200, baseline_map50=0.69,
                    evaluator=evaluator,
                    generated_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
                )
            written = json.loads((output / "external_benchmark_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(written, summary)
        self.assertTrue(summary["promotion_boundary"]["requires_human_approval"])
        self.assertTrue(summary["promotion_boundary"]["not_promoted_by_this_script"])

    def test_cli_wrapper_forwards_arguments_and_evaluator(self) -> None:
        with mock.patch.object(cli, "run_external_benchmark", return_value={"ok": True}) as run:
            result = cli.benchmark_external_model(
                manifest_path=Path("manifest.json"), source_root=Path("source"),
                output_root=Path("output"), splits=["test"], confidence=0.1,
                iou_threshold=0.6, image_size=320, device="cpu",
                min_box_area=0.2, max_images=None, baseline_map50=0.8,
            )

        self.assertEqual(result, {"ok": True})
        self.assertIs(run.call_args.kwargs["evaluator"], cli.evaluate_roi_ap)
        self.assertEqual(run.call_args.kwargs["splits"], ["test"])


if __name__ == "__main__":
    unittest.main()
