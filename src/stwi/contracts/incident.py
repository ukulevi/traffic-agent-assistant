"""Typed, non-executable incident hypotheses for STWI what-if jobs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from stwi.contracts.project import load_project_contract


_INCIDENT_CONTRACT = load_project_contract()["incident_contract"]
_BOUNDS = _INCIDENT_CONTRACT["bounds"]

IncidentType = StrEnum(
    "IncidentType",
    {value.upper(): value for value in _INCIDENT_CONTRACT["event_types"]},
)
IncidentSeverity = StrEnum(
    "IncidentSeverity",
    {value.upper(): value for value in _INCIDENT_CONTRACT["severity_levels"]},
)


class SignalPlanDelta(BaseModel):
    """Bounded signal-plan hypothesis; never an executable controller command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    green_time_ratio_delta: float = Field(
        ...,
        strict=True,
        ge=_BOUNDS["green_time_ratio_delta"]["min"],
        le=_BOUNDS["green_time_ratio_delta"]["max"],
    )


class IncidentVector(BaseModel):
    """One typed synthetic incident hypothesis for the MVP analysis scope."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    event_type: IncidentType
    affected_node_ids: tuple[str, ...] = Field(
        ...,
        min_length=_INCIDENT_CONTRACT["affected_nodes"]["min"],
        max_length=_INCIDENT_CONTRACT["affected_nodes"]["max"],
    )
    severity: IncidentSeverity
    duration_minutes: int = Field(
        ...,
        strict=True,
        ge=_BOUNDS["duration_minutes"]["min"],
        le=_BOUNDS["duration_minutes"]["max"],
    )
    description: str = Field(
        ...,
        min_length=_BOUNDS["description_length"]["min"],
        max_length=_BOUNDS["description_length"]["max"],
    )
    lane_closure_ratio: float | None = Field(
        None,
        strict=True,
        ge=_BOUNDS["lane_closure_ratio"]["min"],
        le=_BOUNDS["lane_closure_ratio"]["max"],
    )
    demand_multiplier: float | None = Field(
        None,
        strict=True,
        gt=_BOUNDS["demand_multiplier"]["exclusive_min"],
        le=_BOUNDS["demand_multiplier"]["max"],
    )
    signal_plan_delta: SignalPlanDelta | None = None

    @field_validator("affected_node_ids")
    @classmethod
    def validate_affected_nodes(cls, node_ids: tuple[str, ...]) -> tuple[str, ...]:
        if any(not node_id or node_id.strip() != node_id for node_id in node_ids):
            raise ValueError("affected_node_ids must contain canonical node IDs")
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("affected_node_ids must be unique")
        return node_ids

    @model_validator(mode="after")
    def validate_event_parameters(self) -> IncidentVector:
        required_field = {
            IncidentType.LANE_CLOSURE: "lane_closure_ratio",
            IncidentType.DEMAND_SURGE: "demand_multiplier",
            IncidentType.SIGNAL_CHANGE: "signal_plan_delta",
        }.get(self.event_type)
        parameter_fields = (
            "lane_closure_ratio",
            "demand_multiplier",
            "signal_plan_delta",
        )
        for field_name in parameter_fields:
            value = getattr(self, field_name)
            if field_name == required_field and value is None:
                raise ValueError(
                    f"{self.event_type.value} requires {required_field}"
                )
            if field_name != required_field and value is not None:
                raise ValueError(
                    f"{field_name} is not valid for {self.event_type.value}"
                )
        return self


__all__ = [
    "IncidentSeverity",
    "IncidentType",
    "IncidentVector",
    "SignalPlanDelta",
]
