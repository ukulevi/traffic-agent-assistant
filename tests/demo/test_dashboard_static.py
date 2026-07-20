"""Static contract checks for the operator demo dashboard."""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "stwi" / "t4_orchestrator" / "static"


class _IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.ids.extend(value for key, value in attrs if key == "id" and value)


class TestDashboardStatic(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.js = (STATIC / "dashboard.js").read_text(encoding="utf-8")
        self.css = (STATIC / "dashboard.css").read_text(encoding="utf-8")

    def test_dashboard_assets_and_ids_are_consistent(self) -> None:
        parser = _IdParser()
        parser.feed(self.html)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        selectors = set(re.findall(r'querySelector\("#([^\"]+)"\)', self.js))
        self.assertTrue(selectors)
        self.assertTrue(selectors.issubset(set(parser.ids)))
        self.assertIn('href="dashboard.css"', self.html)
        self.assertIn('src="dashboard.js"', self.html)

    def test_dashboard_preserves_human_approval_boundary(self) -> None:
        self.assertIn("NON-EXECUTABLE", self.html)
        self.assertIn("human approval required", self.html.lower())
        self.assertIn("operator-decision", self.js)
        self.assertIn("recommended_action", self.js)
        self.assertIn("candidate_action", self.js)
        self.assertIn("không có hành động tự động", self.js)
        self.assertNotIn("innerHTML", self.js)
        self.assertNotIn("window.location", self.js)

    def test_dashboard_has_responsive_and_focus_states(self) -> None:
        self.assertIn("@media (max-width: 590px)", self.css)
        self.assertIn("button:focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn('aria-live="polite"', self.html)

    def test_dashboard_preserves_terminal_result_when_timeline_fails(self) -> None:
        self.assertIn("eventData?.status || eventData?.event || eventName", self.js)
        self.assertIn('addEvent("timeline_unavailable")', self.js)
        self.assertIn('status === "failed" || status === "expired"', self.js)
        self.assertIn("new Date().toISOString()", self.js)

    def test_dashboard_explains_operator_variables_and_units(self) -> None:
        self.assertIn('class="variable-guide"', self.html)
        for term in (
            "tenant_id",
            "node_id",
            "green_time_ratio",
            "scenario_query",
            "job_id / trace_id",
            "model / data",
            "V/C",
            "action payload",
        ):
            self.assertIn(term, self.html)
        self.assertIn('id="green-value" for="green-time"', self.html)
        self.assertIn("Math.round(ratio * 100)", self.js)
        self.assertIn("không phải quy định pháp luật", self.html)

    def test_dashboard_distinguishes_static_preview_from_api_runtime(self) -> None:
        self.assertIn('id="runtime-state"', self.html)
        self.assertIn('fetch("/openapi.json"', self.js)
        self.assertIn("UI preview · chưa có API", self.js)
        self.assertIn("runtimeAvailable === false", self.js)
        self.assertIn("createJobError(response)", self.js)

    def test_dashboard_explains_results_in_plain_vietnamese(self) -> None:
        for element_id in (
            "result-interpretation",
            "interpretation-title",
            "interpretation-summary",
            "interpretation-impact",
            "interpretation-next-step",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("function setInterpretation(result, status)", self.js)
        self.assertIn("function readableReviewReason(reason)", self.js)
        self.assertIn("dữ liệu mô phỏng", self.js)
        self.assertIn("xe/5 phút", self.js)
        self.assertIn("km/h", self.js)
        self.assertIn("Không có lệnh nào được gửi đến đèn tín hiệu", self.js)
        self.assertIn(".interpretation-review", self.css)

    def test_dashboard_exposes_reproducible_demo_presets(self) -> None:
        self.assertIn('id="demo-preset"', self.html)
        for profile in (
            "safe",
            "unsafe-vc",
            "ood",
            "uncertainty",
            "missing-evidence",
            "extreme",
        ):
            self.assertIn(f'value="{profile}"', self.html)
        self.assertIn("const DEMO_PRESETS", self.js)
        self.assertIn("node_00", self.js)
        self.assertIn("node_19", self.html)

    def test_dashboard_blocks_approval_for_non_succeeded_results(self) -> None:
        self.assertIn('status !== "succeeded"', self.js)
        self.assertIn("profile mô phỏng", self.js)

    def test_manual_input_clears_hidden_preset_state(self) -> None:
        self.assertIn("function markCustomPreset()", self.js)
        self.assertIn('scenarioQuery.addEventListener("input", markCustomPreset)', self.js)
        self.assertIn("activeJurisdiction = \"VN\"", self.js)


if __name__ == "__main__":
    unittest.main()
