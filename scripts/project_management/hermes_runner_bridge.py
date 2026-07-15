"""
Bounded Hermes Desktop runner bridge.

This module is the canonical executor entrypoint for the STWI workflow:
- validate `current_dispatch_packet.md`
- prepare prompt/manifest artifacts under `docs/project_management/symphony/hermes_runs`
- run the verified Hermes CLI for oneshot execution
- fail closed on validation/runtime errors instead of broadening scope
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKET = ROOT / "docs/project_management/symphony/current_dispatch_packet.md"
DEFAULT_ARTIFACT_DIR = ROOT / "docs/project_management/symphony/hermes_runs"
WINDOWS_RUNNER_COMMAND = (
    r"C:\Users\PC\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe",
    "--oneshot",
    "{prompt}",
)
MACOS_RUNNER_COMMAND = (
    "/Applications/Hermes.app/Contents/MacOS/hermes",
    "--oneshot",
    "{prompt}",
)
REQUIRED_SECTIONS = (
    "Ticket",
    "Goal",
    "Allowed Files",
    "Forbidden Changes",
    "Acceptance Criteria",
    "Exact Checks",
    "Required Final Report",
)
FORBIDDEN_ALLOWED_FILES = {
    "project_contract.json",
    "AGENTS.md",
    "WORKFLOW.md",
}
REQUIRED_REPORT_FIELDS = (
    "Result:",
    "Changed files:",
    "Checks:",
    "Contract/artifact impact:",
    "Risks/blockers:",
    "Recommended next state:",
)


def candidate_path_exists(path: str) -> bool:
    try:
        return Path(path).exists()
    except PermissionError:
        return True


def resolve_default_runner_command() -> tuple[str, ...] | None:
    if candidate_path_exists(
        r"C:\Users\PC\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
    ):
        return WINDOWS_RUNNER_COMMAND
    if candidate_path_exists("/Applications/Hermes.app/Contents/MacOS/hermes"):
        return MACOS_RUNNER_COMMAND
    runner = shutil.which("hermes")
    if runner:
        return (runner, "--oneshot", "{prompt_file}")
    return None


@dataclass(frozen=True)
class DispatchPacket:
    identifier: str
    title: str
    sections: dict[str, str]
    allowed_files: list[str]
    raw_text: str


def section_map(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def fenced_text(section: str) -> str:
    match = re.search(r"```(?:\w+)?\s*(.*?)```", section, flags=re.DOTALL)
    return match.group(1).strip() if match else section.strip()


def parse_allowed_files(section: str) -> list[str]:
    body = fenced_text(section)
    return [
        line.strip().strip("-").strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def parse_ticket(section: str) -> tuple[str, str]:
    match = re.search(r"\bTRA-\d+\b", section, flags=re.IGNORECASE)
    if match is None:
        match = re.search(r"\bSTWI-[A-Z]+-\d+\b", section, flags=re.IGNORECASE)
    if match:
        identifier = match.group(0).upper()
    else:
        raise ValueError("Ticket section must include a Linear identifier.")
    title_match = re.search(r"\s(?:-|:|\N{EN DASH}|\N{EM DASH})\s+(.+)$", section)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = section.strip()
    return identifier, title


def parse_dispatch_packet(text: str) -> DispatchPacket:
    sections = section_map(text)
    missing = [name for name in REQUIRED_SECTIONS if not sections.get(name)]
    if missing:
        raise ValueError(f"Dispatch packet is missing sections: {', '.join(missing)}")

    identifier, title = parse_ticket(sections["Ticket"])
    allowed_files = parse_allowed_files(sections["Allowed Files"])
    if not allowed_files:
        raise ValueError("Dispatch packet must list at least one allowed file.")

    return DispatchPacket(
        identifier=identifier,
        title=title,
        sections=sections,
        allowed_files=allowed_files,
        raw_text=text,
    )


def validate_packet(packet: DispatchPacket) -> list[str]:
    errors: list[str] = []
    status_match = re.search(r"^Status:\s*(.+)$", packet.raw_text, re.MULTILINE)
    if status_match is None or not status_match.group(1).lower().startswith(
        "ready for hermes"
    ):
        errors.append("Dispatch packet Status must start with 'ready for Hermes'.")
    forbidden = sorted(
        path for path in packet.allowed_files if path in FORBIDDEN_ALLOWED_FILES
    )
    if forbidden:
        errors.append(
            "allowed_files includes source-of-truth files that require Codex "
            f"review before execution: {', '.join(forbidden)}"
        )

    report_section = packet.sections["Required Final Report"]
    missing_report_fields = [
        field for field in REQUIRED_REPORT_FIELDS if field not in report_section
    ]
    if missing_report_fields:
        errors.append(
            "Required Final Report is missing fields: "
            f"{', '.join(missing_report_fields)}"
        )

    forbidden_section = packet.sections["Forbidden Changes"]
    for expected in ("commit", "push", "Linear state", "project_contract.json"):
        if expected.lower() not in forbidden_section.lower():
            errors.append(f"Forbidden Changes must mention {expected!r}.")

    return errors


def build_hermes_prompt(packet: DispatchPacket, repo_root: Path) -> str:
    allowed = "\n".join(f"- {path}" for path in packet.allowed_files)
    return "\n".join(
        [
            "# Hermes Step Executor Packet",
            "",
            "You are Hermes Desktop using Step 3.7 Flash through Nous Portal.",
            "Execute only the dispatch packet below. Do not broaden scope.",
            "",
            "Hard boundaries:",
            "- Read AGENTS.md, README.md, project_contract.json before edits.",
            "- Use only the listed allowed files.",
            "- Do not change Linear, Symphony state, branches, staging, commits, PRs, or pushes.",
            "- Do not access secrets, private data, live services, raw video, credentials, or model weights.",
            "- Stop for Human Review on ambiguity, contract/API/safety/legal changes, dependency changes, or destructive actions.",
            "",
            f"Repository root: {repo_root}",
            f"Linear issue: {packet.identifier}",
            f"Packet title: {packet.title}",
            "",
            "Allowed files:",
            allowed,
            "",
            "Return exactly these fields:",
            *REQUIRED_REPORT_FIELDS,
            "",
            "--- Dispatch Packet ---",
            packet.raw_text.strip(),
            "",
        ]
    )


def render_command(
    command: Sequence[str],
    prompt: str,
    prompt_file: Path,
    packet_file: Path,
) -> list[str]:
    replacements = {
        "{prompt}": prompt,
        "{prompt_file}": str(prompt_file),
        "{packet_file}": str(packet_file),
    }
    return [replacements.get(part, part) for part in command]


def validate_repo_root(repo_root: Path) -> Path:
    resolved = repo_root.resolve()
    if not resolved.is_dir() or not (resolved / ".git").exists():
        raise ValueError(f"repo_root must be a Git workspace: {resolved}")
    return resolved


def git_changed_files(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git status failed")
    changed: list[str] = []
    for line in completed.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            changed.append(path.replace("\\", "/"))
    return changed


def path_is_allowed(path: str, allowed_files: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        fnmatch.fnmatchcase(normalized, pattern.replace("**", "*"))
        for pattern in allowed_files
    )


def validate_report(stdout: str) -> list[str]:
    return [field for field in REQUIRED_REPORT_FIELDS if field not in stdout]


def write_artifacts(
    packet: DispatchPacket,
    prompt: str,
    artifact_dir: Path,
    packet_file: Path,
    runner_command: Sequence[str] | None,
) -> tuple[Path, Path, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = f"{packet.identifier}_{timestamp}"
    prompt_file = artifact_dir / f"{base}_prompt.md"
    manifest_file = artifact_dir / f"{base}_manifest.json"

    prompt_file.write_text(prompt, encoding="utf-8")
    manifest = {
        "identifier": packet.identifier,
        "title": packet.title,
        "packet_file": str(packet_file),
        "prompt_file": str(prompt_file),
        "allowed_files": packet.allowed_files,
        "runner_command": list(runner_command) if runner_command else None,
        "state": "prepared",
        "created_at": timestamp,
    }
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return prompt_file, manifest_file, base


def run_command(
    command: Sequence[str],
    stdout_file: Path,
    stderr_file: Path,
    repo_root: Path,
) -> int:
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout_file.write_text(completed.stdout, encoding="utf-8")
    stderr_file.write_text(completed.stderr, encoding="utf-8")
    return completed.returncode


def require_external_code_transfer(approved: bool) -> None:
    """Fail closed unless the caller explicitly authorizes code export."""
    if not approved:
        raise SystemExit(
            "External code transfer is disabled by default. "
            "Use --allow-external-code-transfer only after ticket-specific "
            "informed user approval."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Isolated Git workspace used as the Hermes process cwd.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Validate and print the prepared status without writing artifacts.",
    )
    parser.add_argument(
        "--allow-external-code-transfer",
        action="store_true",
        help=(
            "Required to send source code or prompts to Hermes/Nous after "
            "ticket-specific informed user approval."
        ),
    )
    parser.add_argument(
        "--resume-dirty",
        action="store_true",
        help=(
            "Continue an explicit Rework turn only when every existing changed "
            "file is already inside Allowed Files."
        ),
    )
    parser.add_argument(
        "--runner-command",
        nargs=argparse.REMAINDER,
        help=(
            "Optional Hermes command. Use {prompt}, {prompt_file}, and "
            "{packet_file} placeholders; native Hermes oneshot should use {prompt}."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = validate_repo_root(args.repo_root)
    packet_file = args.packet.resolve()
    text = packet_file.read_text(encoding="utf-8")
    packet = parse_dispatch_packet(text)
    errors = validate_packet(packet)
    if errors:
        raise SystemExit("\n".join(errors))

    prompt = build_hermes_prompt(packet, repo_root)
    runner_command = args.runner_command or None
    if runner_command is None:
        runner_command = resolve_default_runner_command()
    assume_runner_ready = runner_command is not None

    if args.no_write:
        print(
            json.dumps(
                {
                    "identifier": packet.identifier,
                    "title": packet.title,
                    "state": "validated",
                    "allowed_files": packet.allowed_files,
                    "runner_ready": assume_runner_ready,
                    "repo_root": str(repo_root),
                    "runner_command": list(runner_command) if runner_command else None,
                },
                indent=2,
            )
        )
        return

    require_external_code_transfer(args.allow_external_code_transfer)

    artifact_dir = (
        args.artifact_dir.resolve()
        if args.artifact_dir
        else Path.home()
        / ".codex"
        / "symphony"
        / "logs"
        / "hermes_runs"
        / packet.identifier
    )
    initial_changes = git_changed_files(repo_root)
    initial_scope_violations = [
        path
        for path in initial_changes
        if not path_is_allowed(path, packet.allowed_files)
    ]
    if initial_scope_violations:
        raise SystemExit(
            "Dirty Hermes workspace contains out-of-scope files: "
            + ", ".join(initial_scope_violations)
        )
    if initial_changes and not args.resume_dirty:
        raise SystemExit(
            "Hermes workspace must be clean before dispatch: "
            + ", ".join(initial_changes)
        )

    prompt_file, manifest_file, artifact_base = write_artifacts(
        packet=packet,
        prompt=prompt,
        artifact_dir=artifact_dir,
        packet_file=packet_file,
        runner_command=runner_command,
    )
    stdout_file = artifact_dir / f"{artifact_base}_stdout.txt"
    stderr_file = artifact_dir / f"{artifact_base}_stderr.txt"
    result = {
        "identifier": packet.identifier,
        "title": packet.title,
        "state": "prepared",
        "prompt_file": str(prompt_file),
        "manifest_file": str(manifest_file),
        "stdout_file": str(stdout_file),
        "stderr_file": str(stderr_file),
        "runner_ready": assume_runner_ready,
        "runner_command": list(runner_command) if runner_command else None,
        "repo_root": str(repo_root),
        "initial_changed_files": initial_changes,
    }

    if runner_command:
        command = render_command(runner_command, prompt, prompt_file, packet_file)
        result["runner_command"] = [
            "{prompt}" if part == prompt else part for part in command
        ]
        result["runner_exit_code"] = run_command(
            command, stdout_file, stderr_file, repo_root
        )
        changed_files = git_changed_files(repo_root)
        scope_violations = [
            path
            for path in changed_files
            if not path_is_allowed(path, packet.allowed_files)
        ]
        stdout = stdout_file.read_text(encoding="utf-8")
        missing_report_fields = validate_report(stdout)
        result["changed_files"] = changed_files
        result["scope_violations"] = scope_violations
        result["missing_report_fields"] = missing_report_fields
        if result["runner_exit_code"] != 0:
            result["state"] = "runner_failed"
        elif scope_violations:
            result["state"] = "scope_violation"
        elif missing_report_fields:
            result["state"] = "invalid_report"
        else:
            result["state"] = "human_review"

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
