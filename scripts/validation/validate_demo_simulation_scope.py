"""Validate the approved simulation-first demo scope without production claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_PROHIBITED_CLAIMS = {
    "production forecast accuracy",
    "field-calibrated SUMO",
    "real sensor observations",
    "production-ready recommendations",
}


def validate_demo_scope(
    policy: dict[str, Any],
    handoff: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Return a machine-readable report or fail closed on scope drift."""
    errors: list[str] = []
    if policy.get("policy_id") != "phase2-simulation-first-demo-v1":
        errors.append("unexpected Phase-2 demo policy id")
    if policy.get("data_classification") != "synthetic_simulation_demo_only":
        errors.append("demo data classification is not synthetic simulation")
    if policy.get("demo_scope_approved") is not True:
        errors.append("demo scope is not approved")
    if policy.get("production_scope_deferred") is not True:
        errors.append("production scope must remain deferred")
    prohibited_inputs = {
        item.get("dataset_id")
        for item in policy.get("prohibited_forecast_inputs", [])
        if isinstance(item, dict)
    }
    if not {"rtsp_quarantine_frames", "detector_training_frames"}.issubset(
        prohibited_inputs
    ):
        errors.append("frame-derived forecast inputs are not explicitly prohibited")
    if not REQUIRED_PROHIBITED_CLAIMS.issubset(
        set(policy.get("prohibited_claims", []))
    ):
        errors.append("required production claims are not prohibited")
    if handoff.get("real_data_rework_required_for_demo") is not False:
        errors.append("real data must not block the approved demo scope")
    if handoff.get("real_data_rework_required_for_production") is not True:
        errors.append("real-data production requirement was lost")
    if handoff.get("fail_closed") is not True:
        errors.append("handoff is not fail closed")
    if handoff.get("human_approval_required") is not True:
        errors.append("handoff lost human approval")
    if contract.get("mvp_scope", {}).get("functional_network_nodes") != 20:
        errors.append("demo scope drifted from the 20-node contract")
    if contract.get("data_contract", {}).get("input_shape") != "X[B,12,N,16]":
        errors.append("demo scope drifted from the tensor contract")
    if contract.get("project", {}).get("automatic_actuation") is not False:
        errors.append("automatic actuation must remain disabled")
    if errors:
        raise ValueError("simulation-first demo scope failed:\n- " + "\n- ".join(errors))
    return {
        "status": "pass",
        "policy_id": policy["policy_id"],
        "data_classification": policy["data_classification"],
        "functional_network_nodes": 20,
        "tensor_contract": "X[B,12,N,16] -> Y[B,6,N,2]",
        "frame_derived_forecast_allowed": False,
        "production_ready": False,
        "human_approval_required": True,
        "automatic_actuation_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy", type=Path,
        default=Path("data/manifests/phase2_temporary_data_policy.json"),
    )
    parser.add_argument(
        "--handoff", type=Path,
        default=Path("data/manifests/phase3_temporary_handoff.json"),
    )
    parser.add_argument(
        "--contract", type=Path, default=Path("project_contract.json")
    )
    args = parser.parse_args()
    report = validate_demo_scope(
        json.loads(args.policy.read_text(encoding="utf-8")),
        json.loads(args.handoff.read_text(encoding="utf-8")),
        json.loads(args.contract.read_text(encoding="utf-8")),
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
