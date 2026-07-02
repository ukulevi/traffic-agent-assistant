"""Contract-aligned GCN-LSTM baseline forecaster."""

from __future__ import annotations

import torch
from torch import nn


class GCNLSTM(nn.Module):
    def __init__(
        self,
        *,
        feature_count: int = 16,
        gcn_hidden: int = 64,
        lstm_hidden: int = 64,
        lstm_layers: int = 2,
        forecast_steps: int = 6,
        target_count: int = 2,
    ) -> None:
        super().__init__()
        self.feature_count = feature_count
        self.forecast_steps = forecast_steps
        self.target_count = target_count
        self.self_projection = nn.Linear(feature_count * 2, gcn_hidden)
        self.neighbor_projection = nn.Linear(feature_count * 2, gcn_hidden)
        self.temporal = nn.LSTM(
            input_size=gcn_hidden,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=0.1 if lstm_layers > 1 else 0.0,
        )
        self.head = nn.Linear(
            lstm_hidden, forecast_steps * target_count
        )

    @staticmethod
    def normalize_adjacency(adjacency: torch.Tensor) -> torch.Tensor:
        degree = adjacency.sum(dim=1).clamp_min(1e-6)
        inverse_sqrt = degree.rsqrt()
        return inverse_sqrt[:, None] * adjacency * inverse_sqrt[None, :]

    def forward(
        self,
        X: torch.Tensor,
        M: torch.Tensor,
        A: torch.Tensor,
    ) -> torch.Tensor:
        if X.ndim != 4 or X.shape[-1] != self.feature_count:
            raise ValueError("X must have shape [B,12,N,16]")
        if M.shape != X.shape or A.shape != (X.shape[2], X.shape[2]):
            raise ValueError("M/A contract mismatch")
        features = torch.cat((X, M.to(dtype=X.dtype)), dim=-1)
        normalized_adjacency = self.normalize_adjacency(A.to(dtype=X.dtype))
        propagated = torch.einsum(
            "ij,btjf->btif", normalized_adjacency, features
        )
        spatial = torch.relu(
            self.self_projection(features)
            + self.neighbor_projection(propagated)
        )
        batch, history, nodes, hidden = spatial.shape
        temporal_input = spatial.permute(0, 2, 1, 3).reshape(
            batch * nodes, history, hidden
        )
        temporal_output, _ = self.temporal(temporal_input)
        prediction = self.head(temporal_output[:, -1])
        return prediction.reshape(
            batch, nodes, self.forecast_steps, self.target_count
        ).permute(0, 2, 1, 3)
