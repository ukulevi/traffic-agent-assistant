"""Citation validator with source allowlist and content verification.

Validated citations must have:
1. Source URL in allowlist
2. Effective at scenario time
3. Provision exists in ingested snapshot
4. Content hash matches
5. Claim supported by excerpt
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from stwi.contracts.knowledge import (
    Citation,
    FailureCode,
    LegalChunk,
    RetrievalResult,
    StructuredFailure,
)


class CitationValidator:
    """Validates citations against corpus snapshot and policy."""

    def __init__(self) -> None:
        self._allowlist: set[str] = set()
        self._chunk_registry: dict[tuple[str, str], LegalChunk] = {}  # (document_id, provision) -> chunk

    def add_source_to_allowlist(self, url: str) -> None:
        """Add an official source URL to the allowlist."""
        self._allowlist.add(url)

    def register_chunk(self, chunk: LegalChunk) -> None:
        """Register a chunk for validation.

        Uses (document_id, provision) as key to ensure uniqueness.
        """
        key = (chunk.document_id, chunk.provision)
        self._chunk_registry[key] = chunk

    def validate_citation(self, citation: Citation, scenario_time: datetime) -> Citation | StructuredFailure:
        """Validate a citation and return it or a structured failure.

        Validation steps:
        1. Source URL in allowlist
        2. Document effective at scenario time
        3. Provision exists in registry
        4. Content hash matches stored chunk
        5. Excerpt exists in chunk content
        """
        if not citation.supporting_excerpt.strip():
            return StructuredFailure(
                code=FailureCode.CITATION_MISMATCH,
                message="Citation supporting excerpt is empty",
                details={"citation_document": citation.document_id},
            )

        # 1. Source allowlist check
        if citation.source_url not in self._allowlist:
            return StructuredFailure(
                code=FailureCode.SOURCE_NOT_ALLOWED,
                message=f"Source not in allowlist: {citation.source_url}",
                details={"citation_document": citation.document_id},
            )

        # 2. Effective date check
        if not citation.is_effective_at(scenario_time):
            return StructuredFailure(
                code=FailureCode.DOCUMENT_EXPIRED,
                message=f"Document not effective at scenario time: {scenario_time.isoformat()}",
                details={
                    "effective_from": citation.effective_from.isoformat(),
                    "effective_to": citation.effective_to.isoformat() if citation.effective_to else None,
                },
            )

        # 3. Provision exists check
        chunk_key = (citation.document_id, citation.provision)
        stored_chunk = self._chunk_registry.get(chunk_key)
        if stored_chunk is None:
            return StructuredFailure(
                code=FailureCode.PROVISION_NOT_FOUND,
                message=f"Provision not found in corpus: {citation.provision}",
                details={"document_id": citation.document_id},
            )

        # 4. Content hash check
        if citation.content_hash != stored_chunk.content_hash:
            return StructuredFailure(
                code=FailureCode.CITATION_MISMATCH,
                message="Content hash mismatch",
                details={
                    "expected": stored_chunk.content_hash,
                    "received": citation.content_hash,
                },
            )

        # 5. Excerpt support check (excerpt must be substring of content)
        if citation.supporting_excerpt not in stored_chunk.content:
            return StructuredFailure(
                code=FailureCode.CITATION_MISMATCH,
                message="Excerpt not found in source content",
                details={
                    "excerpt": citation.supporting_excerpt[:100],
                },
            )

        return citation

    def validate_all(
        self, citations: list[Citation], scenario_time: datetime
    ) -> RetrievalResult:
        """Validate multiple citations and return clean result or failure.

        Invalid citations are dropped when at least one valid citation remains.
        If no citation is valid, returns a structured failure with indexes and
        document/provision identifiers of all failed citations.
        """
        validated: list[Citation] = []
        failures: list[dict[str, Any]] = []

        for index, citation in enumerate(citations):
            result = self.validate_citation(citation, scenario_time)
            if isinstance(result, StructuredFailure):
                failures.append(
                    {
                        "index": index,
                        "document_id": citation.document_id,
                        "provision": citation.provision,
                        "code": result.code.value,
                        "message": result.message,
                        "details": result.details,
                    }
                )
                continue
            validated.append(result)

        if validated:
            return RetrievalResult(citations=validated)

        if failures:
            first = failures[0]
            return RetrievalResult(
                structured_failure=StructuredFailure(
                    code=FailureCode(first["code"]),
                    message=first["message"],
                    details={
                        "failed_citations": failures,
                        "failed_count": len(failures),
                    },
                )
            )

        return RetrievalResult(citations=validated)


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


__all__ = ["CitationValidator", "compute_content_hash"]
