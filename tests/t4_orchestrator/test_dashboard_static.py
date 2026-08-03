"""Static safety checks for the aggregate-only operator dashboard."""

from __future__ import annotations

import unittest
from pathlib import Path


STATIC_ROOT = Path(__file__).parents[2] / "src" / "stwi" / "t4_orchestrator" / "static"


class TestDashboardStatic(unittest.TestCase):
    def test_dashboard_uses_result_first_three_region_structure(self) -> None:
        markup = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="command-layout"', markup)
        self.assertIn('class="node-rail"', markup)
        self.assertIn('class="evidence-rail"', markup)
        self.assertLess(markup.index('id="result-conclusion"'), markup.index('id="lifecycle-title"'))
        self.assertLess(markup.index('id="lifecycle-title"'), markup.index('id="scenario-title"'))
        self.assertIn('id="decision-dialog"', markup)
        self.assertIn('type="module" src="dashboard.js"', markup)

    def test_dashboard_data_surfaces_are_solid_not_glass(self) -> None:
        stylesheet = (STATIC_ROOT / "dashboard.css").read_text(encoding="utf-8")
        self.assertIn("--stwi-shell: #072b38", stylesheet)
        self.assertIn("--stwi-surface: #ffffff", stylesheet)
        self.assertNotIn("backdrop-filter", stylesheet)
        self.assertNotIn("linear-gradient", stylesheet)
        self.assertNotIn("radial-gradient", stylesheet)

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
        state = (STATIC_ROOT / "dashboard-state.js").read_text(encoding="utf-8")
        view = (STATIC_ROOT / "dashboard-view.js").read_text(encoding="utf-8")
        self.assertIn('state.job.status === "succeeded"', state)
        self.assertIn("isSafeAction(state.job.result?.recommended_action)", state)
        self.assertIn('status === "succeeded"', view)
        self.assertIn("result?.recommended_action", view)
        self.assertIn('status === "needs_review"', view)
        self.assertIn("result?.candidate_action", view)
        self.assertIn("NON-EXECUTABLE", view)
        self.assertIn("automatic_actuation", state)

    def test_dashboard_streams_named_sse_events_until_terminal_result(self) -> None:
        api = (STATIC_ROOT / "dashboard-api.js").read_text(encoding="utf-8")
        coordinator = (STATIC_ROOT / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("new EventSourceImpl(", api)
        self.assertIn('addEventListener("status", handle)', api)
        self.assertIn('addEventListener("result", handle)', api)
        self.assertIn("TERMINAL_STATUSES", coordinator)


if __name__ == "__main__":
    unittest.main()
