"""Strict, versioned evidence manifest for offline and service demo profiles."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapabilityStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_VERIFIED = "not_verified"


class CapabilityEvidence(BaseModel):
    """One capability verdict with bounded, aggregate-only audit metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    kind: Literal["job", "validation", "authorization", "sse", "static", "service"]
    status: CapabilityStatus
    mandatory: bool = True
    expected: str
    observed: str
    terminal_status: Literal["succeeded", "needs_review", "failed", "expired"] | None = None
    trace_id: str | None = None
    model_version: str | None = None
    data_version: str | None = None
    terminal_event_count: int = Field(0, ge=0, le=1)
    recommended_action: dict[str, Any] | None = None
    candidate_action: dict[str, Any] | None = None
    operator_decision: str | None = None
    applied_by_system: bool = False
    automatic_actuation: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_demo_invariants(self) -> "CapabilityEvidence":
        if self.applied_by_system or self.automatic_actuation:
            raise ValueError("demo evidence forbids automatic actuation")
        for action in (self.recommended_action, self.candidate_action):
            if action is not None and (
                action.get("executable") is not False
                or action.get("automatic_actuation", False) is not False
            ):
                raise ValueError("demo actions must be explicitly non-executable")
        if self.kind == "job" and self.status == CapabilityStatus.PASS:
            if not self.trace_id or not self.model_version or not self.data_version:
                raise ValueError("passing job evidence requires trace and versions")
            if self.terminal_event_count != 1:
                raise ValueError("passing job evidence requires one terminal event")
            if self.terminal_status == "succeeded":
                if self.recommended_action is None or self.candidate_action is not None:
                    raise ValueError("succeeded evidence requires recommendation only")
            elif self.terminal_status == "needs_review":
                if self.candidate_action is None or self.recommended_action is not None:
                    raise ValueError("needs_review evidence requires candidate only")
            elif self.terminal_status in {"failed", "expired"}:
                if self.recommended_action is not None or self.candidate_action is not None:
                    raise ValueError("failed/expired evidence must not expose actions")
            else:
                raise ValueError("passing job evidence requires terminal status")
        return self


class DemoEvidence(BaseModel):
    """Complete evidence bundle; verdict is derived from mandatory capabilities."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    harness: Literal["stwi_comprehensive_hybrid_demo"] = "stwi_comprehensive_hybrid_demo"
    profile: Literal["offline", "services"]
    verdict: Literal["pass", "fail", "incomplete"]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_only: bool = True
    live_services_contacted: bool
    raw_video_retained: bool = False
    automatic_actuation: bool = False
    capabilities: list[CapabilityEvidence] = Field(..., min_length=1)

    @model_validator(mode="after")
    def enforce_manifest_invariants(self) -> "DemoEvidence":
        if not self.aggregate_only or self.raw_video_retained or self.automatic_actuation:
            raise ValueError("demo manifest violates aggregate-only safety boundary")
        if self.profile == "offline" and self.live_services_contacted:
            raise ValueError("offline profile cannot contact live services")
        names = [item.name for item in self.capabilities]
        if len(names) != len(set(names)):
            raise ValueError("duplicate capability evidence")
        mandatory = [item for item in self.capabilities if item.mandatory]
        expected_verdict = "pass"
        if any(item.status == CapabilityStatus.FAIL for item in mandatory):
            expected_verdict = "fail"
        elif any(item.status == CapabilityStatus.NOT_VERIFIED for item in mandatory):
            expected_verdict = "incomplete"
        if self.verdict != expected_verdict:
            raise ValueError("manifest verdict does not match mandatory capabilities")
        return self


def write_evidence_atomic(path: Path, evidence: DemoEvidence) -> None:
    """Replace a manifest atomically using a temporary file beside its target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(evidence.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


__all__ = [
    "CapabilityEvidence",
    "CapabilityStatus",
    "DemoEvidence",
    "write_evidence_atomic",
]
