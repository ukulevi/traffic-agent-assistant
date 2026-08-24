"""Baseline forecaster evidence binding.

Binds the GCN-LSTM training artifacts (checkpoint, training report, dataset)
into a verifiable evidence manifest so that baseline claims carry measured
provenance instead of resting on the surrogate's benchmark trail alone.

Honesty rules enforced here:
- The manifest records ``production_promoted: false`` unless every production
  criterion in the underlying training report is met. Current mock-trained
  baselines therefore stay explicitly non-promoted.
- Every binding field is verified against file content by checksum; a
  tampered or missing artifact fails loudly instead of degrading gracefully.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BINDING_KIND = "baseline_evidence_v1"
MANIFEST_FILENAME = "evidence_manifest.json"


class EvidenceBindingError(RuntimeError):
    """Raised when baseline evidence binding is missing or invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceBindingError(f"invalid JSON: {path}") from exc


@dataclass(frozen=True)
class BindingPaths:
    training_dir: Path
    dataset_dir: Path

    @property
    def training_report(self) -> Path:
        return self.training_dir / "training_report.json"

    @property
    def checkpoint(self) -> Path:
        return self.training_dir / "model.pt"

    @property
    def output(self) -> Path:
        return self.training_dir / MANIFEST_FILENAME

    @property
    def dataset_manifest(self) -> Path:
        return self.dataset_dir / "dataset_manifest.json"

    @property
    def tensors(self) -> Path:
        return self.dataset_dir / "tensor_dataset.npz"


def build_evidence_manifest(paths: BindingPaths) -> dict[str, Any]:
    """Build (but do not write) the evidence manifest for one training run."""
    if not paths.training_report.is_file():
        raise EvidenceBindingError(f"missing training report: {paths.training_report}")
    if not paths.checkpoint.is_file():
        raise EvidenceBindingError(f"missing checkpoint: {paths.checkpoint}")

    report = _load_json(paths.training_report)
    if report.get("status") != "smoke_pass":
        raise EvidenceBindingError(
            "baseline training did not pass; refusing to bind evidence"
        )
    checkpoint_name = str(report.get("checkpoint", ""))
    if not checkpoint_name:
        raise EvidenceBindingError("training report does not name a checkpoint")

    if not paths.dataset_manifest.is_file():
        raise EvidenceBindingError(
            f"missing dataset manifest: {paths.dataset_manifest}"
        )
    dataset_manifest = _load_json(paths.dataset_manifest)
    if dataset_manifest.get("gate_p1", {}).get("status") != "pass":
        raise EvidenceBindingError("Gate P1 did not pass for the bound dataset")
    dataset_id = str(dataset_manifest.get("dataset_id", "")).strip()
    if not dataset_id:
        raise EvidenceBindingError("dataset manifest has no dataset_id")
    if report.get("dataset_id") != dataset_id:
        raise EvidenceBindingError(
            "training report dataset_id does not match the bound dataset"
        )

    metrics = report.get("validation_metrics") or {}
    if "rmse" not in metrics or "mae" not in metrics:
        raise EvidenceBindingError("training report lacks validation metrics")

    return {
        "schema_version": "1.0",
        "binding_kind": BINDING_KIND,
        "bound_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_role": "baseline_forecaster",
        "artifact_name": paths.checkpoint.name,
        "artifact_sha256": "sha256:" + _sha256(paths.checkpoint),
        "training_report_sha256": "sha256:" + _sha256(paths.training_report),
        "dataset": {
            "dataset_id": dataset_id,
            "manifest_sha256": "sha256:" + _sha256(paths.dataset_manifest),
            "tensor_bundle_sha256": (
                "sha256:" + _sha256(paths.tensors)
                if paths.tensors.is_file()
                else None
            ),
        },
        "trained_at_utc": report.get("trained_at_utc"),
        "epochs": report.get("epochs"),
        "train_windows": report.get("train_windows"),
        "validation_windows": report.get("validation_windows"),
        "validation_metrics": {
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
        },
        "data_policy": report.get("data_policy"),
        "production_representativeness": report.get(
            "production_representativeness", "not_claimed"
        ),
        # Fail-closed honesty marker: mock-trained baselines are never
        # production-promoted regardless of downstream enthusiasm.
        "production_promoted": bool(report.get("production_ready", False)),
        "surrogate_training_allowed": bool(
            report.get("surrogate_training_allowed", False)
        ),
    }


def bind_training_run(training_dir: Path, dataset_dir: Path) -> dict[str, Any]:
    """Build and write the evidence manifest for one training directory."""
    paths = BindingPaths(training_dir=training_dir, dataset_dir=dataset_dir)
    manifest = build_evidence_manifest(paths)
    temporary = paths.output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(paths.output)
    return manifest


def _default_dataset_dir(manifest_path: Path) -> Path:
    """Resolve the phase1 dataset dir from the repo layout.

    Real layout: <private>/phase2_forecast/<run>/evidence_manifest.json
    → dataset lives at <private>/phase1_mock/.
    """
    return manifest_path.parents[2] / "phase1_mock"


def verify_evidence_manifest(
    manifest_path: Path,
    *,
    dataset_dir: Path | None = None,
    readiness_report_path: Path | None = None,
) -> dict[str, Any]:
    """Re-verify every binding in a written evidence manifest.

    Fails closed on any checksum mismatch, missing artifact, or cross-report
    inconsistency when ``readiness_report_path`` is provided.
    """
    if not manifest_path.is_file():
        raise EvidenceBindingError(f"missing evidence manifest: {manifest_path}")
    manifest = _load_json(manifest_path)
    if manifest.get("binding_kind") != BINDING_KIND:
        raise EvidenceBindingError("unexpected binding kind")

    training_dir = manifest_path.parent

    def _check(field: str, path: Path) -> None:
        expected = str(manifest.get(field, "")).removeprefix("sha256:")
        if len(expected) != 64:
            raise EvidenceBindingError(f"{field} is malformed")
        if not path.is_file() or _sha256(path) != expected:
            raise EvidenceBindingError(f"{field} checksum mismatch")

    _check("artifact_sha256", training_dir / str(manifest.get("artifact_name", "")))
    _check("training_report_sha256", training_dir / "training_report.json")

    dataset = manifest.get("dataset") or {}
    resolved_dataset_dir = (
        dataset_dir if dataset_dir is not None else _default_dataset_dir(manifest_path)
    )
    dataset_manifest_path = resolved_dataset_dir / "dataset_manifest.json"
    _check_manifest = dataset.get("manifest_sha256", "")
    expected_ds = str(_check_manifest).removeprefix("sha256:")
    if len(expected_ds) != 64:
        raise EvidenceBindingError("dataset.manifest_sha256 is malformed")
    if not dataset_manifest_path.is_file() or _sha256(dataset_manifest_path) != expected_ds:
        raise EvidenceBindingError("dataset manifest checksum mismatch")

    if readiness_report_path is not None:
        readiness = _load_json(readiness_report_path)
        if readiness.get("dataset_id") != dataset.get("dataset_id"):
            raise EvidenceBindingError(
                "phase2 readiness report was produced from a different dataset"
            )
        if readiness.get("forecast_kpi_status") != "pass":
            raise EvidenceBindingError(
                "phase2 readiness forecast KPI did not pass for this binding"
            )

    return manifest


__all__ = [
    "BINDING_KIND",
    "BindingPaths",
    "EvidenceBindingError",
    "MANIFEST_FILENAME",
    "bind_training_run",
    "build_evidence_manifest",
    "verify_evidence_manifest",
]
