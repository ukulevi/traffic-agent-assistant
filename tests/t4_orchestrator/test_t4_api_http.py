"""HTTP-level tests for the Phase 4 What-If API (FastAPI).

Tests all endpoints at the HTTP transport layer using FastAPI TestClient:
  POST /api/v1/what-if-jobs          → 202 + job_id
  GET  /api/v1/what-if-jobs/{job_id} → status + result
  GET  /api/v1/what-if-jobs/{job_id}/events → SSE stream
  POST /api/v1/what-if-jobs/{job_id}/operator-decision → audit record

Covers: happy path, error responses, status codes, SSE format,
operator decision lifecycle, fail-closed semantics at HTTP layer.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from stwi.t4_orchestrator.contracts import JobStatus
from stwi.t4_orchestrator.fake_adapters import (
    FakeSurrogateForecaster,
    safe_scenario,
    unsafe_vc_scenario,
    ood_scenario,
    high_uncertainty_scenario,
)
from stwi.t4_orchestrator.job_store import InMemoryJobStore
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator

SCENARIO_TIME = "2025-06-01T08:00:00"
TENANT = "test-tenant"
CANDIDATE = {"node_id": "node-A", "green_time_ratio": 0.7}


def make_body(**overrides) -> dict:
    defaults = dict(
        tenant_id=TENANT,
        scenario_time=SCENARIO_TIME,
        candidate_action=CANDIDATE,
        node_ids=["node-A"],
        scenario_query="quyền nghĩa vụ người sử dụng đường",
    )
    defaults.update(overrides)
    return defaults


def make_client(scenario=None) -> TestClient:
    from stwi.t4_orchestrator.api import create_app

    store = InMemoryJobStore()
    surrogate = FakeSurrogateForecaster(
        default_scenario=scenario or safe_scenario(),
    )
    orchestrator = WhatIfOrchestrator(surrogate=surrogate)
    app = create_app(store=store, orchestrator=orchestrator)
    return TestClient(app)


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestCreateJob(unittest.TestCase):
    """POST /api/v1/what-if-jobs"""

    def test_create_returns_202(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body())
        self.assertEqual(resp.status_code, 202)

    def test_create_returns_job_id(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body())
        data = resp.json()
        self.assertIn("job_id", data)
        self.assertGreater(len(data["job_id"]), 10)

    def test_create_returns_queued_status(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body())
        self.assertEqual(resp.json()["status"], "queued")

    def test_create_returns_provisional_warning(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body())
        self.assertIn("warning", resp.json())

    def test_create_rejects_empty_node_ids(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body(node_ids=[]))
        self.assertEqual(resp.status_code, 422)

    def test_create_rejects_missing_tenant(self):
        client = make_client()
        body = make_body()
        del body["tenant_id"]
        resp = client.post("/api/v1/what-if-jobs", json=body)
        self.assertEqual(resp.status_code, 422)

    def test_create_rejects_empty_scenario_query(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body(scenario_query=""))
        self.assertEqual(resp.status_code, 422)

    def test_create_rejects_invalid_vc_threshold(self):
        client = make_client()
        resp = client.post("/api/v1/what-if-jobs", json=make_body(vc_threshold=1.5))
        self.assertEqual(resp.status_code, 422)


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestGetJob(unittest.TestCase):
    """GET /api/v1/what-if-jobs/{job_id}"""

    def test_get_existing_job(self):
        client = make_client()
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["job_id"], job_id)
        self.assertIn(data["status"], [s.value for s in JobStatus])

    def test_get_nonexistent_job_returns_404(self):
        client = make_client()
        resp = client.get("/api/v1/what-if-jobs/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    def test_get_completed_job_has_result(self):
        """After background task runs, GET should return result."""
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        # TestClient runs background tasks synchronously
        self.assertIn(data["status"], ["succeeded", "needs_review", "failed"])
        if data["status"] == "succeeded":
            self.assertIn("result", data)

    def test_succeeded_job_has_recommended_action(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        if data["status"] == "succeeded":
            result = data["result"]
            self.assertIsNotNone(result["recommended_action"])
            self.assertIsNone(result["candidate_action"])
            self.assertFalse(result["recommended_action"]["automatic_actuation"])

    def test_needs_review_job_has_candidate_action(self):
        client = make_client(unsafe_vc_scenario(0.95))
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        self.assertEqual(data["status"], "needs_review")
        result = data["result"]
        self.assertIsNone(result["recommended_action"])
        self.assertIsNotNone(result["candidate_action"])
        self.assertFalse(result["candidate_action"]["automatic_actuation"])

    def test_ood_fail_closed_at_http_layer(self):
        client = make_client(ood_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        self.assertEqual(data["status"], "needs_review")

    def test_high_uncertainty_fail_closed_at_http_layer(self):
        client = make_client(high_uncertainty_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        self.assertEqual(data["status"], "needs_review")

    def test_get_response_has_tenant_and_timestamps(self):
        client = make_client()
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        self.assertEqual(data["tenant_id"], TENANT)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_result_has_audit_record(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        if "result" in data:
            result = data["result"]
            self.assertIn("audit_record", result)
            self.assertIn("trace_id", result["audit_record"])
            self.assertIn("safety_iterations", result)


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestOperatorDecision(unittest.TestCase):
    """POST /api/v1/what-if-jobs/{job_id}/operator-decision"""

    def _create_completed_job(self, client, scenario=None):
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        return create_resp.json()["job_id"]

    def test_approve_succeeded_job(self):
        client = make_client(safe_scenario())
        job_id = self._create_completed_job(client)

        resp = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={
                "operator_id": "operator-1",
                "decision": "approved",
                "comment": "Reviewed and approved",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["job_id"], job_id)
        self.assertFalse(data["automatic_actuation"])
        self.assertIn("operator_decision", data)
        self.assertEqual(data["operator_decision"]["decision"], "approved")
        self.assertFalse(data["operator_decision"]["applied_by_system"])

    def test_reject_needs_review_job(self):
        client = make_client(unsafe_vc_scenario())
        job_id = self._create_completed_job(client)

        resp = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={
                "operator_id": "operator-2",
                "decision": "rejected",
                "comment": "V/C too high",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["operator_decision"]["decision"], "rejected")

    def test_decision_on_nonexistent_job_returns_404(self):
        client = make_client()
        resp = client.post(
            "/api/v1/what-if-jobs/nonexistent/operator-decision",
            json={"operator_id": "op-1", "decision": "approved"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_decision_on_running_job_returns_409(self):
        """Cannot record decision before job reaches terminal status."""
        from stwi.t4_orchestrator.api import create_app

        store = InMemoryJobStore()
        orchestrator = WhatIfOrchestrator()
        app = create_app(store=store, orchestrator=orchestrator)

        # Manually create a job in QUEUED state without running it
        from stwi.t4_orchestrator.contracts import WhatIfJobRequest
        req = WhatIfJobRequest(**make_body())
        env = store.create(req)
        store.update_status(env.job_id, JobStatus.RUNNING)

        client = TestClient(app)
        resp = client.post(
            f"/api/v1/what-if-jobs/{env.job_id}/operator-decision",
            json={"operator_id": "op-1", "decision": "approved"},
        )
        self.assertEqual(resp.status_code, 409)

    def test_decision_rejects_empty_operator_id(self):
        client = make_client(safe_scenario())
        job_id = self._create_completed_job(client)

        resp = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={"operator_id": "", "decision": "approved"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_decision_rejects_invalid_decision_value(self):
        client = make_client(safe_scenario())
        job_id = self._create_completed_job(client)

        resp = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={"operator_id": "op-1", "decision": "maybe"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_decision_visible_in_get(self):
        client = make_client(safe_scenario())
        job_id = self._create_completed_job(client)

        client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={"operator_id": "op-1", "decision": "approved"},
        )

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = resp.json()
        self.assertIn("operator_decision", data)
        self.assertEqual(data["operator_decision"]["operator_id"], "op-1")


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestSSEStream(unittest.TestCase):
    """GET /api/v1/what-if-jobs/{job_id}/events"""

    def test_sse_nonexistent_job_returns_404(self):
        client = make_client()
        resp = client.get("/api/v1/what-if-jobs/nonexistent/events")
        self.assertEqual(resp.status_code, 404)

    def test_sse_content_type(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
        self.assertIn("text/event-stream", resp.headers["content-type"])

    def test_sse_has_events_with_id_and_data(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
        body = resp.text

        # SSE format: lines with "id:", "event:", "data:"
        self.assertIn("id:", body)
        self.assertIn("event:", body)
        self.assertIn("data:", body)

    def test_sse_contains_result_event(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
        body = resp.text

        # Should contain a result event with terminal status
        self.assertIn("event: result", body)

    def test_sse_events_have_monotonic_ids(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
        body = resp.text

        ids = []
        for line in body.split("\n"):
            if line.startswith("id:"):
                ids.append(int(line.split(":", 1)[1].strip()))
        self.assertTrue(len(ids) > 0, "Expected at least one SSE event id")
        self.assertEqual(ids, sorted(ids), "SSE event ids must be monotonically increasing")

    def test_sse_cache_control_headers(self):
        client = make_client(safe_scenario())
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        resp = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
        self.assertEqual(resp.headers.get("cache-control"), "no-cache")

    def test_sse_resume_with_last_event_id(self):
        """Passing Last-Event-ID should skip already-seen events."""
        from stwi.t4_orchestrator.api import create_app

        store = InMemoryJobStore()
        orchestrator = WhatIfOrchestrator(
            surrogate=FakeSurrogateForecaster(default_scenario=safe_scenario()),
        )
        app = create_app(store=store, orchestrator=orchestrator)
        client = TestClient(app)

        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        # Full stream
        full_resp = client.get(f"/api/v1/what-if-jobs/{job_id}/events")
        full_ids = [
            int(line.split(":", 1)[1].strip())
            for line in full_resp.text.split("\n")
            if line.startswith("id:")
        ]
        self.assertGreater(len(full_ids), 1)

        # Resume after first event
        resumed_resp = client.get(
            f"/api/v1/what-if-jobs/{job_id}/events",
            headers={"Last-Event-ID": str(full_ids[0])},
        )
        resumed_ids = [
            int(line.split(":", 1)[1].strip())
            for line in resumed_resp.text.split("\n")
            if line.startswith("id:")
        ]
        # All resumed ids should be > the Last-Event-ID
        for rid in resumed_ids:
            self.assertGreater(rid, full_ids[0])


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestEndToEndLifecycle(unittest.TestCase):
    """Full lifecycle: create → poll → decide."""

    def test_full_lifecycle_safe_scenario(self):
        client = make_client(safe_scenario())

        # 1. Create
        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        self.assertEqual(create_resp.status_code, 202)
        job_id = create_resp.json()["job_id"]

        # 2. Poll (TestClient runs bg tasks sync, so job is already done)
        get_resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertEqual(data["status"], "succeeded")
        self.assertIn("result", data)
        self.assertIsNotNone(data["result"]["recommended_action"])
        self.assertFalse(data["result"]["recommended_action"]["automatic_actuation"])

        # 3. Operator decision
        dec_resp = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={"operator_id": "op-1", "decision": "approved", "comment": "LGTM"},
        )
        self.assertEqual(dec_resp.status_code, 200)
        self.assertFalse(dec_resp.json()["automatic_actuation"])

        # 4. Verify decision persisted
        final_resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        self.assertIn("operator_decision", final_resp.json())

    def test_full_lifecycle_unsafe_scenario(self):
        client = make_client(unsafe_vc_scenario(0.95))

        create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = create_resp.json()["job_id"]

        get_resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = get_resp.json()
        self.assertEqual(data["status"], "needs_review")
        self.assertIsNone(data["result"]["recommended_action"])
        self.assertIsNotNone(data["result"]["candidate_action"])

        # Operator rejects
        dec_resp = client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={"operator_id": "op-2", "decision": "rejected"},
        )
        self.assertEqual(dec_resp.status_code, 200)

    def test_no_automatic_actuation_anywhere(self):
        """Verify no response ever contains automatic_actuation=True."""
        for scenario in [safe_scenario(), unsafe_vc_scenario(), ood_scenario()]:
            client = make_client(scenario)
            create_resp = client.post("/api/v1/what-if-jobs", json=make_body())
            job_id = create_resp.json()["job_id"]

            get_resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
            body = json.dumps(get_resp.json())
            self.assertNotIn('"automatic_actuation": true', body)


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestJobTimeoutAndExpiration(unittest.TestCase):
    def test_orchestrator_timeout_marks_expired(self):
        from stwi.t4_orchestrator.api import create_app
        store = InMemoryJobStore()
        # Set a very low timeout so it immediately expires
        orchestrator = WhatIfOrchestrator(timeout_seconds=0.000001)
        app = create_app(store=store, orchestrator=orchestrator)
        client = TestClient(app)

        resp = client.post("/api/v1/what-if-jobs", json=make_body())
        job_id = resp.json()["job_id"]

        job_resp = client.get(f"/api/v1/what-if-jobs/{job_id}")
        data = job_resp.json()
        self.assertEqual(data["status"], "expired")
        self.assertIn("result", data)
        self.assertEqual(data["result"]["status"], "expired")

    def test_sse_timeout_marks_expired(self):
        from stwi.t4_orchestrator.api import create_app
        store = InMemoryJobStore()
        # Create a job manually in RUNNING status so it never completes
        from stwi.t4_orchestrator.contracts import WhatIfJobRequest
        req = WhatIfJobRequest(**make_body())
        env = store.create(req)
        store.update_status(env.job_id, JobStatus.RUNNING)

        import asyncio
        from stwi.t4_orchestrator.api import _event_generator
        
        async def run_test():
            gen = _event_generator(env.job_id, store, timeout_seconds=0.01, poll_interval=0.001)
            events = []
            async for event in gen:
                events.append(event)
            return events

        events = asyncio.run(run_test())
        # Check that the job is now expired in the store
        final_envelope = store.get(env.job_id)
        self.assertEqual(final_envelope.status, JobStatus.EXPIRED)
        # Check that events list contains the event marking it expired
        self.assertTrue(any("expired" in e for e in events))


if __name__ == "__main__":
    unittest.main()
