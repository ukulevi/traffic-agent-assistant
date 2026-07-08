"""Phase 4 orchestrator — sequential state machine.

Implements the what-if job workflow as a sequential graph:
  baseline_forecast → scenario_forecast → rag_query → safety_loop → finalize

This is a LangGraph-inspired design but runs without the LangGraph library
dependency so that contract tests work without the [orchestrator] extras.

The workflow is fail-closed at every node:
- Any unhandled exception → failed status
- OOD or high uncertainty → needs_review (before safety loop)
- Missing legal evidence → needs_review
- Safety loop failure → needs_review
- All checks pass → succeeded (still requires human approval)

IMPORTANT: recommended_action is set ONLY on succeeded status.
           Human approval is always required before applying any action.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from stwi.config.runtime import RuntimeSettings, get_runtime_settings
from stwi.t3_knowledge.tier3_facade import T3KnowledgeTier, T3LegalEvidence
from stwi.t4_orchestrator.contracts import (
    AuditRecord,
    JobStatus,
    SafetyCheckResult,
    WhatIfJobRequest,
    WhatIfJobResult,
)
from stwi.t4_orchestrator.interfaces import (
    BaselineForecast,
    BaselineForecaster,
    LegalEvidenceProvider,
    ScenarioForecast,
    ScenarioForecaster,
)
from stwi.t4_orchestrator.fake_adapters import (
    FakeBaselineForecaster,
    FakeSurrogateForecaster,
    SurrogateScenario,
)
from stwi.t4_orchestrator.safety_loop import CounterfactualSafetyLoop

logger = logging.getLogger(__name__)

CORPUS_PARSER_VERSION = "1.0.0"
MODEL_VERSION = "provisional_mock_v1"
DATA_VERSION = "synthetic_mock_phase4"


@dataclass
class OrchestratorState:
    """Mutable state passed through the workflow graph."""

    job_id: str
    request: WhatIfJobRequest
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Node outputs
    baseline_results: list[BaselineForecast] = field(default_factory=list)
    scenario_results: list[ScenarioForecast] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    safety_checks: list[SafetyCheckResult] = field(default_factory=list)
    safety_passed: bool = False

    # Terminal state
    status: JobStatus = JobStatus.RUNNING
    needs_review_reason: str | None = None
    error_message: str | None = None


class WhatIfOrchestrator:
    """Sequential what-if scenario orchestrator.

    Connects: Baseline (T2) → Surrogate (T2) → RAG (T3) → Safety → Finalize

    All adapters default to fake/in-memory for Phase 4.
    Swap in real adapters when Docker services are available.
    """

    def __init__(
        self,
        baseline: BaselineForecaster | None = None,
        surrogate: ScenarioForecaster | None = None,
        t3: LegalEvidenceProvider | None = None,
        surrogate_node_overrides: dict[str, SurrogateScenario] | None = None,
        settings: RuntimeSettings | None = None,
        timeout_seconds: float = 180.0,
    ) -> None:
        self._settings = settings or get_runtime_settings()
        if not self._settings.allow_provisional_adapters and (
            baseline is None or surrogate is None or t3 is None
        ):
            raise RuntimeError(
                "Production runtime requires explicit baseline, surrogate, and "
                "T3 adapters; provisional fake defaults are disabled."
            )
        self._baseline = baseline
        self._surrogate = surrogate
        self._t3 = t3
        self._timeout_seconds = timeout_seconds

    def run(self, job_id: str, request: WhatIfJobRequest) -> WhatIfJobResult:
        """Execute the full what-if workflow and return the job result."""
        state = OrchestratorState(job_id=job_id, request=request)
        import asyncio

        start_time = datetime.now(timezone.utc)

        def check_timeout() -> None:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed >= self._timeout_seconds:
                raise TimeoutError("Job execution exceeded hard deadline")

        try:
            check_timeout()
            self._node_baseline(state)
            
            check_timeout()
            self._node_scenario(state)

            # Fail-closed: OOD or high uncertainty → needs_review immediately
            if state.status in (JobStatus.NEEDS_REVIEW, JobStatus.FAILED, JobStatus.EXPIRED):
                return self._finalize(state)

            check_timeout()
            self._node_rag(state)

            # Fail-closed: missing legal evidence → needs_review
            if state.status in (JobStatus.NEEDS_REVIEW, JobStatus.FAILED, JobStatus.EXPIRED):
                return self._finalize(state)

            check_timeout()
            self._node_safety(state)
            
            check_timeout()

        except (TimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("Job %s timed out/expired: %s", job_id, exc)
            state.status = JobStatus.EXPIRED
            state.needs_review_reason = "timeout"
            state.error_message = str(exc)
        except Exception as exc:
            logger.exception("Orchestrator node raised unhandled exception: %s", exc)
            state.status = JobStatus.FAILED
            state.error_message = f"Internal error: {exc}"

        return self._finalize(state)

    # -------------------------------------------------------------------------
    # Graph nodes
    # -------------------------------------------------------------------------

    def _node_baseline(self, state: OrchestratorState) -> None:
        """Run baseline GCN-LSTM forecast (30-min no-intervention)."""
        req = state.request
        state.baseline_results = self._baseline.predict(
            node_ids=req.node_ids,
            horizons_minutes=req.horizons_minutes,
            scenario_time=req.scenario_time,
        )
        logger.info(
            "Baseline forecast: %d results for job %s",
            len(state.baseline_results),
            state.job_id,
        )

    def _node_scenario(self, state: OrchestratorState) -> None:
        """Run surrogate forecast with candidate action; check OOD/uncertainty."""
        req = state.request
        state.scenario_results = self._surrogate.predict(
            node_ids=req.node_ids,
            horizons_minutes=req.horizons_minutes,
            candidate_action=req.candidate_action,
            scenario_time=req.scenario_time,
        )

        max_ood = self._surrogate.max_ood_score(state.scenario_results)
        max_unc = self._surrogate.max_uncertainty(state.scenario_results)

        # Pre-safety fail-closed gates (from t2_forecast/safety.py gate policy)
        from stwi.t2_forecast.safety import gate_surrogate_result
        gate = gate_surrogate_result(
            uncertainty_score=max_unc,
            uncertainty_threshold=0.7,
            ood_score=max_ood,
            ood_threshold=0.5,
        )
        if gate.status == "needs_review":
            state.status = JobStatus.NEEDS_REVIEW
            state.needs_review_reason = gate.reason
            logger.warning(
                "Surrogate gate blocked job %s: %s (ood=%.3f, unc=%.3f)",
                state.job_id,
                gate.reason,
                max_ood,
                max_unc,
            )

    def _node_rag(self, state: OrchestratorState) -> None:
        """Query T3 Knowledge Tier for legal evidence."""
        req = state.request
        evidence = self._t3.query_legal_evidence(
            query_text=req.scenario_query,
            scenario_time=req.scenario_time,
            jurisdiction=req.jurisdiction,
        )

        if isinstance(evidence, T3LegalEvidence) and evidence.is_sufficient():
            state.citations = [
                {
                    "document_id": c.document_id,
                    "document_number": c.document_number,
                    "provision": c.provision,
                    "source_url": c.source_url,
                    "supporting_excerpt": c.supporting_excerpt,
                    "effective_from": c.effective_from.isoformat(),
                    "jurisdiction": c.jurisdiction,
                }
                for c in evidence.citations
            ]
            logger.info(
                "RAG: %d citations found for job %s",
                len(state.citations),
                state.job_id,
            )
        else:
            # Missing evidence → fail-closed
            reason = (
                evidence.message
                if hasattr(evidence, "message")
                else "no_legal_evidence"
            )
            state.status = JobStatus.NEEDS_REVIEW
            state.needs_review_reason = f"missing_legal_evidence: {reason}"
            logger.warning("RAG found no legal evidence for job %s", state.job_id)

    def _node_safety(self, state: OrchestratorState) -> None:
        """Run Counterfactual Safety Loop (max 3 iterations)."""
        loop = CounterfactualSafetyLoop(
            surrogate=self._surrogate,
            vc_threshold=state.request.vc_threshold,
        )
        outcome = loop.run(
            scenario_results=state.scenario_results,
            has_citations=len(state.citations) > 0,
        )
        state.safety_checks = outcome.checks
        state.safety_passed = outcome.passed

        if outcome.passed:
            state.status = JobStatus.SUCCEEDED
        else:
            state.status = JobStatus.NEEDS_REVIEW
            state.needs_review_reason = outcome.fail_reason

    # -------------------------------------------------------------------------
    # Finalize
    # -------------------------------------------------------------------------

    def _finalize(self, state: OrchestratorState) -> WhatIfJobResult:
        """Build the immutable WhatIfJobResult from workflow state."""
        req = state.request
        now = datetime.now(timezone.utc)

        audit = AuditRecord(
            trace_id=state.trace_id,
            job_id=state.job_id,
            tenant_id=req.tenant_id,
            scenario_time=req.scenario_time,
            model_version=MODEL_VERSION,
            corpus_parser_version=CORPUS_PARSER_VERSION,
            status=state.status,
            status_reason=state.needs_review_reason or state.error_message or state.status.value,
            safety_iterations=len(state.safety_checks),
        )

        baseline_summary = self._summarize_baseline(state.baseline_results)
        scenario_summary = self._summarize_scenario(state.scenario_results)

        # Action field semantics per contract
        if state.status == JobStatus.SUCCEEDED:
            recommended_action = self._operator_action_payload(
                req.candidate_action,
                executable=False,
                action_kind="recommended_action",
            )
            candidate_action_field = None
        elif state.status == JobStatus.NEEDS_REVIEW:
            recommended_action = None
            candidate_action_field = self._operator_action_payload(
                req.candidate_action,
                executable=False,
                action_kind="candidate_action",
            )
        else:
            recommended_action = None
            candidate_action_field = None

        return WhatIfJobResult(
            job_id=state.job_id,
            status=state.status,
            tenant_id=req.tenant_id,
            scenario_time=req.scenario_time,
            recommended_action=recommended_action,
            candidate_action=candidate_action_field,
            citations=state.citations,
            needs_review_reason=state.needs_review_reason,
            baseline_summary=baseline_summary,
            scenario_summary=scenario_summary,
            safety_iterations=len(state.safety_checks),
            safety_checks=state.safety_checks,
            audit_record=audit,
            model_version=MODEL_VERSION,
            data_version=DATA_VERSION,
            completed_at=now,
        )

    def _operator_action_payload(
        self,
        action: dict[str, Any],
        executable: bool,
        action_kind: str,
    ) -> dict[str, Any]:
        """Attach decision-support guardrails to an operator-facing action."""
        return {
            **action,
            "action_kind": action_kind,
            "executable": executable,
            "requires_operator_approval": True,
            "automatic_actuation": False,
        }

    def _summarize_baseline(
        self, results: list[BaselineForecast]
    ) -> dict[str, Any] | None:
        if not results:
            return None
        return {
            "node_count": len({r.node_id for r in results}),
            "horizon_count": len({r.horizon_minutes for r in results}),
            "avg_volume": round(
                sum(r.predicted_volume for r in results) / len(results), 2
            ),
            "avg_speed": round(
                sum(r.predicted_speed for r in results) / len(results), 2
            ),
            "warning": results[0].warning,
        }

    def _summarize_scenario(
        self, results: list[ScenarioForecast]
    ) -> dict[str, Any] | None:
        if not results:
            return None
        return {
            "node_count": len({r.node_id for r in results}),
            "max_vc_ratio": round(max(r.vc_ratio for r in results), 4),
            "max_uncertainty": round(max(r.uncertainty_score for r in results), 4),
            "max_ood_score": round(max(r.ood_score for r in results), 4),
            "avg_volume": round(
                sum(r.predicted_volume for r in results) / len(results), 2
            ),
            "avg_speed": round(
                sum(r.predicted_speed for r in results) / len(results), 2
            ),
            "warning": results[0].warning,
        }


__all__ = ["WhatIfOrchestrator", "OrchestratorState"]
