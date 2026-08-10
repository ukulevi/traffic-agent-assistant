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
        self.api_js = (STATIC / "dashboard-api.js").read_text(encoding="utf-8")
        self.mode_js = (STATIC / "dashboard-mode.js").read_text(encoding="utf-8")
        self.state_js = (STATIC / "dashboard-state.js").read_text(encoding="utf-8")
        self.view_js = (STATIC / "dashboard-view.js").read_text(encoding="utf-8")
        self.css = (STATIC / "dashboard.css").read_text(encoding="utf-8")

    def test_dashboard_assets_and_ids_are_consistent(self) -> None:
        parser = _IdParser()
        parser.feed(self.html)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        selectors = set(re.findall(r'byId\("([^\"]+)"\)', self.view_js))
        self.assertTrue(selectors)
        self.assertTrue(selectors.issubset(set(parser.ids)))
        self.assertIn('href="dashboard.css"', self.html)
        self.assertIn('type="module" src="dashboard.js"', self.html)
        for module in (
            "dashboard-api.js",
            "dashboard-mode.js",
            "dashboard-state.js",
            "dashboard-view.js",
        ):
            self.assertIn(f'from "./{module}"', self.js)

    def test_dashboard_preserves_human_approval_boundary(self) -> None:
        self.assertIn("NON-EXECUTABLE", self.html)
        self.assertIn("human approval required", self.html.lower())
        self.assertIn("operator-decision", self.api_js)
        self.assertIn("recommended_action", self.view_js)
        self.assertIn("candidate_action", self.view_js)
        self.assertIn("automatic_actuation", self.state_js)
        self.assertIn("requires_operator_approval", self.state_js)
        for script in (self.js, self.api_js, self.mode_js, self.state_js, self.view_js):
            self.assertNotIn("innerHTML", script)
            self.assertNotIn("window.location", script)

    def test_dashboard_has_responsive_and_focus_states(self) -> None:
        self.assertIn("@media (max-width: 590px)", self.css)
        self.assertIn("button:focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('class="skip-link"', self.html)
        self.assertIn('input[type="range"] { min-height: 44px', self.css)
        self.assertNotIn(".text-button { position: absolute; top: 4px; right: 4px; min-height: 32px", self.css)

    def test_dashboard_preserves_job_status_when_transport_fails(self) -> None:
        self.assertIn('case "transport/offline"', self.state_js)
        self.assertIn('case "job/envelope"', self.state_js)
        self.assertIn("job: { ...state.job, events:", self.state_js)
        self.assertIn("state.job.status", self.view_js)
        self.assertIn("state.transport.phase", self.view_js)

    def test_dashboard_explains_operator_variables_and_units(self) -> None:
        self.assertIn('class="variable-guide', self.html)
        for term in (
            "tenant_id",
            "node_id",
            "green_time_ratio",
            "scenario_query",
            "job_id / trace_id",
            "model / data",
            "V/C",
            "Action payload",
        ):
            self.assertIn(term, self.html)
        self.assertIn('id="green-value" for="green-time"', self.html)
        self.assertIn("Math.round(Number(ratio) * 100)", self.view_js)
        self.assertIn("không phải quy định pháp luật", self.html)

    def test_dashboard_distinguishes_static_preview_from_api_runtime(self) -> None:
        self.assertIn('id="runtime-state"', self.html)
        self.assertIn('fetchImpl("/openapi.json"', self.mode_js)
        self.assertIn('mode: "static_preview"', self.mode_js)
        self.assertIn('context.mode === "static_preview"', self.js)
        self.assertIn('byId("submit-button").disabled', self.view_js)
        self.assertIn('byId("open-decision").disabled', self.view_js)

    def test_dashboard_explains_results_in_plain_vietnamese(self) -> None:
        for element_id in (
            "result-interpretation",
            "interpretation-title",
            "interpretation-summary",
            "interpretation-impact",
            "interpretation-next-step",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("function renderInterpretation(result, status)", self.view_js)
        self.assertIn("function readableReason(result, status)", self.view_js)
        self.assertIn("dữ liệu mô phỏng tổng hợp", self.view_js)
        self.assertIn("xe/5 phút", self.html)
        self.assertIn("km/h", self.html)
        self.assertIn("không phải quan sát hay điều khiển hiện trường", self.view_js)
        self.assertIn(".interpretation-review", self.css)

    def test_dashboard_exposes_reproducible_demo_presets(self) -> None:
        self.assertIn('id="demo-preset"', self.html)
        for profile in (
            "safe",
            "refinement",
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

    def test_dashboard_exposes_bounded_operational_presets(self) -> None:
        expected_profiles = {
            "accident": "node_05",
            "flood": "node_06",
            "lane-closure": "node_07",
            "demand-surge": "node_08",
            "environmental-anomaly": "node_09",
        }
        self.assertIn('<optgroup label="Safety cơ bản">', self.html)
        self.assertIn('<optgroup label="Tình huống vận hành">', self.html)
        for profile, node_id in expected_profiles.items():
            self.assertIn(f'value="{profile}"', self.html)
            profile_block = re.search(
                rf'(?:"{re.escape(profile)}"|{re.escape(profile)})\s*:\s*\{{(?P<body>.*?)\n\s*\}},',
                self.js,
                re.DOTALL,
            )
            self.assertIsNotNone(profile_block)
            self.assertIn(node_id, profile_block.group("body"))
            self.assertIn("synthetic", profile_block.group("body"))

    def test_environmental_preset_avoids_causal_claims(self) -> None:
        self.assertIn("tín hiệu tương quan", self.js)
        self.assertIn("không kết luận nguyên nhân", self.js)
        self.assertNotIn("ô nhiễm gây ùn tắc", self.js.lower())

    def test_dashboard_blocks_approval_for_non_succeeded_results(self) -> None:
        self.assertIn('state.job.status === "succeeded"', self.state_js)
        self.assertIn("isSafeAction", self.state_js)
        self.assertIn("profile mô phỏng", self.js)

    def test_manual_input_clears_hidden_preset_state(self) -> None:
        self.assertIn("function markCustomPreset()", self.js)
        self.assertIn("changeScenario", self.js)
        self.assertIn("handlers.changeScenario", self.view_js)
        self.assertIn('activeJurisdiction = "VN"', self.js)

    def test_decision_requires_confirmation_and_reconciliation(self) -> None:
        self.assertIn("openDecisionDialog", self.js)
        self.assertIn("recordDecision", self.js)
        self.assertIn("reconcileDecision", self.js)
        self.assertIn("applied_by_system", self.js)
        self.assertIn('id="decision-rationale" name="rationale" required', self.html)


if __name__ == "__main__":
    unittest.main()
