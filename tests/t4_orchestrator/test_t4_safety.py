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

from stwi.t4_orchestrator.contracts import JobStatus, SafetyCheckResult
from stwi.t4_orchestrator.fake_adapters import (
    FakeSurrogateForecaster,
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
        )
        return surrogate, results

    def test_safe_scenario_passes(self):
        surrogate, results = self._make_surrogate_and_results(safe_scenario())
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=True)
        self.assertTrue(outcome.passed)
        self.assertIsNone(outcome.fail_reason)

    def test_vc_over_threshold_fails(self):
        scenario = unsafe_vc_scenario(vc_ratio=0.95)
        surrogate, results = self._make_surrogate_and_results(scenario)
        loop = CounterfactualSafetyLoop(surrogate=surrogate, vc_threshold=0.9)
        outcome = loop.run(results, has_citations=True)
        self.assertFalse(outcome.passed)
        self.assertIn("vc_ratio", outcome.fail_reason)
        # Check gate detail
        self.assertFalse(outcome.checks[0].vc_ratio_ok)

    def test_vc_exactly_at_threshold_passes(self):
        """vc_ratio == threshold is allowed (<=, not <)."""
        scenario = SurrogateScenario(vc_ratio=0.9, uncertainty_score=0.1, ood_score=0.02)
        surrogate, results = self._make_surrogate_and_results(scenario)
        loop = CounterfactualSafetyLoop(surrogate=surrogate, vc_threshold=0.9)
        outcome = loop.run(results, has_citations=True)
        self.assertTrue(outcome.passed)

    def test_missing_citations_fails(self):
        surrogate, results = self._make_surrogate_and_results(safe_scenario())
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=False)
        self.assertFalse(outcome.passed)
        self.assertIn("missing_legal_evidence", outcome.fail_reason)
        self.assertFalse(outcome.checks[0].citations_ok)

    def test_ood_fails(self):
        surrogate, results = self._make_surrogate_and_results(ood_scenario())
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=True)
        self.assertFalse(outcome.passed)
        self.assertIn("ood_score", outcome.fail_reason)
        self.assertFalse(outcome.checks[0].ood_ok)

    def test_high_uncertainty_fails(self):
        surrogate, results = self._make_surrogate_and_results(high_uncertainty_scenario())
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=True)
        self.assertFalse(outcome.passed)
        self.assertIn("uncertainty", outcome.fail_reason)
        self.assertFalse(outcome.checks[0].uncertainty_ok)

    def test_max_iterations_bounded(self):
        """Safety loop must never exceed MAX_ITERATIONS."""
        surrogate, results = self._make_surrogate_and_results(unsafe_vc_scenario())
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=True)
        self.assertLessEqual(outcome.iterations_run, MAX_ITERATIONS)

    def test_non_converged_policy_runs_max_iterations(self):
        """A policy failure should produce a 3-iteration CSL audit trace."""
        surrogate, results = self._make_surrogate_and_results(unsafe_vc_scenario())
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=True)
        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.iterations_run, MAX_ITERATIONS)
        self.assertEqual(len(outcome.checks), MAX_ITERATIONS)

    def test_compound_failure_reports_all_reasons(self):
        """When multiple gates fail, all are reported in fail_reason."""
        compound = SurrogateScenario(vc_ratio=0.99, uncertainty_score=0.95, ood_score=0.9)
        surrogate, results = self._make_surrogate_and_results(compound)
        loop = CounterfactualSafetyLoop(surrogate=surrogate)
        outcome = loop.run(results, has_citations=False)
        self.assertFalse(outcome.passed)
        # All four failures should appear
        reason = outcome.fail_reason
        self.assertIn("vc_ratio", reason)
        self.assertIn("missing_legal_evidence", reason)
        self.assertIn("uncertainty", reason)
        self.assertIn("ood_score", reason)


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

    def test_needs_review_candidate_action_equals_original_request(self):
        """candidate_action keeps request fields but is explicitly non-executable."""
        candidate = {"node_id": "node-A", "green_time_ratio": 0.7}
        result = run_job(unsafe_vc_scenario())
        if result.status == JobStatus.NEEDS_REVIEW:
            for key, value in candidate.items():
                self.assertEqual(result.candidate_action[key], value)
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
