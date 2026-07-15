"""T3 Knowledge Tier facade — single entry point for Phase 4 orchestrator.

The orchestrator calls T3KnowledgeTier and never imports retriever/validator
internals directly. This keeps the boundary clean and swappable between
fake (test) and real (Qdrant/TimescaleDB) adapters.

Contracts:
    - All outputs are either List[Citation] or StructuredFailure.
    - Output NEVER contains `recommended_action` — that belongs to orchestrator.
    - Missing evidence / OOD / expired always returns StructuredFailure, not silence.
    - No raw SQL accepted; SimulationQuery builder is internal.

Phase 4 integration:
    - Use FakeT3Adapter for all unit/integration tests.
    - Switch to RealT3Adapter for production after Qdrant/TimescaleDB Docker health.
    - Both implement T3Adapter protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import os
from typing import Any
import uuid
from uuid import UUID

from stwi.contracts.knowledge import (
    Citation,
    FailureCode,
    Metric,
    RetrievalQuery,
    RetrievalResult,
    SimulationQuery,
    StructuredFailure,
)
from stwi.t3_knowledge.citation_validator import CitationValidator
from stwi.t3_knowledge.corpus_ingestion import ingest_minimal_corpus
from stwi.t3_knowledge.fake_retriever import FakeRetriever
from stwi.t3_knowledge.query_builder import SQLQueryBuilder
from stwi.t3_knowledge.timescale_executor import DuckDBFakeExecutor


# ============================================================
# T3 Output types (orchestrator-facing)
# ============================================================

class T3LegalEvidence:
    """Legal evidence returned to orchestrator after full validation."""

    def __init__(self, citations: list[Citation], scenario_time: datetime) -> None:
        self.citations = citations
        self.scenario_time = scenario_time

    def is_sufficient(self) -> bool:
        return len(self.citations) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "citations": [
                {
                    "document_id": c.document_id,
                    "document_number": c.document_number,
                    "provision": c.provision,
                    "source_url": c.source_url,
                    "effective_from": c.effective_from.isoformat(),
                    "content_hash": c.content_hash,
                    "supporting_excerpt": c.supporting_excerpt,
                }
                for c in self.citations
            ],
            "scenario_time": self.scenario_time.isoformat(),
            "sufficient": self.is_sufficient(),
        }


class T3SimulationData:
    """Simulation query result returned to orchestrator."""

    def __init__(self, rows: list[dict[str, Any]], query: SimulationQuery) -> None:
        self.rows = rows
        self.query = query

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": str(self.query.job_id),
            "row_count": len(self.rows),
            "rows": self.rows,
        }


# ============================================================
# Adapter protocol
# ============================================================

class T3Adapter(ABC):
    """Abstract adapter protocol for T3 Knowledge Tier."""

    @abstractmethod
    def get_legal_evidence(
        self,
        query_text: str,
        scenario_time: datetime,
        jurisdiction: str = "VN",
    ) -> T3LegalEvidence | StructuredFailure:
        """Retrieve and validate legal citations for a scenario query."""
        ...

    @abstractmethod
    def get_simulation_data(
        self,
        job_id: UUID,
        tenant_id: str,
        metrics: list[Metric],
        node_ids: list[str] | None = None,
        horizons_minutes: list[int] | None = None,
    ) -> T3SimulationData | StructuredFailure:
        """Query simulation results for a job."""
        ...


# ============================================================
# Fake adapter (for Phase 4 unit/integration tests)
# ============================================================

class FakeT3Adapter(T3Adapter):
    """In-memory T3 adapter — no Qdrant or TimescaleDB required.

    Loads from official corpus if available, synthetic fixtures otherwise.
    Use this in all Phase 4 tests.
    """

    is_provisional_adapter = True

    def __init__(self, corpus_dir: Any = None) -> None:
        from pathlib import Path
        if corpus_dir is None:
            corpus_dir = (
                Path(__file__).resolve().parents[3]
                / "data" / "derived" / "private" / "phase3_knowledge" / "corpus"
            )
        chunks, _ = ingest_minimal_corpus(Path(corpus_dir))

        self._retriever = FakeRetriever()
        self._validator = CitationValidator()
        for chunk in chunks:
            self._retriever.add_chunk(chunk)
            self._validator.add_source_to_allowlist(chunk.source_url)
            self._validator.register_chunk(chunk)

        self._executor = DuckDBFakeExecutor()

    def get_legal_evidence(
        self,
        query_text: str,
        scenario_time: datetime,
        jurisdiction: str = "VN",
    ) -> T3LegalEvidence | StructuredFailure:
        query = RetrievalQuery(
            query_text=query_text,
            scenario_time=scenario_time,
            jurisdiction=jurisdiction,
        )
        result = self._retriever.retrieve(query)

        if result.structured_failure:
            return result.structured_failure

        if not result.citations:
            return StructuredFailure(
                code=FailureCode.MISSING_EVIDENCE,
                message="No legal evidence found for the query.",
                details={"query_text": query_text, "scenario_time": scenario_time.isoformat()},
            )

        # Validate all citations
        validated = self._validator.validate_all(result.citations, scenario_time)
        if validated.structured_failure:
            return validated.structured_failure

        return T3LegalEvidence(citations=validated.citations, scenario_time=scenario_time)

    def get_simulation_data(
        self,
        job_id: UUID,
        tenant_id: str,
        metrics: list[Metric],
        node_ids: list[str] | None = None,
        horizons_minutes: list[int] | None = None,
    ) -> T3SimulationData | StructuredFailure:
        query = SimulationQuery(
            job_id=job_id,
            tenant_id=tenant_id,
            metrics=metrics,
            node_ids=node_ids or [],
            horizons_minutes=horizons_minutes or [5, 10, 15, 30],
        )
        result = self._executor.execute(query)
        if result.structured_failure:
            return result.structured_failure
        return T3SimulationData(rows=result.rows, query=query)


# ============================================================
# Real adapter (for production — requires Qdrant + TimescaleDB)
# ============================================================

class RealT3Adapter(T3Adapter):
    """Production T3 adapter using Qdrant + TimescaleDB.

    Requires:
        pip install qdrant-client>=1.9 fastembed>=0.3 'psycopg[binary]>=3.1'

    And running Docker services:
        docker compose -f infra/harness/compose.phase3.yaml up -d
    """

    def __init__(
        self,
        qdrant_url: str | None = None,
        tsdb_dsn: str | None = None,
        corpus_dir: Any = None,
    ) -> None:
        from pathlib import Path
        from stwi.t3_knowledge.qdrant_retriever import QdrantRetriever
        from stwi.t3_knowledge.timescale_executor import TimescaleQueryExecutor

        qdrant_url = qdrant_url or os.environ.get("STWI_QDRANT_URL")
        tsdb_dsn = tsdb_dsn or os.environ.get("STWI_TSDB_DSN")
        if not qdrant_url or not tsdb_dsn:
            raise RuntimeError(
                "RealT3Adapter requires STWI_QDRANT_URL and STWI_TSDB_DSN "
                "or explicit approved configuration."
            )

        if corpus_dir is None:
            corpus_dir = (
                Path(__file__).resolve().parents[3]
                / "data" / "derived" / "private" / "phase3_knowledge" / "corpus"
            )
        chunks, _ = ingest_minimal_corpus(Path(corpus_dir))

        self._retriever = QdrantRetriever(
            url=qdrant_url,
            api_key=os.environ.get("STWI_QDRANT_API_KEY"),
        )
        self._retriever.ensure_collection()
        self._validator = CitationValidator()
        for chunk in chunks:
            self._retriever.index_chunk(chunk)
            self._validator.add_source_to_allowlist(chunk.source_url)
            self._validator.register_chunk(chunk)

        self._executor = TimescaleQueryExecutor(dsn=tsdb_dsn)

    def get_legal_evidence(
        self,
        query_text: str,
        scenario_time: datetime,
        jurisdiction: str = "VN",
    ) -> T3LegalEvidence | StructuredFailure:
        query = RetrievalQuery(
            query_text=query_text,
            scenario_time=scenario_time,
            jurisdiction=jurisdiction,
        )
        result = self._retriever.retrieve(query)

        if result.structured_failure:
            return result.structured_failure

        if not result.citations:
            return StructuredFailure(
                code=FailureCode.MISSING_EVIDENCE,
                message="No legal evidence found for the query.",
                details={"query_text": query_text},
            )

        validated = self._validator.validate_all(result.citations, scenario_time)
        if validated.structured_failure:
            return validated.structured_failure

        return T3LegalEvidence(citations=validated.citations, scenario_time=scenario_time)

    def get_simulation_data(
        self,
        job_id: UUID,
        tenant_id: str,
        metrics: list[Metric],
        node_ids: list[str] | None = None,
        horizons_minutes: list[int] | None = None,
    ) -> T3SimulationData | StructuredFailure:
        query = SimulationQuery(
            job_id=job_id,
            tenant_id=tenant_id,
            metrics=metrics,
            node_ids=node_ids or [],
            horizons_minutes=horizons_minutes or [5, 10, 15, 30],
        )
        result = self._executor.execute(query)
        if result.structured_failure:
            return result.structured_failure
        return T3SimulationData(rows=result.rows, query=query)


# ============================================================
# T3KnowledgeTier — main orchestrator-facing class
# ============================================================

class T3KnowledgeTier:
    """Phase 4 entry point for T3 Knowledge tier.

    Usage (tests):
        t3 = T3KnowledgeTier(adapter=FakeT3Adapter())

    Usage (production):
        t3 = T3KnowledgeTier(adapter=RealT3Adapter())

    Contract:
        - Output is always T3LegalEvidence, T3SimulationData, or StructuredFailure.
        - Never raises unhandled exceptions — always returns structured error.
        - Never returns recommended_action — orchestrator decides that.
        - Missing evidence → StructuredFailure(MISSING_EVIDENCE) → needs_review.
    """

    def __init__(self, adapter: T3Adapter | None = None) -> None:
        self._adapter = adapter or FakeT3Adapter()

    @property
    def uses_provisional_adapter(self) -> bool:
        """Whether the wrapped adapter is safe only for test/demo composition."""
        return bool(getattr(self._adapter, "is_provisional_adapter", False))

    def query_legal_evidence(
        self,
        query_text: str,
        scenario_time: datetime,
        jurisdiction: str = "VN",
    ) -> T3LegalEvidence | StructuredFailure:
        """Query T3 for legal evidence supporting a scenario decision."""
        try:
            return self._adapter.get_legal_evidence(query_text, scenario_time, jurisdiction)
        except Exception:
            trace_id = str(uuid.uuid4())
            return StructuredFailure(
                code=FailureCode.MISSING_EVIDENCE,
                message="Legal evidence service is unavailable.",
                details={},
                trace_id=trace_id,
            )

    def query_simulation_data(
        self,
        job_id: UUID,
        tenant_id: str,
        metrics: list[Metric],
        node_ids: list[str] | None = None,
        horizons_minutes: list[int] | None = None,
    ) -> T3SimulationData | StructuredFailure:
        """Query T3 for simulation results."""
        try:
            return self._adapter.get_simulation_data(
                job_id, tenant_id, metrics, node_ids, horizons_minutes
            )
        except Exception:
            trace_id = str(uuid.uuid4())
            return StructuredFailure(
                code=FailureCode.QUERY_INVALID,
                message="Simulation evidence service is unavailable.",
                details={},
                trace_id=trace_id,
            )


__all__ = [
    "T3Adapter",
    "FakeT3Adapter",
    "RealT3Adapter",
    "T3KnowledgeTier",
    "T3LegalEvidence",
    "T3SimulationData",
]
