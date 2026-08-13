"""Fail-closed composition boundary for the STWI production processes.

Application-specific model and identity adapters are supplied by one explicit
``module:callable`` factory.  STWI owns the approved infrastructure wiring and
never falls back to demo, fake, body-derived or in-memory components here.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stwi.config.runtime import RuntimeMode, RuntimeSettings, get_runtime_settings
from stwi.t3_knowledge.tier3_facade import RealT3Adapter, T3KnowledgeTier
from stwi.t1_pipeline.network_topology import (
    NetworkTopologyRegistry,
    build_synthetic_topology,
)
from stwi.t4_orchestrator.job_dispatch import CeleryJobDispatcher
from stwi.t4_orchestrator.network_context import AuthorizedNetworkContextProvider
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator
from stwi.t4_orchestrator.redis_job_store import RedisJobStore
from stwi.t4_orchestrator.runtime_artifacts import RuntimeArtifactSet


class ProductionConfigurationError(RuntimeError):
    """Stable, redacted production configuration failure."""


@dataclass(frozen=True)
class ProductionSettings:
    """Environment-derived settings required by API and worker composition."""

    redis_url: str
    tsdb_dsn: str
    qdrant_url: str
    qdrant_api_key: str | None
    baseline_manifest: Path
    surrogate_manifest: Path
    legal_corpus_dir: Path
    component_factory: str
    runtime: RuntimeSettings

    @classmethod
    def from_environ(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "ProductionSettings":
        env = environ if environ is not None else os.environ
        try:
            runtime = get_runtime_settings(dict(env))
        except ValueError as exc:
            raise ProductionConfigurationError("PRODUCTION_MODE_INVALID") from exc
        if runtime.mode != RuntimeMode.PRODUCTION:
            raise ProductionConfigurationError("PRODUCTION_MODE_REQUIRED")

        def required(name: str, code: str) -> str:
            value = env.get(name, "").strip()
            if not value:
                raise ProductionConfigurationError(code)
            return value

        return cls(
            redis_url=required("STWI_REDIS_URL", "REDIS_URL_REQUIRED"),
            tsdb_dsn=required("STWI_TSDB_DSN", "TSDB_DSN_REQUIRED"),
            qdrant_url=required("STWI_QDRANT_URL", "QDRANT_URL_REQUIRED"),
            qdrant_api_key=env.get("STWI_QDRANT_API_KEY") or None,
            baseline_manifest=Path(
                required("STWI_BASELINE_MANIFEST", "BASELINE_MANIFEST_REQUIRED")
            ),
            surrogate_manifest=Path(
                required("STWI_SURROGATE_MANIFEST", "SURROGATE_MANIFEST_REQUIRED")
            ),
            legal_corpus_dir=Path(
                required("STWI_LEGAL_CORPUS_DIR", "LEGAL_CORPUS_REQUIRED")
            ),
            component_factory=required(
                "STWI_PRODUCTION_COMPONENT_FACTORY",
                "COMPONENT_FACTORY_REQUIRED",
            ),
            runtime=runtime,
        )


@dataclass(frozen=True)
class ProductionComponents:
    """Deployment-owned adapters required by the STWI composition root."""

    baseline: Any
    surrogate: Any
    principal_resolver: Any
    ui_context_provider: Any


@dataclass(frozen=True)
class ProductionRuntime:
    """Fully composed API/worker dependencies for the production profile."""

    settings: ProductionSettings
    components: ProductionComponents
    artifacts: RuntimeArtifactSet
    store: RedisJobStore
    celery_app: Any
    dispatcher: CeleryJobDispatcher
    orchestrator: WhatIfOrchestrator
    principal_resolver: Any
    ui_context_provider: Any
    network_context_provider: AuthorizedNetworkContextProvider


ComponentFactory = Callable[[ProductionSettings], ProductionComponents]


def load_component_factory(import_path: str) -> ComponentFactory:
    """Load an explicit ``module:callable`` without exposing import details."""
    module_name, separator, attribute_name = import_path.partition(":")
    if not separator or not module_name.strip() or not attribute_name.strip():
        raise ProductionConfigurationError("COMPONENT_FACTORY_INVALID")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute_name)
    except (ImportError, AttributeError) as exc:
        raise ProductionConfigurationError("COMPONENT_FACTORY_UNAVAILABLE") from exc
    if not callable(factory):
        raise ProductionConfigurationError("COMPONENT_FACTORY_NOT_CALLABLE")
    return factory


_PROVISIONAL_MARKERS = (
    "is_provisional_adapter",
    "uses_provisional_adapter",
    "uses_provisional_adapters",
    "is_provisional_resolver",
    "is_provisional_provider",
)


def validate_components(
    components: ProductionComponents,
) -> ProductionComponents:
    """Reject incomplete or explicitly provisional deployment components."""
    if not isinstance(components, ProductionComponents):
        raise ProductionConfigurationError("COMPONENT_FACTORY_RESULT_INVALID")
    for field_name in (
        "baseline",
        "surrogate",
        "principal_resolver",
        "ui_context_provider",
    ):
        component = getattr(components, field_name)
        if component is None:
            raise ProductionConfigurationError(f"COMPONENT_REQUIRED:{field_name}")
        if any(bool(getattr(component, marker, False)) for marker in _PROVISIONAL_MARKERS):
            raise ProductionConfigurationError(
                f"PROVISIONAL_COMPONENT:{field_name}"
            )
    return components


def build_production_runtime(settings: ProductionSettings) -> ProductionRuntime:
    """Compose approved infrastructure and deployment-owned real adapters."""
    factory = load_component_factory(settings.component_factory)
    try:
        components = validate_components(factory(settings))
    except ProductionConfigurationError:
        raise
    except Exception as exc:
        raise ProductionConfigurationError("COMPONENT_FACTORY_FAILED") from exc

    artifacts = RuntimeArtifactSet.load(
        baseline_manifest=settings.baseline_manifest,
        surrogate_manifest=settings.surrogate_manifest,
    )
    store = RedisJobStore.from_url(settings.redis_url)

    try:
        from celery import Celery
    except ImportError as exc:
        raise ProductionConfigurationError("CELERY_DEPENDENCY_REQUIRED") from exc
    celery_app = Celery(
        "stwi",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    celery_app.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        result_serializer="json",
        task_serializer="json",
    )
    dispatcher = CeleryJobDispatcher(celery_app)

    t3 = T3KnowledgeTier(
        adapter=RealT3Adapter(
            qdrant_url=settings.qdrant_url,
            tsdb_dsn=settings.tsdb_dsn,
            corpus_dir=settings.legal_corpus_dir,
        )
    )
    topology = build_synthetic_topology()
    orchestrator = WhatIfOrchestrator(
        baseline=components.baseline,
        surrogate=components.surrogate,
        t3=t3,
        settings=settings.runtime,
        runtime_artifacts=artifacts,
        network_topology=topology,
    )
    network_context_provider = AuthorizedNetworkContextProvider(
        registry=NetworkTopologyRegistry((topology,)),
        network_version=topology.network_version,
        ui_context_provider=components.ui_context_provider,
    )
    return ProductionRuntime(
        settings=settings,
        components=components,
        artifacts=artifacts,
        store=store,
        celery_app=celery_app,
        dispatcher=dispatcher,
        orchestrator=orchestrator,
        principal_resolver=components.principal_resolver,
        ui_context_provider=components.ui_context_provider,
        network_context_provider=network_context_provider,
    )


__all__ = [
    "ComponentFactory",
    "ProductionComponents",
    "ProductionConfigurationError",
    "ProductionRuntime",
    "ProductionSettings",
    "build_production_runtime",
    "load_component_factory",
    "validate_components",
]
