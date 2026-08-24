"""Measure end-to-end what-if job API latency (application layer).

Runs the FastAPI what-if job API in-process (ASGI transport) through the full
job lifecycle — POST /api/v1/what-if-jobs (202) → poll GET status until a
terminal status — and records p50/p95/p99 wall-clock latencies plus failure
counts into a JSON evidence report.

Honesty rules enforced by this script:
- The report always discloses ``adapter_mode``. With provisional adapters the
  evidence is application-layer only and MUST NOT be quoted as production SLA;
  ``validate_e2e_benchmark_evidence.py`` rejects reports whose adapter mode
  does not match what was actually run.
- Every job must reach a terminal status (succeeded/needs_review/failed) or
  the run fails; silent timeouts are never reported as passes.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REPORT_PATH = (
    ROOT / "data/derived/private/phase4_orchestrator/e2e_benchmark_report.json"
)
TERMINAL_STATUSES = {"succeeded", "needs_review", "failed"}
SCENARIO_TIME = "2025-06-01T08:00:00"


def _detect_ram_gb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped]

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        pass
    if sys.platform == "win32":
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.ullTotalPhys / (1024**3), 1)
    return None


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("empty sample")
    index = min(len(sorted_values) - 1, max(0, round(pct / 100 * len(sorted_values)) - 1))
    return sorted_values[index]


def build_client():
    """Build the in-process API client with documented provisional adapters."""
    try:
        from fastapi.testclient import TestClient
    except ImportError as exc:
        raise RuntimeError("Install the project API extra (fastapi)") from exc

    from stwi.config.runtime import get_runtime_settings
    from stwi.t4_orchestrator.api import create_app
    from stwi.t4_orchestrator.fake_adapters import (
        FakeSurrogateForecaster,
        safe_scenario,
    )
    from stwi.t4_orchestrator.job_store import InMemoryJobStore
    from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

    settings = get_runtime_settings({"STWI_RUNTIME_MODE": "test"})
    store = InMemoryJobStore()
    orchestrator = WhatIfOrchestrator(
        settings=settings,
        surrogate=FakeSurrogateForecaster(default_scenario=safe_scenario()),
    )
    app = create_app(store=store, orchestrator=orchestrator, settings=settings)
    return TestClient(app)


def run_one(client, body: dict, *, timeout_s: float) -> tuple[float, str] | tuple[None, str]:
    """Run one job lifecycle; return (latency_ms, terminal_status) or (None, error)."""
    start = time.perf_counter()
    response = client.post("/api/v1/what-if-jobs", json=body)
    if response.status_code != 202:
        return None, f"POST returned HTTP {response.status_code}"
    payload = response.json()
    job_id = payload.get("job_id")
    if not job_id:
        return None, "POST response missing job_id"

    deadline = start + timeout_s
    while True:
        poll = client.get(f"/api/v1/what-if-jobs/{job_id}")
        if poll.status_code != 200:
            return None, f"GET returned HTTP {poll.status_code}"
        status = poll.json().get("status")
        if status in TERMINAL_STATUSES:
            return (time.perf_counter() - start) * 1000.0, status
        if time.perf_counter() > deadline:
            return None, f"timeout after {timeout_s}s waiting for terminal status"
        time.sleep(0.002)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    if args.runs < 1 or args.warmup < 0:
        raise ValueError("runs must be positive and warmup non-negative")

    client = build_client()
    body = {
        "tenant_id": "e2e-benchmark",
        "scenario_time": SCENARIO_TIME,
        "candidate_action": {"node_id": "node-A", "green_time_ratio": 0.7},
        "node_ids": ["node-A"],
        "scenario_query": "quyền nghĩa vụ người sử dụng đường",
    }

    for _ in range(args.warmup):
        result = run_one(client, dict(body), timeout_s=args.timeout_s)
        if result[0] is None:
            raise SystemExit(f"warmup failed: {result[1]}")

    latencies_ms: list[float] = []
    status_counts: dict[str, int] = {}
    failures: list[str] = []
    for _ in range(args.runs):
        latency_ms, detail = run_one(client, dict(body), timeout_s=args.timeout_s)
        if latency_ms is None:
            failures.append(detail)
            continue
        latencies_ms.append(latency_ms)
        status_counts[detail] = status_counts.get(detail, 0) + 1

    ordered = sorted(latencies_ms)
    report = {
        "schema_version": "1.0",
        "evidence_kind": "measured",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "transport": "in-process ASGI (application layer)",
        "adapter_mode": "provisional_fake_adapters",
        "adapter_disclosure": (
            "Measured on the provisional fake-adapter path; NOT a production "
            "SLA claim. Production evidence requires real GCN-LSTM/surrogate/"
            "T3 adapters on the contract hardware profile."
        ),
        "warmup_runs": args.warmup,
        "measured_runs": args.runs,
        "completed_runs": len(latencies_ms),
        "failures": failures[:10],
        "failure_count": len(failures),
        "status_distribution": status_counts,
        "p50_ms": round(_percentile(ordered, 50), 3),
        "p95_ms": round(_percentile(ordered, 95), 3),
        "p99_ms": round(_percentile(ordered, 99), 3),
        "mean_ms": round(statistics.fmean(ordered), 3) if ordered else None,
        "max_ms": round(max(ordered), 3) if ordered else None,
        "targets_ms": {
            "e2e_p95": 30000,
            "hard_deadline_p99": 180000,
        },
        "recorded_profile": {
            "cpu_cores": os.cpu_count(),
            "ram_gb": _detect_ram_gb(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
    }

    if len(latencies_ms) != args.runs:
        report["status"] = "fail"
        reason = f"{len(failures)} of {args.runs} jobs did not complete"
    elif report["p95_ms"] >= 30000 or report["p99_ms"] >= 180000:
        report["status"] = "fail"
        reason = "latency targets breached"
    else:
        report["status"] = "pass"
        reason = ""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=2))
    if report["status"] != "pass":
        raise SystemExit(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
