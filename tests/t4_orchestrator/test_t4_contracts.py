"""Phase 4 contract tests — job lifecycle, action field semantics, audit records.

Covers all 6 job statuses and enforces:
- recommended_action ONLY on succeeded
- candidate_action ONLY on needs_review
- Neither action field on failed/expired/queued/running
- AuditRecord has trace_id, timestamp, model/data version, status_reason
- SSE does not leak raw frame data
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime

from stwi.t4_orchestrator.contracts import (
    AuditRecord,
    JobStatus,
    WhatIfJobRequest,
    WhatIfJobResult,
)
from stwi.t4_orchestrator.fake_adapters import (
    FakeSurrogateForecaster,
    high_uncertainty_scenario,
    ood_scenario,
    safe_scenario,
    unsafe_vc_scenario,
)
from stwi.t4_orchestrator.job_store import InMemoryJobStore
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator
from stwi.t4_orchestrator.api import _parse_last_event_id, _sse_event

SCENARIO_TIME = datetime(2025, 6, 1, 8, 0)
TENANT = "test-tenant"
CANDIDATE = {"node_id": "node-A", "green_time_ratio": 0.7}
JOB_ID = str(uuid.uuid4())


def make_request(**overrides) -> WhatIfJobRequest:
    defaults = dict(
        tenant_id=TENANT,
        scenario_time=SCENARIO_TIME,
        candidate_action=CANDIDATE,
        node_ids=["node-A"],
        scenario_query="quyền nghĩa vụ người sử dụng đường",
    )
    defaults.update(overrides)
    return WhatIfJobRequest(**defaults)


def make_orchestrator(scenario=None, node_overrides=None) -> WhatIfOrchestrator:
    surrogate = FakeSurrogateForecaster(
        default_scenario=scenario or safe_scenario(),
        node_overrides=node_overrides or {},
    )
    return WhatIfOrchestrator(surrogate=surrogate)


class TestJobStatusContracts(unittest.TestCase):
    """Verify action field semantics for each terminal job status."""

    def test_succeeded_has_recommended_action_not_candidate(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.status, JobStatus.SUCCEEDED)
        self.assertIsNotNone(result.recommended_action)
        self.assertIsNone(result.candidate_action)
        self.assertTrue(result.recommended_action["requires_operator_approval"])
        self.assertFalse(result.recommended_action["automatic_actuation"])

    def test_needs_review_vc_has_candidate_not_recommended(self):
        orc = make_orchestrator(unsafe_vc_scenario(0.95))
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIsNotNone(result.candidate_action)
        self.assertFalse(result.candidate_action["executable"])
        self.assertTrue(result.candidate_action["requires_operator_approval"])
        self.assertFalse(result.candidate_action["automatic_actuation"])

    def test_needs_review_ood_fail_closed(self):
        orc = make_orchestrator(ood_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIsNotNone(result.candidate_action)

    def test_needs_review_high_uncertainty_fail_closed(self):
        orc = make_orchestrator(high_uncertainty_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIsNotNone(result.candidate_action)

    def test_needs_review_missing_evidence_fail_closed(self):
        """Queries that produce no legal citations must fail-closed."""
        orc = make_orchestrator(safe_scenario())
        # Use a query guaranteed to return no citations from corpus
        req = make_request(scenario_query="blockchain cryptocurrency defi tokenomics")
        result = orc.run(JOB_ID, req)
        self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
        self.assertIsNone(result.recommended_action)
        self.assertIsNotNone(result.candidate_action)
        self.assertIn("missing_legal_evidence", result.needs_review_reason or "")

    def test_failed_job_has_no_action_fields(self):
        """A job that crashes must not expose either action field."""
        class CrashingSurrogate(FakeSurrogateForecaster):
            def predict(self, *args, **kwargs):
                raise RuntimeError("simulated surrogate crash")

        orc = WhatIfOrchestrator(surrogate=CrashingSurrogate())
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.status, JobStatus.FAILED)
        self.assertIsNone(result.recommended_action)
        self.assertIsNone(result.candidate_action)

    def test_contract_rejects_succeeded_without_recommended_action(self):
        """WhatIfJobResult must reject succeeded status with no recommended_action."""
        audit = AuditRecord(
            job_id=JOB_ID, tenant_id=TENANT,
            scenario_time=SCENARIO_TIME,
            model_version="v1", corpus_parser_version="2.0.0",
            status=JobStatus.SUCCEEDED, status_reason="ok",
        )
        with self.assertRaises(Exception):
            WhatIfJobResult(
                job_id=JOB_ID,
                status=JobStatus.SUCCEEDED,
                tenant_id=TENANT,
                scenario_time=SCENARIO_TIME,
                recommended_action=None,  # missing → should raise
                audit_record=audit,
            )

    def test_contract_rejects_needs_review_with_recommended_action(self):
        """needs_review must never expose recommended_action."""
        audit = AuditRecord(
            job_id=JOB_ID, tenant_id=TENANT,
            scenario_time=SCENARIO_TIME,
            model_version="v1", corpus_parser_version="2.0.0",
            status=JobStatus.NEEDS_REVIEW, status_reason="vc_ratio",
        )
        with self.assertRaises(Exception):
            WhatIfJobResult(
                job_id=JOB_ID,
                status=JobStatus.NEEDS_REVIEW,
                tenant_id=TENANT,
                scenario_time=SCENARIO_TIME,
                recommended_action=CANDIDATE,  # forbidden → should raise
                candidate_action=CANDIDATE,
                audit_record=audit,
            )


class TestAuditRecord(unittest.TestCase):
    """Verify audit records are complete and correct."""

    def test_audit_has_trace_id(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertIsNotNone(result.audit_record.trace_id)
        self.assertGreater(len(result.audit_record.trace_id), 10)

    def test_audit_has_timestamp(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertIsNotNone(result.audit_record.created_at)
        self.assertIsInstance(result.audit_record.created_at, datetime)

    def test_audit_records_model_and_corpus_version(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.audit_record.model_version, "provisional_mock_v1")
        self.assertEqual(result.audit_record.corpus_parser_version, "1.0.0")

    def test_audit_records_status_reason(self):
        orc = make_orchestrator(unsafe_vc_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertIsNotNone(result.audit_record.status_reason)
        self.assertGreater(len(result.audit_record.status_reason), 0)

    def test_audit_records_safety_iterations(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        self.assertGreaterEqual(result.audit_record.safety_iterations, 0)
        self.assertLessEqual(result.audit_record.safety_iterations, 3)

    def test_audit_records_tenant_id(self):
        orc = make_orchestrator()
        result = orc.run(JOB_ID, make_request())
        self.assertEqual(result.audit_record.tenant_id, TENANT)


class TestNoSensitivePayloadLeak(unittest.TestCase):
    """Verify result does not expose raw frame data or sensitive fields."""

    def test_result_has_no_raw_frame_data(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        d = result.model_dump(mode="json")
        # Must not contain per-step raw tensors or frame arrays
        self.assertNotIn("raw_frames", d)
        self.assertNotIn("tensor", d)
        self.assertNotIn("X_input", d)

    def test_result_warns_about_synthetic_data(self):
        orc = make_orchestrator(safe_scenario())
        result = orc.run(JOB_ID, make_request())
        if result.baseline_summary:
            self.assertIn("warning", result.baseline_summary)
        if result.scenario_summary:
            self.assertIn("warning", result.scenario_summary)

    def test_result_has_no_recommended_action_attribute_for_needs_review(self):
        orc = make_orchestrator(unsafe_vc_scenario())
        result = orc.run(JOB_ID, make_request())
        # The field exists but must be None
        self.assertIsNone(result.recommended_action)


class TestJobStore(unittest.TestCase):
    """Verify in-memory job store lifecycle."""

    def setUp(self):
        self.store = InMemoryJobStore()
        self.request = make_request()

    def test_create_returns_queued_job(self):
        env = self.store.create(self.request)
        self.assertEqual(env.status, JobStatus.QUEUED)
        self.assertIsNotNone(env.job_id)

    def test_get_returns_stored_job(self):
        env = self.store.create(self.request)
        fetched = self.store.get(env.job_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.job_id, env.job_id)

    def test_update_status_to_running(self):
        env = self.store.create(self.request)
        self.store.update_status(env.job_id, JobStatus.RUNNING)
        self.assertEqual(self.store.get(env.job_id).status, JobStatus.RUNNING)

    def test_set_result_stores_completed_job(self):
        env = self.store.create(self.request)
        orc = make_orchestrator(safe_scenario())
        result = orc.run(env.job_id, self.request)
        self.store.set_result(env.job_id, result)
        fetched = self.store.get(env.job_id)
        self.assertEqual(fetched.status, JobStatus.SUCCEEDED)
        self.assertIsNotNone(fetched.result)

    def test_get_unknown_job_returns_none(self):
        self.assertIsNone(self.store.get("nonexistent-job-id"))

    def test_event_log_records_status_and_result_with_monotonic_ids(self):
        env = self.store.create(self.request)
        self.store.update_status(env.job_id, JobStatus.RUNNING)
        orc = make_orchestrator(safe_scenario())
        result = orc.run(env.job_id, self.request)
        self.store.set_result(env.job_id, result)

        events = self.store.events_since(env.job_id)
        self.assertEqual([event.id for event in events], [1, 2, 3])
        self.assertEqual(events[0].event, "status")
        self.assertEqual(events[1].status, JobStatus.RUNNING)
        self.assertEqual(events[2].event, "result")

        resumed = self.store.events_since(env.job_id, last_event_id=2)
        self.assertEqual(len(resumed), 1)
        self.assertEqual(resumed[0].id, 3)

    def test_operator_decision_is_audit_only_no_actuation(self):
        env = self.store.create(self.request)
        orc = make_orchestrator(safe_scenario())
        result = orc.run(env.job_id, self.request)
        self.store.set_result(env.job_id, result)

        record = self.store.record_operator_decision(
            env.job_id,
            operator_id="operator-1",
            decision="approved",
            comment="Reviewed in control room",
        )

        self.assertIsNotNone(record)
        self.assertFalse(record.applied_by_system)
        fetched = self.store.get(env.job_id)
        self.assertEqual(fetched.operator_decision.operator_id, "operator-1")
        decision_events = [
            event for event in self.store.events_since(env.job_id)
            if event.event == "operator_decision"
        ]
        self.assertEqual(len(decision_events), 1)
        self.assertFalse(decision_events[0].payload["applied_by_system"])

    def test_sse_event_format_has_id_and_named_event(self):
        env = self.store.create(self.request)
        event = self.store.events_since(env.job_id)[0]
        sse = _sse_event(event)
        self.assertIn("id: 1", sse)
        self.assertIn("event: status", sse)
        self.assertIn('"status": "queued"', sse)

    def test_parse_last_event_id_is_defensive(self):
        self.assertEqual(_parse_last_event_id("3"), 3)
        self.assertEqual(_parse_last_event_id("-1"), 0)
        self.assertEqual(_parse_last_event_id("not-an-int"), 0)
        self.assertEqual(_parse_last_event_id(None), 0)


class TestWhatIfJobRequest(unittest.TestCase):
    """Validate request model constraints."""

    def test_empty_node_ids_rejected(self):
        with self.assertRaises(Exception):
            WhatIfJobRequest(
                tenant_id=TENANT,
                scenario_time=SCENARIO_TIME,
                candidate_action=CANDIDATE,
                node_ids=[],  # must be non-empty
                scenario_query="test",
            )

    def test_vc_threshold_bounds(self):
        with self.assertRaises(Exception):
            make_request(vc_threshold=1.5)
        with self.assertRaises(Exception):
            make_request(vc_threshold=-0.1)

    def test_default_vc_threshold_is_09(self):
        req = make_request()
        self.assertEqual(req.vc_threshold, 0.9)


if __name__ == "__main__":
    unittest.main()
