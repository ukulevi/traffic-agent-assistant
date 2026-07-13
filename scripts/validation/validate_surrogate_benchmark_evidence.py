"""Validate surrogate benchmark evidence against the project contract."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
BENCHMARK_PATH = ROOT / "data/derived/private/phase2_surrogate/v3/benchmark_report.json"
CONTRACT_PATH = ROOT / "project_contract.json"


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_contract_profile() -> dict[str, Any]:
    contract = _load_json(CONTRACT_PATH)
    return contract.get("runtime", {}).get("benchmark_profile", {})


def _map_recorded_profile(benchmark: dict[str, Any]) -> dict[str, Any]:
    return {
        "cpu_cores": benchmark.get("cpu_cores", benchmark.get("cpu_threads")),
        "ram_gb": benchmark.get("ram_gb"),
        "device": benchmark.get("device"),
        "gpu_vram_gb": benchmark.get("gpu_vram_gb"),
    }


def _validate(benchmark: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if benchmark.get("evidence_kind") != "measured":
        errors.append(
            "benchmark evidence_kind must be 'measured'; simulated evidence is "
            "not eligible for contract compliance"
        )

    if str(benchmark.get("status")).lower() != "pass":
        errors.append("benchmark status is not 'pass'")

    if benchmark.get("p99_ms") is None:
        errors.append("benchmark report is missing p99_ms")
    elif benchmark.get("p99_ms", 10**9) >= 500:
        errors.append("surrogate P99 is not below 500 ms")

    recorded = _map_recorded_profile(benchmark)
    required_recorded = ("cpu_cores", "ram_gb", "device", "gpu_vram_gb")
    missing_fields = [key for key in required_recorded if recorded.get(key) is None]
    if missing_fields:
        errors.append(
            "benchmark report is missing profile fields: " + ", ".join(missing_fields)
        )

    unmatched = [
        key
        for key in ("cpu_cores", "ram_gb")
        if recorded.get(key) is not None and recorded.get(key) != profile.get(key)
    ]
    if unmatched:
        missing = ", ".join(f"{key}={recorded.get(key)}" for key in unmatched)
        expected = ", ".join(f"{key}={profile[key]}" for key in unmatched)
        errors.append(
            "benchmark profile does not match contract: " + missing + "; expected: " + expected
        )

    device = str(recorded.get("device") or "").lower()
    if recorded.get("device") is not None and not any(
        marker in device for marker in ("cuda", "gpu", "nvidia")
    ):
        errors.append("benchmark device is not an NVIDIA GPU/CUDA device")

    gpu_vram_gb = recorded.get("gpu_vram_gb")
    if gpu_vram_gb is not None:
        if not isinstance(gpu_vram_gb, (int, float)):
            errors.append("benchmark gpu_vram_gb must be numeric")
        elif not (
            profile["gpu_vram_gb_min"]
            <= gpu_vram_gb
            <= profile["gpu_vram_gb_max"]
        ):
            errors.append(
                "benchmark gpu_vram_gb is outside the contract range: "
                f"recorded={gpu_vram_gb}; expected="
                f"{profile['gpu_vram_gb_min']}-{profile['gpu_vram_gb_max']}"
            )

    return errors


def check_benchmark_evidence() -> dict[str, Any]:
    if not BENCHMARK_PATH.exists():
        return {"status": "fail", "errors": [f"Missing benchmark artifact: {BENCHMARK_PATH}"]}
    if not CONTRACT_PATH.exists():
        return {"status": "fail", "errors": [f"Missing project contract: {CONTRACT_PATH}"]}

    benchmark = _load_json(BENCHMARK_PATH)
    profile = _load_contract_profile()
    if not profile:
        return {"status": "fail", "errors": ["contract is missing benchmark_profile"]}

    errors = _validate(benchmark, profile)
    if errors:
        return {"status": "fail", "errors": errors}

    return {
        "status": "pass",
        "p99_ms": benchmark.get("p99_ms"),
        "target_p99_ms": 500,
        "benchmark_profile": profile,
        "recorded_profile": _map_recorded_profile(benchmark),
    }


def main() -> int:
    result = check_benchmark_evidence()
    if result["status"] != "pass":
        raise SystemExit(
            "Surrogate benchmark evidence validation failed:\n- " + "\n- ".join(result["errors"])
        )

    print(
        json.dumps(
            {
                "status": "pass",
                "p99_ms": result.get("p99_ms"),
                "target_p99_ms": result.get("target_p99_ms"),
                "benchmark_profile": result.get("benchmark_profile"),
                "recorded_profile": result.get("recorded_profile"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
