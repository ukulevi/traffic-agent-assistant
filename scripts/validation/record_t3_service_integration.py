"""Record T3 service-backed integration evidence.

Runs the real-adapter integration suite (Qdrant + TimescaleDB via the Phase 3
harness) and writes a measured evidence report so that previously skipped
integration coverage becomes explicit, owned verification instead of silent
skips. The report records skip counts as ``not_verified`` items — a run with
skips is recorded honestly as ``partial``, never as a clean pass.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "data/derived/private/phase3_knowledge/service_integration_report.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test-path", type=Path,
        default=Path("tests/t3_knowledge/test_t3_integration.py"),
    )
    args = parser.parse_args()

    required_env = {
        "STWI_QDRANT_URL": os.environ.get("STWI_QDRANT_URL"),
        "STWI_QDRANT_API_KEY": "***set" if os.environ.get("STWI_QDRANT_API_KEY") else None,
        "STWI_TSDB_DSN": "***set" if os.environ.get("STWI_TSDB_DSN") else None,
    }
    missing = [key for key, value in required_env.items() if value is None]
    if missing:
        raise SystemExit(
            "Missing required environment variables: " + ", ".join(missing)
            + "\nStart the harness: docker compose --env-file <private-env> "
            "-f infra/harness/compose.phase3.yaml up -d"
        )

    command = [
        sys.executable, "-m", "pytest", str(args.test_path), "-q", "--no-header",
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True
    )
    tail = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""

    # Parse the pytest summary line: e.g. "9 passed in 30.90s" or
    # "7 passed, 2 skipped, 1 warning in 20.00s".
    passed = failed = errors = skipped = 0
    for token in tail.replace(" in ", " , ").split(","):
        parts = token.split()
        if len(parts) >= 2 and parts[0].isdigit():
            count, label = int(parts[0]), parts[1]
            if label.startswith("passed"):
                passed = count
            elif label.startswith("failed"):
                failed = count
            elif label.startswith("error"):
                errors = count
            elif label.startswith("skipped"):
                skipped = count

    total = passed + failed + errors + skipped
    status = (
        "pass" if completed.returncode == 0 and skipped == 0
        else "partial" if completed.returncode == 0
        else "fail"
    )
    not_verified = []
    if skipped:
        not_verified.append({
            "item": f"{skipped} integration test(s) skipped",
            "owner": "unassigned",
            "eta": "unset",
        })

    report = {
        "schema_version": "1.0",
        "evidence_kind": "measured",
        "gate": "T3_service_backed_integration",
        "status": status,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(command),
        "services": {
            "qdrant_url": required_env["STWI_QDRANT_URL"],
            "timescaledb_dsn_host_only": "redacted",
        },
        "results": {
            "tests_run": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "summary_line": tail,
        },
        "not_verified": not_verified,
        "notes": (
            "Run against infra/harness/compose.phase3.yaml services on loopback; "
            "credentials live only in a private env file and are never logged."
        ),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
