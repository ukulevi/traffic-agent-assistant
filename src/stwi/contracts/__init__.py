"""Pydantic contracts: tensor, API, IncidentVector, SimulationResult, Citation, legal, query."""

from stwi.contracts.incident import (
    IncidentSeverity,
    IncidentType,
    IncidentVector,
    SignalPlanDelta,
)

from stwi.contracts.knowledge import (
    Aggregation,
    Citation,
    FailureCode,
    LegalChunk,
    LegalDocument,
    Metric,
    OrderBy,
    RetrievalQuery,
    RetrievalResult,
    RetrieverAdapter,
    SimulationQuery,
    SimulationQueryExecutor,
    StructuredFailure,
)

__all__ = [
    "Aggregation",
    "Citation",
    "FailureCode",
    "IncidentSeverity",
    "IncidentType",
    "IncidentVector",
    "LegalChunk",
    "LegalDocument",
    "Metric",
    "OrderBy",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrieverAdapter",
    "SimulationQuery",
    "SimulationQueryExecutor",
    "StructuredFailure",
    "SignalPlanDelta",
]
