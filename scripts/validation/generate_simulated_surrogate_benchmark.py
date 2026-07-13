"""Generate deterministic non-qualifying surrogate benchmark evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


DEFAULT_P99_MS = 100.0


def build_simulated_benchmark_report(p99_ms: float) -> dict[str, object]:
    """Return development-only evidence that cannot satisfy the contract gate."""
    if not math.isfinite(p99_ms) or p99_ms < 0:
        raise ValueError("p99_ms must be a finite non-negative number")
    return {
        "schema_version": "1.0",
        "evidence_kind": "simulated",
        "status": "simulated",
        "p99_ms": p99_ms,
        "device": "simulated",
        "measurement_note": (
            "Deterministic development fixture; not a measured hardware benchmark "
            "and not eligible for contract compliance."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write non-qualifying simulated surrogate benchmark evidence."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--p99-ms", type=float, default=DEFAULT_P99_MS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_simulated_benchmark_report(args.p99_ms)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
