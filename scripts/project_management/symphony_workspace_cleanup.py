"""Inventory stale Symphony workspaces and optionally delete safe candidates.

The default mode is read-only. Deletion requires both ``--execute`` and
``--yes`` and only applies to clean git workspaces under the configured root.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_STALE_DAYS = 7


@dataclass(frozen=True)
class WorkspaceRecord:
    name: str
    path: str
    modified_at: str
    age_days: float
    has_git: bool
    git_dirty: bool | None
    candidate: bool
    reasons: list[str]


def default_workspace_root() -> Path:
    configured = os.environ.get("SYMPHONY_WORKSPACE_ROOT")
    if configured:
        return Path(configured)
    return Path.home() / ".codex" / "symphony" / "workspaces"


def resolve_under_root(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"path is outside workspace root: {resolved_path}")
    return resolved_path


def git_status(path: Path) -> tuple[bool | None, str | None]:
    if not (path / ".git").exists():
        return None, "not a git workspace"
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"git status failed: {error}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return None, f"git status returned {result.returncode}: {detail}"
    return bool(result.stdout.strip()), None


def iter_workspace_dirs(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def inspect_workspace(
    root: Path,
    path: Path,
    *,
    now: datetime,
    stale_days: int,
    protected_names: set[str],
) -> WorkspaceRecord:
    resolved = resolve_under_root(root, path)
    stat = resolved.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    age_days = max(0.0, (now - modified).total_seconds() / 86_400)
    dirty, git_error = git_status(resolved)
    reasons: list[str] = []

    if resolved.name in protected_names:
        reasons.append("protected by name")
    if age_days < stale_days:
        reasons.append(f"younger than {stale_days} days")
    if dirty is True:
        reasons.append("git workspace has uncommitted changes")
    elif dirty is None:
        reasons.append(git_error or "git status unknown")

    candidate = not reasons
    if candidate:
        reasons.append("stale clean workspace")

    return WorkspaceRecord(
        name=resolved.name,
        path=str(resolved),
        modified_at=modified.isoformat(),
        age_days=round(age_days, 2),
        has_git=(resolved / ".git").exists(),
        git_dirty=dirty,
        candidate=candidate,
        reasons=reasons,
    )


def collect_workspaces(
    root: Path,
    *,
    stale_days: int,
    protected_names: set[str],
    now: datetime | None = None,
) -> list[WorkspaceRecord]:
    now = now or datetime.now(timezone.utc)
    resolved_root = root.resolve()
    return [
        inspect_workspace(
            resolved_root,
            path,
            now=now,
            stale_days=stale_days,
            protected_names=protected_names,
        )
        for path in iter_workspace_dirs(resolved_root)
    ]


def delete_candidates(root: Path, records: list[WorkspaceRecord]) -> list[str]:
    deleted: list[str] = []
    for record in records:
        if not record.candidate:
            continue
        target = resolve_under_root(root, Path(record.path))
        shutil.rmtree(target)
        deleted.append(str(target))
    return deleted


def render_human(records: list[WorkspaceRecord], deleted: list[str]) -> str:
    lines = ["Symphony workspace cleanup", f"Candidates: {sum(r.candidate for r in records)}"]
    if deleted:
        lines.append(f"Deleted: {len(deleted)}")
    lines.append("")
    if not records:
        lines.append("No workspaces found.")
        return "\n".join(lines) + "\n"

    for record in records:
        marker = "candidate" if record.candidate else "keep"
        dirty = "unknown" if record.git_dirty is None else str(record.git_dirty).lower()
        reason = "; ".join(record.reasons)
        lines.append(
            f"- {record.name}: {marker}, age={record.age_days}d, "
            f"git_dirty={dirty}, reason={reason}"
        )
    if not deleted:
        lines.append("")
        lines.append("Dry-run only. Re-run with --execute --yes after Human Review.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_workspace_root())
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--protect", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stale_days < 1:
        raise SystemExit("--stale-days must be at least 1")

    root = args.root.resolve()
    records = collect_workspaces(
        root,
        stale_days=args.stale_days,
        protected_names=set(args.protect),
    )

    deleted: list[str] = []
    if args.execute:
        if not args.yes:
            raise SystemExit("--execute requires --yes")
        deleted = delete_candidates(root, records)

    payload = {
        "root": str(root),
        "stale_days": args.stale_days,
        "deleted": deleted,
        "workspaces": [asdict(record) for record in records],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_human(records, deleted), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
