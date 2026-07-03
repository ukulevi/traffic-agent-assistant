# Linear issue plan for STWI Symphony

Use these issues in the Linear project configured by `WORKFLOW.md`. Every issue
that Symphony may run must include both `stwi-agent` and `symphony-approved`.
Add one lane label so the workflow can assign ownership predictably.

## Required labels

| Purpose | Labels |
|---|---|
| Dispatch gate | `stwi-agent`, `symphony-approved` |
| Lane | `lane:data`, `lane:vision`, `lane:ml`, `lane:simulation`, `lane:rag`, `lane:legal`, `lane:api`, `lane:frontend`, `lane:qa`, `lane:release` |
| Phase | `phase:1`, `phase:2`, `phase:3`, `phase:4` |
| Task type | `task:review`, `task:validate`, `task:qa`, `task:refactor` |
| Review gate | `needs-human-review`, `contract-risk`, `legal-review`, `external-service` |
| Explicit approval | `external-service-approved`, `release-action-approved`, `contract-change-approved` |

## Initial Symphony backlog

### STWI-SYM-001 — Reconcile official vision artifact with current promotion gate

Labels: `stwi-agent`, `symphony-approved`, `lane:vision`, `phase:1`, `task:review`, `needs-human-review`

Acceptance criteria:

- Decide whether the current detector remains `official_mvp_primary`, becomes
  provisional, or must be retrained.
- Record the decision without weakening privacy or aggregate-only constraints.
- Keep promotion criteria consistent with `scripts/training/promote_vision_model.py`.

Expected owner: DataVisionAgent.

### STWI-SYM-003 — Replace Phase 2 mock observations with real aggregate dataset

Labels: `stwi-agent`, `symphony-approved`, `lane:ml`, `lane:simulation`, `phase:2`, `task:review`

Acceptance criteria:

- Chronological split is recorded.
- Scaler is fit only on training split.
- Forecast metrics are reported by horizon, node, and missing bucket.

Expected owner: MLSimulationAgent.

### STWI-SYM-004 — Rerun surrogate calibration and OOD thresholds on non-mock validation data

Labels: `stwi-agent`, `symphony-approved`, `lane:simulation`, `phase:2`, `task:validate`

Acceptance criteria:

- Calibration report uses held-out validation data.
- OOD/high uncertainty returns `needs_review`.
- Retrieved cases are never blended into online input.

Expected owner: MLSimulationAgent.

### STWI-SYM-006 — Ingest approved SOP corpus and validate citation coverage

Labels: `stwi-agent`, `symphony-approved`, `lane:rag`, `lane:legal`, `phase:3`, `task:review`, `legal-review`

Acceptance criteria:

- SOP corpus has source registry, effective date, and content hash.
- Unsupported claim rate is zero after validator/abstention.
- Citation precision target is measured against the evaluation set.

Expected owner: KnowledgeRagAgent.

### STWI-SYM-007 — Switch Phase 3 validation from fake retriever to Qdrant/BGE path

Labels: `stwi-agent`, `symphony-approved`, `lane:rag`, `phase:3`, `task:validate`, `external-service`

Acceptance criteria:

- Qdrant-backed retrieval runs in the integration harness.
- BGE-m3 embedding path is documented and tested.
- Service-dependent skips are reduced or explicitly justified.

Expected owner: KnowledgeRagAgent.

### STWI-SYM-008 — Implement production job persistence with Celery and Redis

Labels: `stwi-agent`, `symphony-approved`, `lane:api`, `phase:4`, `task:review`

Acceptance criteria:

- Jobs are queued and executed by Celery worker.
- Progress and events are persisted in Redis.
- SSE reconnect does not duplicate execution.

Expected owner: OrchestratorAgent.

### STWI-SYM-010 — Build operator dashboard or explicitly scope it out of demo

Labels: `stwi-agent`, `symphony-approved`, `lane:frontend`, `phase:4`, `task:review`, `needs-human-review`

Acceptance criteria:

- Dashboard scope is approved by user.
- If implemented, UI shows job status, citations, warnings, versions,
  `trace_id`, and approval state.
- If deferred, docs and demo script clearly state the limitation.

Expected owner: FrontendAgent.

### STWI-SYM-011 — Run full release QA after current refactor changes are settled

Labels: `stwi-agent`, `symphony-approved`, `lane:qa`, `lane:release`, `task:qa`

Acceptance criteria:

- Docs validator, contract tests, JavaScript checks, slide static check, and
  `git diff --check` pass.
- Skipped tests and unverified service paths are listed.
- No cache/build artifact is staged.

Expected owner: ReleaseQaAgent.

## Roadmap intelligence backlog

These issues come from `roadmap_intelligence_2026-07-03.md`. They turn
external agent reports into reviewable work without changing STWI core
invariants. Do not implement new providers, services, dependencies, SLA
thresholds, tensor/API semantics, or safety policy from these issues unless a
follow-up Human Review explicitly approves the change.

### STWI-SYM-016 - Reconcile readiness scoring and progress evidence

Labels: `stwi-agent`, `symphony-approved`, `lane:qa`, `task:review`

Acceptance criteria:

- Progress estimates are derived from board state, gate criteria, and verified
  checks instead of raw agent-report percentages.
- Stale test counts are replaced or explicitly marked stale.
- A single readiness summary is available for Symphony/Linear handoff.

