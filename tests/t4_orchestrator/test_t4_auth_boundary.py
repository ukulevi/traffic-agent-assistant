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
    PrincipalResolutionError,
    PrincipalRole,
    ProvisionalBodyPrincipalResolver,
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
    def test_missing_trusted_principal_fails_closed_with_stable_code(self) -> None:
        from stwi.t4_orchestrator.api import create_app

        class MissingPrincipalResolver:
            def resolve(self, **_hints: object) -> ServerPrincipal:
                raise PrincipalResolutionError("upstream token details must not leak")

        app = create_app(
            store=InMemoryJobStore(),
            orchestrator=WhatIfOrchestrator(
                surrogate=FakeSurrogateForecaster(default_scenario=safe_scenario())
            ),
            principal_resolver=MissingPrincipalResolver(),
        )
        response = TestClient(app).post("/api/v1/what-if-jobs", json=body())

        self.assertEqual(response.status_code, 401)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "AUTH_PRINCIPAL_REQUIRED")
        self.assertIn("trace_id", detail)
        self.assertNotIn("token details", response.text)

    def test_create_returns_resolved_identity_metadata(self) -> None:
        principal = ServerPrincipal(
            tenant_id=TENANT,
            operator_id="operator-a",
            roles=frozenset({PrincipalRole.OPERATOR}),
        )
        response = TestClient(app_for(InMemoryJobStore(), principal)).post(
            "/api/v1/what-if-jobs", json=body()
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["tenant_id"], TENANT)
        self.assertEqual(response.json()["operator_id"], "operator-a")

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
        self.assertEqual(response.json()["detail"]["code"], "AUTH_TENANT_DENIED")

    def test_sse_reconnect_rejects_cross_tenant_principal(self) -> None:
        store = InMemoryJobStore()
        owner = ServerPrincipal(
            tenant_id=TENANT,
            operator_id="operator-a",
            roles=frozenset({PrincipalRole.OPERATOR}),
        )
        job_id = TestClient(app_for(store, owner)).post(
            "/api/v1/what-if-jobs", json=body()
        ).json()["job_id"]
        other = ServerPrincipal(
            tenant_id="tenant-b",
            operator_id="readonly-b",
            roles=frozenset({PrincipalRole.READONLY}),
        )

        response = TestClient(app_for(store, other)).get(
            f"/api/v1/what-if-jobs/{job_id}/events",
            headers={"Last-Event-ID": "1"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_TENANT_DENIED")

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

    def test_production_rejects_provisional_principal_resolvers(self) -> None:
        from stwi.t4_orchestrator.api import create_app

        settings = RuntimeSettings(mode=RuntimeMode.PRODUCTION, job_concurrency=1)
        provisional_resolvers = (
            ProvisionalBodyPrincipalResolver(),
            StaticPrincipalResolver(
                ServerPrincipal(
                    tenant_id=TENANT,
                    operator_id="operator-a",
                    roles=frozenset({PrincipalRole.OPERATOR}),
                )
            ),
        )

        for resolver in provisional_resolvers:
            with self.subTest(resolver=type(resolver).__name__):
                with self.assertRaisesRegex(RuntimeError, "rejects provisional"):
                    create_app(
                        store=object(),
                        orchestrator=object(),
                        settings=settings,
                        principal_resolver=resolver,
                    )
