"""Tests for the env-bound production principal resolver (TRA-68)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stwi.t4_orchestrator.auth import (  # noqa: E402
    EnvBoundPrincipalResolver,
    PrincipalResolutionError,
    PrincipalRole,
)


VALID_ENV = {
    "STWI_DEPLOYMENT_TENANT_ID": "tenant-alpha",
    "STWI_DEPLOYMENT_OPERATOR_ID": "operator-7",
    "STWI_DEPLOYMENT_ROLES": "operator,analyst",
}


class TestEnvBoundPrincipalResolver(unittest.TestCase):
    def test_resolves_deployment_identity(self):
        resolver = EnvBoundPrincipalResolver(VALID_ENV)
        principal = resolver.resolve()
        self.assertEqual(principal.tenant_id, "tenant-alpha")
        self.assertEqual(principal.operator_id, "operator-7")
        self.assertIn(PrincipalRole.OPERATOR, principal.roles)
        self.assertIn(PrincipalRole.ANALYST, principal.roles)

    def test_is_not_provisional(self):
        resolver = EnvBoundPrincipalResolver(VALID_ENV)
        self.assertFalse(getattr(resolver, "is_provisional_resolver", False))

    def test_missing_tenant_fails_closed(self):
        with self.assertRaises(PrincipalResolutionError):
            EnvBoundPrincipalResolver(
                {"STWI_DEPLOYMENT_OPERATOR_ID": "op", "STWI_DEPLOYMENT_ROLES": "operator"}
            )

    def test_missing_operator_fails_closed(self):
        with self.assertRaises(PrincipalResolutionError):
            EnvBoundPrincipalResolver(
                {"STWI_DEPLOYMENT_TENANT_ID": "t", "STWI_DEPLOYMENT_ROLES": "operator"}
            )

    def test_missing_roles_fails_closed(self):
        with self.assertRaises(PrincipalResolutionError):
            EnvBoundPrincipalResolver(
                {
                    "STWI_DEPLOYMENT_TENANT_ID": "t",
                    "STWI_DEPLOYMENT_OPERATOR_ID": "op",
                }
            )

    def test_unknown_role_fails_closed(self):
        with self.assertRaisesRegex(PrincipalResolutionError, "unknown role"):
            EnvBoundPrincipalResolver(
                {
                    **VALID_ENV,
                    "STWI_DEPLOYMENT_ROLES": "operator,superadmin",
                }
            )

    def test_tenant_hint_cannot_switch_tenant(self):
        """Caller-supplied hints must never override deployment identity."""
        resolver = EnvBoundPrincipalResolver(VALID_ENV)
        principal = resolver.resolve(
            tenant_hint="tenant-evil",
            operator_hint="attacker",
        )
        self.assertEqual(principal.tenant_id, "tenant-alpha")
        self.assertEqual(principal.operator_id, "operator-7")


if __name__ == "__main__":
    unittest.main()
