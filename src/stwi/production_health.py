"""Redacted dependency readiness check for STWI production containers."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TextIO

from stwi.production_components import (
    ProductionConfigurationError,
    ProductionSettings,
    load_component_factory,
    validate_components,
)
from stwi.t4_orchestrator.runtime_artifacts import (
    RuntimeArtifactError,
    RuntimeArtifactSet,
)


Probe = Callable[[ProductionSettings], None]


def validate_static_configuration(
    environ: Mapping[str, str] | None = None,
) -> ProductionSettings:
    """Validate settings, trusted component shape and promoted artifacts."""
    settings = ProductionSettings.from_environ(environ)
    factory = load_component_factory(settings.component_factory)
    try:
        components = factory(settings)
        validate_components(components)
    except ProductionConfigurationError:
        raise
    except Exception as exc:
        raise ProductionConfigurationError("COMPONENT_FACTORY_FAILED") from exc
    RuntimeArtifactSet.load(
        baseline_manifest=settings.baseline_manifest,
        surrogate_manifest=settings.surrogate_manifest,
    )
    _probe_principal_resolver(components)
    return settings


def _probe_principal_resolver(components: Any) -> None:
    """Fail closed when the deployed resolver cannot produce a principal.

    The probe verifies that the non-provisional deployment identity resolves
    to a usable principal. Identity values themselves are never logged.
    """
    resolver = getattr(components, "principal_resolver", None)
    if resolver is None:
        raise RuntimeError("principal resolver missing")
    if any(
        bool(getattr(resolver, marker, False))
        for marker in ("is_provisional_resolver", "is_provisional_adapter")
    ):
        raise RuntimeError("provisional principal resolver rejected")
    try:
        principal = resolver.resolve()
    except Exception as exc:
        raise RuntimeError("principal resolution failed") from exc
    tenant_id = str(getattr(principal, "tenant_id", "")).strip()
    operator_id = str(getattr(principal, "operator_id", "")).strip()
    roles = getattr(principal, "roles", frozenset())
    if not tenant_id or not operator_id or not roles:
        raise RuntimeError("resolved principal is incomplete")


def _probe_redis(settings: ProductionSettings) -> None:
    from redis import Redis

    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    if client.ping() is not True:
        raise RuntimeError("redis ping rejected")


def _probe_qdrant(settings: ProductionSettings) -> None:
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=3,
    )
    client.get_collections()


def _probe_timescaledb(settings: ProductionSettings) -> None:
    import psycopg

    with psycopg.connect(settings.tsdb_dsn, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
    if row != (1,):
        raise RuntimeError("timescaledb probe rejected")


DEFAULT_PROBES: dict[str, Probe] = {
    "redis": _probe_redis,
    "qdrant": _probe_qdrant,
    "timescaledb": _probe_timescaledb,
}


def _configuration_code(exc: Exception) -> str:
    if isinstance(exc, ProductionConfigurationError):
        return str(exc).split(":", 1)[0]
    if isinstance(exc, RuntimeArtifactError):
        return "ARTIFACTS_INVALID"
    return "CONFIGURATION_INVALID"


def evaluate_readiness(
    *,
    environ: Mapping[str, str] | None = None,
    probes: Mapping[str, Probe] | None = None,
    command: str = "readiness",
) -> dict[str, Any]:
    """Return a secret-free verdict; dependency exceptions are never exposed."""
    checks: list[dict[str, str]] = []
    try:
        settings = validate_static_configuration(environ)
    except Exception as exc:
        checks.append(
            {
                "name": "configuration",
                "status": "fail",
                "code": _configuration_code(exc),
            }
        )
        return {
            "command": command,
            "profile": "production",
            "status": "fail",
            "checks": checks,
        }

    checks.append({"name": "configuration", "status": "pass", "code": "OK"})
    selected_probes = probes or DEFAULT_PROBES
    for name in ("redis", "qdrant", "timescaledb"):
        probe = selected_probes.get(name)
        try:
            if probe is None:
                raise RuntimeError("probe missing")
            probe(settings)
        except Exception:
            checks.append(
                {
                    "name": name,
                    "status": "fail",
                    "code": f"{name.upper()}_UNAVAILABLE",
                }
            )
        else:
            checks.append({"name": name, "status": "pass", "code": "OK"})
    return {
        "command": command,
        "profile": "production",
        "status": (
            "pass" if all(item["status"] == "pass" for item in checks) else "fail"
        ),
        "checks": checks,
    }


def run_cli(
    *,
    command: str,
    environ: Mapping[str, str] | None = None,
    probes: Mapping[str, Probe] | None = None,
    stdout: TextIO | None = None,
) -> int:
    verdict = evaluate_readiness(
        environ=environ,
        probes=probes,
        command=command,
    )
    print(
        json.dumps(verdict, ensure_ascii=False, separators=(",", ":")),
        file=stdout or sys.stdout,
    )
    return 0 if verdict["status"] == "pass" else 1


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    probes: Mapping[str, Probe] | None = None,
    stdout: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("readiness",))
    arguments = parser.parse_args(argv)
    return run_cli(
        command=arguments.command,
        environ=environ,
        probes=probes,
        stdout=stdout,
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_PROBES",
    "evaluate_readiness",
    "main",
    "run_cli",
    "validate_static_configuration",
]
