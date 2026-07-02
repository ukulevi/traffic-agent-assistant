"""Tier 4 — LangGraph workflow, async API, and Counterfactual Safety Loop."""

from stwi.t4_orchestrator.contracts import (
    AuditRecord,
    JobEnvelope,
    JobStatus,
    SafetyCheckResult,
    WhatIfJobRequest,
    WhatIfJobResult,
)
from stwi.t4_orchestrator.interfaces import (
    BaselineForecaster,
    JobStore,
    LegalEvidenceProvider,
    ScenarioForecaster,
)
from stwi.t4_orchestrator.fake_adapters import (
    FakeBaselineForecaster,
    FakeSurrogateForecaster,
    SurrogateScenario,
    high_uncertainty_scenario,
    ood_scenario,
    safe_scenario,
    unsafe_vc_scenario,
)
from stwi.t4_orchestrator.job_store import InMemoryJobStore, get_job_store
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator
from stwi.t4_orchestrator.safety_loop import CounterfactualSafetyLoop

__all__ = [
    # Contracts
    "JobStatus",
    "WhatIfJobRequest",
    "WhatIfJobResult",
    "AuditRecord",
    "SafetyCheckResult",
    "JobEnvelope",
    "BaselineForecaster",
    "ScenarioForecaster",
    "LegalEvidenceProvider",
    "JobStore",
    # Fake adapters
    "FakeBaselineForecaster",
    "FakeSurrogateForecaster",
    "SurrogateScenario",
    "safe_scenario",
    "unsafe_vc_scenario",
    "ood_scenario",
    "high_uncertainty_scenario",
    # Core
    "CounterfactualSafetyLoop",
    "WhatIfOrchestrator",
    "InMemoryJobStore",
    "get_job_store",
]
