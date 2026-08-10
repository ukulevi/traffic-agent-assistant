"""Celery worker entrypoint for persisted STWI production jobs."""

from stwi.production_components import (
    ProductionSettings,
    build_production_runtime,
)
from stwi.t4_orchestrator.job_dispatch import (
    JOB_TASK_NAME,
    register_celery_job_task,
)


settings = ProductionSettings.from_environ()
runtime = build_production_runtime(settings)
app = runtime.celery_app
execute_what_if_job = register_celery_job_task(
    app,
    store_factory=lambda: runtime.store,
    orchestrator_factory=lambda: runtime.orchestrator,
)


__all__ = [
    "JOB_TASK_NAME",
    "app",
    "execute_what_if_job",
    "runtime",
    "settings",
]
