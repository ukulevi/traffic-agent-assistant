"""Trusted production dashboard context contract tests."""

from __future__ import annotations

import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from pydantic import ValidationError

from stwi.config.runtime import RuntimeMode, RuntimeSettings
from stwi.t4_orchestrator.api import create_app
from stwi.t4_orchestrator.auth import PrincipalRole, ServerPrincipal
from stwi.t4_orchestrator.ui_context import UiCapabilities, UiContextScope
from stwi.t4_orchestrator.contracts import JobEnvelope, JobStatus, WhatIfJobRequest


class TestUiContextScope(unittest.TestCase):
    def test_scope_preserves_stable_node_order(self) -> None:
        scope = UiContextScope(
            node_ids=("node_02", "node_00", "node_01"),
            record_decision=True,
        )

        self.assertEqual(scope.node_ids, ("node_02", "node_00", "node_01"))
        self.assertTrue(scope.record_decision)

    def test_scope_rejects_invalid_node_sets(self) -> None:
        cases = (
            (),
            ("",),
            (" node_00",),
            ("node_00", "node_00"),
            tuple(f"node_{index:02d}" for index in range(21)),
        )

        for node_ids in cases:
            with self.subTest(node_ids=node_ids):
                with self.assertRaises(ValueError):
                    UiContextScope(node_ids=node_ids, record_decision=False)

    def test_scope_requires_strict_boolean_capability(self) -> None:
        with self.assertRaises(ValueError):
            UiContextScope(node_ids=("node_00",), record_decision=1)  # type: ignore[arg-type]


class TestUiCapabilities(unittest.TestCase):
    def test_capabilities_reject_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            UiCapabilities.model_validate(
                {"record_decision": True, "automatic_actuation": True}
            )

    def test_capabilities_require_strict_boolean(self) -> None:
        with self.assertRaises(ValidationError):
            UiCapabilities.model_validate({"record_decision": 1})


class TrustedPrincipalResolver:
    def __init__(self, principal: ServerPrincipal) -> None:
        self.principal = principal

    def resolve(self, **_kwargs: object) -> ServerPrincipal:
        return self.principal


class MissingPrincipalResolver:
    def resolve(self, **_kwargs: object) -> ServerPrincipal:
        raise ValueError("trusted identity unavailable")


class InvalidPrincipalResolver:
    def resolve(self, **_kwargs: object) -> object:
        return object()


class TrustedUiContextProvider:
    def __init__(self, scope: UiContextScope) -> None:
        self.scope = scope

    def resolve(self, *, principal: ServerPrincipal) -> UiContextScope:
        del principal
        return self.scope


class FailingUiContextProvider:
    def resolve(self, *, principal: ServerPrincipal) -> UiContextScope:
        del principal
        raise LookupError("scope registry unavailable")


class ProvisionalUiContextProvider(TrustedUiContextProvider):
    is_provisional_provider = True


class TrustedJobStore:
    is_provisional_store = False

    def create(self, request: WhatIfJobRequest) -> JobEnvelope:
        return JobEnvelope(
            job_id="job-authorized-scope",
            status=JobStatus.QUEUED,
            tenant_id=request.tenant_id,
            request=request,
        )


class TrustedDispatcher:
    is_provisional_dispatcher = False

    def dispatch(self, job_id: str, request: WhatIfJobRequest) -> None:
        del job_id, request


def job_body(node_id: str = "node_00", *, incident: bool = False) -> dict[str, object]:
    body: dict[str, object] = {
        "tenant_id": "tenant-a",
        "scenario_time": datetime(2025, 6, 1, 8, 0).isoformat(),
        "candidate_action": {"node_id": node_id, "green_time_ratio": 0.7},
        "node_ids": [node_id],
        "scenario_query": "Đánh giá giả định tổng hợp.",
    }
    if incident:
        body["incident"] = {
            "event_type": "accident",
            "affected_node_ids": [node_id],
            "severity": "high",
            "duration_minutes": 30,
            "description": "Tai nạn tổng hợp để đánh giá what-if.",
        }
    return body


def production_app(
    *,
    principal: ServerPrincipal | None = None,
    principal_resolver: object | None = None,
    provider: object | None = None,
    store: object | None = None,
    dispatcher: object | None = None,
) -> object:
    resolved_principal = principal or ServerPrincipal(
        tenant_id="tenant-a",
        operator_id="operator-17",
        roles=frozenset({PrincipalRole.OPERATOR}),
    )
    return create_app(
        store=store or TrustedJobStore(),
        orchestrator=object(),
        settings=RuntimeSettings(mode=RuntimeMode.PRODUCTION, job_concurrency=1),
        principal_resolver=(
            principal_resolver or TrustedPrincipalResolver(resolved_principal)
        ),
        dispatcher=dispatcher or TrustedDispatcher(),
        ui_context_provider=(
            provider
            if provider is not None
            else TrustedUiContextProvider(
                UiContextScope(
                    node_ids=("node_02", "node_00"),
                    record_decision=True,
                )
            )
        ),
    )


