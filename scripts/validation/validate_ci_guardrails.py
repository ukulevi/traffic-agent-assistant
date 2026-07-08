"""Lightweight CI guardrails for STWI repository hygiene.

This validator is designed for GitHub Actions fast CI. It avoids network,
secrets, private artifacts, and heavyweight test setup.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_TRACKED_PATTERNS = [
    re.compile(r"(^|/)\.env($|[./])"),
    re.compile(r"(^|/)\.env\.[^/]*$"),  # .env.local, .env.symphony.local, etc.
    re.compile(r"(^|/)data/(external|quarantine|derived/private)(/|$)"),
    re.compile(r"(^|/)render_tmp(/|$)"),
    re.compile(r".*\.(mp4|mov|avi|mkv|webm|pt|pth|onnx|engine|safetensors|log|jsonl)$", re.I),
]

REQUIRED_CODEXIGNORE_PATTERNS = [
    ".git/",
    "node_modules/",
    "data/external/",
    "data/quarantine/",
    "data/derived/private/",
    "*.mp4",
    "*.pt",
    "*.log",
    "*.jsonl",
]

WORKFLOW_EXPECTATIONS = {
    "max_concurrent_agents: 1": "Symphony must stay single-agent by default",
    "max_turns: 1": "Symphony must stop after one turn by default",
    "max_retry_backoff_ms: 900000": "Retry backoff should avoid tight loops",
    "interval_ms: 300000": "Linear polling should stay at 5 minutes",
    "approval_policy: never": "Unattended agents must not request escalation",
}


def git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def validate_tracked_files(root: Path) -> list[str]:
    errors: list[str] = []
    for path in git_ls_files(root):
        for pattern in FORBIDDEN_TRACKED_PATTERNS:
            if pattern.fullmatch(path) or pattern.match(path):
                errors.append(f"Forbidden tracked artifact: {path}")
                break
    return errors


def validate_codexignore(root: Path) -> list[str]:
    path = root / ".codexignore"
    if not path.exists():
        return [".codexignore is missing"]
    text = path.read_text(encoding="utf-8")
    errors = [
        f".codexignore missing required pattern: {pattern}"
        for pattern in REQUIRED_CODEXIGNORE_PATTERNS
        if pattern not in text
    ]
    if re.search(r"(?m)^\s*\*\.json\s*$", text):
        errors.append(".codexignore must not blanket-ignore *.json")
    return errors


def validate_workflow(root: Path) -> list[str]:
    path = root / "WORKFLOW.md"
    if not path.exists():
        return ["WORKFLOW.md is missing"]
    text = path.read_text(encoding="utf-8")
    errors = [
        f"WORKFLOW.md missing `{needle}`: {reason}"
        for needle, reason in WORKFLOW_EXPECTATIONS.items()
        if needle not in text
    ]
    if "SYMPHONY_REPO_REFERENCE" not in text:
        errors.append("WORKFLOW.md should prefer SYMPHONY_REPO_REFERENCE for clone reuse")
    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_tracked_files(root))
    errors.extend(validate_codexignore(root))
    errors.extend(validate_workflow(root))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate(args.root.resolve())
    if errors:
        print("STWI CI guardrails failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("STWI CI guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
