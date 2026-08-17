from __future__ import annotations

import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from scripts.demo.run_mvp_smoke import run_offline_profile
from stwi.demo.evidence import CapabilityStatus, DemoEvidence
from stwi.demo.scenarios import offline_scenarios


class _DemoPresetParser(HTMLParser):
    """Collect actual dashboard preset values from the canonical select control."""

    def __init__(self) -> None:
        super().__init__()
        self._inside_demo_preset = False
        self.values: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "select" and attributes.get("id") == "demo-preset":
            self._inside_demo_preset = True
        elif tag == "option" and self._inside_demo_preset:
            value = attributes.get("value")
            if value:
                self.values.add(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._inside_demo_preset = False


class ComprehensiveOfflineDemoTest(unittest.TestCase):
    def test_mentor_runbook_matches_catalog_matrix_and_live_dashboard_presets(self) -> None:
        """Catch a runbook that drifts from the offline catalog or rendered controls."""
        repository = Path(__file__).resolve().parents[2]
        runbook = (repository / "docs/guides/mvp_demo_runbook.md").read_text(
            encoding="utf-8"
        )
        canonical_index = (
            repository / "src/stwi/t4_orchestrator/static/index.html"
        ).read_text(encoding="utf-8")

        expected_catalog = (
            "normal_baseline",
            "safe_rejection",
            "route_recommendation",
            "accident_any_node",
            "flood_any_node",
            "lane_closure_any_node",
            "demand_surge_any_node",
            "route_needs_review",
            "ood",
            "high_uncertainty",
            "missing_citation",
            "dependency_failure",
            "deadline_exceeded",
            "invalid_scenario",
            "tenant_scope_denied",
            "sse_reconnect",
            "static_preview",
        )
        catalog_names = tuple(scenario.name for scenario in offline_scenarios())
        self.assertEqual(catalog_names, expected_catalog)
        self.assertEqual(len(catalog_names), 17)
        self.assertEqual(len(set(catalog_names)), len(catalog_names))

        matrix_rows: list[tuple[str, str]] = []
        for line in runbook.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if (
                len(cells) == 4
                and cells[0] in {"Dashboard-live", "Evidence/harness-only"}
                and cells[1].startswith("`")
                and cells[1].endswith("`")
            ):
                matrix_rows.append((cells[0], cells[1][1:-1]))

        self.assertEqual(len(matrix_rows), 17)
        self.assertEqual(len({name for _, name in matrix_rows}), len(matrix_rows))
        self.assertEqual(tuple(name for _, name in matrix_rows), expected_catalog)
        expected_classifications = {
            "normal_baseline": "Dashboard-live",
            "safe_rejection": "Dashboard-live",
            "route_recommendation": "Dashboard-live",
            "accident_any_node": "Dashboard-live",
            "flood_any_node": "Dashboard-live",
            "lane_closure_any_node": "Dashboard-live",
            "demand_surge_any_node": "Dashboard-live",
            "route_needs_review": "Evidence/harness-only",
            "ood": "Evidence/harness-only",
            "high_uncertainty": "Evidence/harness-only",
            "missing_citation": "Dashboard-live",
            "dependency_failure": "Evidence/harness-only",
            "deadline_exceeded": "Evidence/harness-only",
            "invalid_scenario": "Evidence/harness-only",
            "tenant_scope_denied": "Evidence/harness-only",
            "sse_reconnect": "Evidence/harness-only",
            "static_preview": "Evidence/harness-only",
        }
        self.assertEqual(
            tuple(matrix_rows),
            tuple(
                (expected_classifications[capability], capability)
                for capability in expected_catalog
            ),
        )

        parser = _DemoPresetParser()
        parser.feed(canonical_index)
        required_live_presets = {
            "safe",
            "refinement",
            "unsafe-vc",
            "missing-evidence",
            "extreme",
            "accident",
            "flood",
            "lane-closure",
            "demand-surge",
            "signal-change",
        }
        self.assertTrue(required_live_presets.issubset(parser.values))
        for preset in required_live_presets:
            self.assertIn(f"`{preset}`", runbook)

    def test_mentor_runbook_has_five_timed_sections_with_all_presenter_cues(self) -> None:
        """Keep every timed demo segment usable without relying on improvisation."""
        runbook = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "guides"
            / "mvp_demo_runbook.md"
        ).read_text(encoding="utf-8")
        timed_section_headers = (
            "### 0:00–1:00",
            "### 1:00–3:00",
            "### 3:00–6:00",
            "### 6:00–8:00",
            "### 8:00–10:00",
        )
        cue_markers = (
            "**Thao tác:**",
            "**Nói:**",
            "**Chỉ trên màn hình:**",
            "**Kết quả mong đợi:**",
        )

        starts = [runbook.index(header) for header in timed_section_headers]
        self.assertEqual(starts, sorted(starts))
        for index, start in enumerate(starts):
            end = (
                starts[index + 1]
                if index + 1 < len(starts)
                else runbook.index("## 4. Ma trận 17 capability", start)
            )
            section = runbook[start:end]
            for cue in cue_markers:
                self.assertIn(cue, section, msg=f"{timed_section_headers[index]} lacks {cue}")

    def test_evidence_instructions_distinguish_cli_summary_from_json_artifact(self) -> None:
        """Prevent a misleading field lookup or divergent evidence filename."""
        repository = Path(__file__).resolve().parents[2]
        runbook = (repository / "docs/guides/mvp_demo_runbook.md").read_text(
            encoding="utf-8"
        )
        walkthrough = (
            repository / "docs/guides/mvp_dashboard_demo_walkthrough.md"
        ).read_text(encoding="utf-8")
        evidence_path = r"C:\tmp\stwi-offline-evidence.json"

        self.assertIn(evidence_path, runbook)
        self.assertIn(evidence_path, walkthrough)
        self.assertNotIn("stwi-mvp-demo-evidence.json", walkthrough)
        self.assertIn("CLI summary", runbook)
        self.assertIn("`capability_count: 17`", runbook)
        self.assertIn("`capabilities`", runbook)
        self.assertIn("17 entries", runbook)

    def test_mentor_runbook_separates_live_demo_from_harness_evidence(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        runbook = (repository / "docs/guides/mvp_demo_runbook.md").read_text(
            encoding="utf-8"
        )
        walkthrough = (
            repository / "docs/guides/mvp_dashboard_demo_walkthrough.md"
        ).read_text(encoding="utf-8")

        for marker in (
            "Kịch bản demo chính 8–10 phút",
            "**Thao tác:**",
            "**Nói:**",
            "**Chỉ trên màn hình:**",
            "**Kết quả mong đợi:**",
            "Dashboard-live",
            "Evidence/harness-only",
            "Câu hỏi mentor thường gặp",
            "Phương án dự phòng",
        ):
            self.assertIn(marker, runbook)

        for capability in (
            "normal_baseline",
            "route_recommendation",
            "route_needs_review",
            "ood",
            "high_uncertainty",
            "dependency_failure",
            "deadline_exceeded",
            "invalid_scenario",
            "tenant_scope_denied",
            "sse_reconnect",
            "static_preview",
        ):
            self.assertIn(f"`{capability}`", runbook)

        self.assertIn("không có preset `ood`", walkthrough)
        self.assertIn("không có preset `uncertainty`", walkthrough)
        self.assertNotIn("Chọn `ood` và chạy", walkthrough)
        self.assertNotIn("Chọn `uncertainty` và chạy", walkthrough)

    def test_demo_acceptance_matches_verified_release_evidence(self) -> None:
        acceptance = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "project_management"
            / "symphony"
            / "mvp_demo_acceptance.md"
        ).read_text(encoding="utf-8")

        self.assertIn("17 capabilities", acceptance)
        self.assertNotIn("13 capabilities", acceptance)
        self.assertIn("Browser acceptance: pass", acceptance)
        self.assertIn("PDF acceptance: pass", acceptance)

    def test_every_catalog_capability_passes_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "offline.json"
            evidence = run_offline_profile(output)
            persisted = DemoEvidence.model_validate_json(
                output.read_text(encoding="utf-8")
            )

        self.assertEqual(evidence, persisted)
        self.assertEqual(evidence.verdict, "pass")
        self.assertEqual(
            [item.name for item in evidence.capabilities],
            [item.name for item in offline_scenarios()],
        )
        self.assertTrue(
            all(item.status == CapabilityStatus.PASS for item in evidence.capabilities)
        )
        self.assertFalse(evidence.live_services_contacted)
        self.assertFalse(evidence.raw_video_retained)
        self.assertFalse(evidence.automatic_actuation)

    def test_action_semantics_cover_all_terminal_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            evidence = run_offline_profile(Path(temporary) / "offline.json")
        by_name = {item.name: item for item in evidence.capabilities}

        for name in ("normal_baseline", "safe_rejection", "route_recommendation"):
            self.assertIsNotNone(by_name[name].recommended_action)
            self.assertIsNone(by_name[name].candidate_action)
        for name in (
            "accident_any_node",
            "flood_any_node",
            "lane_closure_any_node",
            "demand_surge_any_node",
            "route_needs_review",
            "ood",
            "high_uncertainty",
            "missing_citation",
        ):
            self.assertIsNone(by_name[name].recommended_action)
            self.assertIsNotNone(by_name[name].candidate_action)
        for name in ("dependency_failure", "deadline_exceeded"):
            self.assertIsNone(by_name[name].recommended_action)
            self.assertIsNone(by_name[name].candidate_action)

        refinement = by_name["route_recommendation"]
        self.assertGreaterEqual(refinement.details["safety_iterations"], 2)
        self.assertGreater(
            refinement.recommended_action["green_time_ratio"],
            0.7,
        )

    def test_catalog_covers_independent_incidents_and_route_branches(self) -> None:
        cases = {item.name: item for item in offline_scenarios()}
        self.assertTrue(
            {
                "normal_baseline",
                "accident_any_node",
                "route_recommendation",
                "route_needs_review",
            }.issubset(cases)
        )
        canonical_incidents = [
            cases["accident_any_node"],
            cases["flood_any_node"],
            cases["lane_closure_any_node"],
            cases["demand_surge_any_node"],
            cases["route_recommendation"],
        ]
        self.assertEqual(
            {item.event_type for item in canonical_incidents},
            {"accident", "flood", "lane_closure", "demand_surge", "signal_change"},
        )
        self.assertEqual(
            len({item.node_id for item in canonical_incidents}),
            len(canonical_incidents),
        )

    def test_job_evidence_records_bounded_privacy_safe_route_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            evidence = run_offline_profile(Path(temporary) / "offline.json")
        by_name = {item.name: item for item in evidence.capabilities}

        route = by_name["route_recommendation"]
        self.assertEqual(route.details["route_status"], "recommended")
        self.assertEqual(route.details["route_count"], 3)
        self.assertEqual(route.details["topology_version"], "synthetic-routing-20-v1")
        self.assertIsNone(route.details["safety_reason"])

        held = by_name["route_needs_review"]
        self.assertEqual(held.details["route_status"], "needs_review")
        self.assertEqual(held.details["route_count"], 0)
        self.assertIn("no_passing_route", held.details["safety_reason"])

        forbidden_keys = {
            "description",
            "scenario_query",
            "raw_image",
            "image_base64",
            "secret",
        }
        for item in evidence.capabilities:
            self.assertTrue(forbidden_keys.isdisjoint(item.details))
            if item.kind == "job":
                self.assertTrue(
                    {
                        "event_type",
                        "node_id",
                        "topology_version",
                        "route_count",
                        "route_status",
                        "safety_reason",
                        "policy_version",
                        "citation_present",
                    }.issubset(item.details)
                )

    def test_network_impact_showcase_video_contract(self) -> None:
        """Verify network impact showcase capture script contract & artifact properties."""
        repository = Path(__file__).resolve().parents[2]
        script_path = repository / "scripts/demo/capture_network_impact_showcase.ps1"
        self.assertTrue(script_path.exists(), "Capture script must exist")

        script_content = script_path.read_text(encoding="utf-8")
        self.assertIn("node_05", script_content)
        self.assertIn("node_14", script_content)
        self.assertIn("node_04", script_content)
        self.assertIn("tmp/demo-network-impact-showcase.mp4", script_content)
        self.assertIn("raw_video_input", script_content)
        self.assertIn("finally", script_content)


if __name__ == "__main__":
    unittest.main()