class TestUiContextApi(unittest.TestCase):
    def test_trusted_production_context_returns_no_store_response(self) -> None:
        response = TestClient(production_app()).get("/api/v1/ui-context")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            response.json(),
            {
                "mode": "production",
                "tenant_id": "tenant-a",
                "operator_id": "operator-17",
                "roles": ["operator"],
                "node_ids": ["node_02", "node_00"],
                "capabilities": {"record_decision": True},
            },
        )

    def test_analyst_decision_capability_is_clamped(self) -> None:
        analyst = ServerPrincipal(
            tenant_id="tenant-a",
            operator_id="analyst-4",
            roles=frozenset({PrincipalRole.ANALYST}),
        )

        response = TestClient(production_app(principal=analyst)).get(
            "/api/v1/ui-context"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["capabilities"]["record_decision"])

    def test_missing_principal_fails_closed(self) -> None:
        response = TestClient(
            production_app(principal_resolver=MissingPrincipalResolver())
        ).get("/api/v1/ui-context")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_PRINCIPAL_REQUIRED")
        self.assertTrue(response.json()["detail"]["trace_id"])

    def test_invalid_principal_type_fails_closed(self) -> None:
        response = TestClient(
            production_app(principal_resolver=InvalidPrincipalResolver())
        ).get("/api/v1/ui-context")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_PRINCIPAL_REQUIRED")

    def test_unsupported_dashboard_role_is_denied(self) -> None:
        unsupported = ServerPrincipal(
            tenant_id="tenant-a",
            operator_id="operator-17",
            roles=frozenset({"superuser"}),  # type: ignore[arg-type]
        )

        response = TestClient(production_app(principal=unsupported)).get(
            "/api/v1/ui-context"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_ROLE_DENIED")

    def test_provider_failure_returns_stable_503(self) -> None:
        response = TestClient(
            production_app(provider=FailingUiContextProvider())
        ).get("/api/v1/ui-context")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "UI_CONTEXT_UNAVAILABLE")
        self.assertTrue(response.json()["detail"]["trace_id"])

    def test_production_requires_trusted_provider(self) -> None:
        settings = RuntimeSettings(mode=RuntimeMode.PRODUCTION, job_concurrency=1)
        principal = ServerPrincipal(
            tenant_id="tenant-a",
            operator_id="operator-17",
            roles=frozenset({PrincipalRole.OPERATOR}),
        )
        common = {
            "store": object(),
            "orchestrator": object(),
            "settings": settings,
            "principal_resolver": TrustedPrincipalResolver(principal),
            "dispatcher": object(),
        }

        with self.assertRaisesRegex(RuntimeError, "UiContextProvider"):
            create_app(**common)
        with self.assertRaisesRegex(RuntimeError, "provisional UiContextProvider"):
            create_app(
                **common,
                ui_context_provider=ProvisionalUiContextProvider(
                    UiContextScope(
                        node_ids=("node_00",),
                        record_decision=True,
                    )
                ),
            )

    def test_nonproduction_does_not_register_context_endpoint(self) -> None:
        app = create_app(
            store=object(),
            orchestrator=object(),
            settings=RuntimeSettings(mode=RuntimeMode.TEST, job_concurrency=1),
        )

        self.assertEqual(
            TestClient(app).get("/api/v1/ui-context").status_code,
            404,
        )

    def test_create_job_accepts_only_server_authorized_production_nodes(self) -> None:
        client = TestClient(production_app())

        allowed = client.post("/api/v1/what-if-jobs", json=job_body("node_00"))
        denied = client.post(
            "/api/v1/what-if-jobs",
            json=job_body("node_99", incident=True),
        )

        self.assertEqual(allowed.status_code, 202)
        self.assertEqual(denied.status_code, 403)
        detail = denied.json()["detail"]
        self.assertEqual(detail["code"], "AUTH_NODE_SCOPE_DENIED")
        self.assertTrue(detail["trace_id"])
        self.assertNotIn("node_00", denied.text)

    def test_create_job_fails_closed_when_production_scope_is_unavailable(self) -> None:
        response = TestClient(
            production_app(provider=FailingUiContextProvider())
        ).post("/api/v1/what-if-jobs", json=job_body())

        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "UI_CONTEXT_UNAVAILABLE")
        self.assertTrue(detail["trace_id"])
        self.assertNotIn("scope registry", response.text)


if __name__ == "__main__":
    unittest.main()
