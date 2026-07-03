"""External detector registration and verification helpers."""

from __future__ import annotations

import json
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

from stwi.tooling.vision_training.promotion import REQUIRED_STWI_CLASSES
from stwi.utils.file_hash import sha256_file


def normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError("expected-sha256 must be a 64-character hex digest")
    return normalized


def require_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("url must be an https URL")
    return url


def write_stream_with_sha256(
    *,
    source: BinaryIO,
    output_path: Path,
    expected_sha256: str,
    overwrite: bool,
    chunk_size: int = 1024 * 1024,
) -> dict[str, Any]:
    expected = normalize_sha256(expected_sha256)
    if output_path.exists():
        existing_sha = sha256_file(output_path)
        if existing_sha == expected:
            return {
                "status": "already_present",
                "path": str(output_path),
                "sha256": existing_sha,
                "size_bytes": output_path.stat().st_size,
            }
        if not overwrite:
            raise FileExistsError(
                f"existing file has different sha256 and overwrite is disabled: {output_path}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_name(output_path.name + ".part")
    if partial_path.exists():
        partial_path.unlink()
    with partial_path.open("wb") as handle:
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)

    actual_sha = sha256_file(partial_path)
    if actual_sha != expected:
        partial_path.unlink(missing_ok=True)
        raise ValueError(
            f"downloaded file sha256 mismatch: expected {expected}, got {actual_sha}"
        )
    partial_path.replace(output_path)
    return {
        "status": "downloaded",
        "path": str(output_path),
        "sha256": actual_sha,
        "size_bytes": output_path.stat().st_size,
    }


