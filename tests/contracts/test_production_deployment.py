from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validation.validate_production_deployment import (
    validate_production_deployment,
    validate_production_topology,
)


VALID_COMPOSE = """services:
  stwi-api:
    image: ${STWI_APP_IMAGE:?required promoted image digest}
    command: ["uvicorn", "stwi.production:app", "--host", "0.0.0.0"]
    environment:
      STWI_RUNTIME_MODE: production
      STWI_REDIS_PASSWORD: ${STWI_REDIS_PASSWORD:?required}
      STWI_PRODUCTION_COMPONENT_FACTORY: ${STWI_PRODUCTION_COMPONENT_FACTORY:?required}
      STWI_LEGAL_CORPUS_DIR: /run/stwi/legal-corpus
    ports:
      - "${STWI_API_BIND:-127.0.0.1}:${STWI_API_PORT:-8000}:8000"
    read_only: true
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    healthcheck:
      test: ["CMD", "python", "-m", "stwi.health", "readiness"]
  stwi-worker:
    image: ${STWI_APP_IMAGE:?required promoted image digest}
    command: ["celery", "-A", "stwi.production_worker", "worker"]
    environment:
      STWI_RUNTIME_MODE: production
      STWI_PRODUCTION_COMPONENT_FACTORY: ${STWI_PRODUCTION_COMPONENT_FACTORY:?required}
      STWI_LEGAL_CORPUS_DIR: /run/stwi/legal-corpus
    read_only: true
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    healthcheck:
      test: ["CMD", "celery", "inspect", "ping"]
  stwi-migrate:
    image: ${STWI_APP_IMAGE:?required promoted image digest}
    command: ["python", "-m", "stwi.production_migrate", "check"]
    environment:
      STWI_RUNTIME_MODE: production
      STWI_TSDB_ADMIN_DSN: ${STWI_TSDB_ADMIN_DSN:?required}
    read_only: true
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
  redis:
    image: redis:7.4.2-alpine@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
  timescaledb:
    image: timescale/timescaledb:2.17.2-pg16@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
    environment:
      POSTGRES_PASSWORD: ${STWI_TSDB_ADMIN_PASSWORD:?required}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
  qdrant:
    image: qdrant/qdrant:v1.9.7@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
    environment:
      QDRANT__SERVICE__API_KEY: ${STWI_QDRANT_API_KEY:?required}
    healthcheck:
      test: ["CMD", "bash", "-c", "</dev/tcp/127.0.0.1/6333"]
"""

VALID_DOCKERFILE = """FROM python:3.11.13-slim-bookworm@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
WORKDIR /app
COPY infra/production/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY src/ ./src/
RUN groupadd --system stwi && useradd --system --gid stwi stwi
USER stwi
"""

VALID_ENV = """STWI_APP_IMAGE=
STWI_REDIS_PASSWORD=
STWI_TSDB_ADMIN_PASSWORD=
STWI_TSDB_ADMIN_DSN=
STWI_TSDB_READER_PASSWORD=
STWI_QDRANT_API_KEY=
STWI_BASELINE_MANIFEST=
STWI_SURROGATE_MANIFEST=
STWI_PRODUCTION_COMPONENT_FACTORY=
STWI_LEGAL_CORPUS_DIR_HOST=
"""

VALID_RUNBOOK = """# Production baseline
## Configuration preflight
## Migration
## Backup and restore verification
## Restart recovery
## Rollback
## Human Review gates
"""

VALID_OPS = """def build_command(action, **kwargs):
    return []
"""

ROOT = Path(__file__).resolve().parents[2]


