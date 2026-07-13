"""Run the deterministic, offline STWI MVP demo smoke flow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _request_body() -> dict[str, Any]:
    return {
        "tenant_id": "demo-operator",
        "scenario_time": "2025-06-01T08:00:00+00:00",
        "candidate_action": {"node_id": "node-A", "green_time_ratio": 0.7},
        "node_ids": ["node-A"],
        "scenario_query": "Danh gia kich ban su co tai nut node-A.",
    }


def _client_for(scenario: object) -> object:
    from fastapi.testclient import TestClient
    from stwi.t4_orchestrator.api import create_app
    from stwi.t4_orchestrator.fake_adapters import FakeSurrogateForecaster
    from stwi.t4_orchestrator.job_store import InMemoryJobStore
    from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

    return TestClient(create_app(
        store=InMemoryJobStore(),
        orchestrator=WhatIfOrchestrator(
            surrogate=FakeSurrogateForecaster(default_scenario=scenario)
        ),
    ))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _run_case(name: str, scenario: object, expected_status: str, decision: str) -> dict[str, Any]:
    client = _client_for(scenario)
    accepted = client.post("/api/v1/what-if-jobs", json=_request_body())
    _require(accepted.status_code == 202, f"{name}: expected HTTP 202")
    job_id = accepted.json()["job_id"]
    terminal = client.get(f"/api/v1/what-if-jobs/{job_id}")
    _require(terminal.status_code == 200, f"{name}: terminal GET failed")
    terminal_data = terminal.json()
    _require(terminal_data["status"] == expected_status, f"{name}: wrong terminal status")
    stream = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
    _require("event: result" in stream.text, f"{name}: SSE has no result event")

    result = terminal_data["result"]
    action = result["recommended_action"] or result["candidate_action"]
    if expected_status == "succeeded":
        _require(result["recommended_action"] is not None, f"{name}: missing recommendation")
        _require(result["candidate_action"] is None, f"{name}: unexpected candidate")
    else:
        _require(result["recommended_action"] is None, f"{name}: unexpected recommendation")
        _require(result["candidate_action"] is not None, f"{name}: missing candidate")

    recorded = client.post(
        f"/api/v1/what-if-jobs/{job_id}/operator-decision",
        json={"operator_id": "demo-operator", "decision": decision, "comment": "Offline MVP smoke evidence."},
    )
    _require(recorded.status_code == 200, f"{name}: decision request failed")
    decision_data = recorded.json()
    _require(decision_data["automatic_actuation"] is False, f"{name}: automatic actuation")
    _require(decision_data["operator_decision"]["applied_by_system"] is False, f"{name}: system-applied decision")

    return {
        "case": name,
        "job_id": job_id,
        "accepted_status": accepted.json()["status"],
        "terminal_status": terminal_data["status"],
        "trace_id": result["audit_record"]["trace_id"],
        "model_version": result["model_version"],
        "data_version": result["data_version"],
        "provisional": True,
        "sse_result_event": True,
        "operator_decision": decision,
        "applied_by_system": decision_data["operator_decision"]["applied_by_system"],
        "automatic_actuation": decision_data["automatic_actuation"],
        "invariants": {
            "http_202": accepted.status_code == 202,
            "terminal_status_expected": terminal_data["status"] == expected_status,
            "sse_result_event": "event: result" in stream.text,
            "non_executable_action": action["executable"] is False,
            "human_decision_only": decision_data["operator_decision"]["applied_by_system"] is False,
        },
    }


def run_smoke(output: Path) -> dict[str, Any]:
    """Run safe and fail-closed flows, then write aggregate-only evidence."""
    from stwi.t4_orchestrator.fake_adapters import safe_scenario, unsafe_vc_scenario

    evidence = {
        "harness": "stwi_offline_mvp_smoke_v1",
        "mode": "offline_provisional",
        "live_services_contacted": False,
        "raw_video_retained": False,
        "cases": [
            _run_case("safe_approval", safe_scenario(), "succeeded", "approved"),
            _run_case("unsafe_rejection", unsafe_vc_scenario(), "needs_review", "rejected"),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/derived/private/demo/mvp_smoke_evidence.json")
    args = parser.parse_args()
    evidence = run_smoke(args.output)
    print(json.dumps({"output": str(args.output), "case_count": len(evidence["cases"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
