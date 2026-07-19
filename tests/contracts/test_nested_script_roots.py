"""Nested CLI entrypoints must resolve the repository source tree themselves."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class NestedScriptRootTest(unittest.TestCase):
    def test_phase_entrypoints_expose_help_without_pythonpath(self) -> None:
        scripts = (
            "scripts/data_prep/generate_phase1_mock_data.py",
            "scripts/data_prep/ingest_public_proxy_traffic.py",
            "scripts/training/train_gcn_lstm_smoke.py",
            "scripts/training/train_surrogate_ensemble.py",
            "scripts/validation/evaluate_phase2_baseline.py",
            "scripts/validation/validate_phase1_gate.py",
            "scripts/validation/validate_phase2_start.py",
            "scripts/validation/validate_phase4_start.py",
        )
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        for script in scripts:
            with self.subTest(script=script):
                completed = subprocess.run(
                    [sys.executable, script, "--help"],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=f"{script}: {completed.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
