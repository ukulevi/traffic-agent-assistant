"""Validate provisional Gate P2 and produce the Phase-3 handoff report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validation.validate_surrogate_benchmark_evidence import (  # noqa: E402
    _load_contract_profile,
    _validate,
)


def _check_benchmark_profile(benchmark: dict) -> list[str]:
    return _validate(benchmark, _load_contract_profile())


def _validate_demo_policy(policy: dict) -> list[str]:
    errors = []
    if policy.get("policy_id") != "phase2-simulation-first-demo-v1":
        errors.append("demo-only gate requires the approved simulation policy")
    if policy.get("demo_scope_approved") is not True:
        errors.append("demo scope is not approved")
    if policy.get("production_scope_deferred") is not True:
        errors.append("production scope must remain deferred")
    if policy.get("data_classification") != "synthetic_simulation_demo_only":
        errors.append("demo data classification is not simulation-only")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forecast", type=Path,
        default=Path("data/derived/private/phase2_forecast"),
    )
    parser.add_argument(
        "--sumo", type=Path,
        default=Path("data/derived/private/phase2_sumo"),
    )
    parser.add_argument(
        "--surrogate", type=Path,
        default=Path("data/derived/private/phase2_surrogate/v3"),
    )
    parser.add_argument(
        "--policy", type=Path,
        default=Path("data/manifests/phase2_temporary_data_policy.json"),
    )
    parser.add_argument(
        "--demo-only", action="store_true",
        help="Allow an approved local demo profile without claiming standard-profile compliance.",
    )
    args = parser.parse_args()
    try:
        import torch
        from stwi.t2_forecast.safety import gate_surrogate_result
        from stwi.t2_forecast.surrogate import build_surrogate
    except ImportError as exc:
        raise RuntimeError("Install the project forecast extra") from exc

    forecast = json.loads(
        (args.forecast / "phase2_readiness_report.json").read_text(
            encoding="utf-8"
        )
    )
    sumo = json.loads(
        (args.sumo / "sumo_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    surrogate = json.loads(
        (args.surrogate / "surrogate_report.json").read_text(encoding="utf-8")
    )
    uncertainty = json.loads(
        (args.surrogate / "uncertainty_report.json").read_text(
            encoding="utf-8"
        )
    )
    benchmark = json.loads(
        (args.surrogate / "benchmark_report.json").read_text(encoding="utf-8")
    )
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    errors: list[str] = []
    if args.demo_only:
        errors.extend(_validate_demo_policy(policy))
    if forecast.get("forecast_kpi_status") != "pass":
        errors.append("forecast did not improve over baselines by 20%")
    if sumo.get("status") != "provisional_pass":
        errors.append("SUMO scenario validation did not pass")
    if surrogate.get("status") != "provisional_trained":
        errors.append("surrogate ensemble was not trained")
    if surrogate.get("data_policy") != policy.get("policy_id"):
        errors.append("surrogate data policy does not match the active policy")
    if surrogate.get("data_classification") != "synthetic_simulation_demo_only":
        errors.append("surrogate data classification is not simulation-only")
    if set(surrogate.get("models", {})) != {"mlp", "cnn1d", "transformer"}:
        errors.append("heterogeneous surrogate set is incomplete")
    if uncertainty.get("validation_coverage", 0) < 0.89:
        errors.append("uncertainty coverage is below provisional target")
    if not uncertainty.get("thresholds_fixed_before_test"):
        errors.append("uncertainty/OOD thresholds were not fixed before test")
    if benchmark.get("status") != "pass" or benchmark.get("p99_ms", 9999) >= 500:
        errors.append("surrogate P99 benchmark failed")

    benchmark_profile_errors = _check_benchmark_profile(benchmark)
    if benchmark_profile_errors and not args.demo_only:
        errors.extend(benchmark_profile_errors)

    for split, metrics in surrogate.get("splits", {}).items():
        numeric = [
            metrics["mae"], metrics["rmse"], metrics["max_vc_mae"],
            metrics["delay_rank_correlation"],
        ]
        if not np.all(np.isfinite(numeric)):
            errors.append(f"non-finite surrogate metric in {split}")

    checkpoint = torch.load(
        args.surrogate / "ensemble.pt", map_location="cpu", weights_only=False
    )
    models = {
        name: build_surrogate(
            name, checkpoint["input_size"], checkpoint["output_size"]
        )
        for name in checkpoint["model_names"]
    }
    for name, model in models.items():
        model.load_state_dict(checkpoint["model_states"][name])
        model.eval()
    with np.load(
        args.sumo / "scenario_dataset.npz", allow_pickle=False
    ) as dataset:
        base_input = dataset["inputs"][0].astype(np.float32)
    horizon_inputs = np.concatenate((
        np.repeat(base_input[None, :], 6, axis=0),
        np.eye(6, dtype=np.float32),
    ), axis=1)
    scaled = (
        horizon_inputs - checkpoint["input_mean"]
    ) / checkpoint["input_std"]
    with torch.no_grad():
        outputs = [model(torch.from_numpy(scaled)).numpy() for model in models.values()]
    if any(output.shape != (6, checkpoint["output_size"]) for output in outputs):
        errors.append("surrogate checkpoint output shape mismatch")
    if not all(np.all(np.isfinite(output)) for output in outputs):
        errors.append("surrogate checkpoint produced non-finite values")

    ood_input = horizon_inputs.copy()
    demand_multiplier_index = 60 + 5 + 20 + 1
    ood_input[:, demand_multiplier_index] = 10.0
    ood_scaled = (
        ood_input - checkpoint["input_mean"]
    ) / checkpoint["input_std"]
    ood_score = float(np.max(np.abs(ood_scaled)))
    ood_decision = gate_surrogate_result(
        uncertainty_score=0,
        uncertainty_threshold=checkpoint["uncertainty_threshold"],
        ood_score=ood_score,
        ood_threshold=checkpoint["ood_threshold"],
    )
    high_uncertainty_decision = gate_surrogate_result(
        uncertainty_score=checkpoint["uncertainty_threshold"] + 1,
        uncertainty_threshold=checkpoint["uncertainty_threshold"],
        ood_score=0,
        ood_threshold=checkpoint["ood_threshold"],
    )
    if (
        ood_decision.status != "needs_review"
        or high_uncertainty_decision.status != "needs_review"
        or ood_decision.recommended_action_allowed
        or high_uncertainty_decision.recommended_action_allowed
    ):
        errors.append("OOD/high-uncertainty policy is not fail-closed")
    if errors:
        raise ValueError("Provisional Gate P2 failed:\n- " + "\n- ".join(errors))

    report = {
        "schema_version": "1.0",
        "status": (
            "demo_pass_for_phase3"
            if args.demo_only else "provisional_pass_for_phase3"
        ),
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "forecast_gate": {
            "validation_improvement": forecast[
                "rmse_improvement_over_best_baseline"
            ],
            "test_improvement": forecast[
                "test_rmse_improvement_over_best_baseline"
            ],
            "status": "pass",
        },
        "sumo_gate": {
            "scenario_count": sumo["scenario_count"],
            "family_count": sumo["family_count"],
            "calibration_error": sumo["calibration_normalized_error"],
            "scope": "synthetic_simulation_demo_only",
            "status": "provisional_pass",
        },
        "surrogate_gate": {
            "models": list(checkpoint["model_names"]),
            "uncertainty_validation_coverage": uncertainty[
                "validation_coverage"
            ],
            "p99_ms": benchmark["p99_ms"],
            "benchmark_profile_match": not benchmark_profile_errors,
            "demo_profile_only": args.demo_only,
            "standard_profile_rework": (
                benchmark_profile_errors if args.demo_only else []
            ),
            "checkpoint_load": "pass",
            "status": (
                "demo_profile_pass"
                if args.demo_only else "provisional_pass"
            ),
        },
        "safety_gate": {
            "ood_probe": ood_decision.status,
            "high_uncertainty_probe": high_uncertainty_decision.status,
            "recommended_action_allowed": False,
            "status": "pass",
        },
        "phase3_handoff_allowed": True,
        "demo_scope_approved": args.demo_only,
        "standard_benchmark_gate_passed": not benchmark_profile_errors,
        "production_ready": False,
        "mandatory_rework": [
            "production only: replace synthetic observations with real 5-minute aggregates",
            "production only: recalibrate SUMO against field counts, speed, and signal plans",
            "production only: retrain forecast and surrogate models",
            "production only: rerun uncertainty calibration and standard-profile benchmark"
        ],
    }
    output = args.surrogate.parent / (
        "demo_gate_p2_report.json"
        if args.demo_only else "provisional_gate_p2_report.json"
    )
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
