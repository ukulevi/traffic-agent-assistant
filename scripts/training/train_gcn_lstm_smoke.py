"""Smoke-train GCN-LSTM on the approved temporary Phase-2 dataset."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stwi.contracts.project import feature_names, load_project_contract  # noqa: E402
from stwi.t2_forecast.baselines import regression_metrics  # noqa: E402


def prepare_output(output: Path, replace: bool) -> None:
    if output.exists():
        marker = output / "training_report.json"
        if not replace:
            raise FileExistsError("output exists; pass --replace to rebuild")
        if not marker.is_file():
            raise ValueError("refusing to replace a non-training directory")
        shutil.rmtree(output)
    output.mkdir(parents=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("data/derived/private/phase1_mock"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/derived/private/phase2_forecast/gcn_lstm_smoke"),
    )
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-train-windows", type=int, default=512)
    parser.add_argument("--max-val-windows", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20250621)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError("epochs and batch-size must be positive")
    prepare_output(args.output, args.replace)

    try:
        import torch
        from torch.utils.data import DataLoader, TensorDataset
        from stwi.t2_forecast.gcn_lstm import GCNLSTM
    except ImportError as exc:
        raise RuntimeError("Install the project forecast extra") from exc

    manifest = json.loads(
        (args.dataset / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("gate_p1", {}).get("status") != "pass":
        raise ValueError("Gate P1 must pass before GCN-LSTM training")
    with np.load(
        args.dataset / "tensor_dataset.npz", allow_pickle=False
    ) as tensors:
        X = tensors["X"]
        M = tensors["M"]
        A = tensors["A"]
        Y = tensors["Y"]
        train_indices = tensors["train_indices"]
        val_indices = tensors["val_indices"]
    train_indices = train_indices[:args.max_train_windows]
    val_indices = val_indices[:args.max_val_windows]
    target_mean = Y[train_indices].mean(axis=(0, 1, 2)).astype(np.float32)
    target_std = Y[train_indices].std(axis=(0, 1, 2)).astype(np.float32)
    target_std = np.where(target_std < 1e-6, 1.0, target_std)
    Y_scaled = (Y - target_mean) / target_std

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    train_data = TensorDataset(
        torch.from_numpy(X[train_indices]),
        torch.from_numpy(M[train_indices]),
        torch.from_numpy(Y_scaled[train_indices]),
    )
    loader = DataLoader(
        train_data,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )
    model = GCNLSTM(
        gcn_hidden=args.hidden_size,
        lstm_hidden=args.hidden_size,
    )
    adjacency = torch.from_numpy(A)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-4
    )
    loss_function = torch.nn.MSELoss()
    epoch_losses: list[float] = []
    model.train()
    for _ in range(args.epochs):
        total_loss = 0.0
        batch_count = 0
        for batch_X, batch_M, batch_Y in loader:
            optimizer.zero_grad()
            prediction = model(batch_X, batch_M, adjacency)
            loss = loss_function(prediction, batch_Y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += float(loss.detach())
            batch_count += 1
        epoch_losses.append(total_loss / max(batch_count, 1))
        scheduler.step()

    model.eval()
    with torch.no_grad():
        validation_scaled = model(
            torch.from_numpy(X[val_indices]),
            torch.from_numpy(M[val_indices]),
            adjacency,
        ).numpy()
    validation_prediction = validation_scaled * target_std + target_mean
    validation_metrics = regression_metrics(
        validation_prediction, Y[val_indices]
    )
    contract = load_project_contract()
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "model_class": "GCNLSTM",
        "model_config": {
            "feature_count": 16,
            "gcn_hidden": args.hidden_size,
            "lstm_hidden": args.hidden_size,
            "lstm_layers": 2,
            "forecast_steps": 6,
            "target_count": 2,
        },
        "target_mean": target_mean,
        "target_std": target_std,
        "feature_order": feature_names(),
        "contract_version": contract["contract_version"],
        "dataset_id": manifest["dataset_id"],
    }
    checkpoint_path = args.output / "model.pt"
    torch.save(checkpoint, checkpoint_path)
    report = {
        "schema_version": "1.0",
        "status": "smoke_pass",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": manifest["dataset_id"],
        "data_policy": "phase2-mock-first-v1",
        "epochs": args.epochs,
        "train_windows": int(len(train_indices)),
        "validation_windows": int(len(val_indices)),
        "epoch_losses": epoch_losses,
        "validation_metrics": validation_metrics,
        "checkpoint": checkpoint_path.name,
        "production_ready": False,
        "surrogate_training_allowed": False,
    }
    (args.output / "training_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
