"""Validate readiness to start Phase 4 in provisional/mock-first mode.

This is not Gate P4.  It is a start gate: it verifies that Phase 1, the
provisional Phase 2 handoff, and Phase 3 are coherent enough for implementing
the orchestrator/API/dashboard without weakening STWI safety contracts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


REQUIRED_STATUSES = ["queued", "running", "succeeded", "needs_review", "failed", "expired"]
REQUIRED_TECH = {
    "workflow": "LangGraph",
    "job_worker": "Celery",
    "queue_and_progress": "Redis",
    "time_series_database": "TimescaleDB",
    "vector_database": "Qdrant",
    "embedding_model": "BGE-m3",
    "api": "FastAPI",
    "progress_transport": "SSE",
}

CONTRACT_ERROR_PREFIXES = (
    "project must remain",
    "automatic_actuation",
    "POST /api/v1/what-if-jobs",
    "API status enum",
    "successful action field",
    "review action field",
    "safety.fail_closed",
    "human approval",
    "Counterfactual Safety Loop",
    "technology.",
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_phase4_start(
    contract_path: Path,
    gate_p1_path: Path,
    gate_p2_path: Path,
    gate_p3_path: Path,
    pyproject_path: Path,
    t4_package: Path,
) -> dict[str, Any]:
    """Return a machine-readable Phase 4 start readiness report."""

    contract = read_json(contract_path)
    gate_p1 = read_json(gate_p1_path)
    gate_p2 = read_json(gate_p2_path)
    gate_p3 = read_json(gate_p3_path)
    pyproject_text = pyproject_path.read_text(encoding="utf-8")

    errors: list[str] = []
    warnings: list[str] = []

    if not contract.get("project", {}).get("decision_support_only"):
        errors.append("project must remain decision_support_only=true")
    if contract.get("project", {}).get("automatic_actuation") is not False:
        errors.append("automatic_actuation must remain false")
    if contract.get("api", {}).get("create_status") != 202:
        errors.append("POST /api/v1/what-if-jobs must return HTTP 202")
    if contract.get("api", {}).get("statuses") != REQUIRED_STATUSES:
        errors.append("API status enum drift")
    if contract.get("api", {}).get("successful_action_field") != "recommended_action":
        errors.append("successful action field drift")
    if contract.get("api", {}).get("review_action_field") != "candidate_action":
        errors.append("review action field drift")
    if not contract.get("safety", {}).get("fail_closed"):
        errors.append("safety.fail_closed must be true")
    if not contract.get("safety", {}).get("human_approval_required"):
        errors.append("human approval must remain required")
    if contract.get("safety", {}).get("max_iterations") != 3:
        errors.append("Counterfactual Safety Loop must keep max_iterations=3")

    for key, expected in REQUIRED_TECH.items():
        if contract.get("technology", {}).get(key) != expected:
            errors.append(f"technology.{key} must remain {expected}")

    if gate_p1.get("status") != "pass":
        errors.append("Gate P1 is not pass")
    if gate_p1.get("privacy") != "aggregate_only_no_video_or_frames":
        errors.append("Gate P1 privacy must be aggregate-only without video/frames")

    if gate_p2.get("status") != "provisional_pass_for_phase3":
        errors.append("Provisional Gate P2 is not pass")
    if gate_p2.get("production_ready") is not False:
        errors.append("Phase 2 must not claim production_ready")
    if gate_p2.get("safety_gate", {}).get("recommended_action_allowed") is not False:
        errors.append("P2 safety gate must not allow recommended_action")
    if gate_p2.get("surrogate_gate", {}).get("p99_ms", 999999) >= 500:
        errors.append("P2 surrogate P99 must remain under 500 ms")
    if not gate_p2.get("mandatory_rework"):
        errors.append("P2 mandatory real-data rework must be recorded")
    warnings.append("Phase 2 is provisional/mock-first; Phase 4 must preserve these warnings.")

    if gate_p3.get("status") != "pass":
        errors.append("Gate P3 is not pass")
    criteria = gate_p3.get("gate_criteria", {})
    for required in [
        "corpus_ok",
        "retrieval_questions_ok",
        "citation_precision_ok",
        "unsupported_claim_ok",
        "false_positive_ok",
        "no_raw_sql_path",
    ]:
        if criteria.get(required) is not True:
            errors.append(f"Gate P3 criterion failed: {required}")
    retrieval = gate_p3.get("retrieval", {})
    if retrieval.get("total_questions", 0) < 50:
        errors.append("Gate P3 retrieval suite must have at least 50 questions")
    if retrieval.get("citation_precision", 0.0) < 0.95:
        errors.append("Gate P3 citation precision below 95%")
    if retrieval.get("unsupported_claim_rate", 1.0) != 0.0:
        errors.append("Gate P3 unsupported_claim_rate must be 0")
    if retrieval.get("false_positive_rate", 1.0) != 0.0:
        errors.append("Gate P3 false_positive_rate must be 0")
    warnings.extend(gate_p3.get("known_limitations", []))

    if not t4_package.is_file():
        errors.append("Missing src/stwi/t4_orchestrator package boundary")

    for dep in ["fastapi", "celery", "redis", "langgraph"]:
        if dep not in pyproject_text.lower():
            warnings.append(f"Phase 4 dependency extra does not yet include {dep}")

    status = "ready_for_phase4_provisional" if not errors else "blocked"
    phase4_scope = {
        "allowed": [
            "LangGraph-style state machine scaffold with fake adapters",
            "FastAPI job contract implementation returning HTTP 202",
            "SSE progress event contract and reconnect/idempotency tests",
            "Counterfactual Safety Loop fail-closed policy tests",
            "operator approval/audit skeleton without actuator integration",
        ],
        "prohibited": [
            "claim production forecast/surrogate accuracy",
            "return recommended_action from needs_review",
            "execute candidate_action automatically",
            "connect to field devices or traffic signal controllers",
            "hide P2 provisional/mock-first limitations",
        ],
    }

    return {
        "schema_version": "1.0",
        "gate": "P4_START",
        "status": status,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "contract": str(contract_path),
            "gate_p1": str(gate_p1_path),
            "gate_p2": str(gate_p2_path),
            "gate_p3": str(gate_p3_path),
        },
        "criteria": {
            "contract_api_safety_stack_ok": not any(
                error.startswith(CONTRACT_ERROR_PREFIXES) for error in errors
            ),
            "gate_p1_ok": gate_p1.get("status") == "pass",
            "gate_p2_provisional_ok": (
                gate_p2.get("status") == "provisional_pass_for_phase3"
                and gate_p2.get("production_ready") is False
            ),
            "gate_p3_ok": gate_p3.get("status") == "pass",
            "phase4_package_boundary_ok": t4_package.is_file(),
        },
        "phase4_scope": phase4_scope,
        "errors": errors,
        "warnings": warnings,
        "production_ready": False,
        "real_data_rework_required": True,
        "human_approval_required": True,
        "automatic_actuation_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=Path("project_contract.json"))
    parser.add_argument(
        "--gate-p1",
        type=Path,
        default=Path("data/derived/private/phase1_mock/gate_p1_report.json"),
    )
    parser.add_argument(
        "--gate-p2",
        type=Path,
        default=Path("data/derived/private/phase2_surrogate/provisional_gate_p2_report.json"),
    )
    parser.add_argument(
        "--gate-p3",
        type=Path,
        default=Path("data/derived/private/phase3_knowledge/gate_p3_report.json"),
    )
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument(
        "--t4-package",
        type=Path,
        default=Path("src/stwi/t4_orchestrator/__init__.py"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/derived/private/phase4_orchestrator/phase4_prerequisite_readiness_report.json"),
    )
    args = parser.parse_args()

    report = validate_phase4_start(
        contract_path=args.contract,
        gate_p1_path=args.gate_p1,
        gate_p2_path=args.gate_p2,
        gate_p3_path=args.gate_p3,
        pyproject_path=args.pyproject,
        t4_package=args.t4_package,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
