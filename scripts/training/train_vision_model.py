"""Train YOLOv8 only after the private STWI dataset passes strict checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.validation.validate_vision_dataset import validate_dataset
except ModuleNotFoundError:
    from validate_vision_dataset import validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path,
        default=Path("data/derived/private/vision_training"),
    )
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--amp", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted Ultralytics run from a last.pt checkpoint.",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--lr0", type=float, default=None)
    parser.add_argument("--lrf", type=float, default=None)
    parser.add_argument("--optimizer", default=None)
    parser.add_argument("--mosaic", type=float, default=None)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--translate", type=float, default=None)
    parser.add_argument("--erasing", type=float, default=None)
    parser.add_argument("--cos-lr", action="store_true")
    parser.add_argument("--close-mosaic", type=int, default=None)
    parser.add_argument("--allow-pending-review", action="store_true")
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/derived/private/vision_runs"),
    )
    parser.add_argument("--name", default="yolov8n_stwi")
    parser.add_argument("--model-version", default=None)
    args = parser.parse_args()
    if args.epochs < 1 or args.imgsz < 160 or args.batch < 1:
        raise ValueError("epochs, imgsz, and batch must be positive")

    dataset_counts = validate_dataset(
        args.dataset,
        require_privacy_review=not args.allow_pending_review,
    )
    ultralytics_config_dir = Path("data/derived/private/ultralytics").resolve()
    ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ultralytics_config_dir))
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("WINDIR", os.environ.get("SystemRoot", "C:\\Windows"))
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install the project vision extra before training") from exc

    model = YOLO(args.model)
    train_kwargs = {
        "data": str((args.dataset / "dataset.yaml").resolve()),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
        "project": str(args.output.resolve()),
        "name": args.name,
        "exist_ok": False,
        "cache": False,
        "amp": args.amp,
        "verbose": args.verbose,
        "cos_lr": args.cos_lr,
    }
    if args.resume:
        train_kwargs["resume"] = True
    if args.lr0 is not None:
        train_kwargs["lr0"] = args.lr0
    if args.lrf is not None:
        train_kwargs["lrf"] = args.lrf
    if args.optimizer is not None:
        train_kwargs["optimizer"] = args.optimizer
    if args.mosaic is not None:
        train_kwargs["mosaic"] = args.mosaic
    if args.scale is not None:
        train_kwargs["scale"] = args.scale
    if args.translate is not None:
        train_kwargs["translate"] = args.translate
    if args.erasing is not None:
        train_kwargs["erasing"] = args.erasing
    if args.close_mosaic is not None:
        train_kwargs["close_mosaic"] = args.close_mosaic
    result = model.train(**train_kwargs)
    run_dir = Path(result.save_dir)
    artifact = write_training_artifact(
        dataset_root=args.dataset,
        run_dir=run_dir,
        result_dict=result.results_dict,
        dataset_counts=dataset_counts,
        model_name=args.model,
        model_version=args.model_version or args.name,
        training_params={
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "workers": args.workers,
            "amp": args.amp,
            "resume": args.resume,
            "lr0": args.lr0,
            "lrf": args.lrf,
            "optimizer": args.optimizer,
            "mosaic": args.mosaic,
            "scale": args.scale,
            "translate": args.translate,
            "erasing": args.erasing,
            "cos_lr": args.cos_lr,
            "close_mosaic": args.close_mosaic,
        },
        official_candidate=not args.allow_pending_review,
    )
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_training_artifact(
    *,
    dataset_root: Path,
    run_dir: Path,
    result_dict: dict[str, Any],
    dataset_counts: dict[str, int],
    model_name: str,
    model_version: str,
    training_params: dict[str, Any],
    official_candidate: bool,
) -> dict[str, Any]:
    weights_path = run_dir / "weights" / "best.pt"
    manifest_path = dataset_root / "dataset_manifest.json"
    dataset_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = {
        "schema_version": "1.0",
        "model_version": model_version,
        "model_name": model_name,
        "task": "vehicle_object_detection",
        "run_dir": str(run_dir),
        "weights": str(weights_path),
        "weights_sha256": sha256_file(weights_path) if weights_path.is_file() else None,
        "dataset": str(dataset_root),
        "dataset_version": dataset_manifest.get("dataset_version"),
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "dataset_counts": dataset_counts,
        "classes": dataset_manifest.get("classes"),
        "stwi_class_map": dataset_manifest.get("stwi_class_map"),
        "privacy_status": dataset_manifest.get("privacy_status"),
        "metrics": result_dict,
        "training_params": training_params,
        "official_candidate": official_candidate,
        "promotion_status": (
            "candidate_ready_for_review"
            if official_candidate
            else "training_only_pending_privacy_review"
        ),
    }
    (run_dir / "stwi_model_artifact.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifact


if __name__ == "__main__":
    raise SystemExit(main())
