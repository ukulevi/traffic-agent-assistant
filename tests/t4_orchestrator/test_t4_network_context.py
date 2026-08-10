"""Tests for the authorized, fail-closed network-context boundary."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from stwi.config.runtime import RuntimeMode, RuntimeSettings
from stwi.t1_pipeline.network_topology import (
    NetworkTopologyRegistry,
    build_synthetic_topology,
)
from stwi.t4_orchestrator.api import create_app
from stwi.t4_orchestrator.auth import PrincipalRole, ServerPrincipal
from stwi.t4_orchestrator.network_context import (
    AuthorizedNetworkContextProvider,
    NetworkContextUnavailable,
)
from stwi.t4_orchestrator.ui_context import UiContextScope


class TrustedPrincipalResolver:
    def __init__(self, principal: ServerPrincipal) -> None:
        self._principal = principal

    def resolve(self, **_kwargs: object) -> ServerPrincipal:
        return self._principal


class TrustedUiContextProvider:
    def __init__(self, node_ids: tuple[str, ...]) -> None:
        self._node_ids = node_ids

    def resolve(self, *, principal: ServerPrincipal) -> UiContextScope:
        del principal
        return UiContextScope(node_ids=self._node_ids, record_decision=False)


class FailingNetworkContextProvider:
    def resolve(self, *, principal: ServerPrincipal) -> object:
        del principal
        raise NetworkContextUnavailable("internal topology detail")


class ProvisionalNetworkContextProvider(FailingNetworkContextProvider):
    is_provisional_provider = True


def build_provider(node_ids: tuple[str, ...]) -> AuthorizedNetworkContextProvider:
    topology = build_synthetic_topology()
    return AuthorizedNetworkContextProvider(
        registry=NetworkTopologyRegistry((topology,)),
        network_version=topology.network_version,
        ui_context_provider=TrustedUiContextProvider(node_ids),
    )


def production_app(provider: object) -> object:
    principal = ServerPrincipal(
        tenant_id="tenant-a",
        operator_id="operator-17",
        roles=frozenset({PrincipalRole.OPERATOR}),
    )
    return create_app(
        store=object(),
        orchestrator=object(),
        settings=RuntimeSettings(mode=RuntimeMode.PRODUCTION, job_concurrency=1),
        principal_resolver=TrustedPrincipalResolver(principal),
        dispatcher=object(),
        ui_context_provider=TrustedUiContextProvider(("node_00", "node_01")),
        network_context_provider=provider,
    )


class AuthorizedProjectionTests(unittest.TestCase):
    def test_returns_only_nodes_and_edges_inside_trusted_ui_scope(self) -> None:
        context = build_provider(("node_00", "node_01", "node_05")).resolve(
            principal=ServerPrincipal(
                tenant_id="tenant-a",
                operator_id="operator-17",
                roles=frozenset({PrincipalRole.READONLY}),
            )
        )

        self.assertEqual(
            [node.node_id for node in context.nodes],
            ["node_00", "node_01", "node_05"],
        )
        allowed = {"node_00", "node_01", "node_05"}
        self.assertTrue(context.directed_edges)
        self.assertTrue(
            all(
                edge.source_node_id in allowed and edge.target_node_id in allowed
                for edge in context.directed_edges
            )
        )
        self.assertTrue(context.synthetic)
        self.assertIn("không đại diện địa lý thực", context.geographic_claim)

    def test_unknown_or_empty_authorized_scope_fails_closed(self) -> None:
        principal = ServerPrincipal(
            tenant_id="tenant-a",
            operator_id="operator-17",
            roles=frozenset({PrincipalRole.READONLY}),
        )
        for node_ids in (("node_99",), ()):  # Empty scope is rejected by UI context.
            with self.subTest(node_ids=node_ids):
                with self.assertRaises((NetworkContextUnavailable, ValueError)):
                    build_provider(node_ids).resolve(principal=principal)


class NetworkContextApiTests(unittest.TestCase):
    def test_endpoint_returns_versions_projection_and_no_store(self) -> None:
        response = TestClient(
            production_app(build_provider(("node_00", "node_01", "node_05")))
        ).get("/api/v1/network-context")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        payload = response.json()
        self.assertEqual(payload["network_version"], "synthetic-grid-20-v1")
        self.assertEqual(payload["routing_graph_version"], "synthetic-routing-20-v1")
        self.assertEqual(payload["gcn_adjacency_version"], "mock-adjacency-20-v1")
        self.assertEqual(payload["capacity_version"], "mock-capacity-20-v1")
        self.assertEqual([node["node_id"] for node in payload["nodes"]], ["node_00", "node_01", "node_05"])
        self.assertTrue(payload["synthetic"])

    def test_provider_failure_is_redacted_and_fails_closed(self) -> None:
        response = TestClient(production_app(FailingNetworkContextProvider())).get(
            "/api/v1/network-context"
        )

        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "NETWORK_CONTEXT_UNAVAILABLE")
        self.assertNotIn("internal topology detail", str(detail))

    def test_missing_provider_fails_endpoint_closed_and_provisional_is_rejected(self) -> None:
        common = dict(
            store=object(),
            orchestrator=object(),
            settings=RuntimeSettings(mode=RuntimeMode.PRODUCTION, job_concurrency=1),
            principal_resolver=TrustedPrincipalResolver(
                ServerPrincipal(
                    tenant_id="tenant-a",
                    operator_id="operator-17",
                    roles=frozenset({PrincipalRole.ADMIN}),
                )
            ),
            dispatcher=object(),
            ui_context_provider=TrustedUiContextProvider(("node_00",)),
        )
        response = TestClient(create_app(**common)).get("/api/v1/network-context")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "NETWORK_CONTEXT_UNAVAILABLE",
        )
        with self.assertRaisesRegex(RuntimeError, "provisional NetworkContextProvider"):
            create_app(
                **common,
                network_context_provider=ProvisionalNetworkContextProvider(),
            )

    def test_nonproduction_does_not_register_endpoint(self) -> None:
        app = create_app(
            settings=RuntimeSettings(mode=RuntimeMode.TEST, job_concurrency=1),
        )
        self.assertEqual(
            TestClient(app).get("/api/v1/network-context").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
