"""Orchestrator-facing runtime interfaces.

The protocols keep Tier 4 dependent on behavior, not provisional fake classes.
They are intentionally narrow and match the methods used by the orchestrator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from stwi.t4_orchestrator.contracts import (
    JobEnvelope,
    JobEvent,
    JobStatus,
    OperatorDecisionRecord,
    WhatIfJobRequest,
)


class BaselineForecast(Protocol):
    """Baseline forecast result shape consumed by Tier 4."""

    node_id: str
    horizon_minutes: int
    predicted_volume: float
    predicted_speed: float
    warning: str


class ScenarioForecast(Protocol):
    """Scenario forecast result shape consumed by Tier 4."""

    node_id: str
    horizon_minutes: int
    predicted_volume: float
    predicted_speed: float
    vc_ratio: float
    uncertainty_score: float
    ood_score: float
    warning: str


class BaselineForecaster(Protocol):
    """Forecast no-intervention baseline aggregates."""

    def predict(
        self,
        node_ids: list[str],
        horizons_minutes: list[int],
        scenario_time: datetime,
    ) -> list[BaselineForecast]:
        ...


class ScenarioForecaster(Protocol):
    """Forecast candidate-action scenario aggregates and safety scores."""

    def predict(
        self,
        node_ids: list[str],
        horizons_minutes: list[int],
        candidate_action: dict[str, Any],
        scenario_time: datetime,
    ) -> list[ScenarioForecast]:
        ...

    def max_vc_ratio(self, results: list[ScenarioForecast]) -> float:
        ...

    def max_uncertainty(self, results: list[ScenarioForecast]) -> float:
        ...

    def max_ood_score(self, results: list[ScenarioForecast]) -> float:
        ...


class LegalEvidenceProvider(Protocol):
    """Tier 3 boundary used by the orchestrator."""

    def query_legal_evidence(
        self,
        query_text: str,
        scenario_time: datetime,
        jurisdiction: str = "VN",
    ) -> object:
        ...


class JobStore(Protocol):
    """Job persistence boundary used by the API layer."""

    def create(self, request: WhatIfJobRequest) -> JobEnvelope:
        ...

    def get(self, job_id: str) -> JobEnvelope | None:
        ...

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
    ) -> None:
        ...

    def set_result(self, job_id: str, result: object) -> None:
        ...

    def record_operator_decision(
        self,
        job_id: str,
        operator_id: str,
        decision: str,
        comment: str | None = None,
    ) -> OperatorDecisionRecord | None:
        ...

    def events_since(self, job_id: str, last_event_id: int = 0) -> list[JobEvent]:
        ...

    def acquire_execution(self, job_id: str, ttl_seconds: int) -> bool:
        ...

    def release_execution(self, job_id: str) -> None:
        ...


class JobDispatcher(Protocol):
    """Queue a previously persisted job for asynchronous execution."""

    def dispatch(self, job_id: str, request: WhatIfJobRequest) -> None:
        ...


__all__ = [
    "BaselineForecast",
    "ScenarioForecast",
    "BaselineForecaster",
    "ScenarioForecaster",
    "LegalEvidenceProvider",
    "JobStore",
    "JobDispatcher",
]
