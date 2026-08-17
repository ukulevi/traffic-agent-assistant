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
    re.compile(r"(^|/)\.env(?:$|\.local$|\.[^/]*\.local$)"),
    re.compile(r"(^|/)data/(external|quarantine|derived/private)(/|$)"),
    re.compile(r"(^|/)render_tmp(/|$)"),
    re.compile(r".*\.(mp4|mov|avi|mkv|webm|pt|pth|onnx|engine|safetensors|log|jsonl)$", re.I),
    re.compile(r"(^|/)tmp(/|$)"),
    re.compile(r"(^|/)output(/|$)"),
    re.compile(r"(^|/)docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV\+CB(/|$)"),
    re.compile(r"(^|/)report/internship_main\.tex$"),
    re.compile(r"(^|/)report/chapters/ch(?:00_thong_tin_thuc_tap|12_xac_nhan_doanh_nghiep)\.tex$"),
    re.compile(r"(^|/)report/figures/M2_Logo_BK\.png$"),
    re.compile(r"(^|/)(scripts|tests)/report(/|$)"),
    re.compile(r"(^|/)docs/superpowers/(plans/2026-08-17-internship-report-cbhd-review\.md|specs/2026-08-17-internship-report-cbhd-review-design\.md)$"),
]

SENSITIVE_TEXT_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
)

TEXT_SUFFIXES = frozenset(
    {
        ".cfg", ".css", ".csv", ".html", ".ini", ".js", ".json", ".md",
        ".mjs", ".ps1", ".py", ".sh", ".tex", ".toml", ".ts", ".txt",
        ".yaml", ".yml",
    }
)
MAX_TEXT_BYTES = 2 * 1024 * 1024

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


def git_staged_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def candidate_repository_files(root: Path) -> list[str]:
    """Return the sorted union of tracked and staged candidate paths."""

    return sorted(set(git_ls_files(root)) | set(git_staged_files(root)))


def is_forbidden_repository_path(path: str) -> bool:
    return any(pattern.fullmatch(path) or pattern.match(path) for pattern in FORBIDDEN_TRACKED_PATTERNS)


def validate_forbidden_files(paths: list[str]) -> list[str]:
    return [
        f"Forbidden repository artifact: {path}"
        for path in paths
        if is_forbidden_repository_path(path)
    ]


def validate_tracked_files(root: Path) -> list[str]:
    return [
        f"Forbidden tracked artifact: {path}"
        for path in git_ls_files(root)
        if is_forbidden_repository_path(path)
    ]


def validate_sensitive_content(root: Path, paths: list[str]) -> list[str]:
    """Report high-confidence secret markers without exposing matched values."""

    errors: list[str] = []
    for path in paths:
        candidate = root / path
        if candidate.suffix.lower() not in TEXT_SUFFIXES or not candidate.is_file():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as stream:
                text = stream.read(MAX_TEXT_BYTES + 1)
        except (OSError, UnicodeDecodeError):
            continue
        for name, pattern in SENSITIVE_TEXT_PATTERNS:
            if pattern.search(text):
                errors.append(f"Sensitive content ({name}): {path}")
    return errors


def validate_public_workflows(root: Path) -> list[str]:
    errors: list[str] = []
    workflows = root / ".github" / "workflows"
    if not workflows.exists():
        return errors
    for path in sorted(workflows.glob("*.y*ml")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "internship_main.tex" in text:
            errors.append(
                "Public workflow references private internship artifact: "
                + path.relative_to(root).as_posix()
            )
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
    candidates = candidate_repository_files(root)
    errors.extend(validate_forbidden_files(candidates))
    errors.extend(validate_sensitive_content(root, candidates))
    errors.extend(validate_public_workflows(root))
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
