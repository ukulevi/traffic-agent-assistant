"""Summarize a dirty STWI working tree into reviewable change groups.

The command is read-only. It does not stage, stash, delete, or rewrite files.
Use it before starting a new branch/session and before Human Review so pending
changes can be split by ownership and risk.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]

GROUP_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "project-management",
        (
            "WORKFLOW.md",
            ".codexignore",
            "docs/project_management/",
            "scripts/project_management/",
            "tests/project_management/",
        ),
    ),
    (
        "ci-release",
        (
            ".github/workflows/",
            "scripts/validation/",
            "scripts/validate_docs.py",
            "tests/validation/",
            "tests/test_project_contract.py",
        ),
    ),
    (
        "data-vision",
        (
            "data/manifests/",
            "docs/guides/vision",
            "scripts/benchmark_external_vision_model.py",
            "scripts/data_prep/",
            "scripts/infra/",
            "scripts/training/",
            "src/stwi/t1_pipeline/",
            "tests/t1_pipeline/",
            "tests/vision/",
        ),
    ),
    (
        "source-of-truth-docs",
        (
            "AGENTS.md",
            "README.md",
            "project_contract.json",
            "docs/00_",
            "docs/01_",
            "docs/02_",
            "docs/03_",
            "docs/04_",
            "docs/05_",
            "report/",
            "slides/",
        ),
    ),
    ("runtime-src", ("src/",)),
    ("tests", ("tests/",)),
    ("docs", ("docs/",)),
)

SOURCE_OF_TRUTH_PATHS = {
    "AGENTS.md",
    "README.md",
    "project_contract.json",
    "WORKFLOW.md",
}

GENERATED_OR_PRIVATE_MARKERS = (
    "__pycache__/",
    ".pyc",
    "data/derived/private/",
    "data/external/",
    "render_tmp/",
)

LARGE_OR_RELEASE_EXTENSIONS = (
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".pt",
    ".onnx",
    ".pdf",
    ".log",
)


@dataclass(frozen=True)
class ChangeRecord:
    status: str
    path: str
    original_path: str | None
    group: str
    risks: list[str]


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def parse_status_line(line: str) -> ChangeRecord:
    if len(line) < 4:
        raise ValueError(f"invalid git status line: {line!r}")

    status = line[:2]
    raw_path = line[3:]
    original_path = None
    path = raw_path
    if " -> " in raw_path:
        original_path, path = raw_path.split(" -> ", 1)

    normalized = normalize_path(path)
    return ChangeRecord(
        status=status,
        path=normalized,
        original_path=normalize_path(original_path) if original_path else None,
        group=classify_group(normalized),
        risks=classify_risks(status, normalized),
    )


def parse_status(output: str) -> list[ChangeRecord]:
    return [parse_status_line(line) for line in output.splitlines() if line.strip()]


def git_status(root: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"git status failed with {result.returncode}: {detail}")
    return result.stdout


def classify_group(path: str) -> str:
    for group, prefixes in GROUP_RULES:
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes):
            return group
    return "other"


def classify_risks(status: str, path: str) -> list[str]:
    risks: list[str] = []
    if status == "??":
        risks.append("untracked")
    if path in SOURCE_OF_TRUTH_PATHS or path.startswith(("docs/00_", "docs/01_", "docs/02_", "docs/03_", "docs/04_", "docs/05_")):
        risks.append("source-of-truth")
    if path.startswith(".github/workflows/"):
        risks.append("ci-workflow")
    if path.startswith("data/manifests/"):
        risks.append("evidence-manifest")
    if any(marker in path for marker in GENERATED_OR_PRIVATE_MARKERS):
        risks.append("generated-or-private")
    if path.endswith(LARGE_OR_RELEASE_EXTENSIONS):
        risks.append("large-or-release-artifact")
    return risks


def group_records(records: Iterable[ChangeRecord]) -> dict[str, list[ChangeRecord]]:
    grouped: dict[str, list[ChangeRecord]] = defaultdict(list)
    for record in records:
        grouped[record.group].append(record)
    return dict(sorted(grouped.items()))


def build_payload(root: Path, records: list[ChangeRecord]) -> dict[str, object]:
    groups = group_records(records)
    return {
        "root": str(root),
        "total_changes": len(records),
        "groups": {
            group: {
                "count": len(items),
                "risk_count": sum(1 for item in items if item.risks),
                "changes": [asdict(item) for item in items],
            }
            for group, items in groups.items()
        },
    }


def render_human(root: Path, records: list[ChangeRecord]) -> str:
    lines = [
        "STWI working tree intake",
        f"Root: {root}",
        f"Changes: {len(records)}",
        "",
    ]
    if not records:
        lines.append("Working tree is clean.")
        return "\n".join(lines) + "\n"

    for group, items in group_records(records).items():
        risk_count = sum(1 for item in items if item.risks)
        lines.append(f"## {group} ({len(items)} change(s), {risk_count} with flags)")
        for item in items:
            flags = f" [{', '.join(item.risks)}]" if item.risks else ""
            original = f" (from {item.original_path})" if item.original_path else ""
            lines.append(f"- {item.status} {item.path}{original}{flags}")
        lines.append("")

    lines.extend(
        [
            "Recommended handling:",
            "1. Review and stage one group at a time; do not mix generated manifests with source changes.",
            "2. Resolve source-of-truth and ci-workflow flags before broad implementation work.",
            "3. Keep untracked generated/private artifacts out of commits unless Human Review approves them.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    records = parse_status(git_status(root))
    if args.json:
        print(json.dumps(build_payload(root, records), indent=2))
    else:
        print(render_human(root, records), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
