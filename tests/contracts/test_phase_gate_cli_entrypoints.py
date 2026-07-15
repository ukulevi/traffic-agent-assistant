"""Regression tests for phase-gate command-line import paths."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PhaseGateCliEntrypointTest(unittest.TestCase):
    def _assert_help_succeeds(self, relative_script: str) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / relative_script), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_phase2_gate_help_runs_from_repository_root(self) -> None:
        self._assert_help_succeeds(
            "scripts/validation/validate_provisional_phase2_gate.py"
        )

    def test_phase3_gate_help_runs_from_repository_root(self) -> None:
        self._assert_help_succeeds("scripts/validation/gate_p3_validator.py")


if __name__ == "__main__":
    unittest.main()