class ProductionDeploymentValidationTest(unittest.TestCase):
    def _root(
        self,
        *,
        compose: str = VALID_COMPOSE,
        dockerfile: str = VALID_DOCKERFILE,
        env: str = VALID_ENV,
        runbook: str = VALID_RUNBOOK,
        ops: str = VALID_OPS,
    ) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        production = root / "infra" / "production"
        production.mkdir(parents=True)
        (production / "compose.yaml").write_text(compose, encoding="utf-8")
        (production / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (production / ".env.example").write_text(env, encoding="utf-8")
        (production / "README.md").write_text(runbook, encoding="utf-8")
        (production / "ops.py").write_text(ops, encoding="utf-8")
        package = root / "src" / "stwi"
        package.mkdir(parents=True)
        for module in (
            "production_components.py",
            "production.py",
            "production_worker.py",
            "production_preflight.py",
            "production_health.py",
            "production_migrate.py",
        ):
            (package / module).write_text("# production entrypoint\n", encoding="utf-8")
        init_dir = production / "timescaledb-init"
        init_dir.mkdir()
        (init_dir / "00_create_reader_user.sh").write_text(
            '#!/bin/sh\n: "${STWI_TSDB_READER_PASSWORD:?required}"\n',
            encoding="utf-8",
        )
        (init_dir / "01_schema.sql").write_text(
            "CREATE TABLE IF NOT EXISTS simulation_results (tenant_id TEXT);\n",
            encoding="utf-8",
        )
        return root

    def test_valid_baseline_has_no_static_contract_errors(self) -> None:
        self.assertEqual(validate_production_deployment(self._root()), [])

    def test_repository_production_baseline_satisfies_static_contract(self) -> None:
        self.assertEqual(validate_production_topology(ROOT), [])

    def test_rejects_public_data_service_port(self) -> None:
        compose = VALID_COMPOSE.replace(
            "  redis:\n    image:",
            '  redis:\n    ports: ["6379:6379"]\n    image:',
        )
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn("compose: redis must not publish host ports", errors)

    def test_rejects_provisional_runtime_and_docs_healthcheck(self) -> None:
        compose = VALID_COMPOSE.replace(
            "STWI_RUNTIME_MODE: production",
            "STWI_RUNTIME_MODE: demo",
            1,
        ).replace('"stwi.health", "readiness"', '"urllib.request", "/docs"')
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn("compose: STWI_RUNTIME_MODE must be production", errors)
        self.assertIn("compose: API healthcheck must not use /docs", errors)

    def test_rejects_provisional_application_entrypoint(self) -> None:
        compose = VALID_COMPOSE.replace(
            '"stwi.production:app"', '"stwi.app:app"'
        )
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn(
            "compose: application services must not use provisional stwi.app",
            errors,
        )

    def test_rejects_floating_infrastructure_image(self) -> None:
        compose = VALID_COMPOSE.replace(
            "redis:7.4.2-alpine@sha256:" + "b" * 64,
            "redis:latest",
        )
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn("compose: image tags must not be floating", errors)

    def test_rejects_mutable_infrastructure_image_reference(self) -> None:
        compose = VALID_COMPOSE.replace("@sha256:" + "b" * 64, "", 1)
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn(
            "compose: infrastructure images must be pinned by sha256 digest",
            errors,
        )

    def test_rejects_application_service_without_hardening(self) -> None:
        compose = VALID_COMPOSE.replace("    read_only: true\n", "", 1).replace(
            '    cap_drop: ["ALL"]\n', "", 1
        )
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn("compose: stwi-api must use a read-only root filesystem", errors)
        self.assertIn("compose: stwi-api must drop all Linux capabilities", errors)

    def test_rejects_production_seed_data(self) -> None:
        root = self._root()
        (root / "infra" / "production" / "timescaledb-init" / "01_schema.sql").write_text(
            "INSERT INTO simulation_results VALUES ('synthetic_test_only');\n",
            encoding="utf-8",
        )
        errors = validate_production_deployment(root)
        self.assertIn("timescaledb: production schema must not seed data", errors)

    def test_rejects_root_runtime_and_unpinned_base_image(self) -> None:
        dockerfile = VALID_DOCKERFILE.replace("@sha256:" + "a" * 64, "").replace(
            "USER stwi", "USER root"
        )
        errors = validate_production_deployment(
            self._root(dockerfile=dockerfile)
        )
        self.assertIn(
            "dockerfile: base image must be pinned by sha256 digest", errors
        )
        self.assertIn(
            "dockerfile: application runtime must use a non-root USER", errors
        )

    def test_rejects_credential_defaults(self) -> None:
        env = VALID_ENV.replace("STWI_REDIS_PASSWORD=", "STWI_REDIS_PASSWORD=dev")
        errors = validate_production_deployment(self._root(env=env))
        self.assertIn(
            "environment: credential variables must not have defaults", errors
        )

    def test_rejects_missing_operations_evidence(self) -> None:
        errors = validate_production_deployment(self._root(runbook="# empty"))
        self.assertIn("runbook: missing section Configuration preflight", errors)
        self.assertIn("runbook: missing section Rollback", errors)

    def test_rejects_missing_production_entrypoint_module(self) -> None:
        root = self._root()
        (root / "src" / "stwi" / "production_worker.py").unlink()

        errors = validate_production_deployment(root)

        self.assertIn(
            "application: missing production entrypoint production_worker.py",
            errors,
        )

    def test_rejects_missing_component_factory_wiring(self) -> None:
        compose = VALID_COMPOSE.replace(
            "      STWI_PRODUCTION_COMPONENT_FACTORY: ${STWI_PRODUCTION_COMPONENT_FACTORY:?required}\n",
            "",
        )
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn(
            "compose: stwi-api requires STWI_PRODUCTION_COMPONENT_FACTORY",
            errors,
        )

    def test_rejects_admin_dsn_on_long_running_services(self) -> None:
        compose = VALID_COMPOSE.replace(
            "      STWI_REDIS_PASSWORD: ${STWI_REDIS_PASSWORD:?required}\n",
            "      STWI_REDIS_PASSWORD: ${STWI_REDIS_PASSWORD:?required}\n"
            "      STWI_TSDB_ADMIN_DSN: ${STWI_TSDB_ADMIN_DSN:?required}\n",
            1,
        )
        errors = validate_production_deployment(self._root(compose=compose))
        self.assertIn(
            "compose: stwi-api must not receive STWI_TSDB_ADMIN_DSN",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
