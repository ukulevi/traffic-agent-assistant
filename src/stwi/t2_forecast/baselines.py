"""Leakage-safe forecast baselines used to verify the Phase-2 handoff."""

from __future__ import annotations

from datetime import datetime

import numpy as np


def persistence_forecast(
    last_observation: np.ndarray, forecast_steps: int
) -> np.ndarray:
    if last_observation.ndim != 3 or last_observation.shape[-1] != 2:
        raise ValueError("last_observation must have shape [B,N,2]")
    return np.repeat(last_observation[:, None, :, :], forecast_steps, axis=1)


def regression_metrics(
    prediction: np.ndarray, target: np.ndarray
) -> dict[str, object]:
    if prediction.shape != target.shape or prediction.ndim != 4:
        raise ValueError("prediction/target shape mismatch")
    error = prediction.astype(np.float64) - target.astype(np.float64)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "mae_by_target": np.mean(np.abs(error), axis=(0, 1, 2)).tolist(),
        "rmse_by_target": np.sqrt(np.mean(error ** 2, axis=(0, 1, 2))).tolist(),
        "mae_by_horizon": np.mean(np.abs(error), axis=(0, 2, 3)).tolist(),
    }


def fit_seasonal_average(
    target: np.ndarray,
    window_starts: np.ndarray,
    timestamps: np.ndarray,
    history_steps: int,
) -> dict[tuple[int, int], np.ndarray]:
    if target.shape[0] != len(window_starts):
        raise ValueError("target/window shape mismatch")
    buckets: dict[tuple[int, int], list[np.ndarray]] = {}
    for row, start in enumerate(window_starts):
        timestamp = datetime.fromisoformat(
            str(timestamps[int(start) + history_steps])
        )
        slot = (timestamp.hour * 60 + timestamp.minute) // 5
        buckets.setdefault((timestamp.weekday(), slot), []).append(target[row])
    return {
        key: np.mean(np.stack(values), axis=0).astype(np.float32)
        for key, values in buckets.items()
    }


def seasonal_average_forecast(
    seasonal_index: dict[tuple[int, int], np.ndarray],
    fallback: np.ndarray,
    window_starts: np.ndarray,
    timestamps: np.ndarray,
    history_steps: int,
) -> np.ndarray:
    predictions = []
    for start in window_starts:
        timestamp = datetime.fromisoformat(
            str(timestamps[int(start) + history_steps])
        )
        key = (
            timestamp.weekday(),
            (timestamp.hour * 60 + timestamp.minute) // 5,
        )
        predictions.append(seasonal_index.get(key, fallback))
    return np.stack(predictions).astype(np.float32)


def fit_seasonal_ridge(
    X: np.ndarray,
    Y: np.ndarray,
    alpha: float = 1.0,
) -> np.ndarray:
    if X.ndim != 4 or Y.ndim != 4 or X.shape[0] != Y.shape[0]:
        raise ValueError("invalid ridge training shapes")
    features = X[:, -1].reshape(-1, X.shape[-1]).astype(np.float64)
    response = Y.transpose(0, 2, 1, 3).reshape(
        -1, Y.shape[1] * Y.shape[-1]
    ).astype(np.float64)
    design = np.concatenate(
        [features, np.ones((features.shape[0], 1), dtype=np.float64)], axis=1
    )
    penalty = np.eye(design.shape[1], dtype=np.float64) * alpha
    penalty[-1, -1] = 0
    return np.linalg.solve(
        design.T @ design + penalty, design.T @ response
    ).astype(np.float32)


def seasonal_ridge_forecast(
    X: np.ndarray,
    coefficients: np.ndarray,
    forecast_steps: int,
    target_count: int,
) -> np.ndarray:
    features = X[:, -1].reshape(-1, X.shape[-1]).astype(np.float32)
    design = np.concatenate(
        [features, np.ones((features.shape[0], 1), dtype=np.float32)], axis=1
    )
    prediction = design @ coefficients
    return prediction.reshape(
        X.shape[0], X.shape[2], forecast_steps, target_count
    ).transpose(0, 2, 1, 3)
