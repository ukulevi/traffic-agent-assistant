"""Real Qdrant retriever adapter for T3 Knowledge tier.

Uses BGE-m3 dense embeddings + sparse/keyword signal (hybrid retrieval).
Filters by effective_from <= scenario_time, effective_to > scenario_time
and superseded=False per project_contract.json policy.

This module is ONLY imported in integration tests and production code.
Pure contract tests must use FakeRetriever instead.

Dependencies (install through the project knowledge extra):
    pip install -e .[knowledge]
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
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
EMBEDDING_MODEL = "BAAI/bge-m3"


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
        embedding_device: str | None = None,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._collection = collection
        self._embedding_device = (
            embedding_device
            or os.environ.get("STWI_EMBEDDING_DEVICE", "cpu")
        )
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
        """Lazy-init the contract BGE-m3 encoder."""
        if self._encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for BGE-m3. "
                    "Install the project knowledge extra."
                ) from exc
            self._encoder = SentenceTransformer(
                EMBEDDING_MODEL,
                device=self._embedding_device,
            )
        return self._encoder

    def _embed(self, text: str) -> list[float]:
        """Embed text with BGE-m3."""
        encoder = self._get_encoder()
        vectors = encoder.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        vector = vectors[0]
        if len(vector) != EMBEDDING_DIM:
            raise ValueError("BGE-m3 embedding dimension does not match contract")
        return vector.astype(float).tolist()

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
                        message="Query was rejected by retrieval safety policy.",
                        details={"matched_policy": pattern},
                    )
                )

        try:
            return self._retrieve_validated(query)
        except Exception:
            trace_id = str(uuid.uuid4())
            logger.error("Qdrant retrieval failed trace_id=%s", trace_id)
            return RetrievalResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.TIMEOUT,
                    message="Legal retrieval service is unavailable.",
                    details={},
                    trace_id=trace_id,
                )
            )

    def _retrieve_validated(self, query: RetrievalQuery) -> RetrievalResult:
        """Execute a validated query; public boundary redacts every failure."""
        from qdrant_client.models import (
            DatetimeRange,
            FieldCondition,
            Filter,
            MatchValue,
            NamedSparseVector,
            NamedVector,
            SearchRequest,
            SparseVector,
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
        must_conditions.append(
            FieldCondition(
                key="effective_from",
                range=DatetimeRange(lte=query.scenario_time.date()),
            )
        )

        q_filter = Filter(must=must_conditions)

        dense_vec = self._embed(query.query_text)
        sparse_raw = self._build_sparse_vector(query.query_text)

        batches = client.search_batch(
            collection_name=self._collection,
            requests=[
                SearchRequest(
                    vector=NamedVector(name="dense", vector=dense_vec),
                    filter=q_filter,
                    limit=query.limit * 2,
                    with_payload=True,
                ),
                SearchRequest(
                    vector=NamedSparseVector(
                        name="sparse",
                        vector=SparseVector(
                            indices=sparse_raw["indices"],
                            values=sparse_raw["values"],
                        ),
                    ),
                    filter=q_filter,
                    limit=query.limit * 2,
                    with_payload=True,
                ),
            ],
        )
        # Reciprocal-rank fusion is deterministic and compatible with the
        # Qdrant 1.9.7 server pinned by the integration harness.
        fused_scores: dict[Any, float] = {}
        points: dict[Any, Any] = {}
        for batch in batches:
            for rank, point in enumerate(batch, start=1):
                fused_scores[point.id] = fused_scores.get(point.id, 0.0) + 1.0 / (60 + rank)
                points[point.id] = point
        results = [
            points[point_id]
            for point_id, _score in sorted(
                fused_scores.items(),
                key=lambda item: (-item[1], str(item[0])),
            )[: query.limit]
        ]

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


__all__ = [
    "QdrantRetriever",
    "LEGAL_COLLECTION",
    "CASE_COLLECTION",
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL",
]
