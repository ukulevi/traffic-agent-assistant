"""Run independent, approved Hermes packets concurrently.

This is a sidecar dispatcher, not a replacement for Symphony's Codex app-server
adapter. Linear and the Symphony workspace convention remain the control plane;
each Hermes worker receives a separate existing workspace and packet.

The default is validation-only. Source code is sent to Hermes/Nous only when
both --execute and --allow-external-code-transfer are supplied.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_runner_bridge import (
    DispatchPacket,
    git_changed_files,
    parse_dispatch_packet,
    validate_packet,
    validate_repo_root,
)


MAX_CONCURRENT_WORKERS = 2
REQUIRED_LABEL = "hermes-approved"
FORBIDDEN_LABEL = "codex-symphony-approved"


@dataclass(frozen=True)
class BatchJob:
    ticket: str
    packet_path: Path
    workspace: Path
    labels: tuple[str, ...]
    packet: DispatchPacket


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise ValueError("manifest must contain a jobs array")
    return data


def packet_has_external_transfer_approval(packet: DispatchPacket) -> bool:
    section = packet.sections.get("External Code Transfer Approval", "")
    return "approved: yes" in section.casefold()


def build_job(item: dict[str, Any], manifest_dir: Path) -> BatchJob:
    ticket = str(item.get("ticket", "")).upper()
    packet_path = (manifest_dir / str(item.get("packet", ""))).resolve()
    workspace = (manifest_dir / str(item.get("workspace", ""))).resolve()
    labels = tuple(str(label).casefold() for label in item.get("labels", []))
    if not ticket.startswith("TRA-"):
        raise ValueError("each job ticket must be a TRA identifier")
    if not packet_path.is_file():
        raise ValueError(f"packet not found for {ticket}: {packet_path}")
    packet = parse_dispatch_packet(packet_path.read_text(encoding="utf-8"))
    if packet.identifier != ticket:
        raise ValueError(f"packet ticket mismatch for {ticket}: {packet.identifier}")
    return BatchJob(ticket, packet_path, workspace, labels, packet)


def normalized_scope(packet: DispatchPacket) -> set[str]:
    return {path.replace("\\", "/").rstrip("/") for path in packet.allowed_files}


def scopes_overlap(first: DispatchPacket, second: DispatchPacket) -> bool:
    first_scope, second_scope = normalized_scope(first), normalized_scope(second)
    if any("*" in path or "?" in path for path in first_scope | second_scope):
        return True
    return any(
        left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")
        for left in first_scope
        for right in second_scope
    )


def validate_job(job: BatchJob) -> list[str]:
    errors = validate_packet(job.packet)
    if REQUIRED_LABEL not in job.labels:
        errors.append(f"{job.ticket} is missing {REQUIRED_LABEL}")
    if FORBIDDEN_LABEL in job.labels:
        errors.append(f"{job.ticket} cannot carry {FORBIDDEN_LABEL}")
    if not packet_has_external_transfer_approval(job.packet):
        errors.append(f"{job.ticket} packet lacks explicit external-transfer approval")
    try:
        validate_repo_root(job.workspace)
        dirty = git_changed_files(job.workspace)
        if dirty:
            errors.append(f"{job.ticket} workspace is dirty: {', '.join(dirty)}")
    except (ValueError, RuntimeError) as exc:
        errors.append(str(exc))
    return errors


def run_job(job: BatchJob) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).with_name("hermes_runner_bridge.py")),
        "--packet",
        str(job.packet_path),
        "--repo-root",
        str(job.workspace),
        "--allow-external-code-transfer",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "ticket": job.ticket,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-external-code-transfer", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    concurrency = int(manifest.get("max_concurrent_workers", 1))
    if concurrency < 1 or concurrency > MAX_CONCURRENT_WORKERS:
        raise SystemExit(f"max_concurrent_workers must be between 1 and {MAX_CONCURRENT_WORKERS}")
    jobs = [build_job(item, manifest_path.parent) for item in manifest["jobs"]]
    if not jobs:
        raise SystemExit("manifest contains no jobs")
    if len({job.ticket for job in jobs}) != len(jobs):
        raise SystemExit("manifest contains duplicate ticket identifiers")

    errors = {job.ticket: validate_job(job) for job in jobs}
    for index, job in enumerate(jobs):
        for other in jobs[index + 1 :]:
            if scopes_overlap(job.packet, other.packet):
                errors[job.ticket].append(f"scope overlaps {other.ticket}")
                errors[other.ticket].append(f"scope overlaps {job.ticket}")
    invalid = {ticket: messages for ticket, messages in errors.items() if messages}
    if invalid:
        print(json.dumps({"state": "blocked", "errors": invalid}, indent=2))
        raise SystemExit(2)

    if not args.execute:
        print(json.dumps({"state": "validated", "tickets": [job.ticket for job in jobs], "workers": concurrency}, indent=2))
        return
    if not args.allow_external_code_transfer:
        raise SystemExit("--execute requires --allow-external-code-transfer")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(run_job, job) for job in jobs]
        results = [future.result() for future in as_completed(futures)]
    print(json.dumps({"state": "completed", "results": sorted(results, key=lambda item: item["ticket"])}, indent=2))


if __name__ == "__main__":
    main()
