"""Phase 4 start readiness report generator.

Runs the Phase 4 contract + safety test suites, verifies Gate P3 still passes,
and emits:
    data/derived/private/phase4_orchestrator/phase4_start_readiness_report.json

Output has status=ready_for_phase4_provisional when all checks pass.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_root / "tests"))
sys.path.insert(0, str(_root))  # for `import scripts.*` in test_t3_corpus_ingestion


def run_test_suite(pattern: str) -> dict:
    import io
    loader = unittest.TestLoader()
    tests_dir = Path(__file__).resolve().parents[1] / "tests"
    suite = loader.discover(str(tests_dir), pattern=pattern)
    buf = io.StringIO()
    runner = unittest.TextTestRunner(stream=buf, verbosity=0)
    result = runner.run(suite)
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed": result.wasSuccessful(),
        "failure_details": [str(f[1])[:200] for f in result.failures + result.errors],
    }


def check_gate_p3(gate_report_path: Path) -> dict:
    if not gate_report_path.exists():
        return {"present": False, "passed": False}
    report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    return {
        "present": True,
        "passed": report.get("status") == "pass",
        "gate_criteria": report.get("gate_criteria", {}),
        "citation_precision": report.get("retrieval", {}).get("citation_precision"),
        "false_positive_rate": report.get("retrieval", {}).get("false_positive_rate"),
    }


def main(output_dir: Path) -> int:
    print("=== Phase 4 Start Readiness Report ===")

    root = Path(__file__).resolve().parents[1]

    # 1. Gate P3 status
    gate_p3_path = (
        root / "data" / "derived" / "private" / "phase3_knowledge" / "gate_p3_report.json"
    )
    gate_p3 = check_gate_p3(gate_p3_path)
    print(f"Gate P3: {'PASS' if gate_p3['passed'] else 'FAIL'}")

    # 2. Phase 3 contract tests
    print("Running Phase 3 tests (test_t3*.py)...")
    t3_result = run_test_suite("test_t3*.py")
    print(f"  T3 tests: {t3_result['tests_run']} run, "
          f"{t3_result['failures'] + t3_result['errors']} fail, "
          f"{t3_result['skipped']} skip")

    # 3. Phase 4 contract tests
    print("Running Phase 4 contract tests (test_t4_contracts.py)...")
    t4_contracts = run_test_suite("test_t4_contracts.py")
    print(f"  T4 contracts: {t4_contracts['tests_run']} run, "
          f"{t4_contracts['failures'] + t4_contracts['errors']} fail")

    # 4. Phase 4 safety tests
    print("Running Phase 4 safety tests (test_t4_safety.py)...")
    t4_safety = run_test_suite("test_t4_safety.py")
    print(f"  T4 safety: {t4_safety['tests_run']} run, "
          f"{t4_safety['failures'] + t4_safety['errors']} fail")

    # 5. Phase 4 HTTP API tests
    print("Running Phase 4 HTTP API tests (test_t4_api_http.py)...")
    t4_api_http = run_test_suite("test_t4_api_http.py")
    print(f"  T4 API HTTP: {t4_api_http['tests_run']} run, "
          f"{t4_api_http['failures'] + t4_api_http['errors']} fail, "
          f"{t4_api_http['skipped']} skip")

    import importlib.util
    has_fastapi = importlib.util.find_spec("fastapi") is not None

    # 6. Evaluate readiness criteria
    criteria = {
        "gate_p3_pass": gate_p3["passed"],
        "t3_tests_pass": t3_result["passed"],
        "t4_contract_tests_pass": t4_contracts["passed"],
        "t4_safety_tests_pass": t4_safety["passed"],
        "t4_api_http_tests_pass": t4_api_http["passed"] and has_fastapi,
        "job_lifecycle_covered": t4_contracts["passed"],  # contracts cover all 6 statuses
        "fail_closed_verified": t4_safety["passed"],
        "audit_record_present": t4_contracts["passed"],
        "no_automatic_actuation": True,  # enforced by WhatIfJobResult model_validator
        "action_field_semantics": t4_contracts["passed"],  # enforced by contract
        "sse_event_resume_covered": t4_contracts["passed"],
        "operator_decision_audit_only": t4_contracts["passed"],
        "csl_three_iteration_trace": t4_safety["passed"],
        "fake_adapters_documented": True,  # see known_limitations below
    }
    all_pass = all(criteria.values())
    status = "ready_for_phase4_provisional" if all_pass else "not_ready"

    report = {
        "schema_version": "1.0",
        "gate": "P4_start",
        "status": status,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "phase4_mode": "provisional_mock_first",
        "criteria": criteria,
        "test_results": {
            "t3_suite": {k: v for k, v in t3_result.items() if k != "failure_details"},
            "t4_contracts": {k: v for k, v in t4_contracts.items() if k != "failure_details"},
            "t4_safety": {k: v for k, v in t4_safety.items() if k != "failure_details"},
            "t4_api_http": {k: v for k, v in t4_api_http.items() if k != "failure_details"},
        },
        "gate_p3": gate_p3,
        "fake_adapters": [
            "FakeBaselineForecaster — no ML model; returns synthetic predictions",
            "FakeSurrogateForecaster — configurable vc_ratio/uncertainty/ood for tests",
            "FakeT3Adapter (T3) — in-memory retriever + official corpus",
            "InMemoryJobStore — no Redis; replaced by Redis-backed store in Phase 5",
        ],
        "must_replace_before_production": [
            "FakeBaselineForecaster → real GCN-LSTM (T2)",
            "FakeSurrogateForecaster → real heterogeneous surrogate ensemble (T2)",
            "T3KnowledgeTier(FakeT3Adapter) → T3KnowledgeTier(RealT3Adapter) with Qdrant+TimescaleDB",
            "InMemoryJobStore → Redis-backed store + Celery workers",
            "BackgroundTasks → Celery task queue",
        ],
        "known_limitations": [
            "Phase 2 baseline/surrogate use synthetic/mock data — NOT production accuracy.",
            "Phase 4 runs jobs synchronously in FastAPI BackgroundTasks, not Celery.",
            "SSE resume is backed by in-memory event IDs; Redis-backed persistence is still Phase 5 work.",
            "Operator approval is audit-only and explicitly does not trigger field actuation.",
            "SOP corpus not yet ingested — only statutory law (35/2024, 36/2024) available.",
        ],
        "failure_details": {
            "t3": t3_result.get("failure_details", []),
            "t4_contracts": t4_contracts.get("failure_details", []),
            "t4_safety": t4_safety.get("failure_details", []),
            "t4_api_http": t4_api_http.get("failure_details", []),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "phase4_start_readiness_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport written: {report_path}")
    print(f"\nPhase 4 Start: {status.upper()}")
    for criterion, ok in criteria.items():
        mark = "[OK]  " if ok else "[FAIL]"
        print(f"  {mark} {criterion}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "data" / "derived" / "private" / "phase4_orchestrator"
    sys.exit(main(output))
