"""In-memory job store for Phase 4 provisional orchestrator.

Replaces Redis/Celery for Phase 4 provisional.
Must be replaced with Redis-backed store before Phase 5.

Fake adapter label: in_memory_phase4_provisional
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from typing import Any

from stwi.t4_orchestrator.contracts import (
    JobEnvelope,
    JobEvent,
    JobStatus,
    OperatorDecisionRecord,
    WhatIfJobRequest,
)


class InMemoryJobStore:
    """Thread-safe in-memory job store.

    Phase 4 provisional — replaced by Redis in Phase 5.
    """

    is_provisional_store = True

    def __init__(self) -> None:
        self._jobs: dict[str, JobEnvelope] = {}
        self._events: dict[str, list[JobEvent]] = {}
        self._lock = threading.Lock()

    def create(self, request: WhatIfJobRequest) -> JobEnvelope:
        """Create a new job in QUEUED state and return its envelope."""
        job_id = str(uuid.uuid4())
        envelope = JobEnvelope(
            job_id=job_id,
            status=JobStatus.QUEUED,
            tenant_id=request.tenant_id,
            request=request,
        )
        with self._lock:
            self._jobs[job_id] = envelope
            self._events[job_id] = []
            self._append_event_locked(
                job_id=job_id,
                event="status",
                status=JobStatus.QUEUED,
                payload={"status": JobStatus.QUEUED.value},
            )
        return envelope

    def get(self, job_id: str) -> JobEnvelope | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
    ) -> None:
        with self._lock:
            env = self._jobs.get(job_id)
            if env is None:
                return
            self._jobs[job_id] = env.model_copy(update={
                "status": status,
                "error_message": error_message,
                "updated_at": datetime.now(timezone.utc),
            })
            self._append_event_locked(
                job_id=job_id,
                event="status",
                status=status,
                payload={
                    "status": status.value,
                    **({"error_message": error_message} if error_message else {}),
                },
            )

    def set_result(self, job_id: str, result: object) -> None:
        with self._lock:
            env = self._jobs.get(job_id)
            if env is None:
                return
            self._jobs[job_id] = env.model_copy(update={
                "status": result.status,
                "result": result,
                "updated_at": datetime.now(timezone.utc),
            })
            self._append_event_locked(
                job_id=job_id,
                event="result",
                status=result.status,
                payload={
                    "status": result.status.value,
                    "trace_id": result.audit_record.trace_id,
                    "safety_iterations": result.safety_iterations,
                },
            )

    def record_operator_decision(
        self,
        job_id: str,
        operator_id: str,
        decision: str,
        comment: str | None = None,
    ) -> OperatorDecisionRecord | None:
        """Record a human decision without executing any field action."""
        with self._lock:
            env = self._jobs.get(job_id)
            if env is None:
                return None
            record = OperatorDecisionRecord(
                job_id=job_id,
                tenant_id=env.tenant_id,
                operator_id=operator_id,
                decision=decision,
                comment=comment,
                applied_by_system=False,
            )
            self._jobs[job_id] = env.model_copy(update={
                "operator_decision": record,
                "updated_at": datetime.now(timezone.utc),
            })
            self._append_event_locked(
                job_id=job_id,
                event="operator_decision",
                status=env.status,
                payload={
                    "decision": record.decision.value,
                    "operator_id": operator_id,
                    "applied_by_system": False,
                },
            )
            return record

    def events_since(self, job_id: str, last_event_id: int = 0) -> list[JobEvent]:
        """Return events with id greater than last_event_id for SSE resume."""
        with self._lock:
            return [
                event for event in self._events.get(job_id, [])
                if event.id > last_event_id
            ]

    def all_jobs(self) -> list[JobEnvelope]:
        with self._lock:
            return list(self._jobs.values())

    def _append_event_locked(
        self,
        job_id: str,
        event: str,
        status: JobStatus | None = None,
        payload: dict[str, Any] | None = None,
    ) -> JobEvent:
        events = self._events.setdefault(job_id, [])
        next_id = len(events) + 1
        job_event = JobEvent(
            id=next_id,
            job_id=job_id,
            event=event,
            status=status,
            payload=payload or {},
        )
        events.append(job_event)
        return job_event


# Module-level singleton for the FastAPI app
_default_store: InMemoryJobStore | None = None


def get_job_store() -> InMemoryJobStore:
    global _default_store
    if _default_store is None:
        _default_store = InMemoryJobStore()
    return _default_store


__all__ = ["InMemoryJobStore", "get_job_store"]
