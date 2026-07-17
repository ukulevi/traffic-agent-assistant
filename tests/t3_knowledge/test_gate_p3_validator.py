"""Tests that Gate P3 records executed verification rather than assertions."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from scripts.validation import gate_p3_validator


class TestGateP3Verification(unittest.TestCase):
    @mock.patch("scripts.validation.gate_p3_validator.subprocess.run")
    def test_records_pass_for_successful_test_module(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess([], 0)

        result = gate_p3_validator.run_unittest_module("tests.example")

        self.assertEqual(result, {
            "module": "tests.example",
            "status": "pass",
            "returncode": 0,
        })
        run_mock.assert_called_once()
        self.assertIn("PYTHONPATH", run_mock.call_args.kwargs["env"])

    @mock.patch("scripts.validation.gate_p3_validator.subprocess.run")
    def test_records_failure_for_failed_test_module(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess([], 1)

        result = gate_p3_validator.run_unittest_module("tests.example")

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["returncode"], 1)

    @mock.patch("scripts.validation.gate_p3_validator.subprocess.run")
    def test_records_not_verified_when_runner_is_unavailable(
        self,
        run_mock: mock.Mock,
    ) -> None:
        run_mock.side_effect = OSError("runner unavailable")

        result = gate_p3_validator.run_unittest_module("tests.example")

        self.assertEqual(result, {
            "module": "tests.example",
            "status": "not_verified",
        })


if __name__ == "__main__":
    unittest.main()
