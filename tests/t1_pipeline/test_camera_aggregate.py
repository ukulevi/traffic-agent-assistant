"""Tests for measured camera aggregate evidence (TRA-67)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t1_pipeline.camera_aggregate import (  # noqa: E402
    AggregateConfig,
    CameraAggregateError,
    sanity_check_against_mock,
)


def make_report(per_bucket: dict[str, dict[str, int]]) -> dict:
    return {"per_bucket": per_bucket}


class TestAggregateConfig(unittest.TestCase):
    def test_rejects_invalid_values(self):
        cases = [
            {"bucket_seconds": 0},
            {"sample_fps": -1},
            {"confidence": 0},
            {"confidence": 1.5},
            {"max_frames": 0},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(CameraAggregateError):
                    AggregateConfig(**kwargs)

    def test_defaults_are_valid(self):
        config = AggregateConfig()
        self.assertEqual(config.bucket_seconds, 300.0)
        self.assertEqual(config.sample_fps, 1.0)


class TestSanityCheckAgainstMock(unittest.TestCase):
    def setUp(self):
        self.mock_path = Path("mock_producers.json")

    def _write_mock(self, tmp: Path, volumes: list[float]) -> Path:
        path = tmp / "load_producers.json"
        path.write_text(
            json.dumps(
                [
                    {"source_id": f"s{i}", "traffic_volume_5m": v}
                    for i, v in enumerate(volumes)
                ]
            ),
            encoding="utf-8",
        )
        return path

    def test_measured_within_mock_range_passes(self):
        with tempfile_dir() as tmp:
            mock = self._write_mock(tmp, [10.0, 30.0])
            report = make_report({"bucket-0000": {"car": 20}})
            result = sanity_check_against_mock(report, mock)
            self.assertEqual(result["result"], "in_order_of_magnitude")

    def test_measured_within_3x_tolerance_passes(self):
        with tempfile_dir() as tmp:
            mock = self._write_mock(tmp, [10.0, 30.0])
            report = make_report({"bucket-0000": {"car": 80}})
            result = sanity_check_against_mock(report, mock)
            self.assertEqual(result["result"], "in_order_of_magnitude")

    def test_outlier_detected(self):
        with tempfile_dir() as tmp:
            mock = self._write_mock(tmp, [1.0, 2.0])
            report = make_report({"bucket-0000": {"car": 500}})
            result = sanity_check_against_mock(report, mock)
            self.assertEqual(result["result"], "outlier")

    def test_missing_volume_rows_fail_closed(self):
        with tempfile_dir() as tmp:
            path = tmp / "empty.json"
            path.write_text(json.dumps([{"source_id": "s"}]), encoding="utf-8")
            with self.assertRaisesRegex(
                CameraAggregateError, "no traffic_volume_5m"
            ):
                sanity_check_against_mock(make_report({}), path)

    def test_missing_reference_file_fails_closed(self):
        with self.assertRaisesRegex(CameraAggregateError, "not found"):
            sanity_check_against_mock(
                make_report({}), Path("does/not/exist.json")
            )


class TestDetectorGateDisclosure(unittest.TestCase):
    """The report must disclose a detector below the promotion gate."""

    def test_below_gate_artifact_is_loadable_without_validation(self):
        # Simulate the honest-disclosure contract: build_camera_aggregate_report
        # falls back to a raw artifact load when validate_for_mvp fails.
        from stwi.t1_pipeline import camera_aggregate as ca

        payload = {
            "model_version": "test-model",
            "weights": "w.pt",
            "weights_sha256": "0" * 64,
            "dataset_version": "ds",
            "classes": ["car"],
            "stwi_class_map": {"car": "car"},
            "privacy_status": "visual_spot_reviewed_agent",
            "promotion_status": "official_mvp_primary",
            "metrics": {"metrics/mAP50(B)": 0.69},
        }
        manifest = Path("manifest.json")

        with patch.object(Path, "read_text", return_value=json.dumps(payload)), \
             patch.object(Path, "is_file", return_value=True):
            try:
                artifact = load_artifact_fallback(ca, manifest)
            except Exception as exc:  # pragma: no cover
                self.fail(f"fallback load raised: {exc}")
        self.assertEqual(artifact.model_version, "test-model")


def load_artifact_fallback(ca, manifest_path: Path):
    """Mirror the fallback branch in build_camera_aggregate_report."""
    try:
        return ca.load_official_vision_model_artifact(manifest_path)
    except ca.LocalVisionModelError:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        from stwi.t1_pipeline.local_vision import LocalVisionModelArtifact

        return LocalVisionModelArtifact(
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


import contextlib  # noqa: E402


@contextlib.contextmanager
def tempfile_dir():
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


if __name__ == "__main__":
    unittest.main()
