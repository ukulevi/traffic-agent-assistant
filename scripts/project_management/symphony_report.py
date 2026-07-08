"""Render and validate the local STWI Symphony-style project board."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BOARD_PATH = ROOT / "docs" / "project_management" / "symphony" / "board.json"


def _load_board(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_board(board: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    columns = set(board.get("columns", []))
    lane_names = {lane.get("name") for lane in board.get("lanes", [])}
    task_ids: set[str] = set()

    required_task_fields = {
        "id",
        "title",
        "lane",
        "owner_agent",
        "status",
        "priority",
        "evidence",
        "acceptance_criteria",
        "next_action",
    }
    for task in board.get("tasks", []):
        missing = required_task_fields - set(task)
        if missing:
            errors.append(f"{task.get('id', '<missing-id>')}: missing {sorted(missing)}")

        task_id = task.get("id")
        if task_id in task_ids:
            errors.append(f"{task_id}: duplicate task id")
        task_ids.add(task_id)

        if task.get("status") not in columns:
            errors.append(f"{task_id}: invalid status {task.get('status')!r}")
        if task.get("lane") not in lane_names:
            errors.append(f"{task_id}: invalid lane {task.get('lane')!r}")
        if task.get("status") == "Done" and not task.get("checks"):
            errors.append(f"{task_id}: Done task must record checks")

    return errors


def _lane_readiness_evidence(lane: dict[str, Any]) -> str:
    parts: list[str] = []

    summary = (lane.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    readiness = lane.get("readiness_evidence") or []
    if readiness:
        evidence_items = "; ".join(str(item) for item in readiness if str(item).strip())
        parts.append(f"Evidence: {evidence_items}")

    blockers = lane.get("blockers") or []
    if blockers:
        blocker_items = "; ".join(str(item) for item in blockers if str(item).strip())
        parts.append(f"Blockers: {blocker_items}")

    return " | ".join(parts) if parts else "No lane readiness evidence recorded."


def _render_markdown(board: dict[str, Any]) -> str:
    tasks = board.get("tasks", [])
    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        by_status[task["status"]].append(task)

    counts = Counter(task["status"] for task in tasks)

    lines: list[str] = [
        f"# {board['board_name']}",
        "",
        f"Last reviewed: {board['last_reviewed_at']}",
        "",
        "## Readiness Handoff Summary",
        "",
        f"- Evidence base: {board.get('source_of_truth', ['Unset'])[0]}",
        f"- Todo: {counts.get('Todo', 0)} | In Progress: {counts.get('In Progress', 0)} | "
        f"Human Review: {counts.get('Human Review', 0)} | Rework: {counts.get('Rework', 0)} | "
        f"Done: {counts.get('Done', 0)}",
    ]

    automation = board.get("automation") or {}
    if automation:
        requires = automation.get("requires_human_review_for", [])
        lines.append(f"- Requires human review for: {', '.join(requires) or 'none listed'}")
        report_command = automation.get("report_command")
        if report_command:
            lines.append(f"- Report command: {report_command}")
        if automation.get("daily_agent_update"):
            lines.append("- Daily agent update: enabled")
    lines.extend(
        [
            "- Handoff note: readiness is derived from board/state, gate acceptance criteria, and verified checks; not raw agentReport percentages.",
            "",
            "## Summary",
            "",
            "| Status | Count |",
            "|---|---:|",
        ]
    )
    for column in board["columns"]:
        lines.append(f"| {column} | {counts.get(column, 0)} |")

    lines.extend(
        [
            "",
            "## Lane Readiness Evidence",
            "",
            "| Lane | Owner | Completion | Health | Readiness Evidence |",
            "|---|---|---:|---|---|",
        ]
    )
    for lane in board.get("lanes", []):
        lines.append(
            f"| {lane.get('name', 'Unknown')} | {lane.get('owner_agent', 'Unassigned')} | "
            f"{lane.get('completion_estimate_pct', '?')}% | {lane.get('health', '?')} | "
            f"{_lane_readiness_evidence(lane)} |"
        )

    lines.extend(["", "## Tasks"])
    for column in board["columns"]:
        lines.extend(["", f"### {column}", ""])
        column_tasks = by_status.get(column, [])
        if not column_tasks:
            lines.append("- None")
            continue
        for task in column_tasks:
            linear_ref = (
                f" / {task['linear_identifier']}"
                if task.get("linear_identifier")
                else ""
            )
            lines.append(
                f"- `{task['id']}`{linear_ref} [{task['priority']}] {task['title']} "
                f"({task['lane']}, {task['owner_agent']})"
            )
            if task.get("evidence"):
                evidence_items = ", ".join(str(item) for item in task["evidence"])
                lines.append(f"  Evidence: {evidence_items}")
            if task.get("acceptance_criteria"):
                criteria_items = "; ".join(
                    str(item) for item in task["acceptance_criteria"]
                )
                lines.append(f"  Acceptance: {criteria_items}")
            lines.append(f"  Next: {task['next_action']}")
            if task.get("checks"):
                lines.append(f"  Checks: {'; '.join(str(item) for item in task['checks'])}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--board",
        type=Path,
        default=BOARD_PATH,
        help="Path to board.json",
    )
    parser.add_argument(
        "--write-markdown",
        type=Path,
        help="Optional output path for a rendered Markdown report.",
    )
    args = parser.parse_args()

    board = _load_board(args.board)
    errors = _validate_board(board)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    report = _render_markdown(board)
    if args.write_markdown:
        args.write_markdown.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
