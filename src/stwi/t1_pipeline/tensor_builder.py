"""Quality processing, train-only scaling, and STWI tensor windows."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from stwi.contracts.project import (
    feature_names,
    load_project_contract,
    scaled_feature_indices,
)


SANITY_BOUNDS = (
    (0, 500), (0, 160), (0, 1), (0, 50), (250, 5000),
    (0, 2000), (0, 1000), (0, 1500), (-20, 60), (0, 100),
    (0, 80), (-1.01, 1.01), (-1.01, 1.01), (-1.01, 1.01),
    (-1.01, 1.01), (0, 1),
)


@dataclass(frozen=True)
class QualityResult:
    values: np.ndarray
    observed_mask: np.ndarray
    missing_ratio: float
    outlier_count: int


@dataclass(frozen=True)
class StandardScaler:
    feature_indices: tuple[int, ...]
    mean: np.ndarray
    std: np.ndarray

    def transform(self, values: np.ndarray) -> np.ndarray:
        transformed = values.copy()
        transformed[..., self.feature_indices] = (
            transformed[..., self.feature_indices] - self.mean
        ) / self.std
        return transformed


@dataclass(frozen=True)
class TensorDataset:
    X: np.ndarray
    M: np.ndarray
    A: np.ndarray
    Y: np.ndarray
    window_start_indices: np.ndarray


def apply_quality_and_impute(
    raw_values: np.ndarray,
    raw_observed_mask: np.ndarray,
    adjacency: np.ndarray,
) -> QualityResult:
    if raw_values.shape != raw_observed_mask.shape:
        raise ValueError("value/mask shape mismatch")
    if raw_values.ndim != 3 or raw_values.shape[2] != len(feature_names()):
        raise ValueError("expected [steps,nodes,16]")
    values = raw_values.astype(np.float32, copy=True)
    observed = raw_observed_mask.astype(np.bool_, copy=True)
    outlier_count = 0
    for feature_index, (lower, upper) in enumerate(SANITY_BOUNDS):
        invalid = (
            ~np.isfinite(values[:, :, feature_index])
            | (values[:, :, feature_index] < lower)
            | (values[:, :, feature_index] > upper)
        )
        outlier_count += int(np.count_nonzero(
            invalid & np.isfinite(values[:, :, feature_index])
        ))
        observed[:, :, feature_index][invalid] = False
        values[:, :, feature_index][invalid] = np.nan

    steps, nodes, features = values.shape
    global_medians = np.nanmedian(values, axis=(0, 1))
    global_medians = np.where(np.isfinite(global_medians), global_medians, 0)
    for feature in range(features):
        for node in range(nodes):
            missing_steps = np.flatnonzero(~observed[:, node, feature])
            for step in missing_steps:
                replacement = np.nan
                for lag in range(1, 4):
                    if step - lag >= 0 and observed[step - lag, node, feature]:
                        replacement = values[step - lag, node, feature]
                        break
                if not np.isfinite(replacement):
                    neighbors = np.flatnonzero(adjacency[node] > 0)
                    neighbor_values = values[step, neighbors, feature]
                    if np.any(np.isfinite(neighbor_values)):
                        replacement = np.nanmedian(neighbor_values)
                if not np.isfinite(replacement):
                    population = values[step, :, feature]
                    if np.any(np.isfinite(population)):
                        replacement = np.nanmedian(population)
                if not np.isfinite(replacement):
                    replacement = global_medians[feature]
                values[step, node, feature] = replacement
    if not np.all(np.isfinite(values)):
        raise ValueError("imputation left non-finite values")
    return QualityResult(
        values=values,
        observed_mask=observed,
        missing_ratio=float(1 - observed.mean()),
        outlier_count=outlier_count,
    )


def fit_train_scaler(
    values: np.ndarray,
    observed_mask: np.ndarray,
    train_end_step: int,
) -> StandardScaler:
    indices = scaled_feature_indices()
    train_values = values[:train_end_step, :, indices].astype(np.float64)
    train_mask = observed_mask[:train_end_step, :, indices]
    masked = np.where(train_mask, train_values, np.nan)
    mean = np.nanmean(masked, axis=(0, 1)).astype(np.float32)
    std = np.nanstd(masked, axis=(0, 1)).astype(np.float32)
    std = np.where(std < 1e-6, 1.0, std)
    return StandardScaler(indices, mean, std)


def build_tensor_windows(
    values: np.ndarray,
    observed_mask: np.ndarray,
    adjacency: np.ndarray,
    target_values: np.ndarray | None = None,
) -> TensorDataset:
    contract = load_project_contract()["data_contract"]
    history = contract["history_steps"]
    forecast = contract["forecast_steps"]
    targets = tuple(feature_names().index(name) for name in contract["forecast_targets"])
    target_source = values if target_values is None else target_values
    if target_source.shape != values.shape:
        raise ValueError("target/value shape mismatch")
    window_count = values.shape[0] - history - forecast + 1
    if window_count < 1:
        raise ValueError("not enough timesteps for one window")
    X = np.empty(
        (window_count, history, values.shape[1], values.shape[2]),
        dtype=np.float32,
    )
    M = np.empty_like(X, dtype=np.bool_)
    Y = np.empty(
        (window_count, forecast, values.shape[1], len(targets)),
        dtype=np.float32,
    )
    starts = np.arange(window_count, dtype=np.int32)
    for window_start in range(window_count):
        history_end = window_start + history
        X[window_start] = values[window_start:history_end]
        M[window_start] = observed_mask[window_start:history_end]
        Y[window_start] = target_source[
            history_end:history_end + forecast, :, targets
        ]
    return TensorDataset(X, M, adjacency.astype(np.float32), Y, starts)


def chronological_split_indices(
    dataset: TensorDataset,
    total_steps: int,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> dict[str, np.ndarray]:
    contract = load_project_contract()["data_contract"]
    history = contract["history_steps"]
    forecast = contract["forecast_steps"]
    train_cutoff = int(total_steps * train_ratio)
    validation_cutoff = int(total_steps * (train_ratio + validation_ratio))
    starts = dataset.window_start_indices
    ends = starts + history + forecast
    return {
        "train": np.flatnonzero(ends <= train_cutoff),
        "val": np.flatnonzero(
            (starts >= train_cutoff) & (ends <= validation_cutoff)
        ),
        "test": np.flatnonzero(starts >= validation_cutoff),
    }
