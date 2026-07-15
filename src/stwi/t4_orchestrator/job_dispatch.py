"""Celery dispatch boundary for persisted STWI jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from stwi.t4_orchestrator.contracts import WhatIfJobRequest


JOB_TASK_NAME = "stwi.execute_what_if_job"


class CeleryJobDispatcher:
    """Queue jobs by stable task id; job state remains in RedisJobStore."""

    is_provisional_dispatcher = False

    def __init__(self, celery_app: Any, *, task_name: str = JOB_TASK_NAME) -> None:
        self._app = celery_app
        self._task_name = task_name

    def dispatch(self, job_id: str, request: WhatIfJobRequest) -> None:
        self._app.send_task(
            self._task_name,
            args=[job_id, request.model_dump(mode="json")],
            task_id=job_id,
        )


class BackgroundJobDispatcher:
    """Explicit provisional dispatcher used only for local demo/test."""

    is_provisional_dispatcher = True

    def __init__(self, callback: Callable[[str, WhatIfJobRequest], None]) -> None:
        self._callback = callback

    def dispatch(self, job_id: str, request: WhatIfJobRequest) -> None:
        self._callback(job_id, request)


def register_celery_job_task(
    celery_app: Any,
    *,
    store_factory: Callable[[], Any],
    orchestrator_factory: Callable[[], Any],
) -> Any:
    """Register the worker task without hiding production composition choices."""
    from stwi.t4_orchestrator.api import _run_job

    @celery_app.task(name=JOB_TASK_NAME, acks_late=True)
    def execute(job_id: str, request_payload: dict[str, Any]) -> None:
        _run_job(
            job_id,
            WhatIfJobRequest.model_validate(request_payload),
            store_factory(),
            orchestrator_factory(),
        )

    return execute


__all__ = [
    "BackgroundJobDispatcher",
    "CeleryJobDispatcher",
    "JOB_TASK_NAME",
    "register_celery_job_task",
]
