"""Validate E2E what-if job benchmark evidence against the project contract.

The validator is honest about evidence ownership: a report measured on the
provisional fake-adapter path can only pass as ``application_layer_provisional``
— it must never be quoted as production SLA. Production-grade status requires
``adapter_mode == "production_adapters"`` in the report, which the benchmark
harness sets only when wired to real promoted adapters.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "data/derived/private/phase4_orchestrator/e2e_benchmark_report.json"
)
CONTRACT_PATH = ROOT / "project_contract.json"

ALLOWED_ADAPTER_MODES = {
    "provisional_fake_adapters",
    "production_adapters",
}


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(
    report: dict[str, Any], contract: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Return (blocking_errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if report.get("evidence_kind") != "measured":
        errors.append("evidence_kind must be 'measured'")

    if str(report.get("status")).lower() != "pass":
        errors.append("report status is not 'pass'")

    adapter_mode = report.get("adapter_mode")
    if adapter_mode not in ALLOWED_ADAPTER_MODES:
        errors.append(f"unknown adapter_mode: {adapter_mode!r}")
    elif adapter_mode == "provisional_fake_adapters":
        if not str(report.get("adapter_disclosure", "")).strip():
            errors.append(
                "provisional-mode report is missing an explicit "
                "'adapter_disclosure' statement"
            )
        else:
            warnings.append(
                "PROVISIONAL EVIDENCE: this report measures the application "
                "layer with fake adapters; it does not satisfy the contract "
                "E2E SLA and must not be cited as production performance"
            )

    for field in ("p50_ms", "p95_ms", "p99_ms"):
        value = report.get(field)
        if value is None:
            errors.append(f"missing {field}")

    p95 = report.get("p95_ms")
    p99 = report.get("p99_ms")
    runtime = contract.get("runtime", {})
    e2e_target = runtime.get("e2e_p95_ms")
    deadline_target = runtime.get("hard_deadline_p99_ms")
    if p95 is not None and e2e_target is not None and p95 >= e2e_target:
        errors.append(f"E2E P95 {p95} ms breaches target {e2e_target} ms")
    if p99 is not None and deadline_target is not None and p99 >= deadline_target:
        errors.append(
            f"hard-deadline P99 {p99} ms breaches target {deadline_target} ms"
        )

    runs = report.get("measured_runs")
    completed = report.get("completed_runs")
    failures = report.get("failure_count")
    if not isinstance(runs, int) or runs < 30:
        errors.append("measured_runs must be an integer >= 30")
    if completed != runs or (isinstance(failures, int) and failures > 0):
        errors.append(
            "every measured job must reach a terminal status; "
            f"runs={runs}, completed={completed}, failures={failures}"
        )

    profile_fields = ("cpu_cores", "ram_gb", "platform", "python")
    recorded = report.get("recorded_profile") or {}
    missing = [key for key in profile_fields if recorded.get(key) is None]
    if missing:
        errors.append("recorded_profile missing fields: " + ", ".join(missing))

    return errors, warnings


def check_e2e_evidence() -> dict[str, Any]:
    if not REPORT_PATH.exists():
        return {"status": "fail", "errors": [f"missing report: {REPORT_PATH}"]}
    if not CONTRACT_PATH.exists():
        return {"status": "fail", "errors": ["missing project contract"]}

    report = _load_json(REPORT_PATH)
    contract = _load_json(CONTRACT_PATH)
    errors, warnings = _validate(report, contract)
    if errors:
        return {"status": "fail", "errors": errors}

    provisional = report["adapter_mode"] == "provisional_fake_adapters"
    return {
        "status": "application_layer_provisional" if provisional else "pass",
        "warnings": warnings,
        "p50_ms": report.get("p50_ms"),
        "p95_ms": report.get("p95_ms"),
        "p99_ms": report.get("p99_ms"),
        "targets_ms": {
            "e2e_p95": contract.get("runtime", {}).get("e2e_p95_ms"),
            "hard_deadline_p99": contract.get("runtime", {}).get(
                "hard_deadline_p99_ms"
            ),
        },
        "recorded_profile": report.get("recorded_profile"),
    }


def main() -> int:
    result = check_e2e_evidence()
    print(json.dumps(result, indent=2))
    if result["status"] == "fail":
        raise SystemExit(
            "E2E benchmark evidence validation failed:\n- "
            + "\n- ".join(result["errors"])
        )
    if result["status"] == "application_layer_provisional":
        raise SystemExit(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
