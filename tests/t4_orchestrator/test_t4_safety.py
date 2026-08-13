"""Phase 4 safety tests — Counterfactual Safety Loop fail-closed behavior.

Verifies that ALL of the following fail closed (status=needs_review, no recommended_action):
- vc_ratio exceeds threshold (congestion risk)
- OOD input (out-of-distribution)
- High uncertainty
- Missing legal citations
- Compound failures (multiple gates fail)

Also verifies:
- Safety iterations bounded by MAX_ITERATIONS (max 3)
- Successful scenario returns recommended_action
- vc_threshold is configurable per-request
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime

from stwi.contracts.incident import IncidentVector
from stwi.t1_pipeline.network_topology import build_synthetic_topology
from stwi.t4_orchestrator.contracts import JobStatus, SafetyCheckResult
from stwi.t4_orchestrator.demo_adapters import DemoSurrogateForecaster, demo_node_ids
from stwi.t4_orchestrator.route_evaluation import RouteImpactEvaluator
from stwi.t4_orchestrator.fake_adapters import (
    FakeSurrogateForecaster,
    ScenarioForecastResult,
    SurrogateScenario,
    high_uncertainty_scenario,
    ood_scenario,
    safe_scenario,
    unsafe_vc_scenario,
)
from stwi.t4_orchestrator.safety_loop import (
    DEFAULT_OOD_THRESHOLD,
    DEFAULT_UNCERTAINTY_THRESHOLD,
    DEFAULT_VC_THRESHOLD,
    MAX_ITERATIONS,
    CounterfactualSafetyLoop,
)
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

SCENARIO_TIME = datetime(2025, 6, 1, 8, 0)
TENANT = "test-tenant"


def run_job(scenario: SurrogateScenario, query: str = "quyền nghĩa vụ người sử dụng đường", **req_overrides):
    from stwi.t4_orchestrator.contracts import WhatIfJobRequest
    surrogate = FakeSurrogateForecaster(default_scenario=scenario)
    orc = WhatIfOrchestrator(surrogate=surrogate)
    req = WhatIfJobRequest(
        tenant_id=TENANT,
        scenario_time=SCENARIO_TIME,
        candidate_action={"node_id": "node-A", "green_time_ratio": 0.7},
        node_ids=["node-A"],
        scenario_query=query,
        **req_overrides,
    )
    return orc.run(str(uuid.uuid4()), req)


class TestSafetyLoopUnit(unittest.TestCase):
    """Unit tests for CounterfactualSafetyLoop in isolation."""

    def _make_surrogate_and_results(self, scenario: SurrogateScenario):
        surrogate = FakeSurrogateForecaster(default_scenario=scenario)
        from datetime import datetime
        results = surrogate.predict(
            node_ids=["node-A"],
            horizons_minutes=[5],
            candidate_action={},
            scenario_time=datetime(2025, 6, 1),
            incident=None,
        )
        return surrogate, results

    def _run_loop(
        self,
        scenario: SurrogateScenario,
        *,
        has_citations: bool = True,
        candidate_action: dict[str, object] | None = None,
        vc_threshold: float = 0.9,
    ):
        surrogate, results = self._make_surrogate_and_results(scenario)
        loop = CounterfactualSafetyLoop(surrogate=surrogate, vc_threshold=vc_threshold)
        outcome = loop.run(
            node_ids=["node-A"],
            horizons_minutes=[5],
            candidate_action=candidate_action
            or {"node_id": "node-A", "green_time_ratio": 0.7},
            scenario_time=SCENARIO_TIME,
            incident=None,
            has_citations=has_citations,
            initial_results=results,
        )
        return surrogate, outcome

    def test_safe_scenario_passes(self):
        _, outcome = self._run_loop(safe_scenario())
        self.assertTrue(outcome.passed)
        self.assertIsNone(outcome.fail_reason)

    def test_vc_over_threshold_fails(self):
        scenario = unsafe_vc_scenario(vc_ratio=0.95)
        _, outcome = self._run_loop(scenario)
        self.assertFalse(outcome.passed)
        self.assertIn("vc_ratio", outcome.fail_reason)
        # Check gate detail
        self.assertFalse(outcome.checks[0].vc_ratio_ok)

    def test_vc_exactly_at_threshold_passes(self):
        """vc_ratio == threshold is allowed (<=, not <)."""
        scenario = SurrogateScenario(vc_ratio=0.9, uncertainty_score=0.1, ood_score=0.02)
        _, outcome = self._run_loop(scenario)
        self.assertTrue(outcome.passed)

    def test_missing_citations_fails(self):
        _, outcome = self._run_loop(safe_scenario(), has_citations=False)
        self.assertFalse(outcome.passed)
        self.assertIn("missing_legal_evidence", outcome.fail_reason)
        self.assertFalse(outcome.checks[0].citations_ok)
        self.assertEqual(outcome.iterations_run, 1)

    def test_ood_fails(self):
        _, outcome = self._run_loop(ood_scenario())
        self.assertFalse(outcome.passed)
        self.assertIn("ood_score", outcome.fail_reason)
        self.assertFalse(outcome.checks[0].ood_ok)
        self.assertEqual(outcome.iterations_run, 1)

    def test_high_uncertainty_fails(self):
        _, outcome = self._run_loop(high_uncertainty_scenario())
        self.assertFalse(outcome.passed)
        self.assertIn("uncertainty", outcome.fail_reason)
        self.assertFalse(outcome.checks[0].uncertainty_ok)
        self.assertEqual(outcome.iterations_run, 1)

    def test_max_iterations_bounded(self):
        """Safety loop must never exceed MAX_ITERATIONS."""
        _, outcome = self._run_loop(unsafe_vc_scenario())
        self.assertLessEqual(outcome.iterations_run, MAX_ITERATIONS)

    def test_non_converged_policy_runs_max_iterations(self):
        """A policy failure should produce a 3-iteration CSL audit trace."""
        _, outcome = self._run_loop(unsafe_vc_scenario())
        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.iterations_run, MAX_ITERATIONS)
        self.assertEqual(len(outcome.checks), MAX_ITERATIONS)
        self.assertEqual(
            [item.action["green_time_ratio"] for item in outcome.iterations],
            [0.7, 0.85, 1.0],
        )

    def test_non_converged_policy_returns_last_evaluated_candidate(self):
        """Never expose a refinement that has no surrogate evidence yet."""
        _, outcome = self._run_loop(
            unsafe_vc_scenario(),
            candidate_action={"node_id": "node-A", "green_time_ratio": 0.4},
        )
        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.iterations_run, MAX_ITERATIONS)
        self.assertEqual(
            [item.action["green_time_ratio"] for item in outcome.iterations],
            [0.4, 0.55, 0.7],
        )
        self.assertEqual(outcome.selected_action["green_time_ratio"], 0.7)

    def test_compound_failure_reports_all_reasons(self):
        """When multiple gates fail, all are reported in fail_reason."""
        compound = SurrogateScenario(vc_ratio=0.99, uncertainty_score=0.95, ood_score=0.9)
        _, outcome = self._run_loop(compound, has_citations=False)
        self.assertFalse(outcome.passed)
        # All four failures should appear
        reason = outcome.fail_reason
        self.assertIn("vc_ratio", reason)
        self.assertIn("missing_legal_evidence", reason)
        self.assertIn("uncertainty", reason)
        self.assertIn("ood_score", reason)
        self.assertEqual(outcome.iterations_run, 1)

    def test_vc_failure_repredicts_with_refined_action(self):
        class ResponsiveSurrogate(FakeSurrogateForecaster):
            def __init__(self):
                super().__init__()
                self.requested_ratios: list[float] = []

            def predict(
                self,
                node_ids,
                horizons_minutes,
                candidate_action,
                scenario_time,
                incident,
            ):
                self.assert_incident = incident
                ratio = float(candidate_action["green_time_ratio"])
                self.requested_ratios.append(ratio)
                vc_ratio = 0.95 if ratio < 0.25 else 0.82
                return [
                    ScenarioForecastResult(
                        node_id=node_ids[0],
                        horizon_minutes=horizons_minutes[0],
                        predicted_volume=120.0,
                        predicted_speed=35.0,
                        vc_ratio=vc_ratio,
                        uncertainty_score=0.1,
                        ood_score=0.05,
                    )
                ]

        surrogate = ResponsiveSurrogate()
        initial = surrogate.predict(
            ["node-A"],
            [5],
            {"node_id": "node-A", "green_time_ratio": 0.10},
            SCENARIO_TIME,
            None,
        )
        outcome = CounterfactualSafetyLoop(surrogate=surrogate).run(
            node_ids=["node-A"],
            horizons_minutes=[5],
            candidate_action={"node_id": "node-A", "green_time_ratio": 0.10},
            scenario_time=SCENARIO_TIME,
            incident=None,
            has_citations=True,
            initial_results=initial,
        )

        self.assertTrue(outcome.passed)
        self.assertEqual(surrogate.requested_ratios, [0.10, 0.25])
        self.assertEqual(outcome.selected_action["green_time_ratio"], 0.25)


class TestOrchestratorSafetyIntegration(unittest.TestCase):
    """End-to-end safety tests through the full orchestrator."""

    def test_safe_scenario_succeeds(self):
        result = run_job(safe_scenario())
        self.assertEqual(result.status, JobStatus.SUCCEEDED)
        self.assertIsNotNone(result.recommended_action)
        self.assertIsNone(result.candidate_action)

    def test_vc_failure_needs_review(self):
        result = run_job(unsafe_vc_scenario(0.95))
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIsNotNone(result.candidate_action)
        self.assertIsNotNone(result.needs_review_reason)

    def test_ood_needs_review(self):
        result = run_job(ood_scenario())
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIsNotNone(result.needs_review_reason)

    def test_high_uncertainty_needs_review(self):
        result = run_job(high_uncertainty_scenario())
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)

    def test_missing_evidence_needs_review(self):
        """Unrelated query produces no citations → needs_review."""
        result = run_job(safe_scenario(), query="xylophone orchestra symphony")
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIn("missing_legal_evidence", result.needs_review_reason or "")

    def test_custom_vc_threshold_configurable(self):
        """A lower vc_threshold should cause borderline scenario to fail."""
        borderline = SurrogateScenario(vc_ratio=0.80, uncertainty_score=0.05, ood_score=0.02)
        # With default threshold (0.9) → should pass
        result_pass = run_job(borderline)
        self.assertEqual(result_pass.status, JobStatus.SUCCEEDED)

        # With tight threshold (0.75) → should fail
        result_fail = run_job(borderline, vc_threshold=0.75)
        self.assertEqual(result_fail.status, JobStatus.NEEDS_REVIEW)

    def test_safety_iterations_in_result(self):
        result = run_job(safe_scenario())
        self.assertGreaterEqual(result.safety_iterations, 1)
        self.assertLessEqual(result.safety_iterations, MAX_ITERATIONS)

    def test_policy_failure_records_three_safety_iterations(self):
        result = run_job(unsafe_vc_scenario())
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertEqual(result.safety_iterations, MAX_ITERATIONS)

    def test_safety_iterations_in_audit(self):
        result = run_job(safe_scenario())
        self.assertGreaterEqual(result.audit_record.safety_iterations, 1)

    def test_succeeded_has_citations(self):
        """A succeeded job must have legal evidence."""
        result = run_job(safe_scenario())
        if result.status == JobStatus.SUCCEEDED:
            self.assertGreater(len(result.citations), 0)

    def test_needs_review_candidate_action_uses_last_refined_candidate(self):
        """candidate_action exposes the last evaluated hypothesis as non-executable."""
        result = run_job(unsafe_vc_scenario())
        if result.status == JobStatus.NEEDS_REVIEW:
            self.assertEqual(result.candidate_action["node_id"], "node-A")
            self.assertEqual(result.candidate_action["green_time_ratio"], 1.0)
            self.assertFalse(result.candidate_action["executable"])
            self.assertTrue(result.candidate_action["requires_operator_approval"])
            self.assertFalse(result.candidate_action["automatic_actuation"])

    def test_fail_closed_no_action_on_failed(self):
        """A failed job must expose NO action to operator."""
        class CrashSurrogate(FakeSurrogateForecaster):
            def predict(self, *args, **kwargs):
                raise RuntimeError("crash")
        orc = WhatIfOrchestrator(surrogate=CrashSurrogate())
        from stwi.t4_orchestrator.contracts import WhatIfJobRequest
        req = WhatIfJobRequest(
            tenant_id=TENANT, scenario_time=SCENARIO_TIME,
            candidate_action={"node_id": "node-A", "green_time_ratio": 0.7},
            node_ids=["node-A"], scenario_query="test",
        )
        result = orc.run(str(uuid.uuid4()), req)
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertIsNone(result.recommended_action)
        self.assertIsNone(result.candidate_action)

    def test_same_immutable_incident_reaches_initial_and_refined_predictions(self):
        class RecordingSurrogate(FakeSurrogateForecaster):
            def __init__(self) -> None:
                super().__init__()
                self.incidents: list[IncidentVector | None] = []

            def predict(
                self,
                node_ids,
                horizons_minutes,
                candidate_action,
                scenario_time,
                incident,
            ):
                self.incidents.append(incident)
                ratio = float(candidate_action["green_time_ratio"])
                scenario = unsafe_vc_scenario() if ratio < 0.85 else safe_scenario()
                original = self._default
                self._default = scenario
                try:
                    return super().predict(
                        node_ids,
                        horizons_minutes,
                        candidate_action,
                        scenario_time,
                        incident=None,
                    )
                finally:
                    self._default = original

        typed_incident = IncidentVector.model_validate(
            {
                "event_type": "accident",
                "affected_node_ids": ["node-A"],
                "severity": "medium",
                "duration_minutes": 30,
                "description": "Synthetic accident",
            }
        )
        from stwi.t4_orchestrator.contracts import WhatIfJobRequest

        request = WhatIfJobRequest(
            tenant_id=TENANT,
            scenario_time=SCENARIO_TIME,
            incident=typed_incident,
            candidate_action={"node_id": "node-A", "green_time_ratio": 0.7},
            node_ids=["node-A"],
            scenario_query="quyền nghĩa vụ người sử dụng đường",
        )
        surrogate = RecordingSurrogate()
        result = WhatIfOrchestrator(surrogate=surrogate).run("incident-refinement", request)

        self.assertEqual(result.status, JobStatus.SUCCEEDED)
        self.assertGreaterEqual(len(surrogate.incidents), 2)
        self.assertTrue(all(item is request.incident for item in surrogate.incidents))


class TestOrchestratorRouteIntegration(unittest.TestCase):
    def _request(self):
        from stwi.t4_orchestrator.contracts import WhatIfJobRequest

        return WhatIfJobRequest(
            tenant_id=TENANT,
            scenario_time=SCENARIO_TIME,
            incident={
                "event_type": "signal_change",
                "affected_node_ids": ["node_07"],
                "severity": "medium",
                "duration_minutes": 30,
                "description": "Synthetic signal hypothesis",
                "signal_plan_delta": {"green_time_ratio_delta": 0.15},
            },
            candidate_action={"node_id": "node_07", "green_time_ratio": 0.85},
            node_ids=list(demo_node_ids()),
            scenario_query="quyền nghĩa vụ người sử dụng đường",
        )

    def _orchestrator(self, **overrides):
        values = {
            "surrogate": DemoSurrogateForecaster(),
            "network_topology": build_synthetic_topology(),
        }
        values.update(overrides)
        return WhatIfOrchestrator(**values)

    def test_succeeded_incident_job_contains_ranked_non_executable_routes(self):
        result = self._orchestrator().run("route-success", self._request())

        self.assertEqual(result.status, JobStatus.SUCCEEDED)
        routes = result.recommended_action["route_recommendations"]
        self.assertEqual([item["rank"] for item in routes], [1, 2, 3])
        self.assertTrue(
            all(item["evaluation"]["evidence_complete"] for item in routes)
        )
        self.assertTrue(
            all("node_07" not in item["route"]["node_sequence"] for item in routes)
        )
        self.assertTrue(all(item["executable"] is False for item in routes))
        self.assertTrue(
            all(item["requires_operator_approval"] is True for item in routes)
        )
        self.assertTrue(all(item["applied_by_system"] is False for item in routes))

    def test_no_generated_route_needs_review_without_fabrication(self):
        class NoRoutesGenerator:
            def generate(self, *args, **kwargs):
                return ()

        result = self._orchestrator(route_generator=NoRoutesGenerator()).run(
            "route-empty",
            self._request(),
        )

        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertEqual(result.candidate_action["route_candidates"], [])
        self.assertIn("no_passing_route", result.needs_review_reason or "")

    def test_route_evaluator_timeout_expires_without_action(self):
        class TimeoutEvaluator:
            def evaluate_all(self, **kwargs):
                raise TimeoutError("route evaluator timed out")

        result = self._orchestrator(route_evaluator=TimeoutEvaluator()).run(
            "route-timeout",
            self._request(),
        )

        self.assertEqual(result.status, JobStatus.EXPIRED)
        self.assertIsNone(result.recommended_action)
        self.assertIsNone(result.candidate_action)

    def test_route_evaluator_dependency_failure_fails_without_action(self):
        class CrashEvaluator:
            def evaluate_all(self, **kwargs):
                raise RuntimeError("route evaluator unavailable")

        result = self._orchestrator(route_evaluator=CrashEvaluator()).run(
            "route-failed",
            self._request(),
        )

        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertIsNone(result.recommended_action)
        self.assertIsNone(result.candidate_action)

    def test_topology_version_mismatch_needs_review(self):
        result = self._orchestrator(
            expected_routing_graph_version="stale-routing-v0"
        ).run("route-version-mismatch", self._request())

        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIn("topology_version_mismatch", result.needs_review_reason or "")


class TestSafetyCheckResultContract(unittest.TestCase):
    """Validate SafetyCheckResult Pydantic model."""

    def test_valid_pass_result(self):
        r = SafetyCheckResult(
            passed=True, iteration=1,
            vc_ratio_ok=True, citations_ok=True,
            uncertainty_ok=True, ood_ok=True,
        )
        self.assertTrue(r.passed)
        self.assertIsNone(r.fail_reason)

    def test_valid_fail_result(self):
        r = SafetyCheckResult(
            passed=False, iteration=1,
            vc_ratio_ok=False, citations_ok=True,
            uncertainty_ok=True, ood_ok=True,
            fail_reason="vc_ratio 0.95 exceeds threshold 0.90",
            max_vc_ratio=0.95,
            vc_threshold=0.90,
        )
        self.assertFalse(r.passed)
        self.assertIn("vc_ratio", r.fail_reason)

    def test_iteration_bounds(self):
        with self.assertRaises(Exception):
            SafetyCheckResult(
                passed=True, iteration=0,  # must be >= 1
                vc_ratio_ok=True, citations_ok=True,
                uncertainty_ok=True, ood_ok=True,
            )
        with self.assertRaises(Exception):
            SafetyCheckResult(
                passed=True, iteration=4,  # must be <= 3
                vc_ratio_ok=True, citations_ok=True,
                uncertainty_ok=True, ood_ok=True,
            )


if __name__ == "__main__":
    unittest.main()
