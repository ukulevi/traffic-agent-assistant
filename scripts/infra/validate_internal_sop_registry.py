"""Validate project-owned SOP registry records without indexing them."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t3_knowledge.internal_sop import (  # noqa: E402
    InternalSopValidationError,
    validate_internal_sop_record,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path, default=Path("docs/ops/internal_sop_registry.json")
    )
    args = parser.parse_args()
    payload = json.loads(args.registry.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or not isinstance(payload.get("documents"), list):
        raise InternalSopValidationError("registry must use schema_version 1.0 with documents list")
    reports = [
        validate_internal_sop_record(record, repository_root=ROOT)
        for record in payload["documents"]
    ]
    print(json.dumps({"registry": str(args.registry), "documents": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
