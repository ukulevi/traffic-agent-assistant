"""Owner review gate for Firecrawl snapshot manifests."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class FirecrawlReviewError(ValueError):
    """Raised when a Firecrawl snapshot review would break corpus policy."""


def _review_timestamp(reviewed_at: str | None) -> str:
    return reviewed_at or datetime.now(timezone.utc).isoformat()


def review_firecrawl_snapshot_manifest(
    manifest: dict[str, Any],
    *,
    reviewer: str,
    approved_snapshot_ids: Iterable[str] = (),
    rejected_snapshot_ids: Iterable[str] = (),
    reviewed_at: str | None = None,
    rejection_reason: str = "",
) -> dict[str, Any]:
    """Apply an explicit owner review decision to a Firecrawl snapshot manifest.

    Only documents marked ``eligible_for_promotion`` can become
    ``approved_for_index``. This keeps public operational sources, short
    snippets, and malformed records fail-closed even when their IDs are passed
    to the review script.
    """
    reviewer = reviewer.strip()
    if not reviewer:
        raise FirecrawlReviewError("reviewer is required")

    approved_ids = {item.strip() for item in approved_snapshot_ids if item and item.strip()}
    rejected_ids = {item.strip() for item in rejected_snapshot_ids if item and item.strip()}
    if not approved_ids and not rejected_ids:
        raise FirecrawlReviewError("at least one approve or reject decision is required")

    overlap = approved_ids & rejected_ids
    if overlap:
        raise FirecrawlReviewError(f"snapshot_id cannot be both approved and rejected: {sorted(overlap)}")

    reviewed_manifest = copy.deepcopy(manifest)
    documents = reviewed_manifest.get("documents")
    if not isinstance(documents, list):
        raise FirecrawlReviewError("manifest is missing documents list")

    by_id: dict[str, dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            continue
        snapshot_id = document.get("snapshot_id")
        if isinstance(snapshot_id, str):
            by_id[snapshot_id] = document

    unknown_ids = (approved_ids | rejected_ids) - set(by_id)
    if unknown_ids:
        raise FirecrawlReviewError(f"unknown snapshot_id: {sorted(unknown_ids)}")

    timestamp = _review_timestamp(reviewed_at)

    for snapshot_id in approved_ids:
        document = by_id[snapshot_id]
        if not document.get("eligible_for_promotion"):
            raise FirecrawlReviewError(f"snapshot_id is not eligible for promotion: {snapshot_id}")
        document["approved_for_index"] = True
        document["review_status"] = "approved"
        document["reviewed_by"] = reviewer
        document["reviewed_at"] = timestamp

    for snapshot_id in rejected_ids:
        document = by_id[snapshot_id]
        document["approved_for_index"] = False
        document["review_status"] = "rejected"
        document["reviewed_by"] = reviewer
        document["reviewed_at"] = timestamp
        if rejection_reason:
            document["review_reason"] = rejection_reason

    counts = dict(reviewed_manifest.get("counts", {}))
    counts["approved_for_index"] = sum(1 for item in documents if item.get("approved_for_index") is True)
    counts["rejected_by_reviewer"] = sum(1 for item in documents if item.get("review_status") == "rejected")
    reviewed_manifest["counts"] = counts
    reviewed_manifest["review_policy"] = {
        "reviewer_required": True,
        "approved_ids_explicit": True,
        "eligible_for_promotion_required": True,
        "qdrant_indexing_performed": False,
    }
    return reviewed_manifest


def write_reviewed_firecrawl_snapshot(
    input_path: Path,
    output_path: Path,
    *,
    reviewer: str,
    approved_snapshot_ids: Iterable[str] = (),
    rejected_snapshot_ids: Iterable[str] = (),
    reviewed_at: str | None = None,
    rejection_reason: str = "",
) -> dict[str, Any]:
    """Read, review, and write a Firecrawl snapshot manifest."""
    manifest = json.loads(input_path.read_text(encoding="utf-8"))
    reviewed_manifest = review_firecrawl_snapshot_manifest(
        manifest,
        reviewer=reviewer,
        approved_snapshot_ids=approved_snapshot_ids,
        rejected_snapshot_ids=rejected_snapshot_ids,
        reviewed_at=reviewed_at,
        rejection_reason=rejection_reason,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(reviewed_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return reviewed_manifest


__all__ = [
    "FirecrawlReviewError",
    "review_firecrawl_snapshot_manifest",
    "write_reviewed_firecrawl_snapshot",
]
