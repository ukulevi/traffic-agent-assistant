"""Pydantic contracts: tensor, API, IncidentVector, SimulationResult, Citation, legal, query."""

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
]