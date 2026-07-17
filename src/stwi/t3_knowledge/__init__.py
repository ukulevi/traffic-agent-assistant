"""Tier 3 knowledge module initialization.

Provides retrieval and citation validation for legal evidence.
"""

from stwi.contracts.knowledge import (
    Aggregation,
    Citation,
    FailureCode,
    LegalChunk,
    Metric,
    OrderBy,
    RetrievalQuery,
    RetrievalResult,
    SimulationQuery,
    SimulationQueryResult,
    StructuredFailure,
)
from stwi.t3_knowledge.citation_validator import CitationValidator, compute_content_hash
from stwi.t3_knowledge.corpus_ingestion import (
    OFFICIAL_SOURCES,
    ingest_law_35_2024_qh15,
    ingest_law_36_2024_qh15,
    ingest_minimal_corpus,
)
from stwi.t3_knowledge.fake_retriever import (
    FakeRetriever,
    sample_law_35_chunk,
    sample_law_36_chunk,
)
from stwi.t3_knowledge.firecrawl_review import review_firecrawl_snapshot_manifest
from stwi.t3_knowledge.firecrawl_snapshot import build_firecrawl_snapshot_manifest
from stwi.t3_knowledge.query_builder import SQLQueryBuilder
from stwi.t3_knowledge.source_registry import DEFAULT_TRUSTED_SOURCES, SourceTier
from stwi.t3_knowledge.timescale_executor import DuckDBFakeExecutor

# Real adapters (require optional deps: qdrant-client, sentence-transformers, psycopg)
# Imported lazily so contract tests don't need these installed.
__all__ = [
    # Contracts
    "Aggregation",
    "Citation",
    "FailureCode",
    "LegalChunk",
    "Metric",
    "OrderBy",
    "RetrievalQuery",
    "RetrievalResult",
    "SimulationQuery",
    "SimulationQueryResult",
    "StructuredFailure",
    # Retrieval
    "FakeRetriever",
    "CitationValidator",
    "compute_content_hash",
    # Corpus
    "OFFICIAL_SOURCES",
    "ingest_law_35_2024_qh15",
    "ingest_law_36_2024_qh15",
    "ingest_minimal_corpus",
    "DEFAULT_TRUSTED_SOURCES",
    "SourceTier",
    "build_firecrawl_snapshot_manifest",
    "review_firecrawl_snapshot_manifest",
    # Query builder + executors
    "SQLQueryBuilder",
    "DuckDBFakeExecutor",
    # Real adapters — imported on demand to avoid hard dep
    # "QdrantRetriever" from stwi.t3_knowledge.qdrant_retriever
    # "TimescaleQueryExecutor" from stwi.t3_knowledge.timescale_executor
]
