"""Tier 3 contracts: Legal documents, citations, retrieval queries, and constrained simulation queries.

All types use Pydantic for runtime validation. External input must be validated at boundaries.
Failure modes return StructuredFailure, never fall back to free-form answers or raw SQL.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# =============================================================================
# Legal Document Contracts
# =============================================================================


class LegalDocument(BaseModel):
    """Validated legal document metadata."""

    document_id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    document_number: str = Field(..., description="Official document number")
    source_url: str = Field(..., description="Official source URL")
    effective_from: date = Field(..., description="Effective date (inclusive)")
    effective_to: date | None = Field(None, description="Superseded date, if any")
    superseded: bool = Field(False, description="Whether document is superseded")
    jurisdiction: str = Field(..., description="Jurisdiction code (e.g., 'VN')")
    content_hash: str = Field(..., description="SHA256 hash of full content")
    retrieved_at: datetime = Field(..., description="Ingestion timestamp")
    parser_version: str = Field(..., description="Parser version used for ingestion")

    @model_validator(mode="after")
    def check_effective_range(self) -> LegalDocument:
        """Validate that the effective date interval is well-formed."""
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class LegalChunk(BaseModel):
    """Validated chunk preserving complete article/provision."""

    document_id: str = Field(..., description="Reference to parent document")
    title: str = Field(..., description="Document title for convenience")
    document_number: str = Field(..., description="Document number for citation")
    provision: str = Field(..., description="Complete provision identifier (e.g., 'Điều 10, Khoản 2')")
    source_url: str = Field(..., description="Source URL for verification")
    effective_from: date = Field(..., description="Effective date (inclusive)")
    effective_to: date | None = Field(None, description="Superseded date, if any")
    superseded: bool = Field(False, description="Whether this version is superseded")
    jurisdiction: str = Field(..., description="Jurisdiction code")
    content_hash: str = Field(..., description="SHA256 hash of chunk content")
    content: str = Field(..., description="Full provision content (not truncated)")

    @model_validator(mode="after")
    def check_effective_range(self) -> LegalChunk:
        """Validate that the effective date interval is well-formed."""
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self

    def is_effective_at(self, scenario_time: datetime) -> bool:
        """Check if this chunk is effective at the given scenario time."""
        time_date = scenario_time.date() if isinstance(scenario_time, datetime) else scenario_time
        if time_date < self.effective_from:
            return False
        if self.effective_to is not None and time_date >= self.effective_to:
            return False
        return not self.superseded

    def citation(self, excerpt: str) -> Citation:
        """Create a citation for this chunk with the given excerpt."""
        return Citation(
            document_id=self.document_id,
            title=self.title,
            document_number=self.document_number,
            provision=self.provision,
            source_url=self.source_url,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
            superseded=self.superseded,
            jurisdiction=self.jurisdiction,
            content_hash=self.content_hash,
            supporting_excerpt=excerpt,
        )


class Citation(BaseModel):
    """Structured citation with verification metadata."""

    document_id: str
    title: str
    document_number: str
    provision: str
    source_url: str
    effective_from: date
    effective_to: date | None = None
    superseded: bool = False
    jurisdiction: str = Field("VN", description="Jurisdiction code")
    content_hash: str
    supporting_excerpt: str = Field(
        ..., min_length=1, description="Excerpt used to support a claim"
    )

    @model_validator(mode="after")
    def check_effective_range(self) -> Citation:
        """Validate that the effective date interval is well-formed."""
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        if not self.supporting_excerpt.strip():
            raise ValueError("supporting_excerpt must not be blank")
        return self

    def is_effective_at(self, scenario_time: datetime) -> bool:
        """Check if this citation is effective at the given scenario time."""
        time_date = scenario_time.date() if isinstance(scenario_time, datetime) else scenario_time
        if time_date < self.effective_from:
            return False
        if self.effective_to is not None and time_date >= self.effective_to:
            return False
        return not self.superseded


# =============================================================================
# Retrieval Contracts
# =============================================================================

class RetrievalQuery(BaseModel):
    """Query for legal/evidence retrieval with temporal context."""

    query_text: str = Field(..., min_length=1, description="Natural language query")
    scenario_time: datetime = Field(..., description="Time context for effective-date filtering")
    jurisdiction: str | None = Field("VN", description="Jurisdiction filter, defaults to VN")
    limit: int = Field(10, ge=1, le=50, description="Maximum results to return")
    include_cases: bool = Field(False, description="Include operational case collection")


class RetrievalResult(BaseModel):
    """Result from retrieval with optional citations or failure."""

    citations: list[Citation] = Field(default_factory=list)
    structured_failure: StructuredFailure | None = None

    @model_validator(mode="after")
    def check_failure_or_citations(self) -> RetrievalResult:
        """If there's a structured failure, citations must be empty."""
        if self.structured_failure is not None and self.citations:
            raise ValueError("structured_failure must have empty citations")
        return self


