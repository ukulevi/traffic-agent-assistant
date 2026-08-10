"""Explicit, admin-only TimescaleDB schema migration entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO


DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "production"
    / "timescaledb-init"
    / "01_schema.sql"
)
ConnectionFactory = Callable[[str], Any]


def _schema_path(
    environ: Mapping[str, str],
    explicit_path: Path | None,
) -> Path:
    if explicit_path is not None:
        return explicit_path
    configured_path = environ.get("STWI_PRODUCTION_SCHEMA_PATH", "").strip()
    if configured_path:
        return Path(configured_path)
    repository_path = (
        Path.cwd()
        / "infra"
        / "production"
        / "timescaledb-init"
        / "01_schema.sql"
    )
    return repository_path if repository_path.is_file() else DEFAULT_SCHEMA_PATH


def _verdict(action: str, status: str, code: str) -> dict[str, str]:
    return {
        "action": action,
        "profile": "production",
        "status": status,
        "code": code,
    }


def _print(payload: dict[str, str], stdout: TextIO | None) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        file=stdout or sys.stdout,
    )


def _admin_dsn(environ: Mapping[str, str]) -> str:
    if environ.get("STWI_RUNTIME_MODE", "").strip().lower() not in {
        "production",
        "prod",
    }:
        raise ValueError("PRODUCTION_MODE_REQUIRED")
    admin_dsn = environ.get("STWI_TSDB_ADMIN_DSN", "").strip()
    reader_dsn = environ.get("STWI_TSDB_DSN", "").strip()
    if not admin_dsn or admin_dsn == reader_dsn:
        raise ValueError("ADMIN_DSN_REQUIRED")
    return admin_dsn


def _default_connection_factory(dsn: str) -> Any:
    import psycopg

    return psycopg.connect(dsn, connect_timeout=5)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    connection_factory: ConnectionFactory | None = None,
    schema_path: Path | None = None,
    stdout: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "apply"))
    parser.add_argument("--approved", action="store_true")
    arguments = parser.parse_args(argv)
    action = arguments.action

    if action == "apply" and not arguments.approved:
        _print(_verdict(action, "fail", "APPROVAL_REQUIRED"), stdout)
        return 1

    env = environ if environ is not None else os.environ
    try:
        admin_dsn = _admin_dsn(env)
    except ValueError as exc:
        _print(_verdict(action, "fail", str(exc)), stdout)
        return 1

    connect = connection_factory or _default_connection_factory
    try:
        with connect(admin_dsn) as connection:
            with connection.cursor() as cursor:
                if action == "check":
                    cursor.execute(
                        "SELECT to_regclass('public.simulation_results')"
                    )
                    row = cursor.fetchone()
                    if not row or row[0] is None:
                        _print(
                            _verdict(action, "fail", "SCHEMA_NOT_APPLIED"),
                            stdout,
                        )
                        return 1
                else:
                    selected_schema = _schema_path(env, schema_path)
                    if not selected_schema.is_file():
                        _print(
                            _verdict(action, "fail", "SCHEMA_FILE_REQUIRED"),
                            stdout,
                        )
                        return 1
                    cursor.execute(selected_schema.read_text(encoding="utf-8"))
                    connection.commit()
    except Exception:
        _print(_verdict(action, "fail", "DATABASE_UNAVAILABLE"), stdout)
        return 1

    _print(_verdict(action, "pass", "OK"), stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["DEFAULT_SCHEMA_PATH", "main"]
