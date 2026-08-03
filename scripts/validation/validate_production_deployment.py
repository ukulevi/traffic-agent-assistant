"""Validate the fail-closed STWI production deployment baseline."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_DIR = Path("infra/production")
REQUIRED_SERVICES = (
    "stwi-api",
    "stwi-worker",
    "redis",
    "timescaledb",
    "qdrant",
)
DATA_SERVICES = ("redis", "timescaledb", "qdrant")
REQUIRED_RUNBOOK_SECTIONS = (
    "Configuration preflight",
    "Migration",
    "Backup and restore verification",
    "Restart recovery",
    "Rollback",
    "Human Review gates",
)
CREDENTIAL_NAMES = (
    "STWI_REDIS_PASSWORD",
    "STWI_TSDB_ADMIN_PASSWORD",
    "STWI_TSDB_READER_PASSWORD",
    "STWI_QDRANT_API_KEY",
)


def _read(path: Path, label: str, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"{label}: file is missing")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        errors.append(f"{label}: file cannot be read")
        return ""


def _service_block(compose: str, service: str) -> str:
    pattern = re.compile(
        rf"(?ms)^  {re.escape(service)}:\s*\n(.*?)(?=^  [a-zA-Z0-9_-]+:\s*\n|\Z)"
    )
    match = pattern.search(compose)
    return match.group(1) if match else ""


def _validate_compose(text: str) -> list[str]:
    errors: list[str] = []
    for service in REQUIRED_SERVICES:
        if not _service_block(text, service):
            errors.append(f"compose: missing required service {service}")

    for service in DATA_SERVICES:
        block = _service_block(text, service)
        if re.search(r"(?m)^    ports:\s*(?:\[|$)", block):
            errors.append(f"compose: {service} must not publish host ports")

    for service in ("stwi-api", "stwi-worker"):
        block = _service_block(text, service)
        if "STWI_RUNTIME_MODE: production" not in block:
            errors.append("compose: STWI_RUNTIME_MODE must be production")
            break
        if "read_only: true" not in block:
            errors.append(
                f"compose: {service} must use a read-only root filesystem"
            )
        if not re.search(r"(?m)^    cap_drop:\s*(?:\[\"ALL\"\]|$)", block):
            errors.append(f"compose: {service} must drop all Linux capabilities")
        if "no-new-privileges:true" not in block:
            errors.append(f"compose: {service} must enable no-new-privileges")

    api_block = _service_block(text, "stwi-api")
    if "/docs" in api_block:
        errors.append("compose: API healthcheck must not use /docs")
    application_blocks = "\n".join(
        _service_block(text, service) for service in ("stwi-api", "stwi-worker")
    )
    if "stwi.app:app" in application_blocks:
        errors.append(
            "compose: application services must not use provisional stwi.app"
        )
    if re.search(r"(?mi)^\s*image:\s*\S+:(?:latest|main|edge)\s*$", text):
        errors.append("compose: image tags must not be floating")
    return errors


def _validate_dockerfile(text: str) -> list[str]:
    errors: list[str] = []
    first_instruction = next(
        (line.strip() for line in text.splitlines() if line.strip()), ""
    )
    if not re.fullmatch(r"FROM\s+\S+@sha256:[0-9a-fA-F]{64}", first_instruction):
        errors.append("dockerfile: base image must be pinned by sha256 digest")
    user_lines = re.findall(r"(?mi)^USER\s+(\S+)\s*$", text)
    if not user_lines or user_lines[-1].lower() in {"0", "root"}:
        errors.append("dockerfile: application runtime must use a non-root USER")
    return errors


def _validate_environment(text: str) -> list[str]:
    errors: list[str] = []
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        values[name.strip()] = value.strip()
    if any(values.get(name, "") for name in CREDENTIAL_NAMES):
        errors.append("environment: credential variables must not have defaults")
    return errors


def _validate_runbook(text: str) -> list[str]:
    errors: list[str] = []
    for section in REQUIRED_RUNBOOK_SECTIONS:
        if not re.search(rf"(?mi)^##+\s+{re.escape(section)}\s*$", text):
            errors.append(f"runbook: missing section {section}")
    return errors


def _validate_timescaledb_init(production: Path) -> list[str]:
    errors: list[str] = []
    init_dir = production / "timescaledb-init"
    reader = init_dir / "00_create_reader_user.sh"
    schema = init_dir / "01_schema.sql"
    if not reader.is_file():
        errors.append("timescaledb: reader-role initializer is missing")
    if not schema.is_file():
        errors.append("timescaledb: production schema is missing")
        return errors
    try:
        schema_text = schema.read_text(encoding="utf-8")
    except OSError:
        errors.append("timescaledb: production schema cannot be read")
        return errors
    if re.search(r"(?mi)^\s*INSERT\s+INTO\b", schema_text):
        errors.append("timescaledb: production schema must not seed data")
    return errors


def validate_production_deployment(root: Path) -> list[str]:
    """Return stable errors without reading credentials or external services."""
    production = root / PRODUCTION_DIR
    errors: list[str] = []
    compose = _read(production / "compose.yaml", "compose", errors)
    dockerfile = _read(production / "Dockerfile", "dockerfile", errors)
    environment = _read(production / ".env.example", "environment", errors)
    runbook = _read(production / "README.md", "runbook", errors)
    _read(production / "ops.py", "operations", errors)
    if compose:
        errors.extend(_validate_compose(compose))
    if dockerfile:
        errors.extend(_validate_dockerfile(dockerfile))
    if environment:
        errors.extend(_validate_environment(environment))
    if runbook:
        errors.extend(_validate_runbook(runbook))
    errors.extend(_validate_timescaledb_init(production))
    return errors


def validate_production_topology(root: Path) -> list[str]:
    """Validate Compose, image, and environment files before runbook work."""
    production = root / PRODUCTION_DIR
    errors: list[str] = []
    compose = _read(production / "compose.yaml", "compose", errors)
    dockerfile = _read(production / "Dockerfile", "dockerfile", errors)
    environment = _read(production / ".env.example", "environment", errors)
    if compose:
        errors.extend(_validate_compose(compose))
    if dockerfile:
        errors.extend(_validate_dockerfile(dockerfile))
    if environment:
        errors.extend(_validate_environment(environment))
    errors.extend(_validate_timescaledb_init(production))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> int:
    errors = validate_production_deployment(parse_args().root.resolve())
    if errors:
        print("STWI production deployment validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("STWI production deployment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
