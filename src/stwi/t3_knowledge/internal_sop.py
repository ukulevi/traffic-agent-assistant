"""Fail-closed validation for project-owned internal SOP candidates."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any


PENDING_OWNER = "pending_user_approval"
PENDING_CONTENT_HASH = "pending_validation"


class InternalSopValidationError(ValueError):
    """Raised when an internal SOP cannot safely become an index candidate."""


def content_hash(path: Path) -> str:
    """Return a stable content hash with the citation-compatible prefix."""
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def validate_internal_sop_record(
    record: dict[str, Any], *, repository_root: Path
) -> dict[str, Any]:
    """Validate metadata and return an audit report without indexing anything.

    A draft may be registered for review but is never eligible for indexing.
    An approved document requires an explicit owner, approver, approval date,
    scope and matching content hash.  This keeps a project template from being
    mistaken for an operator-authorized procedure.
    """
    required_text = ("document_id", "title", "version", "owner", "scope", "source_path")
    for field in required_text:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise InternalSopValidationError(f"{field} must be a non-empty string")

    source_path = Path(record["source_path"])
    if source_path.is_absolute() or ".." in source_path.parts:
        raise InternalSopValidationError("source_path must be a repository-relative path")
    document_path = repository_root / source_path
    if not document_path.is_file():
        raise InternalSopValidationError("source_path does not point to a file")
    computed_hash = content_hash(document_path)

    approval_status = record.get("approval_status")
    approved_for_index = record.get("approved_for_index")
    if approval_status == "draft":
        if record["owner"] != PENDING_OWNER:
            raise InternalSopValidationError("draft SOP owner must remain pending_user_approval")
        if approved_for_index is not False:
            raise InternalSopValidationError("draft SOP must not be approved for index")
        if record.get("approval_date") is not None:
            raise InternalSopValidationError("draft SOP must not have an approval_date")
        declared_hash = record.get("content_hash")
        if declared_hash not in (PENDING_CONTENT_HASH, computed_hash):
            raise InternalSopValidationError("draft SOP content_hash does not match content")
        return {
            "document_id": record["document_id"],
            "approval_status": "draft",
            "eligible_for_index": False,
            "reason": "awaiting explicit owner, approval date, and index decision",
            "content_hash": computed_hash,
        }

    if approval_status != "approved":
        raise InternalSopValidationError("approval_status must be draft or approved")
    if record["owner"] == PENDING_OWNER:
        raise InternalSopValidationError("approved SOP needs a named owner")
    if not isinstance(record.get("approved_by"), str) or not record["approved_by"].strip():
        raise InternalSopValidationError("approved SOP needs approved_by")
    if approved_for_index is not True:
        raise InternalSopValidationError("approved SOP requires explicit approved_for_index=true")
    try:
        date.fromisoformat(str(record.get("approval_date")))
    except ValueError as exc:
        raise InternalSopValidationError("approved SOP needs ISO approval_date") from exc
    if record.get("content_hash") != computed_hash:
        raise InternalSopValidationError("approved SOP content_hash does not match content")
    return {
        "document_id": record["document_id"],
        "approval_status": "approved",
        "eligible_for_index": True,
        "reason": "metadata complete; a separate corpus/index operation is still required",
        "content_hash": computed_hash,
    }
