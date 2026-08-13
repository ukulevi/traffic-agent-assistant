"""Run versioned STWI demo evidence profiles without upgrading mock claims."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_OPEN_CLIENTS: list[Any] = []


def _request_body(
    *,
    node_id: str = "node_00",
    tenant_id: str = "demo-operator",
    jurisdiction: str = "VN",
    ratio: float = 0.7,
    event_type: str | None = None,
) -> dict[str, Any]:
    from stwi.t4_orchestrator.demo_adapters import demo_node_ids

    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "scenario_time": "2025-06-01T08:00:00+00:00",
        "candidate_action": {
            "node_id": node_id,
            "green_time_ratio": ratio,
        },
        "node_ids": list(demo_node_ids()),
        "scenario_query": (
            f"Đánh giá quyền và nghĩa vụ người sử dụng đường tại {node_id}."
        ),
        "jurisdiction": jurisdiction,
    }
    if event_type is not None:
        incident: dict[str, Any] = {
            "event_type": event_type,
            "affected_node_ids": [node_id],
            "severity": "medium",
            "duration_minutes": 30,
            "description": f"Synthetic {event_type} incident.",
        }
        if event_type == "lane_closure":
            incident["lane_closure_ratio"] = 0.5
        elif event_type == "demand_surge":
            incident["demand_multiplier"] = 1.5
        elif event_type == "signal_change":
            incident["signal_plan_delta"] = {"green_time_ratio_delta": 0.1}
        payload["incident"] = incident
    return payload


def _client_for(orchestrator: object, principal_resolver: object | None = None) -> object:
    from fastapi.testclient import TestClient

    from stwi.config.runtime import get_runtime_settings
    from stwi.t4_orchestrator.api import create_app
    from stwi.t4_orchestrator.job_store import InMemoryJobStore

    settings = get_runtime_settings({"STWI_RUNTIME_MODE": "demo"})
    client = TestClient(
        create_app(
            store=InMemoryJobStore(),
            orchestrator=orchestrator,
            settings=settings,
            principal_resolver=principal_resolver,
        )
    )
    _OPEN_CLIENTS.append(client)
    return client


def _close_demo_clients() -> None:
    while _OPEN_CLIENTS:
        _OPEN_CLIENTS.pop().close()


def _orchestrator_for(profile: str) -> object:
    from stwi.config.runtime import get_runtime_settings
    from stwi.t4_orchestrator.demo_adapters import (
        DemoSurrogateForecaster,
        RefinementDemoSurrogateForecaster,
    )
    from stwi.t4_orchestrator.fake_adapters import FakeBaselineForecaster
    from stwi.t4_orchestrator.fake_adapters import (
        FakeSurrogateForecaster,
        high_uncertainty_scenario,
        ood_scenario,
    )
    from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

    settings = get_runtime_settings({"STWI_RUNTIME_MODE": "demo"})
    baseline: object = FakeBaselineForecaster()
    surrogate: object = DemoSurrogateForecaster()
    timeout_seconds = 180.0
    route_generator: object | None = None

    if profile == "refinement":
        surrogate = RefinementDemoSurrogateForecaster()
    elif profile == "ood":
        surrogate = FakeSurrogateForecaster(default_scenario=ood_scenario())
    elif profile == "high_uncertainty":
        surrogate = FakeSurrogateForecaster(
            default_scenario=high_uncertainty_scenario()
        )
    elif profile == "dependency_failure":

        class FailingBaseline:
            is_provisional_adapter = True

            def predict(self, **_kwargs: object) -> list[object]:
                raise RuntimeError("synthetic dependency unavailable")

        baseline = FailingBaseline()
    elif profile == "deadline_exceeded":
        timeout_seconds = 0.0
    elif profile == "route_no_candidates":

        class NoSyntheticRoutes:
            def generate(
                self, *_args: object, **_kwargs: object
            ) -> tuple[object, ...]:
                return ()

        route_generator = NoSyntheticRoutes()

    return WhatIfOrchestrator(
        baseline=baseline,
        surrogate=surrogate,
        settings=settings,
        timeout_seconds=timeout_seconds,
        route_generator=route_generator,
    )


def _policy_version() -> str:
    """Return the machine-readable contract version used by the smoke run."""

    contract = json.loads((ROOT / "project_contract.json").read_text(encoding="utf-8"))
    version = contract.get("contract_version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("project contract version is unavailable")
    return version


def _run_job_case(scenario: object) -> object:
    from stwi.demo.evidence import CapabilityEvidence, CapabilityStatus

    orchestrator = _orchestrator_for(scenario.profile or "safe")
    client = _client_for(orchestrator)
    jurisdiction = "DEMO-NONE" if scenario.profile == "missing_citation" else "VN"
    accepted = client.post(
        "/api/v1/what-if-jobs",
        json=_request_body(
            node_id=scenario.node_id,
            jurisdiction=jurisdiction,
            event_type=scenario.event_type,
        ),
    )
    if accepted.status_code != scenario.expected_http_status:
        raise RuntimeError("unexpected create status")
    job_id = accepted.json()["job_id"]
    terminal = client.get(f"/api/v1/what-if-jobs/{job_id}")
    if terminal.status_code != 200:
        raise RuntimeError("terminal GET failed")
    envelope = terminal.json()
    if envelope["status"] != scenario.expected_terminal_status:
        raise RuntimeError("unexpected terminal status")
    stream = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
    terminal_event_count = stream.text.count("event: result")
    result = envelope["result"]
    action = result["recommended_action"] or result["candidate_action"] or {}
    if "route_recommendations" in action:
        routes = action["route_recommendations"]
        route_status = "recommended"
    elif "route_candidates" in action:
        routes = action["route_candidates"]
        route_status = "needs_review"
    else:
        routes = []
        route_status = "not_evaluated"

    decision_data: dict[str, Any] | None = None
    if scenario.operator_decision:
        decision = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={
                "operator_id": "demo-operator",
                "decision": scenario.operator_decision,
                "comment": "Comprehensive offline demo evidence.",
            },
        )
        if decision.status_code != 200:
            raise RuntimeError("operator decision failed")
        decision_data = decision.json()

    return CapabilityEvidence(
        name=scenario.name,
        kind="job",
        status=CapabilityStatus.PASS,
        mandatory=scenario.mandatory,
        expected=scenario.expected_terminal_status,
        observed=envelope["status"],
        terminal_status=envelope["status"],
        trace_id=result["audit_record"]["trace_id"],
        model_version=result["model_version"],
        data_version=result["data_version"],
        terminal_event_count=terminal_event_count,
        recommended_action=result["recommended_action"],
        candidate_action=result["candidate_action"],
        operator_decision=scenario.operator_decision,
        applied_by_system=(
            decision_data["operator_decision"]["applied_by_system"]
            if decision_data
            else False
        ),
        automatic_actuation=(
            decision_data["automatic_actuation"] if decision_data else False
        ),
        details={
            "http_202": accepted.status_code == 202,
            "safety_iterations": result["safety_iterations"],
            "provisional": True,
            "node_id": scenario.node_id,
            "event_type": scenario.event_type,
            "topology_version": getattr(orchestrator, "routing_graph_version", None),
            "route_count": len(routes),
            "route_status": route_status,
            "safety_reason": result["needs_review_reason"],
            "policy_version": _policy_version(),
            "citation_present": bool(result["citations"]),
        },
    )


def _run_invalid_scenario(scenario: object) -> object:
    from stwi.demo.evidence import CapabilityEvidence, CapabilityStatus

    client = _client_for(_orchestrator_for("safe"))
    response = client.post(
        "/api/v1/what-if-jobs",
        json=_request_body(ratio=1.1),
    )
    if response.status_code != scenario.expected_http_status:
        raise RuntimeError("invalid input was not rejected")
    return CapabilityEvidence(
        name=scenario.name,
        kind="validation",
        status=CapabilityStatus.PASS,
        expected=str(scenario.expected_http_status),
        observed=str(response.status_code),
        details={"job_created": False},
    )


def _run_tenant_denied(scenario: object) -> object:
    from stwi.demo.evidence import CapabilityEvidence, CapabilityStatus
    from stwi.t4_orchestrator.auth import (
        PrincipalRole,
        ServerPrincipal,
        StaticPrincipalResolver,
    )

    resolver = StaticPrincipalResolver(
        ServerPrincipal(
            tenant_id="trusted-tenant",
            operator_id="trusted-operator",
            roles=frozenset({PrincipalRole.OPERATOR}),
        )
    )
    client = _client_for(_orchestrator_for("safe"), resolver)
    response = client.post(
        "/api/v1/what-if-jobs",
        json=_request_body(tenant_id="untrusted-tenant"),
    )
    if response.status_code != scenario.expected_http_status:
        raise RuntimeError("cross-tenant request was not denied")
    return CapabilityEvidence(
        name=scenario.name,
        kind="authorization",
        status=CapabilityStatus.PASS,
        expected=str(scenario.expected_http_status),
        observed=str(response.status_code),
        details={"job_created": False, "code": "AUTH_TENANT_DENIED"},
    )


def _run_sse_reconnect(scenario: object) -> object:
    from stwi.demo.evidence import CapabilityEvidence, CapabilityStatus

    client = _client_for(_orchestrator_for("safe"))
    accepted = client.post("/api/v1/what-if-jobs", json=_request_body())
    job_id = accepted.json()["job_id"]
    initial = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
    resumed = client.get(
        f"/api/v1/what-if-jobs/{job_id}/events",
        headers={"Last-Event-ID": "1"},
    )
    passed = (
        initial.status_code == 200
        and resumed.status_code == scenario.expected_http_status
        and "event: result" in resumed.text
        and "id: 1\n" not in resumed.text
    )
    if not passed:
        raise RuntimeError("SSE resume contract failed")
    return CapabilityEvidence(
        name=scenario.name,
        kind="sse",
        status=CapabilityStatus.PASS,
        expected="resume_after_event_1",
        observed="terminal_event_resumed",
        terminal_event_count=resumed.text.count("event: result"),
        details={"last_event_id": 1},
    )


def _run_static_preview(scenario: object) -> object:
    from stwi.demo.evidence import CapabilityEvidence, CapabilityStatus

    mode_source = (
        ROOT
        / "src"
        / "stwi"
        / "t4_orchestrator"
        / "static"
        / "dashboard-mode.js"
    ).read_text(encoding="utf-8")
    controller_source = (
        ROOT
        / "src"
        / "stwi"
        / "t4_orchestrator"
        / "static"
        / "dashboard.js"
    ).read_text(encoding="utf-8")
    passed = (
        'mode: "static_preview"' in mode_source
        and 'state.context.mode === "static_preview"' in controller_source
        and "Static preview" in controller_source
    )
    if not passed:
        raise RuntimeError("static preview mutation guard missing")
    return CapabilityEvidence(
        name=scenario.name,
        kind="static",
        status=CapabilityStatus.PASS,
        expected="non_mutating_static_preview",
        observed="non_mutating_static_preview",
        details={"network_contacted": False},
    )


def _run_capability(scenario: object) -> object:
    if scenario.kind == "job":
        return _run_job_case(scenario)
    if scenario.kind == "validation":
        return _run_invalid_scenario(scenario)
    if scenario.kind == "authorization":
        return _run_tenant_denied(scenario)
    if scenario.kind == "sse":
        return _run_sse_reconnect(scenario)
    return _run_static_preview(scenario)


def run_offline_profile(output: Path) -> object:
    """Run all mandatory offline capabilities and atomically write evidence."""
    from stwi.demo.evidence import (
        CapabilityEvidence,
        CapabilityStatus,
        DemoEvidence,
        write_evidence_atomic,
    )
    from stwi.demo.scenarios import offline_scenarios

    capabilities = []
    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        for scenario in offline_scenarios():
            try:
                capabilities.append(_run_capability(scenario))
            except Exception as exc:
                capabilities.append(
                    CapabilityEvidence(
                        name=scenario.name,
                        kind=(scenario.kind if scenario.kind != "job" else "job"),
                        status=CapabilityStatus.FAIL,
                        mandatory=scenario.mandatory,
                        expected=(
                            scenario.expected_terminal_status
                            or str(scenario.expected_http_status)
                        ),
                        observed="capability_failed",
                        details={"error_type": type(exc).__name__},
                    )
                )
            finally:
                _close_demo_clients()
    finally:
        _close_demo_clients()
        logging.disable(previous_logging_disable)
    verdict = "pass" if all(
        item.status == CapabilityStatus.PASS
        for item in capabilities
        if item.mandatory
    ) else "fail"
    evidence = DemoEvidence(
        profile="offline",
        verdict=verdict,
        live_services_contacted=False,
        capabilities=capabilities,
    )
    write_evidence_atomic(output, evidence)
    return evidence


def run_smoke(output: Path) -> dict[str, Any]:
    """Backward-compatible dictionary facade for existing automation."""
    return run_offline_profile(output).model_dump(mode="json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("offline", "services"),
        default="offline",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args(argv)
    output = args.output or (
        ROOT
        / "data"
        / "derived"
        / "private"
        / "demo"
        / f"comprehensive_{args.profile}_evidence.json"
    )
    if args.profile == "services":
        from stwi.demo.service_lab import run_service_profile

        evidence = run_service_profile(output)
    else:
        evidence = run_offline_profile(output)
    print(
        json.dumps(
            {
                "output": str(output),
                "profile": evidence.profile,
                "verdict": evidence.verdict,
                "capability_count": len(evidence.capabilities),
            }
        )
    )
    return 0 if evidence.verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