Expected owner: LeadCoordinator.

### STWI-SYM-017 - Draft auth, RBAC, and tenant-boundary design

Labels: `stwi-agent`, `lane:api`, `phase:4`, `task:review`, `needs-human-review`, `contract-risk`

Acceptance criteria:

- Design derives operator identity and tenant context server-side instead of
  trusting request body fields.
- Role boundaries for `operator`, `analyst`, `admin`, and `readonly` are
  specified without choosing a new identity provider.
- No auth dependency, external IdP, or API schema change is implemented before
  Human Review approval.

Expected owner: OrchestratorReleaseAgent.

### STWI-SYM-018 - Specify observability minimum for trace, logs, and metrics

Labels: `stwi-agent`, `symphony-approved`, `lane:api`, `phase:4`, `task:review`

Acceptance criteria:

- Required `trace_id`, job timing, model/data/policy version, status
  transition, and safety reason fields are listed.
- Metric names are specified for job counts, job latency, safety loop outcomes,
  retrieval latency, and surrogate latency.
- Prometheus, OpenTelemetry, or other observability services remain optional
  future deployment choices until explicitly approved.

Expected owner: OrchestratorReleaseAgent.

### STWI-SYM-019 - Define project-native model registry evidence format

Labels: `stwi-agent`, `symphony-approved`, `lane:ml`, `phase:2`, `task:review`

Acceptance criteria:

- Evidence schema covers model version, dataset version, checksum, metrics,
  calibration, benchmark profile, thresholds, and promotion decision.
- The format works for vision, baseline forecast, and surrogate artifacts
  without requiring MLflow.
- Existing promotion and validation paths either produce or validate the
  required fields.

Expected owner: MLSimulationAgent.

### STWI-SYM-020 - Document fail-closed resilience policy for dependency failures

Labels: `stwi-agent`, `symphony-approved`, `lane:api`, `phase:4`, `task:review`, `contract-risk`

Acceptance criteria:

- Retries, timeout, circuit-breaker-style behavior, and dependency failure
  classes map to `needs_review`, `failed`, or `expired`.
- No runtime path returns an executable action after tool, RAG, TimescaleDB,
  Qdrant, Celery, Redis, or model failure.
- The rejected fail-open wording is replaced with an explicit fail-closed
  policy and focused tests are identified.

Expected owner: OrchestratorReleaseAgent.

### STWI-SYM-021 - Review production deployment options without changing the approved stack

Labels: `stwi-agent`, `lane:release`, `phase:4`, `task:review`, `needs-human-review`, `contract-risk`

Acceptance criteria:

- Docker Compose production, Kubernetes, and managed-service options are
  compared as deployment options only.
- No Kubernetes, secrets manager, tracing, or model-serving framework is added
  to active architecture.
- The recommendation lists cost, complexity, safety, rollback, and Human Review
  requirements for a later decision.

Expected owner: ReleaseQaAgent.

## RTSP real-time test backlog

Do not paste live RTSP endpoints into Linear issues, repository files, logs, or
manifests. Use source alias `edge_camera_1`; provide the actual endpoint only
through the local `STWI_RTSP_URL` environment variable during a human-supervised
run.

### STWI-RTSP-001 - Prepare RTSP source alias and capture guardrails for edge_camera_1

Labels: `stwi-agent`, `symphony-approved`, `lane:data`, `phase:1`, `task:validate`

Acceptance criteria:

- `edge_camera_1` is accepted as a safe source id and unsafe source ids remain
  rejected.
- Capture path continues reading the endpoint only from `STWI_RTSP_URL`.
- Command output and manifests do not include the RTSP endpoint, credentials,
  image base64, or raw video paths.
- Focused tests cover URL validation, missing env handling, safe source id,
  and fail-closed behavior without opening a live stream.

Expected owner: DataVisionAgent.

### STWI-RTSP-002 - Document supervised RTSP-to-quarantine smoke test procedure

Labels: `stwi-agent`, `symphony-approved`, `lane:vision`, `phase:1`, `task:review`

Acceptance criteria:

- Runbook explains how an operator sets `STWI_RTSP_URL` locally without writing
  it to repo, Linear, logs, or manifests.
- Procedure captures only sparse frames into `data/quarantine/rtsp_frames` and
  never stores a raw video container.
- Procedure lists privacy review, retention, cleanup, and aggregate-only next
  steps before any frame leaves quarantine.
- Procedure includes the exact verification commands that can run offline after
  capture.

Expected owner: DataVisionAgent.

### STWI-RTSP-003 - Run supervised live RTSP smoke test for edge_camera_1

Labels: `stwi-agent`, `lane:data`, `phase:1`, `task:review`, `needs-human-review`, `external-service`

Default Linear state: `In Review` (Human Review gate; not Symphony-active).

Acceptance criteria:

- Human operator confirms the RTSP endpoint is approved for STWI testing and
  sets it only in `STWI_RTSP_URL`.
- Live capture is bounded to a small sample, stores sparse frames only in
  quarantine, and retains no raw video.
- Manifest is reviewed to confirm no endpoint, credentials, image base64, or
  raw video reference is present.
- Resulting evidence is either deleted, kept in quarantine for privacy review,
  or converted into approved aggregate-only evidence by a follow-up issue.

Expected owner: DataVisionAgent with human supervision.
