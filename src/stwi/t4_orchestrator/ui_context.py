"""Trusted, read-only dashboard bootstrap boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, StrictBool

from stwi.t4_orchestrator.auth import PrincipalRole, ServerPrincipal


class UiContextResolutionError(RuntimeError):
    """Raised when trusted UI scope cannot be resolved safely."""


@dataclass(frozen=True)
class UiContextScope:
    """Network scope and bounded capabilities resolved on the server."""

    node_ids: tuple[str, ...]
    record_decision: bool

    def __post_init__(self) -> None:
        if not 1 <= len(self.node_ids) <= 20:
            raise ValueError("UI context requires between 1 and 20 nodes")
        if any(
            not isinstance(node_id, str)
            or not node_id
            or node_id.strip() != node_id
            for node_id in self.node_ids
        ):
            raise ValueError("UI context node IDs must be non-empty canonical strings")
        if len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("UI context node IDs must be unique")
        if type(self.record_decision) is not bool:
            raise ValueError("record_decision must be a strict boolean")


class UiContextProvider(Protocol):
    """Resolve allowlisted UI scope for a trusted server principal."""

    def resolve(self, *, principal: ServerPrincipal) -> UiContextScope:
        ...


class UiCapabilities(BaseModel):
    """Capabilities safe to expose to the dashboard."""

    model_config = ConfigDict(extra="forbid")

    record_decision: StrictBool


class UiContextResponse(BaseModel):
    """Canonical wire response for production dashboard bootstrap."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["production"] = "production"
    tenant_id: str
    operator_id: str
    roles: list[PrincipalRole]
    node_ids: list[str]
    capabilities: UiCapabilities


__all__ = [
    "UiCapabilities",
    "UiContextProvider",
    "UiContextResolutionError",
    "UiContextResponse",
    "UiContextScope",
]
