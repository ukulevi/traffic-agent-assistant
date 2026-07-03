# Roadmap intelligence review - 2026-07-03

## Purpose

This note converts external agent progress/readiness reports into controlled
roadmap input. It is not a source of truth, does not replace
`project_contract.json`, and must not be used to change STWI invariants without
Human Review.

Reference inputs reviewed:

- `claude_progress_assessment.md`
- `claude_production_readiness_analysis.md`
- `ProgressAssessment_2026_07_03.md`

Keep those raw reports unstaged unless they are sanitized, de-duplicated, and
clearly marked as non-canonical review input.

## Non-negotiable guardrails

Any roadmap update derived from these reports must preserve the current STWI
contract:

- STWI remains decision support only; no automatic field-device actuation.
- No raw video retention or publication.
- MVP scale remains 20 functional nodes, up to 20 recorded/RTSP camera streams,
  and 1,000 synthetic aggregate producers for load testing.
- Tensor and forecast contracts remain `X[B,12,N,16]`, `M[B,12,N,16]`,
  `A[N,N]`, and `Y[B,6,N,2]`.
- The active stack remains TimescaleDB, Qdrant, BGE-m3, LangGraph, Celery,
  Redis, FastAPI, and SSE.
- Safety, OOD, legal evidence, timeout, and uncertainty failures fail closed.
- `needs_review` may expose only a non-executable `candidate_action`;
  only `succeeded` may expose `recommended_action`.
- Retrieved cases may provide evidence, but must never be blended into online
  surrogate inputs.
- New infrastructure, services, dependencies, identity providers, model
  registries, or observability stacks require an explicit approved issue before
  implementation.

The phrase "fail-open" from the production-readiness report is rejected for
STWI runtime policy. The acceptable form is fail closed to `needs_review`,
`failed`, or `expired` with auditable reason codes and no executable action.

## Evidence normalization

The three reports disagree on readiness. One report estimates roughly 80%
completion while another estimates roughly 45-55%. Treat these as heuristics,
not project status.

For roadmap decisions, readiness must be derived from:

1. `docs/project_management/symphony/board.json`
2. gate acceptance criteria in the canonical docs
3. local verification output from the current review pass
4. unresolved blockers recorded in the issue board

The latest full local verification observed during this staging pass was:

- `python -m unittest discover -s tests`: 287 tests passed, 48 skipped
- `python scripts/validation/validate_docs.py`: passed
- `python scripts/validation/validate_ci_guardrails.py`: passed
- `python -m unittest tests.contracts.test_project_contract`: passed
- `node --check slides/js/presentation.js`: passed
- `node --check slides/js/presentation-tools.js`: passed
- `git diff --check`: passed after whitespace fixes

Older report claims such as "293 passed, 11 skipped" should be replaced after
the next QA run or explicitly labeled stale.

## Roadmap signals to keep

These items are useful because they align with current MVP gaps or phase gates:

| Signal | Current handling |
|---|---|
| Celery plus Redis production job execution and persistence | Already tracked by `STWI-SYM-008`; keep as Phase 4 P1. |
| Real aggregate dataset for Phase 2 | Already tracked by `STWI-SYM-003`; keep chronological split and scaler evidence as acceptance criteria. |
| Surrogate calibration, OOD thresholds, and benchmark evidence | Already tracked by `STWI-SYM-004` and `STWI-SYM-005`; do not claim SLA without profile evidence. |
| Qdrant/BGE integration path | Already tracked by `STWI-SYM-007`; service-dependent skips must be justified. |
| Approved SOP corpus and citation coverage | Already tracked by `STWI-SYM-006`; legal review remains required. |
| Dashboard scope | Already tracked by `STWI-SYM-010`; either build minimal operator UI or document demo limitation. |
| Vision artifact metadata, thresholds, latency, ROI, license/source | Already tracked by `STWI-SYM-013` to `STWI-SYM-015`. |

## Candidate future issues

These should be considered only after the current dirty-tree review batch is
merged or deliberately split. They are roadmap proposals, not active contract
changes.

| Candidate | Scope |
|---|---|
| `STWI-SYM-016` Reconcile readiness scoring | Define one progress metric based on gates, board state, and verified test output; remove conflicting percent estimates. |
| `STWI-SYM-017` Auth, RBAC, and tenant-boundary design | Draft a minimal production boundary for operator identity, roles, tenant derivation, and audit without implementing a new identity provider yet. |
| `STWI-SYM-018` Observability minimum | Specify trace IDs, structured logs, and metrics names first; defer Prometheus/OpenTelemetry deployment until approved. |
| `STWI-SYM-019` Model registry evidence format | Define required fields for model version, dataset version, checksum, metrics, calibration, and promotion decision; prefer project-native metadata before proposing MLflow. |
| `STWI-SYM-020` Fail-closed resilience policy | Document retries, circuit-breaker style behavior, and dependency failure mapping to `needs_review`/`failed` without fail-open fallback. |
| `STWI-SYM-021` Production deployment options review | Compare Docker Compose production, Kubernetes, and managed services as options only; no stack change without user approval. |

## How to consume future agent reports

1. Extract claims into issue-sized proposals.
2. Reject or rewrite any claim that weakens fail-closed behavior, human
   approval, citation validation, API semantics, tensor shapes, or MVP scale.
3. Replace local `file:///...` links with repository-relative paths before
   committing any report-derived document.
4. Convert readiness percentages into gate-backed status summaries.
5. Keep broad production recommendations in roadmap notes until an approved
   issue defines acceptance criteria and required verification.
