"""Budget guard for Symphony dashboard token and rate-limit usage.

The guard is read-only: it polls the local Symphony dashboard state, estimates
current token burn, projects near-term usage, and prints a coordinator action.
It does not stop Symphony or update Linear by itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATE_URL = "http://127.0.0.1:4011/api/v1/state"
RATE_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)%")


@dataclass(frozen=True)
class Thresholds:
    issue_warn_tokens: int = 300_000
    issue_stop_tokens: int = 900_000
    batch_warn_tokens: int = 750_000
    batch_stop_tokens: int = 1_500_000
    rate_warn_pct: float = 35.0
    rate_stop_pct: float = 50.0
    projection_minutes: int = 10


@dataclass(frozen=True)
class IssueBudget:
    identifier: str
    state: str
    total_tokens: int
    started_at: str | None
    turn_count: int | None
    workspace_path: str | None
    has_diff: bool | None
    last_message: str | None


def load_state(url: str, state_file: Path | None = None) -> dict[str, Any]:
    if state_file is not None:
        return json.loads(state_file.read_text(encoding="utf-8"))

    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise SystemExit(f"Cannot read Symphony state from {url}: {error}") from error


def token_total(entry: dict[str, Any] | None) -> int:
    if not entry:
        return 0
    try:
        return int(entry.get("total_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except ValueError:
        return None


def elapsed_seconds(state: dict[str, Any], issues: list[IssueBudget]) -> int:
    totals = state.get("codex_totals") or {}
    seconds = totals.get("seconds_running")
    if isinstance(seconds, (int, float)) and seconds > 0:
        return int(seconds)

    generated_at = parse_iso_utc(state.get("generated_at"))
    starts = [
        parse_iso_utc(issue.started_at)
        for issue in issues
        if parse_iso_utc(issue.started_at) is not None
    ]
    starts = [start for start in starts if start is not None]
    if generated_at and starts:
        return max(1, int((generated_at - min(starts)).total_seconds()))
    return 0


def git_has_diff(workspace_path: str | None) -> bool | None:
    if not workspace_path:
        return None
    path = Path(workspace_path)
    if not path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def running_issues(
    state: dict[str, Any], *, check_diff: bool = True
) -> list[IssueBudget]:
    issues = []
    for item in state.get("running") or []:
        workspace_path = item.get("workspace_path")
        issues.append(
            IssueBudget(
                identifier=str(item.get("issue_identifier") or item.get("issue_id")),
                state=str(item.get("state") or ""),
                total_tokens=token_total(item.get("tokens")),
                started_at=item.get("started_at"),
                turn_count=item.get("turn_count"),
                workspace_path=workspace_path,
                has_diff=git_has_diff(workspace_path) if check_diff else None,
                last_message=item.get("last_message"),
            )
        )
    return issues


def collect_rate_percentages(value: Any) -> list[float]:
    percentages: list[float] = []
    if isinstance(value, dict):
        for child in value.values():
            percentages.extend(collect_rate_percentages(child))
    elif isinstance(value, list):
        for child in value:
            percentages.extend(collect_rate_percentages(child))
    elif isinstance(value, (int, float)):
        number = float(value)
        if 0 <= number <= 100:
            percentages.append(number)
    elif isinstance(value, str):
        percentages.extend(float(match) for match in RATE_PERCENT_PATTERN.findall(value))
    return percentages


def rate_limit_pct(state: dict[str, Any], issues: list[IssueBudget]) -> float | None:
    candidates = collect_rate_percentages(state.get("rate_limits"))
    for issue in issues:
        candidates.extend(collect_rate_percentages(issue.last_message))
    return max(candidates) if candidates else None


def evaluate_budget(
    state: dict[str, Any],
    thresholds: Thresholds,
    *,
    check_diff: bool = True,
) -> dict[str, Any]:
    issues = running_issues(state, check_diff=check_diff)
    total_tokens = token_total(state.get("codex_totals"))
    if total_tokens == 0:
        total_tokens = sum(issue.total_tokens for issue in issues)

    seconds = elapsed_seconds(state, issues)
    tokens_per_minute = (total_tokens / (seconds / 60)) if seconds else 0.0
    projected_tokens = int(
        total_tokens + tokens_per_minute * thresholds.projection_minutes
    )
    rate_pct = rate_limit_pct(state, issues)
    remaining_rate_pct = None if rate_pct is None else max(0.0, 100.0 - rate_pct)

    reasons: list[str] = []
    recommendations: list[str] = []
    action = "ok"

    for issue in issues:
        if (
            issue.total_tokens >= thresholds.issue_stop_tokens
            and issue.has_diff is False
        ):
            action = "stop"
            reasons.append(
                f"{issue.identifier} used {issue.total_tokens:,} tokens without a diff"
            )
        elif issue.total_tokens >= thresholds.issue_warn_tokens:
            action = max_action(action, "throttle")
            reasons.append(
                f"{issue.identifier} used {issue.total_tokens:,} tokens"
            )

    if total_tokens >= thresholds.batch_stop_tokens:
        action = "stop"
        reasons.append(f"batch used {total_tokens:,} tokens")
    elif total_tokens >= thresholds.batch_warn_tokens:
        action = max_action(action, "throttle")
        reasons.append(f"batch used {total_tokens:,} tokens")

    if rate_pct is not None:
        if rate_pct >= thresholds.rate_stop_pct:
            action = "stop"
            reasons.append(f"rate-limit pressure is {rate_pct:.1f}%")
        elif rate_pct >= thresholds.rate_warn_pct:
            action = max_action(action, "throttle")
            reasons.append(f"rate-limit pressure is {rate_pct:.1f}%")

    if projected_tokens >= thresholds.batch_stop_tokens and action != "stop":
        action = max_action(action, "throttle")
        reasons.append(
            f"projected {thresholds.projection_minutes}m usage is "
            f"{projected_tokens:,} tokens"
        )

    if action == "ok":
        early_issue = next(
            (
                issue
                for issue in issues
                if issue.total_tokens >= thresholds.issue_warn_tokens // 2
            ),
            None,
        )
        if early_issue is not None:
            action = "watch"
            reasons.append(
                f"{early_issue.identifier} is approaching the issue watch band"
            )
        elif total_tokens >= thresholds.batch_warn_tokens // 2:
            action = "watch"
            reasons.append("batch is approaching the watch band")
        elif projected_tokens >= thresholds.batch_warn_tokens:
            action = "watch"
            reasons.append(
                f"projected {thresholds.projection_minutes}m usage is "
                f"{projected_tokens:,} tokens"
            )
        elif rate_pct is None and issues:
            action = "watch"
            reasons.append("rate-limit usage is unknown while agents are running")

    if action == "ok" and issues:
        recommendations.append("Keep current one-issue batch; do not add agents yet.")
    elif action == "watch":
        recommendations.append("Continue current batch, but poll again before dispatch.")
    elif action == "throttle":
        recommendations.append("Do not dispatch new issues; let active agents finish.")
        recommendations.append("Prefer Human Review before another implementation task.")
    elif action == "stop":
        recommendations.append("Stop Symphony or move active issues to Human Review.")
        recommendations.append("Review workspace diffs before restarting.")

    if not issues:
        recommendations.append("No running agents detected.")

    return {
        "action": action,
        "reasons": reasons,
        "recommendations": recommendations,
        "running_agents": len(issues),
        "total_tokens": total_tokens,
        "elapsed_seconds": seconds,
        "tokens_per_minute": round(tokens_per_minute, 2),
        "projected_tokens": projected_tokens,
        "projection_minutes": thresholds.projection_minutes,
        "rate_limit_used_pct": rate_pct,
        "estimated_rate_limit_remaining_pct": remaining_rate_pct,
        "issues": [issue.__dict__ for issue in issues],
    }


def max_action(left: str, right: str) -> str:
    order = {"ok": 0, "watch": 1, "throttle": 2, "stop": 3}
    return right if order[right] > order[left] else left


def render_human(report: dict[str, Any]) -> str:
    lines = [
        "Symphony budget guard",
        f"Action: {report['action']}",
        f"Running agents: {report['running_agents']}",
        f"Total tokens: {report['total_tokens']:,}",
        f"Tokens/minute: {report['tokens_per_minute']:,}",
        (
            f"Projected +{report['projection_minutes']}m: "
            f"{report['projected_tokens']:,}"
        ),
    ]
    rate_pct = report["rate_limit_used_pct"]
    if rate_pct is None:
        lines.append("Rate limit used: unknown")
    else:
        remaining = report["estimated_rate_limit_remaining_pct"]
        lines.append(f"Rate limit used: {rate_pct:.1f}%")
        lines.append(f"Estimated rate-limit remaining: {remaining:.1f}%")

    lines.append("")
    lines.append("Issues:")
    if report["issues"]:
        for issue in report["issues"]:
            diff = issue["has_diff"]
            diff_label = "unknown" if diff is None else str(diff).lower()
            lines.append(
                f"- {issue['identifier']}: {issue['total_tokens']:,} tokens, "
                f"state={issue['state']}, turn={issue['turn_count']}, "
                f"has_diff={diff_label}"
            )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Reasons:")
    if report["reasons"]:
        lines.extend(f"- {reason}" for reason in report["reasons"])
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Recommendations:")
    lines.extend(f"- {item}" for item in report["recommendations"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_STATE_URL)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-diff-check", action="store_true")
    parser.add_argument("--fail-on-stop", action="store_true")
    parser.add_argument("--issue-warn-tokens", type=int, default=300_000)
    parser.add_argument("--issue-stop-tokens", type=int, default=900_000)
    parser.add_argument("--batch-warn-tokens", type=int, default=750_000)
    parser.add_argument("--batch-stop-tokens", type=int, default=1_500_000)
    parser.add_argument("--rate-warn-pct", type=float, default=35.0)
    parser.add_argument("--rate-stop-pct", type=float, default=50.0)
    parser.add_argument("--projection-minutes", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    thresholds = Thresholds(
        issue_warn_tokens=args.issue_warn_tokens,
        issue_stop_tokens=args.issue_stop_tokens,
        batch_warn_tokens=args.batch_warn_tokens,
        batch_stop_tokens=args.batch_stop_tokens,
        rate_warn_pct=args.rate_warn_pct,
        rate_stop_pct=args.rate_stop_pct,
        projection_minutes=args.projection_minutes,
    )
    state = load_state(args.url, args.state_file)
    report = evaluate_budget(
        state,
        thresholds,
        check_diff=not args.no_diff_check,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report), end="")
    if args.fail_on_stop and report["action"] == "stop":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
