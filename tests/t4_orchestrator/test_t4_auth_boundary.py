"""Focused HTTP tests for the server-side principal boundary."""

from __future__ import annotations

import unittest
from datetime import datetime

try:
    from fastapi.testclient import TestClient

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from stwi.config.runtime import RuntimeMode, RuntimeSettings
from stwi.t4_orchestrator.auth import (
    PrincipalRole,
    ServerPrincipal,
    StaticPrincipalResolver,
)
from stwi.t4_orchestrator.fake_adapters import FakeSurrogateForecaster, safe_scenario
from stwi.t4_orchestrator.job_store import InMemoryJobStore
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator


TENANT = "tenant-a"


def body(tenant_id: str = TENANT) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "scenario_time": datetime(2025, 6, 1, 8, 0).isoformat(),
        "candidate_action": {"node_id": "node-A", "green_time_ratio": 0.7},
        "node_ids": ["node-A"],
        "scenario_query": "traffic safety evidence",
    }


def app_for(store: InMemoryJobStore, principal: ServerPrincipal) -> object:
    from stwi.t4_orchestrator.api import create_app

    return create_app(
        store=store,
        orchestrator=WhatIfOrchestrator(
            surrogate=FakeSurrogateForecaster(default_scenario=safe_scenario())
        ),
        principal_resolver=StaticPrincipalResolver(principal),
    )


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestAuthBoundary(unittest.TestCase):
    def test_create_rejects_client_tenant_mismatch(self) -> None:
        client = TestClient(
            app_for(
                InMemoryJobStore(),
                ServerPrincipal(
                    tenant_id=TENANT,
                    operator_id="operator-a",
                    roles=frozenset({PrincipalRole.OPERATOR}),
                ),
            )
        )

        response = client.post("/api/v1/what-if-jobs", json=body("tenant-b"))

        self.assertEqual(response.status_code, 403)

    def test_get_rejects_cross_tenant_principal(self) -> None:
        store = InMemoryJobStore()
        owner = ServerPrincipal(
            tenant_id=TENANT,
            operator_id="operator-a",
            roles=frozenset({PrincipalRole.OPERATOR}),
        )
        owner_client = TestClient(app_for(store, owner))
        job_id = owner_client.post("/api/v1/what-if-jobs", json=body()).json()["job_id"]
        other_client = TestClient(
            app_for(
                store,
                ServerPrincipal(
                    tenant_id="tenant-b",
                    operator_id="operator-b",
                    roles=frozenset({PrincipalRole.READONLY}),
                ),
            )
        )

        response = other_client.get(f"/api/v1/what-if-jobs/{job_id}")

        self.assertEqual(response.status_code, 403)

    def test_analyst_cannot_record_operator_decision(self) -> None:
        store = InMemoryJobStore()
        owner = ServerPrincipal(
            tenant_id=TENANT,
            operator_id="operator-a",
            roles=frozenset({PrincipalRole.OPERATOR}),
        )
        owner_client = TestClient(app_for(store, owner))
        job_id = owner_client.post("/api/v1/what-if-jobs", json=body()).json()["job_id"]
        analyst_client = TestClient(
            app_for(
                store,
                ServerPrincipal(
                    tenant_id=TENANT,
                    operator_id="analyst-a",
                    roles=frozenset({PrincipalRole.ANALYST}),
                ),
            )
        )

        response = analyst_client.post(
            f"/api/v1/what-if-jobs/{job_id}/operator-decision",
            json={"operator_id": "analyst-a", "decision": "approved"},
        )

        self.assertEqual(response.status_code, 403)

    def test_production_requires_explicit_principal_resolver(self) -> None:
        from stwi.t4_orchestrator.api import create_app

        settings = RuntimeSettings(mode=RuntimeMode.PRODUCTION, job_concurrency=1)
        with self.assertRaisesRegex(RuntimeError, "PrincipalResolver"):
            create_app(store=object(), orchestrator=object(), settings=settings)