def fetch_external_weight(
    *,
    url: str,
    output_path: Path,
    expected_sha256: str,
    overwrite: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    safe_url = require_https_url(url)
    expected = normalize_sha256(expected_sha256)
    if output_path.exists() and sha256_file(output_path) == expected:
        result = {
            "status": "already_present",
            "path": str(output_path),
            "sha256": expected,
            "size_bytes": output_path.stat().st_size,
        }
    else:
        with urllib.request.urlopen(safe_url, timeout=timeout_seconds) as response:
            result = write_stream_with_sha256(
                source=response,
                output_path=output_path,
                expected_sha256=expected,
                overwrite=overwrite,
            )
    manifest = {
        "schema_version": "1.0",
        "task": "external_vision_model_weight_fetch",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": safe_url,
        "expected_sha256": expected,
        "result": result,
    }
    manifest_path = output_path.with_name(output_path.name + ".fetch_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def slugify_model_id(model_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_id.strip())
    slug = slug.strip("._-").lower()
    if not slug:
        raise ValueError("model id must contain at least one safe character")
    return slug


def normalize_source_classes(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        class_name = value.strip().lower()
        if not class_name or class_name in seen:
            continue
        normalized.append(class_name)
        seen.add(class_name)
    return normalized


def normalize_prompt_classes(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        class_name = value.strip().lower()
        if not class_name or class_name in seen:
            continue
        normalized.append(class_name)
        seen.add(class_name)
    return normalized


def normalize_class_aliases(values: list[str] | None) -> dict[str, str]:
    if not values:
        return {}
    aliases: dict[str, str] = {}
    for value in values:
        if ":" not in value:
            raise ValueError(
                "class aliases must use SOURCE:TARGET format, "
                f"got {value!r}"
            )
        source, target = value.split(":", maxsplit=1)
        source_name = source.strip().lower()
        target_name = target.strip().lower()
        if not source_name or not target_name:
            raise ValueError(
                "class aliases must include non-empty SOURCE and TARGET names"
            )
        aliases[source_name] = target_name
    return aliases


def build_class_map(values: list[str] | None) -> dict[str, str]:
    return normalize_class_aliases(values)


def copy_candidate_weights(
    *,
    weights_path: Path,
    candidate_dir: Path,
    overwrite: bool,
) -> Path:
    if not weights_path.is_file():
        raise FileNotFoundError(f"weights file is missing: {weights_path}")
    target = candidate_dir / weights_path.name
    if target.exists() and not overwrite:
        if sha256_file(target) == sha256_file(weights_path):
            return target
        raise FileExistsError(
            f"target weights already exist with different content: {target}"
        )
    shutil.copy2(weights_path, target)
    return target


def register_external_model(
    *,
    model_id: str,
    source_url: str,
    source_license: str,
    weights_path: Path,
    output_root: Path,
    model_family: str,
    source_classes: list[str] | None,
    class_map_values: list[str] | None,
    class_alias_values: list[str] | None,
    prompt_classes: list[str] | None,
    reviewer: str,
    notes: str,
    copy_weights: bool,
    overwrite: bool,
) -> dict[str, Any]:
    if not source_url.startswith("https://"):
        raise ValueError("source-url must be an https URL")
    if not source_license.strip():
        raise ValueError("source-license is required")
    candidate_dir = output_root / slugify_model_id(model_id)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    registered_weights = (
        copy_candidate_weights(
            weights_path=weights_path,
            candidate_dir=candidate_dir,
            overwrite=overwrite,
        )
        if copy_weights
        else weights_path
    )
    if not registered_weights.is_file():
        raise FileNotFoundError(f"weights file is missing: {registered_weights}")

    class_map = build_class_map(class_map_values)
    aliases = normalize_class_aliases(class_alias_values)
    mapped_classes = {target for target in class_map.values() if target}
    missing_classes = sorted(REQUIRED_STWI_CLASSES - mapped_classes)
    status = (
        "ready_for_local_benchmark"
        if not missing_classes
        else "needs_class_map_review"
    )
    manifest_path = candidate_dir / "external_model_manifest.json"
    manifest = {
        "schema_version": "1.0",
        "task": "external_vision_model_candidate",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "source_url": source_url,
        "source_license": source_license.strip(),
        "model_family": model_family,
        "runtime_format": registered_weights.suffix.lower().lstrip(".") or "unknown",
        "weights": str(registered_weights),
        "weights_sha256": sha256_file(registered_weights),
        "weights_size_bytes": registered_weights.stat().st_size,
        "manifest_path": str(manifest_path),
        "source_classes": normalize_source_classes(source_classes),
        "stwi_class_map": class_map,
        "class_aliases": aliases,
        "prompt_classes": normalize_prompt_classes(prompt_classes),
        "missing_stwi_classes": missing_classes,
        "candidate_status": status,
        "promotion_gate": {
            "min_map50": 0.85,
            "requires_validation_split": True,
            "requires_test_split": True,
            "requires_latency_record": True,
            "requires_privacy_review": True,
            "requires_human_approval": True,
        },
        "review": {
            "reviewer": reviewer,
            "notes": notes,
            "license_is_self_reported": True,
            "not_promotable_without_local_metrics": True,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_external_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("task") != "external_vision_model_candidate":
        raise ValueError("manifest is not an external vision model candidate")
    weights = Path(str(manifest.get("weights", "")))
    if not weights.is_file():
        raise FileNotFoundError(f"weights file is missing: {weights}")
    expected_sha = manifest.get("weights_sha256")
    if expected_sha != sha256_file(weights):
        raise ValueError("weights sha256 does not match external manifest")
    missing_classes = set(manifest.get("missing_stwi_classes", []))
    if missing_classes:
        raise ValueError(
            "external model class map is incomplete: "
            + ", ".join(sorted(missing_classes))
        )
    mapped_classes = set(manifest.get("stwi_class_map", {}).values())
    missing_mapped = REQUIRED_STWI_CLASSES - mapped_classes
    if missing_mapped:
        raise ValueError(
            "external model does not map all STWI classes: "
            + ", ".join(sorted(missing_mapped))
        )
    return manifest


def build_external_verdict(
    *,
    map50: float,
    seconds_per_image: float,
    min_map50: float,
    splits: list[str],
    max_images: int | None,
    baseline_map50: float | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    is_sample = max_images is not None
    has_test = "test" in splits
    if is_sample:
        reasons.append("sample_only_not_promotable")
    if not has_test:
        reasons.append("test_split_not_evaluated")
    if baseline_map50 is not None and map50 < baseline_map50:
        reasons.append("below_current_best_candidate")
    if map50 < min_map50:
        reasons.append("below_mvp_map50_gate")
    if seconds_per_image <= 0:
        reasons.append("latency_not_recorded")

    if map50 >= min_map50 and not is_sample and has_test:
        status = "metric_gate_passed_requires_privacy_and_human_review"
    elif map50 >= min_map50:
        status = "metric_promising_requires_full_gate"
    elif baseline_map50 is not None and map50 > baseline_map50 and is_sample:
        status = "sample_beats_current_best_run_full_validation"
    else:
        status = "not_promotable"

    return {
        "status": status,
        "map50": map50,
        "min_map50": min_map50,
        "seconds_per_image": seconds_per_image,
        "baseline_map50": baseline_map50,
        "reasons": reasons,
    }
