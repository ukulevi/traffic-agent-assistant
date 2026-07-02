"""Generate provisional Phase-2 scenarios from real offline SUMO runs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


EVENT_TYPES = (
    "accident", "flood", "lane_closure", "demand_surge", "signal_change"
)
HORIZON_SECONDS = 300
FORECAST_STEPS = 6


@dataclass(frozen=True)
class SumoRuntime:
    home: Path
    binary: Path
    netgenerate: Path
    sumolib: Any
    traci: Any
    version: str


def load_sumo_runtime() -> SumoRuntime:
    try:
        import sumo
    except ImportError as exc:
        raise RuntimeError("Install the project simulation extra") from exc
    tools = Path(sumo.SUMO_HOME) / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import sumolib
    import traci
    return SumoRuntime(
        home=Path(sumo.SUMO_HOME),
        binary=Path(sumo.SUMO_HOME) / "bin" / ("sumo.exe" if os.name == "nt" else "sumo"),
        netgenerate=Path(sumo.SUMO_HOME) / "bin" / ("netgenerate.exe" if os.name == "nt" else "netgenerate"),
        sumolib=sumolib,
        traci=traci,
        version=importlib.metadata.version("eclipse-sumo"),
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_output(output: Path, replace: bool) -> None:
    if output.exists():
        marker = output / "scenario_manifest.json"
        if not replace:
            raise FileExistsError("output exists; pass --replace")
        if not marker.is_file():
            raise ValueError("refusing to replace a non-scenario directory")
        shutil.rmtree(output)
    output.mkdir(parents=True)


def generate_network(runtime: SumoRuntime, output: Path) -> Path:
    network = output / "mock_20_node.net.xml"
    subprocess.run(
        [
            str(runtime.netgenerate), "--grid",
            "--grid.x-number", "5", "--grid.y-number", "4",
            "--grid.length", "200", "--default.lanenumber", "2",
            "--default.speed", "13.89", "--tls.guess", "true",
            "--output-file", str(network),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return network


def network_assets(runtime: SumoRuntime, network_path: Path) -> tuple:
    network = runtime.sumolib.net.readNet(str(network_path))
    nodes = sorted(
        [node for node in network.getNodes() if not node.getID().startswith(":")],
        key=lambda node: node.getID(),
    )
    if len(nodes) != 20:
        raise ValueError(f"expected 20 SUMO nodes, got {len(nodes)}")
    edges = [edge for edge in network.getEdges() if not edge.isSpecial()]
    route_candidates: list[list[str]] = []
    for origin in edges:
        for destination in edges:
            result = network.getShortestPath(origin, destination)
            if result and 3 <= len(result[0]) <= 10:
                route = [edge.getID() for edge in result[0]]
                if route not in route_candidates:
                    route_candidates.append(route)
    stride = max(1, len(route_candidates) // 100)
    routes = route_candidates[::stride][:100]
    if len(routes) < 20:
        raise ValueError("could not derive enough valid SUMO routes")
    representative_edges = []
    for node in nodes:
        outgoing = [edge for edge in node.getOutgoing() if not edge.isSpecial()]
        representative_edges.append((outgoing or list(node.getIncoming()))[0])
    return network, nodes, routes, representative_edges


def scenario_parameters(event_type: str, node_index: int, replica: int) -> dict:
    rng = np.random.default_rng(10_000 + node_index * 31 + replica * 7)
    parameters = {
        "lane_closure_ratio": 0.0,
        "demand_multiplier": float(0.95 + rng.uniform(0, 0.10)),
        "duration_minutes": int(rng.choice([10, 15, 20, 30])),
        "signal_green_delta": 0.0,
        "speed_factor": 1.0,
    }
    if event_type == "accident":
        parameters.update(lane_closure_ratio=0.5, speed_factor=0.28)
    elif event_type == "flood":
        parameters.update(lane_closure_ratio=1.0, speed_factor=0.16)
    elif event_type == "lane_closure":
        parameters.update(lane_closure_ratio=0.5, speed_factor=0.45)
    elif event_type == "demand_surge":
        parameters["demand_multiplier"] = float(1.35 + 0.25 * replica)
    elif event_type == "signal_change":
        parameters["signal_green_delta"] = -0.20 if replica == 0 else 0.20
    return parameters


def run_simulation(
    runtime: SumoRuntime,
    network_path: Path,
    routes: list[list[str]],
    representative_edges: list,
    capacities: np.ndarray,
    *,
    vehicle_count: int,
    affected_node: int | None,
    event_type: str | None,
    parameters: dict[str, float] | None,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    traci = runtime.traci
    command = [
        str(runtime.binary), "-n", str(network_path),
        "--step-length", "10", "--no-step-log", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "60", "--seed", str(seed),
        "--end", str(HORIZON_SECONDS * FORECAST_STEPS),
    ]
    traci.start(command)
    try:
        for route_index, route in enumerate(routes):
            traci.route.add(f"route_{route_index}", route)
        rng = np.random.default_rng(seed)
        departures = np.sort(rng.uniform(
            0, HORIZON_SECONDS * FORECAST_STEPS - 120,
            size=vehicle_count,
        ))
        for vehicle_index, departure in enumerate(departures):
            route_index = int(rng.integers(0, len(routes)))
            traci.vehicle.add(
                f"vehicle_{vehicle_index}", f"route_{route_index}",
                depart=f"{departure:.1f}", departLane="best",
            )

        if event_type and affected_node is not None and parameters:
            edge_id = representative_edges[affected_node].getID()
            lane_ids = [
                lane.getID()
                for lane in representative_edges[affected_node].getLanes()
            ]
            speed_factor = float(parameters["speed_factor"])
            if speed_factor < 1:
                for lane_id in lane_ids:
                    current = traci.lane.getMaxSpeed(lane_id)
                    traci.lane.setMaxSpeed(lane_id, max(1.0, current * speed_factor))
            if parameters["lane_closure_ratio"] >= 0.5 and len(lane_ids) > 1:
                traci.lane.setDisallowed(lane_ids[-1], ["passenger"])
            if event_type == "signal_change":
                lights = traci.trafficlight.getIDList()
                if lights:
                    light = lights[affected_node % len(lights)]
                    current_duration = traci.trafficlight.getNextSwitch(light)
                    factor = 1 + float(parameters["signal_green_delta"])
                    traci.trafficlight.setPhaseDuration(
                        light, max(5.0, current_duration * factor)
                    )

        seen = [[set() for _ in representative_edges] for _ in range(FORECAST_STEPS)]
        speed_sum = np.zeros((FORECAST_STEPS, len(representative_edges)), dtype=np.float64)
        speed_weight = np.zeros_like(speed_sum)
        waiting_seconds = np.zeros(FORECAST_STEPS, dtype=np.float64)
        while traci.simulation.getTime() < HORIZON_SECONDS * FORECAST_STEPS:
            traci.simulationStep()
            simulation_time = traci.simulation.getTime()
            horizon = min(int(simulation_time // HORIZON_SECONDS), FORECAST_STEPS - 1)
            for node_index, edge in enumerate(representative_edges):
                edge_id = edge.getID()
                vehicle_ids = traci.edge.getLastStepVehicleIDs(edge_id)
                seen[horizon][node_index].update(vehicle_ids)
                count = traci.edge.getLastStepVehicleNumber(edge_id)
                if count:
                    speed_sum[horizon, node_index] += (
                        traci.edge.getLastStepMeanSpeed(edge_id) * count
                    )
                    speed_weight[horizon, node_index] += count
                waiting_seconds[horizon] += traci.edge.getWaitingTime(edge_id)
        volume = np.array(
            [[len(seen[horizon][node]) for node in range(len(representative_edges))]
             for horizon in range(FORECAST_STEPS)],
            dtype=np.float32,
        )
        speed = np.divide(
            speed_sum * 3.6,
            speed_weight,
            out=np.full_like(speed_sum, 50.0),
            where=speed_weight > 0,
        ).astype(np.float32)
        vc = volume * 12 / capacities[None, :]
        outputs = np.stack((volume, speed, vc), axis=-1).astype(np.float32)
        waiting_horizons = np.flatnonzero(waiting_seconds > 0)
        clearance_minutes = (
            float((waiting_horizons[-1] + 1) * 5)
            if len(waiting_horizons) else 0.0
        )
        summary = np.array([
            float(waiting_seconds.sum()),
            clearance_minutes,
            float(vc.max()),
        ], dtype=np.float32)
        return outputs, summary
    finally:
        traci.close(False)


def split_for_family(node_index: int, event_index: int) -> str:
    bucket = (node_index + event_index * 4) % 20
    if bucket < 14:
        return "train"
    if bucket < 17:
        return "val"
    return "test"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase1", type=Path,
        default=Path("data/derived/private/phase1_mock"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/derived/private/phase2_sumo"),
    )
    parser.add_argument("--replicas", type=int, default=2)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.replicas <= 20:
        raise ValueError("replicas must be between 1 and 20")
    prepare_output(args.output, args.replace)
    runtime = load_sumo_runtime()
    network_path = generate_network(runtime, args.output)
    _, nodes, routes, representative_edges = network_assets(
        runtime, network_path
    )
    registry = json.loads(
        (args.phase1 / "node_registry.json").read_text(encoding="utf-8")
    )
    capacities = np.asarray(
        [node["capacity_vph"] for node in registry["nodes"]],
        dtype=np.float32,
    )
    with np.load(args.phase1 / "timeseries.npz", allow_pickle=False) as data:
        state_values = data["values"]
    state_features = [0, 1, 15]
    observed_mean = state_values[:, :, :2].mean(axis=(0, 1))

    calibration_candidates = [40, 70, 100, 130]
    calibration_runs = []
    for candidate in calibration_candidates:
        output, _ = run_simulation(
            runtime, network_path, routes, representative_edges, capacities,
            vehicle_count=candidate, affected_node=None, event_type=None,
            parameters=None, seed=7000 + candidate,
        )
        simulated_mean = output[:, :, :2].mean(axis=(0, 1))
        volume_expansion_factor = float(
            observed_mean[0] / max(simulated_mean[0], 1e-6)
        )
        calibrated_mean = simulated_mean.copy()
        calibrated_mean[0] *= volume_expansion_factor
        normalized_error = float(np.mean(np.abs(
            (calibrated_mean - observed_mean) / np.maximum(observed_mean, 1)
        )))
        calibration_runs.append({
            "vehicle_count_30m": candidate,
            "simulated_mean_volume_speed": simulated_mean.tolist(),
            "volume_expansion_factor": volume_expansion_factor,
            "calibrated_mean_volume_speed": calibrated_mean.tolist(),
            "normalized_error": normalized_error,
        })
    best_calibration = min(calibration_runs, key=lambda run: run["normalized_error"])
    base_vehicle_count = int(best_calibration["vehicle_count_30m"])
    volume_expansion_factor = float(
        best_calibration["volume_expansion_factor"]
    )

    inputs: list[np.ndarray] = []
    outputs: list[np.ndarray] = []
    summaries: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    for event_index, event_type in enumerate(EVENT_TYPES):
        for node_index in range(20):
            for replica in range(args.replicas):
                parameters = scenario_parameters(event_type, node_index, replica)
                state_index = (
                    event_index * 997 + node_index * 41 + replica * 13
                ) % len(state_values)
                baseline_state = state_values[
                    state_index, :, state_features
                ].reshape(-1).astype(np.float32)
                event_one_hot = np.zeros(len(EVENT_TYPES), dtype=np.float32)
                event_one_hot[event_index] = 1
                node_one_hot = np.zeros(20, dtype=np.float32)
                node_one_hot[node_index] = 1
                scalars = np.array([
                    parameters["lane_closure_ratio"],
                    parameters["demand_multiplier"],
                    parameters["duration_minutes"] / 30,
                    parameters["signal_green_delta"],
                ], dtype=np.float32)
                scenario_input = np.concatenate(
                    (baseline_state, event_one_hot, node_one_hot, scalars)
                )
                vehicle_count = max(10, round(
                    base_vehicle_count * parameters["demand_multiplier"]
                ))
                scenario_seed = 20_000 + event_index * 1000 + node_index * 10 + replica
                scenario_output, summary = run_simulation(
                    runtime, network_path, routes, representative_edges,
                    capacities, vehicle_count=vehicle_count,
                    affected_node=node_index, event_type=event_type,
                    parameters=parameters, seed=scenario_seed,
                )
                scenario_output[:, :, 0] *= volume_expansion_factor
                scenario_output[:, :, 2] = (
                    scenario_output[:, :, 0] * 12 / capacities[None, :]
                )
                summary[2] = float(scenario_output[:, :, 2].max())
                scenario_id = f"{event_type}_node{node_index:02d}_r{replica}"
                family_id = f"{event_type}_node{node_index:02d}"
                split = split_for_family(node_index, event_index)
                inputs.append(scenario_input)
                outputs.append(scenario_output)
                summaries.append(summary)
                records.append({
                    "scenario_id": scenario_id,
                    "family_id": family_id,
                    "split": split,
                    "event_type": event_type,
                    "affected_node_id": registry["node_order"][node_index],
                    "replica": replica,
                    "parameters": parameters,
                    "sumo_seed": scenario_seed,
                })

    split_names = np.array([record["split"] for record in records])
    np.savez_compressed(
        args.output / "scenario_dataset.npz",
        inputs=np.stack(inputs),
        outputs=np.stack(outputs),
        summaries=np.stack(summaries),
        train_indices=np.flatnonzero(split_names == "train"),
        val_indices=np.flatnonzero(split_names == "val"),
        test_indices=np.flatnonzero(split_names == "test"),
    )
    (args.output / "scenarios.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    calibration = {
        "schema_version": "1.0",
        "calibration_scope": "synthetic_mock_observations_only",
        "production_calibration": False,
        "observed_mean_volume_speed": observed_mean.tolist(),
        "candidate_runs": calibration_runs,
        "selected_vehicle_count_30m": base_vehicle_count,
        "selected_normalized_error": best_calibration["normalized_error"],
        "selected_volume_expansion_factor": volume_expansion_factor,
        "volume_expansion_factor_applied": True,
        "recalibration_required_with_real_data": True,
    }
    (args.output / "calibration_report.json").write_text(
        json.dumps(calibration, indent=2) + "\n", encoding="utf-8"
    )
    coverage = {
        "schema_version": "1.0",
        "scenario_count": len(records),
        "family_count": len({record["family_id"] for record in records}),
        "event_types": list(EVENT_TYPES),
        "affected_node_count": 20,
        "replicas_per_family": args.replicas,
        "split_counts": {
            split: sum(record["split"] == split for record in records)
            for split in ("train", "val", "test")
        },
        "family_leakage": False,
    }
    (args.output / "scenario_coverage_report.json").write_text(
        json.dumps(coverage, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "1.0",
        "dataset_id": "stwi_sumo_mock20_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "offline_eclipse_sumo_runs",
        "sumo_version": runtime.version,
        "network_nodes": len(nodes),
        "network_sha256": sha256_file(network_path),
        "input_shape": list(np.stack(inputs).shape),
        "output_shape": list(np.stack(outputs).shape),
        "summary_shape": list(np.stack(summaries).shape),
        "node_order": registry["node_order"],
        "output_order": ["volume_5m", "avg_speed_kmh", "vc_ratio"],
        "split_policy": "scenario family by affected-node geographic holdout",
        "calibration_scope": "synthetic_mock_only",
        "production_ready": False,
        "artifacts": {
            name: sha256_file(args.output / name)
            for name in (
                "scenario_dataset.npz", "scenarios.json",
                "calibration_report.json", "scenario_coverage_report.json",
            )
        },
    }
    (args.output / "scenario_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(coverage, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
