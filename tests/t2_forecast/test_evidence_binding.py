"""Tests for baseline forecaster evidence binding (fail-closed)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t2_forecast.evidence_binding import (  # noqa: E402
    EvidenceBindingError,
    bind_training_run,
    build_evidence_manifest,
    verify_evidence_manifest,
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def make_fixture(root: Path) -> tuple[Path, Path]:
    """Create a minimal valid training + dataset fixture."""
    training_dir = root / "training"
    dataset_dir = root / "dataset"
    training_dir.mkdir()
    dataset_dir.mkdir()

    checkpoint = training_dir / "model.pt"
    checkpoint.write_bytes(b"weights-bytes")
    (training_dir / "training_report.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "smoke_pass",
                "trained_at_utc": "2026-08-23T00:00:00+00:00",
                "dataset_id": "ds-v1",
                "data_policy": "mock-first",
                "epochs": 2,
                "train_windows": 10,
                "validation_windows": 4,
                "validation_metrics": {"mae": 1.0, "rmse": 2.0},
                "checkpoint": "model.pt",
                "production_ready": False,
                "surrogate_training_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    manifest = dataset_dir / "dataset_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset_id": "ds-v1",
                "gate_p1": {"status": "pass"},
            }
        ),
        encoding="utf-8",
    )
    return training_dir, dataset_dir


class TestEvidenceBinding(unittest.TestCase):
    def test_bind_and_verify_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_dir, dataset_dir = make_fixture(root)
            manifest = bind_training_run(training_dir, dataset_dir)

            self.assertEqual(manifest["artifact_role"], "baseline_forecaster")
            self.assertFalse(manifest["production_promoted"])
            verified = verify_evidence_manifest(
                training_dir / "evidence_manifest.json",
                dataset_dir=dataset_dir,
            )
            self.assertEqual(verified["binding_kind"], manifest["binding_kind"])

    def test_tampered_checkpoint_fails_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_dir, dataset_dir = make_fixture(root)
            bind_training_run(training_dir, dataset_dir)
            (training_dir / "model.pt").write_bytes(b"tampered")

            with self.assertRaisesRegex(EvidenceBindingError, "checksum mismatch"):
                verify_evidence_manifest(
                    training_dir / "evidence_manifest.json",
                    dataset_dir=dataset_dir,
                )

    def test_tampered_dataset_manifest_fails_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_dir, dataset_dir = make_fixture(root)
            bind_training_run(training_dir, dataset_dir)
            ds_manifest = dataset_dir / "dataset_manifest.json"
            payload = json.loads(ds_manifest.read_text(encoding="utf-8"))
            payload["gate_p1"]["status"] = "fail"
            ds_manifest.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(
                EvidenceBindingError, "dataset manifest checksum mismatch"
            ):
                verify_evidence_manifest(
                    training_dir / "evidence_manifest.json",
                    dataset_dir=dataset_dir,
                )

    def test_binding_refuses_failed_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_dir, dataset_dir = make_fixture(root)
            report_path = training_dir / "training_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["status"] = "failed"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(
                EvidenceBindingError, "did not pass"
            ):
                build_evidence_manifest(
                    __import__(
                        "stwi.t2_forecast.evidence_binding", fromlist=["BindingPaths"]
                    ).BindingPaths(
                        training_dir=training_dir, dataset_dir=dataset_dir
                    )
                )

    def test_binding_refuses_dataset_id_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_dir, dataset_dir = make_fixture(root)
            report_path = training_dir / "training_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["dataset_id"] = "ds-other"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(EvidenceBindingError, "dataset_id"):
                bind_training_run(training_dir, dataset_dir)

    def test_readiness_crosscheck_rejects_other_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            training_dir, dataset_dir = make_fixture(root)
            bind_training_run(training_dir, dataset_dir)

            readiness = root / "readiness.json"
            readiness.write_text(
                json.dumps({"dataset_id": "ds-v2", "forecast_kpi_status": "pass"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvidenceBindingError, "different dataset"):
                verify_evidence_manifest(
                    training_dir / "evidence_manifest.json",
                    dataset_dir=dataset_dir,
                    readiness_report_path=readiness,
                )


if __name__ == "__main__":
    unittest.main()
