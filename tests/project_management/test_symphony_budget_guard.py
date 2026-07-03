from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "project_management" / "symphony_budget_guard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("symphony_budget_guard", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SymphonyBudgetGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = load_module()

    def test_throttles_when_projected_batch_exceeds_stop_threshold(self) -> None:
        state = {
            "generated_at": "2026-07-03T01:46:12Z",
            "running": [
                {
                    "issue_identifier": "TRA-9",
                    "state": "In Progress",
                    "tokens": {"total_tokens": 500_000},
                    "started_at": "2026-07-03T01:36:12Z",
                    "turn_count": 1,
                    "last_message": "rate limits updated: primary 45% / 300m",
                }
            ],
            "codex_totals": {"total_tokens": 500_000, "seconds_running": 600},
        }

        report = self.guard.evaluate_budget(
            state,
            self.guard.Thresholds(batch_stop_tokens=1_000_000),
            check_diff=False,
        )

        self.assertEqual(report["action"], "throttle")
        self.assertGreaterEqual(report["projected_tokens"], 1_000_000)

    def test_stops_when_rate_limit_pressure_exceeds_stop_threshold(self) -> None:
        state = {
            "running": [
                {
                    "issue_identifier": "TRA-7",
                    "state": "In Progress",
                    "tokens": {"total_tokens": 100_000},
                    "last_message": "rate limits updated: primary 61% / 300m",
                }
            ],
            "codex_totals": {"total_tokens": 100_000, "seconds_running": 300},
        }

        report = self.guard.evaluate_budget(
            state,
            self.guard.Thresholds(),
            check_diff=False,
        )

        self.assertEqual(report["action"], "stop")
        self.assertEqual(report["rate_limit_used_pct"], 61.0)

    def test_watch_when_rate_limit_is_unknown_for_running_agent(self) -> None:
        state = {
            "running": [
                {
                    "issue_identifier": "TRA-10",
                    "state": "In Progress",
                    "tokens": {"total_tokens": 10_000},
                    "turn_count": 1,
                }
            ],
            "codex_totals": {"total_tokens": 10_000, "seconds_running": 300},
        }

        report = self.guard.evaluate_budget(
            state,
            self.guard.Thresholds(),
            check_diff=False,
        )

        self.assertEqual(report["action"], "watch")
        self.assertIsNone(report["rate_limit_used_pct"])

    def test_stops_when_issue_has_high_tokens_without_diff(self) -> None:
        state = {
            "running": [
                {
                    "issue_identifier": "TRA-5",
                    "state": "In Progress",
                    "tokens": {"total_tokens": 1_600_000},
                    "turn_count": 1,
                }
            ],
            "codex_totals": {"total_tokens": 1_600_000, "seconds_running": 900},
        }

        original = self.guard.git_has_diff
        self.guard.git_has_diff = lambda _path: False
        try:
            report = self.guard.evaluate_budget(
                state,
                self.guard.Thresholds(),
                check_diff=True,
            )
        finally:
            self.guard.git_has_diff = original

        self.assertEqual(report["action"], "stop")
        self.assertIn("without a diff", report["reasons"][0])


if __name__ == "__main__":
    unittest.main()
