"""STWI FastAPI server entrypoint — Phase 4 provisional.

Start with:
    uvicorn stwi.app:app --host 0.0.0.0 --port 8000 --reload

Or via Docker:
    docker compose -f infra/harness/compose.phase4.yaml up

Phase 4 uses InMemoryJobStore (no Redis/Celery).
Replace with real adapters when Docker services are available.
"""

from stwi.t4_orchestrator.api import create_app

app = create_app()
