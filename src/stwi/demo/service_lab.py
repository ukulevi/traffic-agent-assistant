"""Optional real-service demo probes with pass/fail/not_verified semantics."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from stwi.demo.evidence import (
    CapabilityEvidence,
    CapabilityStatus,
    DemoEvidence,
    write_evidence_atomic,
)


class ServiceUnavailable(RuntimeError):
    """The service profile lacks configuration or a runnable dependency."""


ServiceProbe = Callable[[], bool]


def evaluate_service_probes(
    probes: Mapping[str, ServiceProbe],
) -> list[CapabilityEvidence]:
    """Evaluate probes without exposing connection values or exception text."""
    results: list[CapabilityEvidence] = []
    for name, probe in probes.items():
        try:
            passed = probe()
        except ServiceUnavailable:
            status = CapabilityStatus.NOT_VERIFIED
            observed = "unavailable"
        except Exception:
            status = CapabilityStatus.FAIL
            observed = "probe_failed"
        else:
            status = CapabilityStatus.PASS if passed is True else CapabilityStatus.FAIL
            observed = "healthy" if passed is True else "unhealthy"
        results.append(
            CapabilityEvidence(
                name=name,
                kind="service",
                status=status,
                mandatory=True,
                expected="available_and_healthy",
                observed=observed,
            )
        )
    return results


def default_service_probes(
    environ: Mapping[str, str] | None = None,
) -> dict[str, ServiceProbe]:
    env = environ if environ is not None else os.environ

    def docker() -> bool:
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise ServiceUnavailable() from exc
        return result.returncode == 0 and bool(result.stdout.strip())

    def redis_celery() -> bool:
        redis_url = env.get("STWI_REDIS_URL", "").strip()
        if not redis_url:
            raise ServiceUnavailable()
        from redis import Redis
        from celery import Celery

        redis_ok = Redis.from_url(
            redis_url,
            socket_connect_timeout=3,
            socket_timeout=3,
        ).ping()
        celery_app = Celery("stwi-demo-probe", broker=redis_url)
        workers = celery_app.control.inspect(timeout=3).ping()
        return redis_ok is True and bool(workers)

    def qdrant() -> bool:
        url = env.get("STWI_QDRANT_URL", "").strip()
        if not url:
            raise ServiceUnavailable()
        from qdrant_client import QdrantClient

        QdrantClient(
            url=url,
            api_key=env.get("STWI_QDRANT_API_KEY") or None,
            timeout=3,
        ).get_collections()
        return True

    def timescaledb() -> bool:
        dsn = env.get("STWI_TSDB_DSN", "").strip()
        if not dsn:
            raise ServiceUnavailable()
        import psycopg

        with psycopg.connect(dsn, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
        return row == (1,)

    return {
        "docker": docker,
        "redis_celery": redis_celery,
        "qdrant": qdrant,
        "timescaledb": timescaledb,
    }


def run_service_profile(
    output: Path,
    *,
    probes: Mapping[str, ServiceProbe] | None = None,
    environ: Mapping[str, str] | None = None,
) -> DemoEvidence:
    capabilities = evaluate_service_probes(
        probes if probes is not None else default_service_probes(environ)
    )
    verdict = "pass"
    if any(item.status == CapabilityStatus.FAIL for item in capabilities):
        verdict = "fail"
    elif any(item.status == CapabilityStatus.NOT_VERIFIED for item in capabilities):
        verdict = "incomplete"
    evidence = DemoEvidence(
        profile="services",
        verdict=verdict,
        live_services_contacted=True,
        capabilities=capabilities,
    )
    write_evidence_atomic(output, evidence)
    return evidence


__all__ = [
    "ServiceUnavailable",
    "default_service_probes",
    "evaluate_service_probes",
    "run_service_profile",
]
