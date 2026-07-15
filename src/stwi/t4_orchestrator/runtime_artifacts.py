"""Fail-closed runtime artifact manifests for production inference."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeArtifactError(RuntimeError):
    """Raised when production artifact evidence is missing or invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class RuntimeArtifact:
    role: str
    model_version: str
    data_version: str
    artifact_name: str
    artifact_sha256: str
    manifest_sha256: str
    uncertainty_threshold: float
    ood_threshold: float

    @classmethod
    def load(cls, manifest_path: Path, *, expected_role: str) -> "RuntimeArtifact":
        if not manifest_path.is_file():
            raise RuntimeArtifactError(f"missing {expected_role} manifest")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeArtifactError(f"invalid {expected_role} manifest") from exc
        if payload.get("artifact_role") != expected_role:
            raise RuntimeArtifactError(f"unexpected {expected_role} artifact role")
        promotion = payload.get("promotion") or {}
        if promotion.get("status") != "promoted" or promotion.get("provisional") is not False:
            raise RuntimeArtifactError(f"{expected_role} artifact is not production-promoted")
        calibration = payload.get("calibration") or {}
        if calibration.get("status") != "calibrated":
            raise RuntimeArtifactError(f"{expected_role} artifact is uncalibrated")
        try:
            expires_at = datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeArtifactError(f"{expected_role} artifact has invalid expiry") from exc
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise RuntimeArtifactError(f"{expected_role} artifact is stale")

        artifact_path = Path(str(payload.get("artifact_path", "")))
        if not artifact_path.is_absolute():
            artifact_path = (manifest_path.parent / artifact_path).resolve()
        if not artifact_path.is_file():
            raise RuntimeArtifactError(f"missing {expected_role} artifact")
        expected_sha256 = str(payload.get("artifact_sha256", "")).removeprefix("sha256:")
        actual_sha256 = _sha256(artifact_path)
        if len(expected_sha256) != 64 or actual_sha256 != expected_sha256:
            raise RuntimeArtifactError(f"{expected_role} artifact checksum mismatch")

        try:
            uncertainty_threshold = float(calibration["uncertainty_threshold"])
            ood_threshold = float(calibration["ood_threshold"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeArtifactError(f"{expected_role} thresholds are invalid") from exc
        if not 0 <= uncertainty_threshold <= 1 or not 0 <= ood_threshold <= 1:
            raise RuntimeArtifactError(f"{expected_role} thresholds are out of range")

        required = ("model_version", "data_version", "artifact_name")
        if any(not str(payload.get(field, "")).strip() for field in required):
            raise RuntimeArtifactError(f"{expected_role} provenance is incomplete")
        return cls(
            role=expected_role,
            model_version=str(payload["model_version"]),
            data_version=str(payload["data_version"]),
            artifact_name=str(payload["artifact_name"]),
            artifact_sha256="sha256:" + actual_sha256,
            manifest_sha256="sha256:" + _sha256(manifest_path),
            uncertainty_threshold=uncertainty_threshold,
            ood_threshold=ood_threshold,
        )

    def audit_dict(self) -> dict[str, Any]:
        return {
            "artifact_name": self.artifact_name,
            "model_version": self.model_version,
            "data_version": self.data_version,
            "artifact_sha256": self.artifact_sha256,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True)
class RuntimeArtifactSet:
    baseline: RuntimeArtifact
    surrogate: RuntimeArtifact

    @classmethod
    def load(cls, *, baseline_manifest: Path, surrogate_manifest: Path) -> "RuntimeArtifactSet":
        return cls(
            baseline=RuntimeArtifact.load(
                baseline_manifest, expected_role="baseline_forecaster"
            ),
            surrogate=RuntimeArtifact.load(
                surrogate_manifest, expected_role="surrogate_ensemble"
            ),
        )

    @property
    def model_version(self) -> str:
        return f"{self.baseline.model_version}+{self.surrogate.model_version}"

    @property
    def data_version(self) -> str:
        return f"{self.baseline.data_version}+{self.surrogate.data_version}"

    def audit_dict(self) -> dict[str, dict[str, Any]]:
        return {
            "baseline_forecaster": self.baseline.audit_dict(),
            "surrogate_ensemble": self.surrogate.audit_dict(),
        }


__all__ = ["RuntimeArtifact", "RuntimeArtifactError", "RuntimeArtifactSet"]
