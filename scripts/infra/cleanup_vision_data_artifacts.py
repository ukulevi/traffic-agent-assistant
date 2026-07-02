"""Clean unused private vision data artifacts with an explicit allowlist."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TARGETS = [
    "data/derived/private/vision_smoke",
    "data/derived/private/vision_training/images",
    "data/derived/private/vision_training/labels",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_aug",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann_rebalanced_moto_r3",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann_smallmoto_area006_r2",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_moto_r2",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_moto_r2_bus_r2",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_yolor_hardcase160",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_vietnam_aug",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_vietnam_hardcase80",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_vietnam_motoonly",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_yolor_moto_aug",
]

KEEP_PATHS = {
    "data/derived/private/vision_training/roboflow_v001",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_aug",
    "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor",
    "data/derived/private/vision_training/mvp_round1_motorcycle_label_fix_candidates",
    "data/derived/private/vision_reviews",
    "data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6",
}


def path_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    if path.is_file():
        return 1, path.stat().st_size
    files = 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            files += 1
            total += child.stat().st_size
    return files, total


def ensure_safe_target(root: Path, target: Path) -> Path:
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    if resolved_target == resolved_root:
        raise ValueError("refusing to clean repository root")
    if resolved_root not in resolved_target.parents:
        raise ValueError(f"target is outside repository: {target}")
    relative = resolved_target.relative_to(resolved_root).as_posix()
    if relative in KEEP_PATHS:
        raise ValueError(f"target is marked keep: {relative}")
    if not relative.startswith("data/derived/private/"):
        raise ValueError(f"target is outside private derived data: {relative}")
    return resolved_target


def cleanup_targets(
    *,
    root: Path,
    targets: list[Path],
    mode: str,
    quarantine_root: Path,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "task": "cleanup_vision_data_artifacts",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "targets": [],
        "total_files": 0,
        "total_bytes": 0,
    }
    quarantine_root.mkdir(parents=True, exist_ok=True)
    for target in targets:
        safe_target = ensure_safe_target(root, root / target)
        exists = safe_target.exists()
        files, total = path_size(safe_target)
        entry = {
            "path": safe_target.relative_to(root.resolve()).as_posix(),
            "exists": exists,
            "files": files,
            "bytes": total,
            "action": "skipped_missing" if not exists else mode,
        }
        if exists and mode == "delete":
            if safe_target.is_dir():
                shutil.rmtree(safe_target)
            else:
                safe_target.unlink()
        elif exists and mode == "quarantine":
            destination = quarantine_root / safe_target.name
            suffix = 1
            while destination.exists():
                destination = quarantine_root / f"{safe_target.name}_{suffix}"
                suffix += 1
            shutil.move(str(safe_target), str(destination))
            entry["quarantine_path"] = destination.relative_to(root.resolve()).as_posix()
        manifest["targets"].append(entry)
        manifest["total_files"] += files
        manifest["total_bytes"] += total
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["dry-run", "quarantine", "delete"], default="dry-run")
    parser.add_argument("--target", action="append", default=None)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifests/vision_data_cleanup_manifest.json"),
    )
    parser.add_argument(
        "--quarantine-root",
        type=Path,
        default=Path("data/quarantine/vision_data_cleanup"),
    )
    args = parser.parse_args()
    root = Path.cwd()
    targets = [Path(value) for value in (args.target or DEFAULT_TARGETS)]
    manifest = cleanup_targets(
        root=root,
        targets=targets,
        mode=args.mode,
        quarantine_root=root / args.quarantine_root,
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "mode": args.mode,
        "targets": len(manifest["targets"]),
        "total_files": manifest["total_files"],
        "total_mb": round(manifest["total_bytes"] / 1024 / 1024, 2),
        "manifest": args.manifest.as_posix(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
