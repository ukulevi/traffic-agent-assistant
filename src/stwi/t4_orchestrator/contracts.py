"""Phase 4 orchestrator contracts.

All orchestrator outputs are strictly typed. The system is decision-support only:
- 'recommended_action' is ONLY set when status == succeeded AND all safety checks pass.
- 'candidate_action' is set when status == needs_review (human must approve/reject).
- Automatic actuation is NEVER performed.
- Human approval is ALWAYS required before any action is applied.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Job lifecycle statuses (from project_contract.json)
# =============================================================================

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    EXPIRED = "expired"


# =============================================================================
# Request
# =============================================================================

class CandidateAction(BaseModel):
    """Typed, non-executable signal-plan candidate evaluated by STWI."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    node_id: str = Field(..., min_length=1, max_length=64)
    green_time_ratio: float = Field(..., ge=0.0, le=1.0)


class WhatIfJobRequest(BaseModel):
    """Input specification for a what-if scenario job."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(
        ..., min_length=1, max_length=128,
        description="Tenant scope for row ownership and audit",
    )
    scenario_time: datetime = Field(..., description="Time context for legal/temporal filtering")
    candidate_action: CandidateAction = Field(
        ..., description="Proposed action (e.g. {'node_id': 'A', 'green_time_ratio': 0.7})"
    )
    node_ids: list[str] = Field(..., min_length=1, description="Network nodes to evaluate")
    scenario_query: str = Field(
        ..., min_length=1, description="Natural language query for RAG legal evidence"
    )
    horizons_minutes: list[int] = Field(
        default_factory=lambda: [5, 10, 15, 30],
        min_length=1,
        max_length=12,
        description="Forecast horizons in minutes",
    )
    jurisdiction: str = Field(
        "VN", min_length=1, max_length=32,
        description="Jurisdiction for legal corpus filtering",
    )
    vc_threshold: float = Field(
        0.9, ge=0.0, le=1.0,
        description="Volume-capacity ratio safety threshold (configurable policy)"
    )

    @model_validator(mode="after")
    def validate_action_scope(self) -> WhatIfJobRequest:
        if any(not node_id for node_id in self.node_ids):
            raise ValueError("node_ids must not contain blank identifiers")
        if self.candidate_action.node_id not in self.node_ids:
            raise ValueError("candidate_action.node_id must be present in node_ids")
        return self


class OperatorDecision(str, Enum):
    """Human operator decision recorded after a job result is reviewed."""

    APPROVED = "approved"
    REJECTED = "rejected"
    REQUEST_CHANGES = "request_changes"


class OperatorDecisionRecord(BaseModel):
    """Audit-only operator decision.

    This record never triggers an actuator. It is a human approval/rejection
    trace for decision-support accountability.
    """

    job_id: str
    tenant_id: str
    operator_id: str = Field(..., min_length=1)
    decision: OperatorDecision
    comment: str | None = None
    applied_by_system: bool = Field(
        False,
        description="Must remain false; STWI does not execute field actions.",
    )
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def enforce_no_system_actuation(self) -> OperatorDecisionRecord:
        if self.applied_by_system is not False:
            raise ValueError("operator decision must not trigger system actuation")
        return self


class OperatorDecisionRequest(BaseModel):
    """API request to record a human operator decision."""

    operator_id: str = Field(..., min_length=1)
    decision: OperatorDecision
    comment: str | None = None


class JobEvent(BaseModel):
    """Append-only progress event for SSE resume/idempotency."""

    id: int = Field(..., ge=1)
    job_id: str
    event: str
    status: JobStatus | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Audit record
# =============================================================================

class AuditRecord(BaseModel):
    """Immutable audit trail for every job outcome.

    Recorded regardless of job status. Required for regulatory traceability.
    """

    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    tenant_id: str
    scenario_time: datetime
    model_version: str
    corpus_parser_version: str
    status: JobStatus
    status_reason: str
    safety_iterations: int = Field(0, ge=0, le=3)
    artifact_provenance: dict[str, dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Safety check result
# =============================================================================

class SafetyCheckResult(BaseModel):
    """Result from one iteration of the Counterfactual Safety Loop."""

    passed: bool
    iteration: int = Field(..., ge=1, le=3)
    vc_ratio_ok: bool
    citations_ok: bool
    uncertainty_ok: bool
    ood_ok: bool
    fail_reason: str | None = None

    # Raw metrics (for audit/debug)
    max_vc_ratio: float | None = None
    vc_threshold: float | None = None
    uncertainty_score: float | None = None
    ood_score: float | None = None


# =============================================================================
# Job result
# =============================================================================

class WhatIfJobResult(BaseModel):
    """Complete result of a what-if scenario job.

    Contract invariants enforced by model_validator:
    - recommended_action is ONLY set when status == succeeded.
    - candidate_action is ONLY set when status == needs_review.
    - Neither is set when status == failed or expired.
    """

    job_id: str
    status: JobStatus
    tenant_id: str
    scenario_time: datetime

    # Action fields — mutually exclusive, enforced below
    recommended_action: dict[str, Any] | None = Field(
        None, description="Safe action for operator to OPTIONALLY apply. NEVER auto-executed."
    )
    candidate_action: dict[str, Any] | None = Field(
        None, description="Proposed action that REQUIRES human review before any use."
    )

    # Evidence
    citations: list[dict[str, Any]] = Field(
        default_factory=list, description="Legal evidence supporting the evaluation"
    )
    needs_review_reason: str | None = None

    # Forecast summaries (aggregate only — no raw frame data)
    baseline_summary: dict[str, Any] | None = None
    scenario_summary: dict[str, Any] | None = None

    # Safety
    safety_iterations: int = Field(0, ge=0, le=3)
    safety_checks: list[SafetyCheckResult] = Field(default_factory=list)

    # Audit
    audit_record: AuditRecord
    model_version: str = "provisional_mock_v1"
    data_version: str = "synthetic_mock_phase4"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def enforce_action_field_semantics(self) -> WhatIfJobResult:
        """Enforce contract: action fields must match job status."""
        if self.status == JobStatus.SUCCEEDED:
            if self.recommended_action is None:
                raise ValueError("succeeded job must have recommended_action")
            if self.candidate_action is not None:
                raise ValueError("succeeded job must not have candidate_action")
        elif self.status == JobStatus.NEEDS_REVIEW:
            if self.candidate_action is None:
                raise ValueError("needs_review job must have candidate_action")
            if self.recommended_action is not None:
                raise ValueError("needs_review job must not have recommended_action")
        else:
            # failed, expired, queued, running — neither action field
            if self.recommended_action is not None:
                raise ValueError(f"{self.status} job must not have recommended_action")
            if self.candidate_action is not None:
                raise ValueError(f"{self.status} job must not have candidate_action")
        return self


# =============================================================================
# Job envelope (stored in job store, returned from GET endpoint)
# =============================================================================

class JobEnvelope(BaseModel):
    """Stored job state — returned by GET /api/v1/what-if-jobs/{job_id}."""

    job_id: str
    status: JobStatus
    tenant_id: str
    request: WhatIfJobRequest
    result: WhatIfJobResult | None = None
    operator_decision: OperatorDecisionRecord | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: str | None = None


__all__ = [
    "JobStatus",
    "CandidateAction",
    "WhatIfJobRequest",
    "WhatIfJobResult",
    "OperatorDecision",
    "OperatorDecisionRequest",
    "OperatorDecisionRecord",
    "AuditRecord",
    "SafetyCheckResult",
    "JobEvent",
    "JobEnvelope",
]
