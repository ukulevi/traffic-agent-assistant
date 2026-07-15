"""FastAPI application — Phase 4 what-if job API.

Endpoints (from project_contract.json):
  POST /api/v1/what-if-jobs          → 202 Accepted + job_id
  GET  /api/v1/what-if-jobs/{job_id} → job status + result
  GET  /api/v1/what-if-jobs/{job_id}/events → SSE progress stream

Phase 4 provisional:
- Jobs run synchronously in a background thread (no real Celery/Redis).
- SSE streams the final result event; polling GET also works.
- Swap BackgroundTasks for Celery workers in Phase 5.

SSE event format:
  data: {"event": "status", "status": "queued", "job_id": "..."}
  data: {"event": "status", "status": "running", "job_id": "..."}
  data: {"event": "result", "status": "succeeded|needs_review|failed", ...}
  data: {"event": "error", "message": "..."}
"""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from stwi.config.runtime import RuntimeSettings, get_runtime_settings
from stwi.t4_orchestrator.auth import (
    PrincipalResolutionError,
    PrincipalResolver,
    PrincipalRole,
    ProvisionalBodyPrincipalResolver,
    ServerPrincipal,
)
from stwi.t4_orchestrator.contracts import (
    JobEnvelope,
    JobEvent,
    JobStatus,
    OperatorDecisionRequest,
    WhatIfJobRequest,
)
from stwi.t4_orchestrator.interfaces import JobDispatcher, JobStore
from stwi.t4_orchestrator.job_store import InMemoryJobStore, get_job_store
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app factory — lazy import so the module loads without fastapi
# installed (for contract tests that only import orchestrator/contracts).
# ---------------------------------------------------------------------------

