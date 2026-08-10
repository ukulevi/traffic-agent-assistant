"""Bounded operator commands for the STWI production baseline.

The CLI never deletes volumes and never prints environment values. Restore and
rollback actions require an explicit approval flag and remain verification-only
until deployment-specific storage ownership is reviewed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra" / "production" / "compose.yaml"
PROJECT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
SUPPORTED_ACTIONS = {
    "preflight",
    "start",
    "readiness",
    "migration",
    "backup",
    "restore-verify",
    "restart-recovery",
    "rollback",
    "stop",
}


def _compose(project_name: str, *arguments: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        project_name,
        "-f",
        str(COMPOSE_FILE),
        *arguments,
    ]


def _approved_path(path: Path | None, label: str) -> Path:
    if path is None:
        raise ValueError(f"{label} is required")
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"{label} must be an existing directory")
    if resolved == Path(resolved.anchor):
        raise ValueError(f"{label} must not be a filesystem root")
    return resolved


def build_command(
    action: str,
    *,
    project_name: str,
    backup_dir: Path | None = None,
    restore_source: Path | None = None,
    approved: bool = False,
) -> list[list[str]]:
    """Build bounded argument arrays without reading secrets or running tools."""
    if not PROJECT_NAME_PATTERN.fullmatch(project_name):
        raise ValueError("project name must match ^[a-z][a-z0-9-]{2,40}$")
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported action: {action}")
    if action in {"migration", "restore-verify", "rollback"} and not approved:
        raise ValueError(f"{action} requires explicit --approved")

    if action == "preflight":
        return [
            [
                sys.executable,
                str(ROOT / "scripts" / "validation" / "validate_production_deployment.py"),
            ],
            _compose(project_name, "config", "--quiet"),
        ]
    if action == "start":
        return [_compose(project_name, "up", "-d")]
    if action == "readiness":
        return [
            _compose(project_name, "ps"),
            _compose(
                project_name,
                "exec",
                "-T",
                "stwi-api",
                "python",
                "-m",
                "stwi.production_health",
                "readiness",
            ),
        ]
    if action == "migration":
        return [
            _compose(
                project_name,
                "run",
                "--rm",
                "--no-deps",
                "stwi-migrate",
                "python",
                "-m",
                "stwi.production_migrate",
                "apply",
                "--approved",
            )
        ]
    if action == "backup":
        target = _approved_path(backup_dir, "backup directory")
        return [
            _compose(
                project_name,
                "exec",
                "-T",
                "timescaledb",
                "sh",
                "-c",
                'pg_dump --format=custom --file=/tmp/stwi.backup --username "$POSTGRES_USER" "$POSTGRES_DB"',
            ),
            _compose(
                project_name,
                "cp",
                f"timescaledb:/tmp/stwi.backup",
                str(target / "timescaledb.backup"),
            ),
            _compose(
                project_name,
                "exec",
                "-T",
                "redis",
                "sh",
                "-c",
                'REDISCLI_AUTH="$STWI_REDIS_PASSWORD" redis-cli BGSAVE',
            ),
            _compose(
                project_name,
                "exec",
                "-T",
                "stwi-api",
                "python",
                "-m",
                "stwi.production_snapshot",
                "qdrant",
            ),
        ]
    if action == "restore-verify":
        source = _approved_path(restore_source, "restore source")
        return [
            _compose(project_name, "config", "--quiet"),
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "preflight",
                "--project-name",
                project_name,
                "--restore-source",
                str(source),
            ],
        ]
    if action == "restart-recovery":
        return [
            _compose(project_name, "restart", "stwi-api", "stwi-worker"),
            _compose(project_name, "ps"),
        ]
    if action == "rollback":
        return [
            _compose(project_name, "config", "--quiet"),
            _compose(project_name, "up", "-d", "--no-deps", "stwi-api", "stwi-worker"),
        ]
    return [_compose(project_name, "down")]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=sorted(SUPPORTED_ACTIONS))
    parser.add_argument("--project-name", default="stwi-prod")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--restore-source", type=Path)
    parser.add_argument("--approved", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        commands = build_command(
            args.action,
            project_name=args.project_name,
            backup_dir=args.backup_dir,
            restore_source=args.restore_source,
            approved=args.approved,
        )
        for command in commands:
            print(f"Running {args.action} step: {command[0]}")
            subprocess.run(command, cwd=ROOT, check=True, timeout=180)
    except (ValueError, subprocess.SubprocessError) as exc:
        print(f"Production operation failed: {type(exc).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
