"""Fake/in-memory retriever adapter for contract tests.

This adapter does NOT require Qdrant or any external service.
It provides RetrievalResult with citations or structured failures.

Matching strategy: TF-IDF-inspired discriminative matching.
- Terms that appear in more than CORPUS_FREQ_THRESHOLD of chunks are treated
  as corpus-wide stopwords and excluded from matching.
- Remaining terms use adaptive min_overlap: 1 for 1-2 meaningful terms, 2 for
  3+ meaningful terms.
- Provision/title/document number are included in searchable text so tests can
  ask for "Điều 10" without requiring the content body to repeat the heading.

Note: FakeRetriever is for contract tests only. For semantic relevance, use
QdrantRetriever with BGE-m3 embeddings.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime

from stwi.contracts.knowledge import (
    FailureCode,
    LegalChunk,
    RetrievalQuery,
    RetrievalResult,
    RetrieverAdapter,
    StructuredFailure,
)

# Terms appearing in more than this fraction of chunks are non-discriminative.
CORPUS_FREQ_THRESHOLD = 0.40


class FakeRetriever(RetrieverAdapter):
    """In-memory retriever adapter for testing."""

    def __init__(self) -> None:
        self._chunks: list[LegalChunk] = []
        self._sources_allowlist: set[str] = set()
        self._doc_freq: dict[str, int] = defaultdict(int)

    @staticmethod
    def _terms(text: str) -> frozenset[str]:
        """Tokenize Vietnamese/ASCII text consistently for fake retrieval."""
        normalized = unicodedata.normalize("NFC", text).lower()
        return frozenset(re.findall(r"\w+", normalized, flags=re.UNICODE))

    @staticmethod
    def _searchable_text(chunk: LegalChunk) -> str:
        """Include citation metadata in fake retrieval, especially provision IDs."""
        return " ".join(
            [
                chunk.document_id,
                chunk.title,
                chunk.document_number,
                chunk.provision,
                chunk.content,
            ]
        )

    def add_chunk(self, chunk: LegalChunk) -> None:
        """Add a chunk to the in-memory store and update term frequencies."""
        self._chunks.append(chunk)
        self._sources_allowlist.add(chunk.source_url)
        for term in self._terms(self._searchable_text(chunk)):
            self._doc_freq[term] += 1

    def _discriminative_terms(self, text: str) -> frozenset[str]:
        """Return only high-IDF terms from text."""
        if not self._chunks:
            return self._terms(text)

        threshold_count = math.ceil(len(self._chunks) * CORPUS_FREQ_THRESHOLD)
        return frozenset(
            term
            for term in self._terms(text)
            if len(term) > 1 and self._doc_freq.get(term, 0) <= threshold_count
        )

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Retrieve citations matching query with temporal + discriminative filtering."""
        suspicious_patterns = [
            "ignore previous instructions",
            "system prompt",
            "forget",
            "jailbreak",
        ]
        query_lower = query.query_text.lower()
        for pattern in suspicious_patterns:
            if pattern in query_lower:
                return RetrievalResult(
                    structured_failure=StructuredFailure(
                        code=FailureCode.PROMPT_INJECTION,
                        message=f"Query contains suspicious pattern: {pattern}",
                        details={"query_text": query.query_text[:100]},
                    )
                )

        jurisdiction = query.jurisdiction or "VN"
        query_terms = self._discriminative_terms(query.query_text)
        if not query_terms:
            return RetrievalResult(citations=[])

        min_overlap = 1 if len(query_terms) <= 2 else 2

        matching_chunks: list[LegalChunk] = []
        for chunk in self._chunks:
            if chunk.jurisdiction != jurisdiction:
                continue
            if not chunk.is_effective_at(query.scenario_time):
                continue

            content_terms = self._discriminative_terms(self._searchable_text(chunk))
            if len(query_terms & content_terms) >= min_overlap:
                matching_chunks.append(chunk)

        citations = [
            chunk.citation(
                excerpt=chunk.content[:200] if len(chunk.content) > 200 else chunk.content
            )
            for chunk in matching_chunks[: query.limit]
        ]
        return RetrievalResult(citations=citations)

    def is_source_allowed(self, url: str) -> bool:
        """Check if source URL is in allowlist."""
        return url in self._sources_allowlist


def sample_law_35_chunk() -> LegalChunk:
    """Create a sample chunk for Luật Đường bộ 35/2024/QH15."""
    return LegalChunk(
        document_id="law-35-2024-qh15",
        title="Luật Đường bộ",
        document_number="35/2024/QH15",
        provision="Điều 1",
        source_url="https://vanban.chinhphu.vn/?pageid=27160&docid=211193",
        effective_from=datetime(2025, 1, 1).date(),
        effective_to=None,
        superseded=False,
        jurisdiction="VN",
        content_hash="sha256:placeholder_dieu1_law35",
        content=(
            "Luật Đường bộ quy định về quyền và nghĩa vụ của người sử dụng đường, "
            "quan hệ pháp luật trong giao thông đường bộ, nguyên tắc quản lý và điều hành "
            "ảnh hưởng đến an toàn giao thông. Đường bộ gồm đường, cầu đường, bến phà "
            "và các công trình phụ trợ khác phục vụ giao thông đường bộ. "
            "Phương tiện giao thông đường bộ phải tuân thủ biển báo đường bộ và có thể "
            "bị xử lý vi phạm hành chính khi không chấp hành."
        ),
    )


def sample_law_36_chunk() -> LegalChunk:
    """Create a sample chunk for Luật Trật tự, an toàn giao thông đường bộ 36/2024/QH15."""
    return LegalChunk(
        document_id="law-36-2024-qh15",
        title="Luật Trật tự, an toàn giao thông đường bộ",
        document_number="36/2024/QH15",
        provision="Điều 10",
        source_url="https://vanban.chinhphu.vn/?pageid=27160&docid=211194&classid=1&typegroupid=3",
        effective_from=datetime(2025, 1, 1).date(),
        effective_to=None,
        superseded=False,
        jurisdiction="VN",
        content_hash="sha256:placeholder_dieu10_law36",
        content=(
            "Người tham gia giao thông đường bộ phải tuân thủ quy định về trật tự, "
            "an toàn trên đường; vi phạm luật sẽ bị xử lý kỷ luật, hành chính hoặc hình sự "
            "tùy mức độ nghiêm trọng. Bao gồm người lái xe, người ngồi trên xe, "
            "người đi bộ và người dẫn xe. Người lái xe có trách nhiệm tránh tai nạn, "
            "kiểm tra phanh, hệ thống lái, đèn, còi và cảnh báo người tham gia giao thông khác."
        ),
    )


__all__ = [
    "FakeRetriever",
    "CORPUS_FREQ_THRESHOLD",
    "sample_law_35_chunk",
    "sample_law_36_chunk",
]