def create_app(
    store: JobStore | None = None,
    orchestrator: WhatIfOrchestrator | None = None,
    settings: RuntimeSettings | None = None,
    principal_resolver: PrincipalResolver | None = None,
    dispatcher: JobDispatcher | None = None,
) -> object:
    """Create and return the FastAPI application.

    Args:
        store: Job store to use (defaults to module-level singleton).
        orchestrator: Orchestrator to use (defaults to FakeT3Adapter-backed).
    """
    _settings = settings or get_runtime_settings()
    if not _settings.allow_provisional_adapters and (
        store is None or orchestrator is None
    ):
        raise RuntimeError(
            "Production runtime requires explicit job store and orchestrator; "
            "InMemoryJobStore/provisional defaults are disabled."
        )
    if not _settings.allow_provisional_adapters and (
        getattr(store, "is_provisional_store", False)
        or getattr(orchestrator, "uses_provisional_adapters", False)
    ):
        raise RuntimeError(
            "Production runtime rejects provisional in-memory stores and "
            "adapters."
        )
    if principal_resolver is None:
        if not _settings.allow_provisional_adapters:
            raise RuntimeError(
                "Production runtime requires an explicit server-side "
                "PrincipalResolver."
            )
        principal_resolver = ProvisionalBodyPrincipalResolver()
    if not _settings.allow_provisional_adapters and getattr(
        principal_resolver,
        "is_provisional_resolver",
        False,
    ):
        raise RuntimeError(
            "Production runtime rejects provisional PrincipalResolver "
            "implementations."
        )
    if not _settings.allow_provisional_adapters and dispatcher is None:
        raise RuntimeError(
            "Production runtime requires an explicit Celery job dispatcher."
        )
    if not _settings.allow_provisional_adapters and getattr(
        dispatcher,
        "is_provisional_dispatcher",
        False,
    ):
        raise RuntimeError("Production runtime rejects provisional job dispatchers.")

    try:
        from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
        from fastapi.responses import JSONResponse, StreamingResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise ImportError(
            "fastapi is required for the API. "
            "Install with: pip install 'stwi[orchestrator]'"
        ) from exc

    _store = store or get_job_store()
    _orchestrator = orchestrator or WhatIfOrchestrator()
    _job_slots = threading.BoundedSemaphore(_settings.job_concurrency)

    def resolve_principal(
        *,
        tenant_hint: str | None = None,
        operator_hint: str | None = None,
    ) -> ServerPrincipal:
        try:
            return principal_resolver.resolve(
                tenant_hint=tenant_hint,
                operator_hint=operator_hint,
            )
        except (PrincipalResolutionError, RuntimeError, ValueError) as exc:
            trace_id = str(uuid.uuid4())
            logger.warning(
                "Auth boundary denied request code=AUTH_PRINCIPAL_REQUIRED trace_id=%s",
                trace_id,
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "AUTH_PRINCIPAL_REQUIRED",
                    "message": "Trusted principal is required",
                    "trace_id": trace_id,
                },
            ) from exc

    def require_roles(principal: ServerPrincipal, *roles: PrincipalRole) -> None:
        if not principal.has_any_role(*roles):
            trace_id = str(uuid.uuid4())
            logger.warning(
                "Auth boundary denied request code=AUTH_ROLE_DENIED trace_id=%s",
                trace_id,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_ROLE_DENIED",
                    "message": "Principal role is not authorized",
                    "trace_id": trace_id,
                },
            )

    def require_tenant(principal: ServerPrincipal, tenant_id: str) -> None:
        if principal.tenant_id != tenant_id:
            trace_id = str(uuid.uuid4())
            logger.warning(
                "Auth boundary denied request code=AUTH_TENANT_DENIED trace_id=%s",
                trace_id,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_TENANT_DENIED",
                    "message": "Cross-tenant access is denied",
                    "trace_id": trace_id,
                },
            )

    app = FastAPI(
        title="STWI What-If API",
        description=(
            "Decision-support only. Automatic actuation is NEVER performed. "
            "Human approval is required before applying any recommended action."
        ),
        version="0.4.0-provisional",
    )
    app.mount(
        "/demo",
        StaticFiles(directory=Path(__file__).with_name("static"), html=True),
        name="demo",
    )

    # -----------------------------------------------------------------------
    # POST /api/v1/what-if-jobs — create job (HTTP 202)
    # -----------------------------------------------------------------------

    @app.post("/api/v1/what-if-jobs", status_code=202)
    async def create_job(
        request: WhatIfJobRequest,
        background_tasks: BackgroundTasks,
    ) -> JSONResponse:
        """Create a what-if scenario job and return 202 Accepted."""
        principal = resolve_principal(tenant_hint=request.tenant_id)
        require_roles(
            principal,
            PrincipalRole.OPERATOR,
            PrincipalRole.ANALYST,
            PrincipalRole.ADMIN,
        )
        require_tenant(principal, request.tenant_id)
        resolved_request = request.model_copy(update={"tenant_id": principal.tenant_id})
        envelope = _store.create(resolved_request)

        try:
            if dispatcher is None:
                background_tasks.add_task(
                    _run_job,
                    envelope.job_id,
                    resolved_request,
                    _store,
                    _orchestrator,
                    _job_slots,
                )
            else:
                dispatcher.dispatch(envelope.job_id, resolved_request)
        except Exception:
            trace_id = str(uuid.uuid4())
            logger.error("Job dispatch failed trace_id=%s", trace_id)
            _store.update_status(
                envelope.job_id,
                JobStatus.FAILED,
                error_message=f"JOB_DISPATCH_FAILED trace_id={trace_id}",
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "JOB_DISPATCH_FAILED",
                    "message": "Job queue is unavailable",
                    "trace_id": trace_id,
                },
            )

        return JSONResponse(
            status_code=202,
            content={
                "job_id": envelope.job_id,
                "status": JobStatus.QUEUED.value,
                "tenant_id": principal.tenant_id,
                "operator_id": principal.operator_id,
                "runtime_mode": _settings.mode.value,
                "message": (
                    "Job accepted. Poll GET /api/v1/what-if-jobs/{job_id} "
                    "or stream GET /api/v1/what-if-jobs/{job_id}/events"
                ),
                "warning": (
                    "Phase 4 provisional — uses synthetic/mock data. "
                    "Not production-ready."
                ),
            },
        )

    # -----------------------------------------------------------------------
    # GET /api/v1/what-if-jobs/{job_id} — poll status
    # -----------------------------------------------------------------------

    @app.get("/api/v1/what-if-jobs/{job_id}")
    async def get_job(job_id: str) -> dict:
        """Return current job status and result (if complete)."""
        envelope = _store.get(job_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        principal = resolve_principal(tenant_hint=envelope.tenant_id)
        require_tenant(principal, envelope.tenant_id)

        response: dict = {
            "job_id": envelope.job_id,
            "status": envelope.status.value,
            "tenant_id": envelope.tenant_id,
            "created_at": envelope.created_at.isoformat(),
            "updated_at": envelope.updated_at.isoformat(),
        }
        if envelope.result is not None:
            response["result"] = _serialize_result(envelope.result)
        if envelope.operator_decision is not None:
            response["operator_decision"] = envelope.operator_decision.model_dump(mode="json")
        if envelope.error_message:
            response["error_message"] = envelope.error_message
        return response

    # -----------------------------------------------------------------------
    # POST /api/v1/what-if-jobs/{job_id}/operator-decision â€” audit-only
    # -----------------------------------------------------------------------

    @app.post("/api/v1/what-if-jobs/{job_id}/operator-decision")
    async def record_operator_decision(
        job_id: str,
        decision_request: OperatorDecisionRequest,
    ) -> dict:
        """Record a human operator decision without executing any action."""
        envelope = _store.get(job_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        principal = resolve_principal(
            tenant_hint=envelope.tenant_id,
            operator_hint=decision_request.operator_id,
        )
        require_tenant(principal, envelope.tenant_id)
        require_roles(principal, PrincipalRole.OPERATOR, PrincipalRole.ADMIN)
        if decision_request.operator_id != principal.operator_id:
            trace_id = str(uuid.uuid4())
            logger.warning(
                "Auth boundary denied request code=AUTH_OPERATOR_MISMATCH trace_id=%s",
                trace_id,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_OPERATOR_MISMATCH",
                    "message": "Operator identity mismatch",
                    "trace_id": trace_id,
                },
            )
        if envelope.status not in (
            JobStatus.SUCCEEDED,
            JobStatus.NEEDS_REVIEW,
            JobStatus.FAILED,
            JobStatus.EXPIRED,
        ):
            raise HTTPException(
                status_code=409,
                detail="Operator decision is allowed only after a terminal job status",
            )
        record = _store.record_operator_decision(
            job_id=job_id,
            operator_id=principal.operator_id,
            decision=decision_request.decision.value,
            comment=decision_request.comment,
        )
        if record is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return {
            "job_id": job_id,
            "operator_decision": record.model_dump(mode="json"),
            "automatic_actuation": False,
            "message": "Decision recorded for audit only; no field action was executed.",
        }

    # -----------------------------------------------------------------------
    # GET /api/v1/what-if-jobs/{job_id}/events — SSE stream
    # -----------------------------------------------------------------------

    @app.get("/api/v1/what-if-jobs/{job_id}/events")
    async def stream_events(
        job_id: str,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        """Stream SSE events for the job lifecycle."""
        envelope = _store.get(job_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        principal = resolve_principal(tenant_hint=envelope.tenant_id)
        require_tenant(principal, envelope.tenant_id)
        resume_after = _parse_last_event_id(last_event_id)

        return StreamingResponse(
            _event_generator(job_id, _store, last_event_id=resume_after),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------

def _run_job(
    job_id: str,
    request: WhatIfJobRequest,
    store: JobStore,
    orchestrator: WhatIfOrchestrator,
    job_slots: threading.BoundedSemaphore | None = None,
) -> None:
    """Run one job within the configured resource-concurrency bound."""
    acquire = getattr(store, "acquire_execution", None)
    acquired = acquire(job_id, 180) if acquire else True
    if not acquired:
        logger.info("Skipped duplicate or terminal job execution job_id=%s", job_id)
        return
    if job_slots is not None:
        job_slots.acquire()
    try:
        store.update_status(job_id, JobStatus.RUNNING)
        try:
            result = orchestrator.run(job_id=job_id, request=request)
            store.set_result(job_id, result)
            logger.info("Job %s completed with status %s", job_id, result.status.value)
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning("Job %s timed out/expired", job_id)
            store.update_status(
                job_id,
                JobStatus.EXPIRED,
                error_message="JOB_HARD_DEADLINE_EXCEEDED",
            )
        except Exception:
            trace_id = str(uuid.uuid4())
            logger.error("Job execution failed job_id=%s trace_id=%s", job_id, trace_id)
            store.update_status(
                job_id,
                JobStatus.FAILED,
                error_message=f"JOB_EXECUTION_FAILED trace_id={trace_id}",
            )
    finally:
        if job_slots is not None:
            job_slots.release()
        release = getattr(store, "release_execution", None)
        if release:
            release(job_id)


# ---------------------------------------------------------------------------
# SSE event generator
# ---------------------------------------------------------------------------

async def _event_generator(
    job_id: str,
    store: JobStore,
    last_event_id: int = 0,
    poll_interval: float = 0.2,
    timeout_seconds: float = 180.0,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted events until job is terminal or timeout."""
    elapsed = 0.0
    cursor = max(last_event_id, 0)

    while elapsed < timeout_seconds:
        envelope = store.get(job_id)
        if envelope is None:
            yield _sse({"event": "error", "message": f"Job {job_id} not found"})
            return

        for event in store.events_since(job_id, cursor):
            cursor = event.id
            yield _sse_event(event)

        terminal = envelope.status in (
            JobStatus.SUCCEEDED,
            JobStatus.NEEDS_REVIEW,
            JobStatus.FAILED,
            JobStatus.EXPIRED,
        )
        if terminal and not store.events_since(job_id, cursor):
            return

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    yield _sse({
        "event": "error",
        "message": "SSE stream window ended; reconnect with Last-Event-ID",
    })


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_event(event: JobEvent) -> str:
    """Format a stored JobEvent with SSE id/event fields for resume."""
    data = {
        "job_id": event.job_id,
        "status": event.status.value if event.status else None,
        "timestamp": event.created_at.isoformat(),
        **event.payload,
    }
    return (
        f"id: {event.id}\n"
        f"event: {event.event}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def _parse_last_event_id(last_event_id: str | None) -> int:
    """Parse Last-Event-ID defensively; invalid values resume from start."""
    if not last_event_id:
        return 0
    try:
        parsed = int(last_event_id)
    except ValueError:
        return 0
    return max(parsed, 0)


# ---------------------------------------------------------------------------
# Result serializer (no sensitive raw data)
# ---------------------------------------------------------------------------

def _serialize_result(result: object) -> dict:
    """Serialize WhatIfJobResult to JSON-safe dict (aggregate only)."""
    d = result.model_dump(mode="json")
    # Nested datetime serialization
    for key in ("scenario_time", "created_at", "completed_at"):
        if d.get(key) and not isinstance(d[key], str):
            d[key] = d[key].isoformat()
    return d


__all__ = ["create_app"]
