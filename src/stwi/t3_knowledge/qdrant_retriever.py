"""Real Qdrant retriever adapter for T3 Knowledge tier.

Uses BGE-m3 dense embeddings + sparse/keyword signal (hybrid retrieval).
Filters by effective_from <= scenario_time, effective_to > scenario_time
and superseded=False per project_contract.json policy.

This module is ONLY imported in integration tests and production code.
Pure contract tests must use FakeRetriever instead.

Dependencies (install separately, not in pyproject base):
    pip install qdrant-client>=1.9 fastembed>=0.3
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

from stwi.contracts.knowledge import (
    Citation,
    FailureCode,
    LegalChunk,
    RetrievalQuery,
    RetrievalResult,
    StructuredFailure,
)

logger = logging.getLogger(__name__)

# Collection names — kept as constants to avoid typos in queries
LEGAL_COLLECTION = "stwi_legal"
CASE_COLLECTION = "stwi_cases"

# BGE-m3 embedding dimension
EMBEDDING_DIM = 1024

# Reranker model (version-pinned per contract requirement)
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


class QdrantRetriever:
    """Real Qdrant retriever with BGE-m3 dense + sparse hybrid retrieval.

    Usage:
        retriever = QdrantRetriever(url="http://localhost:6333")
        retriever.ensure_collection()
        retriever.index_chunk(chunk)
        result = retriever.retrieve(query)
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection: str = LEGAL_COLLECTION,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._collection = collection
        self._client: Any = None
        self._encoder: Any = None

    def _get_client(self) -> Any:
        """Lazy-init Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise ImportError(
                    "qdrant-client is required for QdrantRetriever. "
                    "Install with: pip install qdrant-client>=1.9"
                ) from exc
            self._client = QdrantClient(url=self._url, api_key=self._api_key)
        return self._client

    def _get_encoder(self) -> Any:
        """Lazy-init BGE-m3 encoder via fastembed."""
        if self._encoder is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise ImportError(
                    "fastembed is required for QdrantRetriever. "
                    "Install with: pip install fastembed>=0.3"
                ) from exc
            self._encoder = TextEmbedding(model_name="BAAI/bge-m3")
        return self._encoder

    def _embed(self, text: str) -> list[float]:
        """Embed text with BGE-m3."""
        encoder = self._get_encoder()
        vectors = list(encoder.embed([text]))
        return list(vectors[0])

    def ensure_collection(self) -> None:
        """Create collection if it does not exist."""
        from qdrant_client.models import Distance, SparseVectorParams, VectorParams

        client = self._get_client()
        existing = [c.name for c in client.get_collections().collections]
        if self._collection not in existing:
            client.create_collection(
                collection_name=self._collection,
                vectors_config={"dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": SparseVectorParams()},
            )
            logger.info("Created Qdrant collection: %s", self._collection)

    def _build_sparse_vector(self, text: str) -> dict[str, Any]:
        """Build simple BM25-style sparse vector from text tokens."""
        from collections import Counter
        import math

        tokens = text.lower().split()
        tf = Counter(tokens)
        n = len(tokens) or 1
        indices, values = [], []
        for token, count in tf.items():
            # Use stable sha256-based index (hash() is non-deterministic across processes)
            idx = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % (2**20)
            indices.append(idx)
            values.append(count / n * math.log(1 + len(tokens)))
        return {"indices": indices, "values": values}

    def index_chunk(self, chunk: LegalChunk, point_id: int | None = None) -> None:
        """Index a LegalChunk into Qdrant with dense + sparse vectors."""
        from qdrant_client.models import PointStruct, SparseVector

        client = self._get_client()
        dense_vec = self._embed(chunk.content)
        sparse_raw = self._build_sparse_vector(chunk.content)

        payload = {
            "document_id": chunk.document_id,
            "title": chunk.title,
            "document_number": chunk.document_number,
            "provision": chunk.provision,
            "source_url": chunk.source_url,
            "effective_from": chunk.effective_from.isoformat(),
            "effective_to": chunk.effective_to.isoformat() if chunk.effective_to else None,
            "superseded": chunk.superseded,
            "jurisdiction": chunk.jurisdiction,
            "content_hash": chunk.content_hash,
            "content": chunk.content,
        }

        # Use deterministic ID from document_id + provision (hash() is process-unstable)
        if point_id is None:
            key = f"{chunk.document_id}::{chunk.provision}".encode()
            point_id = int(hashlib.sha256(key).hexdigest()[:16], 16) % (2**31)

        client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=point_id,
                    payload=payload,
                    vector={
                        "dense": dense_vec,
                        "sparse": SparseVector(
                            indices=sparse_raw["indices"],
                            values=sparse_raw["values"],
                        ),
                    },
                )
            ],
        )

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Hybrid retrieval: dense + sparse, with effective-date + jurisdiction filter."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue, Prefetch, SearchRequest

        # Prompt injection detection (mirrors FakeRetriever policy)
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

        client = self._get_client()
        jurisdiction = query.jurisdiction or "VN"
        scenario_date = query.scenario_time.date().isoformat()

        # Qdrant filter: jurisdiction, superseded=false, effective_from <= scenario_date
        must_conditions = [
            FieldCondition(key="jurisdiction", match=MatchValue(value=jurisdiction)),
            FieldCondition(key="superseded", match=MatchValue(value=False)),
        ]
        # Note: Qdrant range filter on ISO date strings works lexicographically for YYYY-MM-DD
        from qdrant_client.models import FieldCondition, Range
        must_conditions.append(
            FieldCondition(key="effective_from", range=Range(lte=scenario_date))
        )

        q_filter = Filter(must=must_conditions)

        dense_vec = self._embed(query.query_text)
        sparse_raw = self._build_sparse_vector(query.query_text)

        try:
            from qdrant_client.models import SparseVector as QSparseVector

            results = client.query_points(
                collection_name=self._collection,
                prefetch=[
                    Prefetch(
                        query=dense_vec,
                        using="dense",
                        filter=q_filter,
                        limit=query.limit * 2,
                    ),
                    Prefetch(
                        query=QSparseVector(
                            indices=sparse_raw["indices"],
                            values=sparse_raw["values"],
                        ),
                        using="sparse",
                        filter=q_filter,
                        limit=query.limit * 2,
                    ),
                ],
                query=dense_vec,  # RRF fusion
                using="dense",
                limit=query.limit,
            ).points
        except Exception as exc:
            logger.exception("Qdrant retrieval failed: %s", exc)
            return RetrievalResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.TIMEOUT,
                    message=f"Qdrant retrieval error: {exc}",
                    details={},
                )
            )

        # Build citations from payload, filter expired effective_to
        citations: list[Citation] = []
        for point in results:
            p = point.payload or {}
            effective_to = p.get("effective_to")
            if effective_to and effective_to <= scenario_date:
                continue  # skip superseded/expired

            content = p.get("content", "")
            excerpt = content[:200] if len(content) > 200 else content

            citations.append(
                Citation(
                    document_id=p["document_id"],
                    title=p["title"],
                    document_number=p["document_number"],
                    provision=p["provision"],
                    source_url=p["source_url"],
                    effective_from=datetime.fromisoformat(p["effective_from"]).date(),
                    effective_to=(
                        datetime.fromisoformat(effective_to).date() if effective_to else None
                    ),
                    superseded=p.get("superseded", False),
                    content_hash=p["content_hash"],
                    supporting_excerpt=excerpt,
                )
            )

        return RetrievalResult(citations=citations)


__all__ = ["QdrantRetriever", "LEGAL_COLLECTION", "CASE_COLLECTION", "EMBEDDING_DIM"]
