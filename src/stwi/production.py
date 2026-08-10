"""ASGI entrypoint for the fail-closed STWI production composition."""

from stwi.production_components import (
    ProductionSettings,
    build_production_runtime,
)
from stwi.t4_orchestrator.api import create_app


settings = ProductionSettings.from_environ()
runtime = build_production_runtime(settings)
app = create_app(
    store=runtime.store,
    orchestrator=runtime.orchestrator,
    settings=settings.runtime,
    principal_resolver=runtime.principal_resolver,
    dispatcher=runtime.dispatcher,
    ui_context_provider=runtime.ui_context_provider,
    network_context_provider=runtime.network_context_provider,
)


__all__ = ["app", "runtime", "settings"]
