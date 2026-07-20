"""Static safety checks for the aggregate-only operator dashboard."""

from __future__ import annotations

import unittest
from pathlib import Path


STATIC_ROOT = Path(__file__).parents[2] / "src" / "stwi" / "t4_orchestrator" / "static"


class TestDashboardStatic(unittest.TestCase):
    def test_result_first_dashboard_exposes_required_audit_fields(self) -> None:
        markup = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        for required_id in (
            "forecast-volume",
            "forecast-speed",
            "capacity-version",
            "citations",
            "trace-id",
            "versions",
            "json-view",
        ):
            self.assertIn(f'id="{required_id}"', markup)
        self.assertIn("V/C = 0.9", markup)
        self.assertNotIn("video", markup.lower())

    def test_dashboard_preserves_fail_closed_action_mapping(self) -> None:
        script = (STATIC_ROOT / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn('serverStatus === "succeeded" && !complete ? "needs_review"', script)
        self.assertIn('displayStatus === "succeeded" ? result.recommended_action', script)
        self.assertIn('displayStatus === "needs_review" ? result.candidate_action', script)
        self.assertIn("candidate_action · non-executable", script)
        self.assertIn("automatic_actuation", script)

    def test_dashboard_streams_named_sse_events_until_terminal_result(self) -> None:
        script = (STATIC_ROOT / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("new EventSource(", script)
        self.assertIn('addEventListener("status", handleEvent)', script)
        self.assertIn('addEventListener("result", handleEvent)', script)
        self.assertIn("TERMINAL_STATUSES", script)


if __name__ == "__main__":
    unittest.main()
