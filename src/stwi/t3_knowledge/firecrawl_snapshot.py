"""Firecrawl snapshot builder for Tier 3 corpus candidates.

This module consumes JSON returned by Firecrawl search/crawl/scrape jobs and
writes immutable candidate metadata. It does not call Firecrawl directly; the
runtime integration stays outside the STWI core so tests remain deterministic.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stwi.t3_knowledge.source_registry import (
    DEFAULT_TRUSTED_SOURCES,
    SourceRegistryError,
    TrustedSource,
    require_trusted_source,
)

SNAPSHOT_SCHEMA_VERSION = "1.0"
MIN_FULL_TEXT_CHARS = 500


def compute_snapshot_hash(content: str) -> str:
    """Compute a stable hash for crawled content."""
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _record_url(record: dict[str, Any]) -> str | None:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return (
        record.get("url")
        or record.get("sourceURL")
        or record.get("source_url")
        or metadata.get("sourceURL")
        or metadata.get("url")
    )


def _record_content(record: dict[str, Any]) -> tuple[str, str]:
    """Return best available content and its extraction level."""
    for key, level in (
        ("markdown", "full_text"),
        ("content", "full_text"),
        ("text", "full_text"),
        ("summary", "summary"),
        ("description", "snippet"),
    ):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), level
    return "", "missing"


def _iter_firecrawl_records(payload: Any) -> list[dict[str, Any]]:
    """Extract result records from common Firecrawl response shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    records: list[dict[str, Any]] = []
    data = payload.get("data")

    if isinstance(data, list):
        records.extend(item for item in data if isinstance(item, dict))
    elif isinstance(data, dict):
        for key in ("web", "news", "results", "documents"):
            items = data.get(key)
            if isinstance(items, list):
                records.extend(item for item in items if isinstance(item, dict))

    for key in ("web", "news", "results", "documents"):
        items = payload.get(key)
        if isinstance(items, list):
            records.extend(item for item in items if isinstance(item, dict))

    if _record_url(payload):
        records.append(payload)

    return records


def _snapshot_id(url: str, content_hash: str) -> str:
    digest = hashlib.sha256(f"{url}|{content_hash}".encode("utf-8")).hexdigest()[:16]
    return f"fc-{digest}"


def _document_candidate(
    record: dict[str, Any],
    source: TrustedSource,
    created_at: str,
) -> dict[str, Any]:
    url = _record_url(record)
    if url is None:
        raise ValueError("record is missing url")

    content, extraction_level = _record_content(record)
    content_hash = compute_snapshot_hash(content)
    ready_for_chunking = extraction_level == "full_text" and len(content) >= MIN_FULL_TEXT_CHARS
    eligible_for_promotion = source.can_seed_legal_corpus and ready_for_chunking

    return {
        "snapshot_id": _snapshot_id(url, content_hash),
        "source_url": url,
        "source_id": source.source_id,
        "source_tier": source.tier.value,
        "source_role": source.source_role,
        "title": record.get("title") or "",
        "content_hash": content_hash,
        "content_length": len(content),
        "extraction_level": extraction_level,
        "ready_for_chunking": ready_for_chunking,
        "eligible_for_promotion": eligible_for_promotion,
        "approved_for_index": False,
        "review_status": "needs_legal_review" if source.can_seed_legal_corpus else "needs_owner_review",
        "review_owner": source.owner,
        "retrieved_at": created_at,
        "content": content,
    }


def build_firecrawl_snapshot_manifest(
    firecrawl_payload: dict[str, Any] | list[Any],
    *,
    registry: tuple[TrustedSource, ...] = DEFAULT_TRUSTED_SOURCES,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build an immutable candidate manifest from a Firecrawl response.

    Untrusted or malformed records are kept in ``rejected`` for audit. Accepted
    documents are never approved for indexing by this function.
    """
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    records = _iter_firecrawl_records(firecrawl_payload)
    documents: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        url = _record_url(record)
        if not url:
            rejected.append({"index": index, "reason": "missing_url"})
            continue
        try:
            source = require_trusted_source(url, registry)
            documents.append(_document_candidate(record, source, timestamp))
        except (SourceRegistryError, ValueError) as exc:
            rejected.append({"index": index, "url": url, "reason": str(exc)})

    firecrawl_job_id = None
    if isinstance(firecrawl_payload, dict):
        firecrawl_job_id = firecrawl_payload.get("id") or firecrawl_payload.get("crawl_id")

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "pipeline": "firecrawl_candidate_snapshot",
        "created_at": timestamp,
        "firecrawl_job_id": firecrawl_job_id,
        "promotion_policy": {
            "default_approved_for_index": False,
            "requires_owner_review": True,
            "requires_content_hash": True,
            "requires_effective_date_validation": True,
        },
        "documents": documents,
        "rejected": rejected,
        "counts": {
            "records_seen": len(records),
            "accepted": len(documents),
            "rejected": len(rejected),
            "eligible_for_promotion": sum(1 for item in documents if item["eligible_for_promotion"]),
        },
    }


def write_firecrawl_snapshot_manifest(
    firecrawl_payload: dict[str, Any] | list[Any],
    output_path: Path,
    *,
    registry: tuple[TrustedSource, ...] = DEFAULT_TRUSTED_SOURCES,
) -> dict[str, Any]:
    """Build and write a Firecrawl snapshot manifest."""
    manifest = build_firecrawl_snapshot_manifest(firecrawl_payload, registry=registry)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


__all__ = [
    "MIN_FULL_TEXT_CHARS",
    "SNAPSHOT_SCHEMA_VERSION",
    "build_firecrawl_snapshot_manifest",
    "compute_snapshot_hash",
    "write_firecrawl_snapshot_manifest",
]
