"""Single typed catalog for the comprehensive offline demo profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DemoKind = Literal["job", "validation", "authorization", "sse", "static"]
INCIDENT_EVENT_TYPES = frozenset(
    {"accident", "flood", "lane_closure", "demand_surge", "signal_change"}
)


@dataclass(frozen=True)
class DemoScenario:
    """One reproducible capability probe and its expected public outcome."""

    name: str
    kind: DemoKind
    expected_http_status: int
    expected_terminal_status: str | None = None
    node_id: str | None = None
    profile: str | None = None
    operator_decision: str | None = None
    mandatory: bool = True
    event_type: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"job", "validation", "authorization", "sse", "static"}:
            raise ValueError("unsupported demo scenario kind")
        if not self.name or self.expected_http_status < 100:
            raise ValueError("invalid demo scenario")
        if self.kind == "job":
            if self.expected_terminal_status not in {
                "succeeded",
                "needs_review",
                "failed",
                "expired",
            }:
                raise ValueError("job demo requires a canonical terminal status")
            if not self.node_id:
                raise ValueError("job demo requires a node")
            if self.event_type is not None and self.event_type not in INCIDENT_EVENT_TYPES:
                raise ValueError("job demo requires a canonical event type")


_OFFLINE_SCENARIOS = (
    DemoScenario(
        "normal_baseline", "job", 202, "succeeded", "node_00", "safe", "approved"
    ),
    DemoScenario("safe_rejection", "job", 202, "succeeded", "node_00", "safe", "rejected"),
    DemoScenario(
        "route_recommendation",
        "job",
        202,
        "succeeded",
        "node_10",
        "refinement",
        "approved",
        event_type="signal_change",
    ),
    DemoScenario(
        "accident_any_node", "job", 202, "needs_review", "node_01", "unsafe_vc",
        "rejected", event_type="accident",
    ),
    DemoScenario(
        "flood_any_node", "job", 202, "needs_review", "node_13", "flood",
        "rejected", event_type="flood",
    ),
    DemoScenario(
        "lane_closure_any_node", "job", 202, "needs_review", "node_17",
        "lane_closure", "rejected", event_type="lane_closure",
    ),
    DemoScenario(
        "demand_surge_any_node", "job", 202, "needs_review", "node_19",
        "demand_surge", "rejected", event_type="demand_surge",
    ),
    DemoScenario(
        "route_needs_review",
        "job",
        202,
        "needs_review",
        "node_07",
        "route_no_candidates",
        "rejected",
        event_type="signal_change",
    ),
    DemoScenario("ood", "job", 202, "needs_review", "node_02", "ood", "rejected"),
    DemoScenario(
        "high_uncertainty",
        "job",
        202,
        "needs_review",
        "node_03",
        "high_uncertainty",
        "rejected",
    ),
    DemoScenario(
        "missing_citation",
        "job",
        202,
        "needs_review",
        "node_04",
        "missing_citation",
        "rejected",
    ),
    DemoScenario("dependency_failure", "job", 202, "failed", "node_11", "dependency_failure"),
    DemoScenario("deadline_exceeded", "job", 202, "expired", "node_12", "deadline_exceeded"),
    DemoScenario("invalid_scenario", "validation", 422),
    DemoScenario("tenant_scope_denied", "authorization", 403),
    DemoScenario("sse_reconnect", "sse", 200),
    DemoScenario("static_preview", "static", 200),
)


def offline_scenarios() -> tuple[DemoScenario, ...]:
    """Return the immutable, ordered offline presenter catalog."""
    names = [scenario.name for scenario in _OFFLINE_SCENARIOS]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate offline demo scenario name")
    return _OFFLINE_SCENARIOS


__all__ = ["DemoKind", "DemoScenario", "offline_scenarios"]
