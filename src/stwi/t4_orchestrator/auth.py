"""Server-principal boundary for the STWI API.

Production composition must supply a resolver backed by a trusted upstream
identity boundary. The provisional resolver exists only for deterministic
development, test, and demo flows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class PrincipalRole(str, Enum):
    OPERATOR = "operator"
    ANALYST = "analyst"
    ADMIN = "admin"
    READONLY = "readonly"


class PrincipalResolutionError(ValueError):
    """Raised when trusted server identity context is unavailable."""


@dataclass(frozen=True)
class ServerPrincipal:
    """Identity and tenant scope resolved by the server, not API payloads."""

    tenant_id: str
    operator_id: str
    roles: frozenset[PrincipalRole]

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.operator_id or not self.roles:
            raise PrincipalResolutionError("principal requires tenant, operator, and role")

    def has_any_role(self, *roles: PrincipalRole) -> bool:
        return bool(self.roles.intersection(roles))


class PrincipalResolver(Protocol):
    """Resolve a principal from a trusted server-side boundary."""

    def resolve(
        self,
        *,
        tenant_hint: str | None = None,
        operator_hint: str | None = None,
    ) -> ServerPrincipal:
        ...


@dataclass(frozen=True)
class StaticPrincipalResolver:
    """Deterministic principal adapter for focused tests only."""

    principal: ServerPrincipal
    is_provisional_resolver = True

    def resolve(
        self,
        *,
        tenant_hint: str | None = None,
        operator_hint: str | None = None,
    ) -> ServerPrincipal:
        return self.principal


class ProvisionalBodyPrincipalResolver:
    """Explicit non-production resolver for offline demo and test adapters."""

    is_provisional_resolver = True

    def resolve(
        self,
        *,
        tenant_hint: str | None = None,
        operator_hint: str | None = None,
    ) -> ServerPrincipal:
        if not tenant_hint:
            raise PrincipalResolutionError("provisional resolver requires tenant hint")
        return ServerPrincipal(
            tenant_id=tenant_hint,
            operator_id=operator_hint or "provisional-operator",
            roles=frozenset({PrincipalRole.OPERATOR, PrincipalRole.ANALYST}),
        )


class EnvBoundPrincipalResolver:
    """Deployment-bound principal resolver for the production profile.

    Identity comes from server-side deployment configuration (environment
    bound at container start), never from request payloads. The deployment
    owns exactly one trusted service identity; requests inherit it, so
    tenant hints from callers cannot cross tenant boundaries.

    Not provisional: production composition accepts this resolver.
    """

    def __init__(self, environ: Mapping[str, str]) -> None:
        tenant_id = environ.get("STWI_DEPLOYMENT_TENANT_ID", "").strip()
        operator_id = environ.get("STWI_DEPLOYMENT_OPERATOR_ID", "").strip()
        roles_raw = environ.get("STWI_DEPLOYMENT_ROLES", "").strip()
        if not tenant_id or not operator_id:
            raise PrincipalResolutionError(
                "deployment identity requires STWI_DEPLOYMENT_TENANT_ID "
                "and STWI_DEPLOYMENT_OPERATOR_ID"
            )
        try:
            roles = frozenset(
                PrincipalRole(role.strip())
                for role in roles_raw.split(",")
                if role.strip()
            )
        except ValueError as exc:
            raise PrincipalResolutionError(
                "deployment roles contain an unknown role name"
            ) from exc
        if not roles:
            raise PrincipalResolutionError("deployment identity requires a role")
        self._principal = ServerPrincipal(
            tenant_id=tenant_id,
            operator_id=operator_id,
            roles=roles,
        )

    def resolve(
        self,
        *,
        tenant_hint: str | None = None,
        operator_hint: str | None = None,
    ) -> ServerPrincipal:
        # Hints are deliberately ignored: only the deployment-bound identity
        # is authoritative. Callers cannot elevate or switch tenants.
        return self._principal


__all__ = [
    "EnvBoundPrincipalResolver",
    "PrincipalResolutionError",
    "PrincipalResolver",
    "PrincipalRole",
    "ProvisionalBodyPrincipalResolver",
    "ServerPrincipal",
    "StaticPrincipalResolver",
]
