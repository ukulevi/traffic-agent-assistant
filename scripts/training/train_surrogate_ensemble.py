"""Train, calibrate, and benchmark the provisional SUMO surrogate ensemble."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


MODEL_NAMES = ("mlp", "cnn1d", "transformer")


def prepare_output(output: Path, replace: bool) -> None:
    if output.exists():
        marker = output / "surrogate_report.json"
        if not replace:
            raise FileExistsError("output exists; pass --replace")
        if not marker.is_file():
            raise ValueError("refusing to replace a non-surrogate directory")
        shutil.rmtree(output)
    output.mkdir(parents=True)


def ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    result = np.empty_like(order, dtype=np.float64)
    result[order] = np.arange(len(values), dtype=np.float64)
    return result


def metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float]:
    error = prediction.astype(np.float64) - target.astype(np.float64)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
    }


def predict_in_batches(model, values, torch, batch_size: int = 64) -> np.ndarray:
    predictions = []
    model.eval()
    with torch.no_grad():
        for offset in range(0, len(values), batch_size):
            predictions.append(model(torch.from_numpy(
                values[offset:offset + batch_size]
            )).numpy())
    return np.concatenate(predictions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("data/derived/private/phase2_sumo"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/derived/private/phase2_surrogate/v1"),
    )
    parser.add_argument("--epochs", type=int, default=180)
    parser.add_argument("--seed", type=int, default=20250622)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    prepare_output(args.output, args.replace)
    try:
        import torch
        from torch.utils.data import DataLoader, TensorDataset
        from stwi.t2_forecast.surrogate import build_surrogate
    except ImportError as exc:
        raise RuntimeError("Install the project forecast extra") from exc

    manifest = json.loads(
        (args.dataset / "scenario_manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("validation", {}).get("status") != "provisional_pass":
        raise ValueError("SUMO scenario validation must pass first")
    if manifest.get("data_classification") != "synthetic_simulation_demo_only":
        raise ValueError("surrogate demo training requires simulation-only data")
    if manifest.get("production_ready") is not False:
        raise ValueError("synthetic SUMO data must not claim production readiness")
    with np.load(
        args.dataset / "scenario_dataset.npz", allow_pickle=False
    ) as dataset:
        scenario_inputs = dataset["inputs"].astype(np.float32)
        scenario_outputs = dataset["outputs"].astype(np.float32)
        summaries = dataset["summaries"].astype(np.float32)
        scenario_split_indices = {
            "train": dataset["train_indices"],
            "val": dataset["val_indices"],
            "test": dataset["test_indices"],
        }
    scenario_count, horizon_count, node_count, metric_count = (
        scenario_outputs.shape
    )
    horizon_one_hot = np.tile(
        np.eye(horizon_count, dtype=np.float32), (scenario_count, 1)
    )
    inputs = np.concatenate((
        np.repeat(scenario_inputs, horizon_count, axis=0),
        horizon_one_hot,
    ), axis=1)
    targets = np.concatenate((
        scenario_outputs.reshape(scenario_count * horizon_count, -1),
        np.repeat(summaries, horizon_count, axis=0),
    ), axis=1)
    split_indices = {
        split: np.concatenate([
            np.arange(index * horizon_count, (index + 1) * horizon_count)
            for index in indices
        ])
        for split, indices in scenario_split_indices.items()
    }
    train_indices = split_indices["train"]
    val_indices = split_indices["val"]
    test_indices = split_indices["test"]
    input_mean = inputs[train_indices].mean(axis=0)
    input_std = inputs[train_indices].std(axis=0)
    input_std = np.where(input_std < 1e-5, 1.0, input_std)
    target_mean = targets[train_indices].mean(axis=0)
    target_std = targets[train_indices].std(axis=0)
    target_std = np.where(target_std < 1e-5, 1.0, target_std)
    scaled_inputs = ((inputs - input_mean) / input_std).astype(np.float32)
    scaled_targets = ((targets - target_mean) / target_std).astype(np.float32)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    train_loader = DataLoader(
        TensorDataset(
            torch.from_numpy(scaled_inputs[train_indices]),
            torch.from_numpy(scaled_targets[train_indices]),
        ),
        batch_size=32,
        shuffle=True,
        num_workers=0,
    )
    model_predictions: dict[str, dict[str, np.ndarray]] = {}
    model_reports: dict[str, dict[str, Any]] = {}
    checkpoint_payload: dict[str, Any] = {}
    for model_offset, name in enumerate(MODEL_NAMES):
        torch.manual_seed(args.seed + model_offset)
        model = build_surrogate(name, inputs.shape[1], targets.shape[1])
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.002)
        loss_function = torch.nn.MSELoss()
        best_state = None
        best_validation = float("inf")
        patience = 35
        stale_epochs = 0
        epoch_losses = []
        for _ in range(args.epochs):
            model.train()
            running = 0.0
            batches = 0
            for batch_X, batch_Y in train_loader:
                optimizer.zero_grad()
                prediction = model(batch_X)
                loss = loss_function(prediction, batch_Y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                running += float(loss.detach())
                batches += 1
            epoch_losses.append(running / max(batches, 1))
            validation_scaled = predict_in_batches(
                model, scaled_inputs[val_indices], torch
            )
            validation_loss = float(np.mean(
                (validation_scaled - scaled_targets[val_indices]) ** 2
            ))
            if validation_loss < best_validation - 1e-5:
                best_validation = validation_loss
                best_state = {
                    key: value.detach().clone()
                    for key, value in model.state_dict().items()
                }
                stale_epochs = 0
            else:
                stale_epochs += 1
            if stale_epochs >= patience:
                break
        if best_state is None:
            raise RuntimeError(f"{name} did not produce a checkpoint")
        model.load_state_dict(best_state)
        split_predictions = {}
        for split, indices in split_indices.items():
            prediction_scaled = predict_in_batches(
                model, scaled_inputs[indices], torch
            )
            horizon_prediction = (
                prediction_scaled * target_std + target_mean
            ).astype(np.float32)
            scenario_rows = len(scenario_split_indices[split])
            structured = horizon_prediction.reshape(
                scenario_rows, horizon_count, -1
            )
            output_prediction = structured[:, :, :node_count * metric_count]
            summary_prediction = structured[:, :, node_count * metric_count:].mean(
                axis=1
            )
            split_predictions[split] = np.concatenate((
                output_prediction.reshape(scenario_rows, -1),
                summary_prediction,
            ), axis=1)
        model_predictions[name] = split_predictions
        model_reports[name] = {
            "epochs_ran": len(epoch_losses),
            "best_validation_scaled_mse": best_validation,
            "final_train_loss": epoch_losses[-1],
        }
        checkpoint_payload[name] = best_state

    validation_scaled_rmse = {
        name: float(np.sqrt(model_reports[name]["best_validation_scaled_mse"]))
        for name in MODEL_NAMES
    }
    inverse = np.array([
        1 / max(validation_scaled_rmse[name], 1e-6) for name in MODEL_NAMES
    ])
    weights = inverse / inverse.sum()

    ensemble_predictions = {}
    uncertainty_elements = {}
    for split in split_indices:
        stack = np.stack([
            model_predictions[name][split] for name in MODEL_NAMES
        ])
        ensemble_predictions[split] = np.tensordot(
            weights, stack, axes=(0, 0)
        ).astype(np.float32)
        uncertainty_elements[split] = np.std(stack, axis=0).astype(np.float32)

    scenario_targets = {
        split: np.concatenate((
            scenario_outputs[indices].reshape(len(indices), -1),
            summaries[indices],
        ), axis=1)
        for split, indices in scenario_split_indices.items()
    }
    validation_error = np.abs(
        ensemble_predictions["val"] - scenario_targets["val"]
    )
    validation_uncertainty = uncertainty_elements["val"]
    conformal_ratio = validation_error / np.maximum(
        validation_uncertainty, 1e-4
    )
    calibration_scale = float(np.quantile(conformal_ratio, 0.90))
    validation_width = calibration_scale * validation_uncertainty
    validation_coverage = float(np.mean(validation_error <= validation_width))
    sample_uncertainty = np.mean(validation_width, axis=1)
    uncertainty_threshold = float(np.quantile(sample_uncertainty, 0.95))

    train_distance = np.max(np.abs(scaled_inputs[train_indices]), axis=1)
    validation_distance = np.max(
        np.abs(scaled_inputs[val_indices]).reshape(-1, horizon_count, inputs.shape[1]),
        axis=(1, 2),
    )
    ood_threshold = float(max(
        np.quantile(train_distance, 0.995),
        np.quantile(validation_distance, 0.95),
    ))

    output_count = horizon_count * node_count * metric_count
    split_reports = {}
    for split, indices in scenario_split_indices.items():
        prediction = ensemble_predictions[split]
        truth = scenario_targets[split]
        output_prediction = prediction[:, :output_count].reshape(
            -1, 6, 20, 3
        )
        summary_prediction = prediction[:, output_count:]
        output_truth = scenario_outputs[indices]
        summary_truth = summaries[indices]
        max_vc_error = float(np.mean(np.abs(
            output_prediction[:, :, :, 2].max(axis=(1, 2))
            - output_truth[:, :, :, 2].max(axis=(1, 2))
        )))
        rank_correlation = float(np.corrcoef(
            ranks(summary_prediction[:, 0]), ranks(summary_truth[:, 0])
        )[0, 1]) if len(indices) > 1 else 1.0
        calibrated_width = calibration_scale * uncertainty_elements[split]
        uncertainty_score = np.mean(calibrated_width, axis=1)
        expanded_indices = split_indices[split]
        ood_score = np.max(
            np.abs(scaled_inputs[expanded_indices]).reshape(
                len(indices), horizon_count, inputs.shape[1]
            ),
            axis=(1, 2),
        )
        needs_review = (
            (uncertainty_score > uncertainty_threshold)
            | (ood_score > ood_threshold)
        )
        split_reports[split] = {
            **metrics(prediction, truth),
            "max_vc_mae": max_vc_error,
            "delay_rank_correlation": rank_correlation,
            "needs_review_ratio": float(np.mean(needs_review)),
            "ood_count": int(np.count_nonzero(ood_score > ood_threshold)),
            "high_uncertainty_count": int(np.count_nonzero(
                uncertainty_score > uncertainty_threshold
            )),
        }

    models = {
        name: build_surrogate(name, inputs.shape[1], targets.shape[1])
        for name in MODEL_NAMES
    }
    for name in MODEL_NAMES:
        models[name].load_state_dict(checkpoint_payload[name])
        models[name].eval()
    benchmark_input = torch.from_numpy(scaled_inputs[:horizon_count])
    for _ in range(20):
        with torch.no_grad():
            for model in models.values():
                model(benchmark_input)
    latencies_ms = []
    for _ in range(300):
        started = time.perf_counter_ns()
        with torch.no_grad():
            for model in models.values():
                model(benchmark_input)
        latencies_ms.append((time.perf_counter_ns() - started) / 1_000_000)
    benchmark = {
        "device": "cpu",
        "cpu_threads": torch.get_num_threads(),
        "payload_nodes": 20,
        "warmup_runs": 20,
        "measured_runs": 300,
        "p50_ms": float(np.percentile(latencies_ms, 50)),
        "p95_ms": float(np.percentile(latencies_ms, 95)),
        "p99_ms": float(np.percentile(latencies_ms, 99)),
        "surrogate_p99_target_ms": 500,
    }
    benchmark["status"] = (
        "pass" if benchmark["p99_ms"] < 500 else "fail"
    )

    checkpoint = {
        "model_states": checkpoint_payload,
        "model_names": MODEL_NAMES,
        "input_size": inputs.shape[1],
        "output_size": targets.shape[1],
        "horizon_conditioned": True,
        "horizon_count": horizon_count,
        "input_mean": input_mean,
        "input_std": input_std,
        "target_mean": target_mean,
        "target_std": target_std,
        "weights": weights,
        "calibration_scale": calibration_scale,
        "uncertainty_threshold": uncertainty_threshold,
        "ood_threshold": ood_threshold,
        "dataset_id": manifest["dataset_id"],
    }
    torch.save(checkpoint, args.output / "ensemble.pt")
    report = {
        "schema_version": "1.0",
        "status": "provisional_trained",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": manifest["dataset_id"],
        "data_policy": manifest["data_policy"],
        "data_classification": manifest["data_classification"],
        "production_representativeness": "not_claimed",
        "models": model_reports,
        "ensemble_weights": {
            name: float(weights[index])
            for index, name in enumerate(MODEL_NAMES)
        },
        "splits": split_reports,
        "production_ready": False,
    }
    uncertainty_report = {
        "schema_version": "1.0",
        "fit_split": "validation",
        "target_coverage": 0.90,
        "validation_coverage": validation_coverage,
        "calibration_scale": calibration_scale,
        "uncertainty_threshold": uncertainty_threshold,
        "ood_threshold": ood_threshold,
        "thresholds_fixed_before_test": True,
        "high_uncertainty_or_ood_status": "needs_review",
        "recommended_action_allowed": False,
    }
    for name, payload in (
        ("surrogate_report.json", report),
        ("uncertainty_report.json", uncertainty_report),
        ("benchmark_report.json", benchmark),
    ):
        (args.output / name).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "surrogate": report,
        "uncertainty": uncertainty_report,
        "benchmark": benchmark,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
