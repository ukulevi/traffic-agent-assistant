"""Run a persistence baseline against the Gate-P1 Phase-2 handoff."""

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

from stwi.contracts.project import feature_names  # noqa: E402
from stwi.t2_forecast.baselines import (  # noqa: E402
    fit_seasonal_average,
    fit_seasonal_ridge,
    persistence_forecast,
    regression_metrics,
    seasonal_average_forecast,
    seasonal_ridge_forecast,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    manifest = json.loads(
        (args.dataset / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("gate_p1", {}).get("status") != "pass":
        raise ValueError("Gate P1 must pass before Phase-2 evaluation")
    scaler = json.loads(
        (args.dataset / "scaler.json").read_text(encoding="utf-8")
    )
    scaled_indices = scaler["feature_indices"]
    target_indices = [feature_names().index("traffic_volume_5m"),
                      feature_names().index("avg_speed_kmh")]
    scaler_positions = [scaled_indices.index(index) for index in target_indices]
    target_mean = np.asarray(scaler["mean"], dtype=np.float32)[scaler_positions]
    target_std = np.asarray(scaler["std"], dtype=np.float32)[scaler_positions]

    with np.load(
        args.dataset / "tensor_dataset.npz", allow_pickle=False
    ) as tensors:
        X = tensors["X"]
        Y = tensors["Y"]
        split_indices = {
            "train": tensors["train_indices"],
            "val": tensors["val_indices"],
            "test": tensors["test_indices"],
        }
        window_starts = tensors["window_start_indices"]
    with np.load(
        args.dataset / "timeseries.npz", allow_pickle=False
    ) as time_series:
        timestamps = time_series["timestamps"]
    history_steps = X.shape[1]
    train_indices = split_indices["train"]
    seasonal_index = fit_seasonal_average(
        Y[train_indices],
        window_starts[train_indices],
        timestamps,
        history_steps,
    )
    seasonal_fallback = np.mean(Y[train_indices], axis=0)
    ridge_coefficients = fit_seasonal_ridge(
        X[train_indices], Y[train_indices]
    )
    report = {
        "schema_version": "1.0",
        "baselines": ["persistence", "historical_average", "seasonal_ridge"],
        "target_order": ["traffic_volume_5m", "avg_speed_kmh"],
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": manifest["dataset_id"],
        "results": {},
    }
    for split, indices in split_indices.items():
        last_scaled = X[indices, -1][:, :, target_indices]
        last_physical = last_scaled * target_std + target_mean
        prediction = persistence_forecast(last_physical, Y.shape[1])
        historical = seasonal_average_forecast(
            seasonal_index,
            seasonal_fallback,
            window_starts[indices],
            timestamps,
            history_steps,
        )
        ridge = seasonal_ridge_forecast(
            X[indices], ridge_coefficients, Y.shape[1], Y.shape[-1]
        )
        report["results"][split] = {
            "persistence": regression_metrics(prediction, Y[indices]),
            "historical_average": regression_metrics(historical, Y[indices]),
            "seasonal_ridge": regression_metrics(ridge, Y[indices]),
        }
    output = args.dataset / "phase2_baseline_report.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
