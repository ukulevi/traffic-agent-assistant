"""Local open-source detector artifact loading for Tier 1 perception."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OFFICIAL_MANIFEST = Path(
    "data/derived/private/vision_models/official/model_artifact.json"
)


class LocalVisionModelError(RuntimeError):
    """Raised when the local vision model artifact is missing or unsafe."""


@dataclass(frozen=True)
class LocalVisionModelArtifact:
    """Versioned local detector artifact used by the CCTV aggregate path."""

    model_version: str
    weights: Path
    weights_sha256: str
    dataset_version: str
    classes: tuple[str, ...]
    stwi_class_map: Mapping[str, str | None]
    privacy_status: str
    promotion_status: str
    metrics: Mapping[str, Any]

    @classmethod
    def from_file(cls, path: Path) -> "LocalVisionModelArtifact":
        payload = json.loads(path.read_text(encoding="utf-8"))
        weights = Path(payload["weights"])
        return cls(
            model_version=str(payload["model_version"]),
            weights=weights,
            weights_sha256=str(payload["weights_sha256"]),
            dataset_version=str(payload["dataset_version"]),
            classes=tuple(payload["classes"]),
            stwi_class_map=dict(payload["stwi_class_map"]),
            privacy_status=str(payload["privacy_status"]),
            promotion_status=str(payload["promotion_status"]),
            metrics=dict(payload.get("metrics", {})),
        )

    def validate_for_mvp(self) -> None:
        if self.privacy_status != "visual_spot_reviewed_agent":
            raise LocalVisionModelError("official model requires finalized privacy review")
        if self.promotion_status != "official_mvp_primary":
            raise LocalVisionModelError("model artifact is not promoted as official MVP primary")
        if not self.weights.is_file():
            raise LocalVisionModelError(f"missing weights: {self.weights}")
        required = {"car", "motorcycle", "bus", "truck"}
        mapped = {value for value in self.stwi_class_map.values() if value}
        missing = required - mapped
        if missing:
            names = ", ".join(sorted(missing))
            raise LocalVisionModelError(f"model class map misses required STWI classes: {names}")


def load_official_vision_model_artifact(
    manifest_path: Path = DEFAULT_OFFICIAL_MANIFEST,
) -> LocalVisionModelArtifact:
    """Load the promoted local detector artifact without importing YOLO."""

    if not manifest_path.is_file():
        raise LocalVisionModelError(f"official model manifest not found: {manifest_path}")
    artifact = LocalVisionModelArtifact.from_file(manifest_path)
    artifact.validate_for_mvp()
    return artifact
