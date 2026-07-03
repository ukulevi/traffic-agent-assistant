"""Vision detector training, registration, and promotion helpers."""

from stwi.tooling.vision_training.external_models import (
    build_class_map,
    build_external_verdict,
    copy_candidate_weights,
    fetch_external_weight,
    load_external_manifest,
    normalize_class_aliases,
    normalize_prompt_classes,
    normalize_sha256,
    normalize_source_classes,
    register_external_model,
    require_https_url,
    slugify_model_id,
    write_stream_with_sha256,
)
from stwi.tooling.vision_training.promotion import (
    REQUIRED_STWI_CLASSES,
    metric_value,
    promote_artifact,
    validate_artifact_for_promotion,
)

__all__ = [
    "REQUIRED_STWI_CLASSES",
    "build_class_map",
    "build_external_verdict",
    "copy_candidate_weights",
    "fetch_external_weight",
    "load_external_manifest",
    "metric_value",
    "normalize_class_aliases",
    "normalize_prompt_classes",
    "normalize_sha256",
    "normalize_source_classes",
    "promote_artifact",
    "register_external_model",
    "require_https_url",
    "slugify_model_id",
    "validate_artifact_for_promotion",
    "write_stream_with_sha256",
]
