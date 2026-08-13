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
        self.map_js = (STATIC / "dashboard-map.js").read_text(encoding="utf-8")
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
        self.assertIn('href="vendor/leaflet/leaflet.css"', self.html)
        self.assertIn('src="vendor/leaflet/leaflet.js"', self.html)
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
            "missing-evidence",
            "extreme",
            "signal-change",
        ):
            self.assertIn(f'value="{profile}"', self.html)
        self.assertIn("const DEMO_PRESETS", self.js)
        self.assertNotIn("nodeId:", self.js)
        self.assertIn("node_19", self.html)

    def test_dashboard_exposes_bounded_operational_presets(self) -> None:
        expected_profiles = {
            "accident": "accident",
            "flood": "flood",
            "lane-closure": "lane_closure",
            "demand-surge": "demand_surge",
            "signal-change": "signal_change",
        }
        self.assertIn('<optgroup label="Safety cơ bản">', self.html)
        self.assertIn('<optgroup label="Tình huống vận hành">', self.html)
        for profile, event_type in expected_profiles.items():
            self.assertIn(f'value="{profile}"', self.html)
            profile_block = re.search(
                rf'(?:"{re.escape(profile)}"|{re.escape(profile)})\s*:\s*\{{(?P<body>.*?)\n\s*\}},',
                self.js,
                re.DOTALL,
            )
            self.assertIsNotNone(profile_block)
            self.assertIn(f'eventType: "{event_type}"', profile_block.group("body"))
            self.assertNotIn("nodeId", profile_block.group("body"))
            self.assertIn("synthetic", profile_block.group("body"))

    def test_node_selection_does_not_turn_incident_preset_into_custom(self) -> None:
        select_node = re.search(
            r"function selectNode\(nodeId\) \{(?P<body>.*?)\n  \}",
            self.js,
            re.DOTALL,
        )
        self.assertIsNotNone(select_node)
        self.assertNotIn("markCustomPreset", select_node.group("body"))

    def test_typed_incident_defaults_pass_native_form_validation(self) -> None:
        self.assertIn(
            'id="demand-multiplier" name="demand-multiplier" type="number" '
            'min="1.01" max="3" step="0.01" value="1.5"',
            self.html,
        )

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

    def test_dashboard_uses_five_region_workflow_order(self) -> None:
        self.assertLess(self.html.index('id="scenario-form"'), self.html.index('id="lifecycle-title"'))
        self.assertLess(self.html.index('id="lifecycle-title"'), self.html.index('id="result-conclusion"'))
        self.assertLess(self.html.index('id="result-conclusion"'), self.html.index('id="evidence-panel"'))
        self.assertLess(self.html.index('id="evidence-panel"'), self.html.index('id="decision-title"'))

    def test_dashboard_has_skip_links_and_node_list_aria(self) -> None:
        self.assertEqual(self.html.count('class="skip-link"'), 2)
        self.assertIn('href="#scenario-form"', self.html)
        self.assertIn('href="#result-conclusion"', self.html)
        self.assertIn('id="node-list" class="node-list"', self.html)
        self.assertNotIn('role="option"', self.html)
        self.assertNotIn('aria-selected="false"', self.html)
        self.assertIn('aria-pressed', self.view_js)
        self.assertIn('id="evidence-panel"', self.html)
        self.assertIn('class="workspace"', self.html)
        self.assertIn('grid-template-columns: 220px minmax(560px, 1fr)', self.css)
        self.assertNotIn('.scenario-panel { order:', self.css)
        self.assertNotIn('.lifecycle-panel { order:', self.css)
        self.assertNotIn('.result-panel { order:', self.css)
        self.assertNotIn('#evidence-panel { order:', self.css)
        self.assertNotIn('#uncertainty-panel { order:', self.css)
        self.assertNotIn('.decision-panel { order:', self.css)
        self.assertNotIn('.help-panel { order:', self.css)
        self.assertNotIn('.node-rail { order:', self.css)

    def test_dashboard_has_offline_synthetic_network_view(self) -> None:
        for element_id in (
            "network-analysis",
            "network-map",
            "network-fallback",
            "network-version",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('from "./dashboard-map.js"', self.js)
        self.assertIn('getNetworkContext', self.api_js)
        self.assertIn("L.CRS.Simple", self.map_js)
        self.assertNotIn("tileLayer(", self.map_js)
        self.assertNotIn("innerHTML", self.map_js)
        self.assertIn("synthetic-grid-20-v1", self.map_js)
        runtime_assets = re.findall(r'(?:src|href)="([^"]+)"', self.html)
        self.assertFalse(any(asset.startswith(("http://", "https://", "//")) for asset in runtime_assets))
        self.assertIn(".network-map", self.css)
        self.assertIn(".network-fallback", self.css)

    def test_dashboard_exposes_accessible_route_evidence_without_color_only_state(self) -> None:
        for element_id in (
            "route-evidence",
            "route-heading",
            "route-table",
            "route-rows",
            "route-empty",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('aria-label="Bảng bằng chứng hành lang"', self.html)
        self.assertIn('tabindex="0"', self.html)
        self.assertIn("Nét liền", self.html)
        self.assertIn("nét đứt", self.html)
        self.assertIn(".route-row-candidate", self.css)
        self.assertIn("border-left: 6px dashed", self.css)
        self.assertIn(".route-table-wrap:focus-visible", self.css)
        self.assertIn("@media (max-width: 590px)", self.css)
        self.assertNotIn("innerHTML", self.map_js)
        self.assertNotIn("innerHTML", self.view_js)


if __name__ == "__main__":
    unittest.main()
