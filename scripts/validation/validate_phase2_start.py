"""Validate the approved simulation-first demo Phase 2 boundary."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("data/derived/private/phase1_mock"),
    )
    parser.add_argument(
        "--training", type=Path,
        default=Path("data/derived/private/phase2_forecast/gcn_lstm_mock_v1"),
    )
    parser.add_argument(
        "--policy", type=Path,
        default=Path("data/manifests/phase2_temporary_data_policy.json"),
    )
    args = parser.parse_args()
    try:
        import torch
        from stwi.t2_forecast.gcn_lstm import GCNLSTM
        from stwi.t2_forecast.baselines import regression_metrics
    except ImportError as exc:
        raise RuntimeError("Install the project forecast extra") from exc

    manifest = json.loads(
        (args.dataset / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    baseline = json.loads(
        (args.dataset / "phase2_baseline_report.json").read_text(
            encoding="utf-8"
        )
    )
    training = json.loads(
        (args.training / "training_report.json").read_text(encoding="utf-8")
    )
    if manifest.get("gate_p1", {}).get("status") != "pass":
        raise ValueError("Gate P1 is not finalized")
    if policy["surrogate_policy"]["training_allowed"]:
        raise ValueError("surrogate policy must remain fail-closed")
    if set(baseline["baselines"]) != {
        "persistence", "historical_average", "seasonal_ridge"
    }:
        raise ValueError("required baseline set is incomplete")
    if training.get("status") != "smoke_pass":
        raise ValueError("GCN-LSTM training did not pass")

    checkpoint_path = args.training / training["checkpoint"]
    checkpoint = torch.load(
        checkpoint_path, map_location="cpu", weights_only=False
    )
    model = GCNLSTM(**checkpoint["model_config"])
    model.load_state_dict(checkpoint["model_state_dict"])
    with np.load(
        args.dataset / "tensor_dataset.npz", allow_pickle=False
    ) as tensors:
        sample_X = torch.from_numpy(tensors["X"][:2])
        sample_M = torch.from_numpy(tensors["M"][:2])
        adjacency = torch.from_numpy(tensors["A"])
        test_indices = tensors["test_indices"]
        test_X = tensors["X"][test_indices]
        test_M = tensors["M"][test_indices]
        test_Y = tensors["Y"][test_indices]
    model.eval()
    with torch.no_grad():
        sample_output = model(sample_X, sample_M, adjacency)
    if tuple(sample_output.shape) != (2, 6, 20, 2):
        raise ValueError("checkpoint output contract mismatch")
    if not torch.all(torch.isfinite(sample_output)):
        raise ValueError("checkpoint produced non-finite output")

    test_batches = []
    with torch.no_grad():
        for offset in range(0, len(test_X), 128):
            test_batches.append(model(
                torch.from_numpy(test_X[offset:offset + 128]),
                torch.from_numpy(test_M[offset:offset + 128]),
                adjacency,
            ).numpy())
    test_scaled = np.concatenate(test_batches)
    target_mean = np.asarray(checkpoint["target_mean"], dtype=np.float32)
    target_std = np.asarray(checkpoint["target_std"], dtype=np.float32)
    test_prediction = test_scaled * target_std + target_mean
    test_metrics = regression_metrics(test_prediction, test_Y)

    validation_baselines = baseline["results"]["val"]
    best_name, best_metrics = min(
        validation_baselines.items(), key=lambda item: item[1]["rmse"]
    )
    model_rmse = training["validation_metrics"]["rmse"]
    improvement = (best_metrics["rmse"] - model_rmse) / best_metrics["rmse"]
    best_test_name, best_test_metrics = min(
        baseline["results"]["test"].items(),
        key=lambda item: item[1]["rmse"],
    )
    test_improvement = (
        best_test_metrics["rmse"] - test_metrics["rmse"]
    ) / best_test_metrics["rmse"]
    forecast_kpi_pass = improvement >= 0.20 and test_improvement >= 0.20
    report = {
        "schema_version": "1.0",
        "status": "phase2_started_simulation_demo_only",
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": manifest["dataset_id"],
        "data_policy": policy["policy_id"],
        "gate_p1": "pass",
        "required_baselines": "pass",
        "gcn_lstm_checkpoint": "load_and_shape_pass",
        "output_shape": list(sample_output.shape),
        "best_validation_baseline": {
            "name": best_name,
            "rmse": best_metrics["rmse"],
        },
        "gcn_lstm_validation_rmse": model_rmse,
        "rmse_improvement_over_best_baseline": improvement,
        "best_test_baseline": {
            "name": best_test_name,
            "rmse": best_test_metrics["rmse"],
        },
        "gcn_lstm_test_metrics": test_metrics,
        "test_rmse_improvement_over_best_baseline": test_improvement,
        "forecast_kpi_status": (
            "pass" if forecast_kpi_pass else "needs_improvement"
        ),
        "production_ready": False,
        "surrogate_status": "blocked_until_calibrated_sumo_dataset",
        "demo_scope_approved": True,
        "real_data_replacement_required_for_demo": False,
        "real_data_replacement_required_for_production": True,
    }
    output = args.training.parent / "phase2_readiness_report.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
