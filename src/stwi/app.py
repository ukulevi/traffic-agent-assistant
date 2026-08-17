"""STWI FastAPI server entrypoint — Phase 4 provisional.

Start with:
    uvicorn stwi.app:app --host 0.0.0.0 --port 8000 --reload

Or via Docker:
    docker compose -f infra/harness/compose.phase4.yaml up

Phase 4 uses InMemoryJobStore (no Redis/Celery).
Replace with real adapters when Docker services are available.
"""

from stwi.config.runtime import RuntimeMode, get_runtime_settings
from stwi.t4_orchestrator.api import create_app
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

_settings = get_runtime_settings()
if _settings.mode == RuntimeMode.DEMO:
    from stwi.t4_orchestrator.demo_adapters import RefinementDemoSurrogateForecaster

    _orchestrator = WhatIfOrchestrator(
        surrogate=RefinementDemoSurrogateForecaster(),
        settings=_settings,
    )
    app = create_app(orchestrator=_orchestrator, settings=_settings)
else:
    app = create_app(settings=_settings)
