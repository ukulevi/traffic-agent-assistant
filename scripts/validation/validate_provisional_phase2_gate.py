"""Validate provisional Gate P2 and produce the Phase-3 handoff report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402

BENCHMARK_PROFILE = {
    "cpu_cores": 8,
    "ram_gb": 32,
    "gpu_vram_gb_min": 12,
    "gpu_vram_gb_max": 16,
}


def _check_benchmark_profile(benchmark: dict) -> list[str]:
    errors: list[str] = []
    recorded = {
        "cpu_cores": benchmark.get("cpu_cores", benchmark.get("cpu_threads")),
        "ram_gb": benchmark.get("ram_gb"),
        "gpu_vram_gb_min": benchmark.get("gpu_vram_gb_min"),
        "gpu_vram_gb_max": benchmark.get("gpu_vram_gb_max"),
    }
    missing_fields = [key for key, target in BENCHMARK_PROFILE.items() if target is not None and recorded.get(key) is None]
    if missing_fields:
        errors.append(
            "benchmark report is missing profile fields: " + ", ".join(missing_fields)
        )

    unmatched = [
        key for key, target in BENCHMARK_PROFILE.items()
        if target is not None and recorded.get(key) is not None and recorded.get(key) != target
    ]
    if unmatched:
        recorded_text = ", ".join(f"{key}={recorded.get(key)}" for key in unmatched)
        expected_text = ", ".join(f"{key}={BENCHMARK_PROFILE[key]}" for key in unmatched)
        errors.append(
            "benchmark profile does not match contract: " + recorded_text + "; expected: " + expected_text
        )
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
    errors: list[str] = []
    if forecast.get("forecast_kpi_status") != "pass":
        errors.append("forecast did not improve over baselines by 20%")
    if sumo.get("status") != "provisional_pass":
        errors.append("SUMO scenario validation did not pass")
    if surrogate.get("status") != "provisional_trained":
        errors.append("surrogate ensemble was not trained")
    if set(surrogate.get("models", {})) != {"mlp", "cnn1d", "transformer"}:
        errors.append("heterogeneous surrogate set is incomplete")
    if uncertainty.get("validation_coverage", 0) < 0.89:
        errors.append("uncertainty coverage is below provisional target")
    if not uncertainty.get("thresholds_fixed_before_test"):
        errors.append("uncertainty/OOD thresholds were not fixed before test")
    if benchmark.get("status") != "pass" or benchmark.get("p99_ms", 9999) >= 500:
        errors.append("surrogate P99 benchmark failed")

    benchmark_profile_errors = _check_benchmark_profile(benchmark)
    if benchmark_profile_errors:
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
        "status": "provisional_pass_for_phase3",
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
            "scope": "synthetic_mock_only",
            "status": "provisional_pass",
        },
        "surrogate_gate": {
            "models": list(checkpoint["model_names"]),
            "uncertainty_validation_coverage": uncertainty[
                "validation_coverage"
            ],
            "p99_ms": benchmark["p99_ms"],
            "benchmark_profile_match": not benchmark_profile_errors,
            "checkpoint_load": "pass",
            "status": "provisional_pass",
        },
        "safety_gate": {
            "ood_probe": ood_decision.status,
            "high_uncertainty_probe": high_uncertainty_decision.status,
            "recommended_action_allowed": False,
            "status": "pass",
        },
        "phase3_handoff_allowed": True,
        "production_ready": False,
        "mandatory_rework": [
            "replace mock observations with real 5-minute aggregates",
            "recalibrate SUMO against field counts, speed, and signal plans",
            "retrain forecast and surrogate models",
            "rerun uncertainty calibration and standard-profile benchmark"
        ],
    }
    output = args.surrogate.parent / "provisional_gate_p2_report.json"
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
