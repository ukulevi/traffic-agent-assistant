"""Heterogeneous surrogate models and fail-closed inference policy."""

from __future__ import annotations

import torch
from torch import nn


class MLPSurrogate(nn.Module):
    def __init__(self, input_size: int, output_size: int) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 128), nn.ReLU(),
            nn.Linear(128, 128), nn.ReLU(),
            nn.Linear(128, output_size),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.network(values)


class CNN1DSurrogate(nn.Module):
    def __init__(self, input_size: int, output_size: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2), nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool1d(8),
        )
        self.head = nn.Sequential(
            nn.Flatten(), nn.Linear(32 * 8, 128), nn.ReLU(),
            nn.Linear(128, output_size),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(values[:, None, :]))


class TransformerSurrogate(nn.Module):
    def __init__(
        self, input_size: int, output_size: int, model_size: int = 32
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.projection = nn.Linear(1, model_size)
        self.position = nn.Parameter(torch.zeros(1, input_size, model_size))
        layer = nn.TransformerEncoderLayer(
            d_model=model_size,
            nhead=4,
            dim_feedforward=64,
            dropout=0.1,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=2)
        self.head = nn.Linear(model_size, output_size)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        tokens = self.projection(values[:, :, None]) + self.position
        return self.head(self.encoder(tokens).mean(dim=1))


def build_surrogate(
    name: str, input_size: int, output_size: int
) -> nn.Module:
    if name == "mlp":
        return MLPSurrogate(input_size, output_size)
    if name == "cnn1d":
        return CNN1DSurrogate(input_size, output_size)
    if name == "transformer":
        return TransformerSurrogate(input_size, output_size)
    raise ValueError(f"unknown surrogate model: {name}")
