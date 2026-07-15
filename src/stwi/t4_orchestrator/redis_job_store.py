"""Redis-backed append-only job and SSE event persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from stwi.t4_orchestrator.contracts import (
    JobEnvelope,
    JobEvent,
    JobStatus,
    OperatorDecisionRecord,
    WhatIfJobRequest,
)


TERMINAL_STATUSES = {
    JobStatus.SUCCEEDED,
    JobStatus.NEEDS_REVIEW,
    JobStatus.FAILED,
    JobStatus.EXPIRED,
}


class RedisJobStore:
    """Persistent job store with optimistic locking and monotonic SSE IDs."""

    is_provisional_store = False

    def __init__(self, client: Any, *, prefix: str = "stwi") -> None:
        self._client = client
        self._prefix = prefix.rstrip(":")
        self._execution_tokens: dict[str, str] = {}

    @classmethod
    def from_url(cls, redis_url: str, *, prefix: str = "stwi") -> "RedisJobStore":
        if not redis_url:
            raise ValueError("Redis URL is required")
        from redis import Redis

        return cls(Redis.from_url(redis_url, decode_responses=True), prefix=prefix)

    def _key(self, job_id: str) -> str:
        return f"{self._prefix}:job:{job_id}"

    def _events_key(self, job_id: str) -> str:
        return f"{self._key(job_id)}:events"

    def _sequence_key(self, job_id: str) -> str:
        return f"{self._key(job_id)}:event-sequence"

    def _lock_key(self, job_id: str) -> str:
        return f"{self._key(job_id)}:execution-lock"

    def create(self, request: WhatIfJobRequest) -> JobEnvelope:
        job_id = str(uuid.uuid4())
        envelope = JobEnvelope(
            job_id=job_id,
            status=JobStatus.QUEUED,
            tenant_id=request.tenant_id,
            request=request,
        )
        event = JobEvent(
            id=1,
            job_id=job_id,
            event="status",
            status=JobStatus.QUEUED,
            payload={"status": JobStatus.QUEUED.value},
        )
        with self._client.pipeline(transaction=True) as pipe:
            pipe.set(self._key(job_id), envelope.model_dump_json())
            pipe.set(self._sequence_key(job_id), 1)
            pipe.rpush(self._events_key(job_id), event.model_dump_json())
            pipe.execute()
        return envelope

    def get(self, job_id: str) -> JobEnvelope | None:
        raw = self._client.get(self._key(job_id))
        return JobEnvelope.model_validate_json(raw) if raw else None

    def _mutate(
        self,
        job_id: str,
        update: Callable[[JobEnvelope], JobEnvelope | None],
        event_name: str,
        event_payload: Callable[[JobEnvelope], dict[str, Any]],
    ) -> JobEnvelope | None:
        from redis.exceptions import WatchError

        key = self._key(job_id)
        while True:
            with self._client.pipeline() as pipe:
                try:
                    pipe.watch(key, self._sequence_key(job_id))
                    raw = pipe.get(key)
                    if not raw:
                        pipe.unwatch()
                        return None
                    current = JobEnvelope.model_validate_json(raw)
                    updated = update(current)
                    if updated is None:
                        pipe.unwatch()
                        return current
                    next_id = int(pipe.get(self._sequence_key(job_id)) or 0) + 1
                    event = JobEvent(
                        id=next_id,
                        job_id=job_id,
                        event=event_name,
                        status=updated.status,
                        payload=event_payload(updated),
                    )
                    pipe.multi()
                    pipe.set(key, updated.model_dump_json())
                    pipe.set(self._sequence_key(job_id), next_id)
                    pipe.rpush(self._events_key(job_id), event.model_dump_json())
                    pipe.execute()
                    return updated
                except WatchError:
                    continue

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: str | None = None,
    ) -> None:
        def update(envelope: JobEnvelope) -> JobEnvelope | None:
            if envelope.status == status:
                return None
            if envelope.status in TERMINAL_STATUSES:
                return None
            return envelope.model_copy(
                update={
                    "status": status,
                    "error_message": error_message,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        self._mutate(
            job_id,
            update,
            "status",
            lambda envelope: {
                "status": envelope.status.value,
                **(
                    {"error_message": envelope.error_message}
                    if envelope.error_message
                    else {}
                ),
            },
        )

    def set_result(self, job_id: str, result: object) -> None:
        def update(envelope: JobEnvelope) -> JobEnvelope | None:
            if envelope.status in TERMINAL_STATUSES:
                return None
            return envelope.model_copy(
                update={
                    "status": result.status,
                    "result": result,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        self._mutate(
            job_id,
            update,
            "result",
            lambda envelope: {
                "status": envelope.status.value,
                "trace_id": envelope.result.audit_record.trace_id,
                "safety_iterations": envelope.result.safety_iterations,
            },
        )

    def record_operator_decision(
        self,
        job_id: str,
        operator_id: str,
        decision: str,
        comment: str | None = None,
    ) -> OperatorDecisionRecord | None:
        record_holder: list[OperatorDecisionRecord] = []

        def update(envelope: JobEnvelope) -> JobEnvelope | None:
            if envelope.status not in TERMINAL_STATUSES:
                return None
            if envelope.operator_decision is not None:
                record_holder.append(envelope.operator_decision)
                return None
            record = OperatorDecisionRecord(
                job_id=job_id,
                tenant_id=envelope.tenant_id,
                operator_id=operator_id,
                decision=decision,
                comment=comment,
                applied_by_system=False,
            )
            record_holder.append(record)
            return envelope.model_copy(
                update={
                    "operator_decision": record,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        updated = self._mutate(
            job_id,
            update,
            "operator_decision",
            lambda _envelope: {
                "decision": record_holder[0].decision.value,
                "operator_id": record_holder[0].operator_id,
                "applied_by_system": False,
            },
        )
        if updated is None or not record_holder:
            return None
        return record_holder[0]

    def events_since(self, job_id: str, last_event_id: int = 0) -> list[JobEvent]:
        raw_events = self._client.lrange(self._events_key(job_id), 0, -1)
        events = [JobEvent.model_validate_json(raw) for raw in raw_events]
        return [event for event in events if event.id > last_event_id]

    def acquire_execution(self, job_id: str, ttl_seconds: int) -> bool:
        envelope = self.get(job_id)
        if envelope is None or envelope.status in TERMINAL_STATUSES:
            return False
        token = str(uuid.uuid4())
        acquired = bool(
            self._client.set(
                self._lock_key(job_id),
                token,
                nx=True,
                ex=max(int(ttl_seconds), 1),
            )
        )
        if not acquired:
            return False
        self._execution_tokens[job_id] = token
        current = self.get(job_id)
        if current is None or current.status in TERMINAL_STATUSES:
            self.release_execution(job_id)
            return False
        return True

    def release_execution(self, job_id: str) -> None:
        from redis.exceptions import WatchError

        token = self._execution_tokens.pop(job_id, None)
        if token is None:
            return
        key = self._lock_key(job_id)
        while True:
            with self._client.pipeline() as pipe:
                try:
                    pipe.watch(key)
                    if pipe.get(key) != token:
                        pipe.unwatch()
                        return
                    pipe.multi()
                    pipe.delete(key)
                    pipe.execute()
                    return
                except WatchError:
                    continue


__all__ = ["RedisJobStore", "TERMINAL_STATUSES"]