# =============================================================================
# Simulation Query Contracts
# =============================================================================

class Metric(str, Enum):
    """Allowed metrics for simulation queries."""

    TRAFFIC_VOLUME_5M = "traffic_volume_5m"
    AVG_SPEED_KMH = "avg_speed_kmh"
    HEAVY_VEHICLE_RATIO = "heavy_vehicle_ratio"
    VC_RATIO = "vc_ratio"
    GREEN_TIME_RATIO = "green_time_ratio"


class Aggregation(str, Enum):
    """Allowed aggregation functions."""

    AVG = "avg"
    SUM = "sum"
    MAX = "max"
    MIN = "min"


class OrderBy(str, Enum):
    """Allowed order-by fields."""

    HORIZON_MINUTES = "horizon_minutes"
    NODE_ID = "node_id"
    TIMESTAMP = "timestamp"


class SimulationQuery(BaseModel):
    """Typed simulation query specification (LLM output only).

    This is a Pydantic model - NOT SQL. The SQL builder constructs
    parameterized queries from this specification only.
    """

    job_id: UUID = Field(..., description="Parent what-if job")
    node_ids: list[str] = Field(
        default_factory=list, max_length=100, description="List of node IDs to query"
    )
    metrics: list[Metric] = Field(..., min_length=1, max_length=5, description="Metrics to retrieve")
    horizons_minutes: list[int] = Field(
        default_factory=lambda: [5, 10, 15, 30],
        min_length=1,
        max_length=12,
        description="Forecast horizons in minutes",
    )
    aggregation: Aggregation | None = Field(None, description="Aggregation function")
    order_by: OrderBy | None = Field(None, description="Order by field")
    limit: int = Field(100, ge=1, le=10000, description="Row limit per security policy")
    tenant_id: str | None = Field(None, description="Tenant scope for row ownership filter")


# =============================================================================
# Structured Failure
# =============================================================================

class FailureCode(str, Enum):
    """Structured failure codes for T3."""

    MISSING_EVIDENCE = "missing_evidence"
    OUT_OF_DISTRIBUTION = "out_of_distribution"
    DOCUMENT_EXPIRED = "document_expired"
    CITATION_MISMATCH = "citation_mismatch"
    QUERY_INVALID = "query_invalid"
    INSUFFICIENT_SIMILARITY = "insufficient_similarity"
    PROMPT_INJECTION = "prompt_injection"
    SOURCE_NOT_ALLOWED = "source_not_allowed"
    PROVISION_NOT_FOUND = "provision_not_found"
    TIMEOUT = "timeout"


class StructuredFailure(BaseModel):
    """Structured failure with machine-readable code and message."""

    code: FailureCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


# =============================================================================
# Adapter Protocols
# =============================================================================

class RetrieverAdapter(BaseModel):
    """Protocol for retrieval adapters (Qdrant or fake)."""

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Retrieve citations or return structured failure."""
        raise NotImplementedError


class SimulationQueryResult(BaseModel):
    """Result from executing a SimulationQuery against TimescaleDB or DuckDB.

    rows: list of dicts keyed by column name (e.g. {"node_id": "A", "traffic_volume_5m": 120.0})
    structured_failure: set on error (QUERY_INVALID, TIMEOUT) or no-results (MISSING_EVIDENCE)
    """

    rows: list[dict[str, Any]] = Field(default_factory=list)
    structured_failure: StructuredFailure | None = None

    @model_validator(mode="after")
    def check_failure_or_rows(self) -> SimulationQueryResult:
        """Rows and structured failure are mutually exclusive."""
        if self.structured_failure is not None and self.rows:
            raise ValueError("structured_failure must have empty rows")
        return self


class SimulationQueryExecutor(BaseModel):
    """Protocol for executing SimulationQuery against TimescaleDB."""

    def execute(self, query: SimulationQuery) -> SimulationQueryResult:
        """Execute query and return results or structured failure."""
        raise NotImplementedError


# Re-export for module users
__all__ = [
    "LegalDocument",
    "LegalChunk",
    "Citation",
    "RetrievalQuery",
    "RetrievalResult",
    "SimulationQuery",
    "SimulationQueryResult",
    "Metric",
    "Aggregation",
    "OrderBy",
    "StructuredFailure",
    "FailureCode",
    "RetrieverAdapter",
    "SimulationQueryExecutor",
]
