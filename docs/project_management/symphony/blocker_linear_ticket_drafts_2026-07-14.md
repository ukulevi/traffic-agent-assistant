# STWI blocker Linear ticket drafts — 2026-07-14

Status: **Draft for Human Review**
Source request: đánh giá blocker hiện tại, chuẩn bị ticket theo thứ tự ưu tiên để
chạy Symphony ở lượt sau.
This file does not create Linear issues, change issue state, or authorize a
Symphony dispatch.

## Dispatch rules

- Linear remains the operational source of truth. Reconcile existing Linear
  state before creating any new issue.
- Add `symphony-approved` only after the user explicitly approves the issue for
  dispatch. A draft with `needs-human-review`, `contract-risk`,
  `legal-review`, or `external-service` is not Symphony-active by default.
- Run one implementation issue at a time. Each issue uses an isolated
  `ticket/<linear-seed>-<short-slug>` branch/workspace.
- No ticket may change `project_contract.json`, API status semantics, the
  approved stack, legal sources, model thresholds, or the decision-support
  boundary without a separate Human Review decision.
- Workers stop at a reviewable diff. Commit, push, PR, release, live-service,
  private-data, benchmark-hardware, and production-credential actions remain
  Human Review gates.

## Pre-dispatch finding

The local mirror is stale: `STWI-SYM-026` through `STWI-SYM-028` remain
`Todo`, `STWI-SYM-029` remains `Backlog`, and the current dispatch packet still
points to `TRA-23`. The acceptance evidence says TRA-23/24/25 were merged and
TRA-26 should be in review. Dispatching before reconciliation can repeat old
work or prepare the wrong workspace.

## Priority and dependency order

| Order | Ticket | Outcome | Dispatch posture |
|---:|---|---|---|
| 0 | STWI-SYM-030 | Reconcile Linear, board mirror, and dispatch packet | First ticket; review-only |
| 1 | STWI-SYM-031 | Repair full-suite and gate/CI integrity | Demo blocker |
| 2 | STWI-SYM-032 | Enforce hard deadline and terminal-state immutability | Demo/safety blocker |
| 3 | STWI-SYM-033 | Type and validate scenario actions without API status drift | Human Review before implementation |
| 4 | STWI-SYM-034 | Fix dashboard async lifecycle and deterministic demo branches | Depends on 032, 033 |
| 5 | STWI-SYM-035 | Reconcile API/report/slides and PDF layout | Depends on 033, 034 |
| 6 | STWI-SYM-036 | Re-run hardened offline MVP demo acceptance | Depends on 031–035 |
| 7 | Existing data/ML/vision/RAG tickets | Replace provisional evidence with measured/service-backed evidence | Pilot gate |
| 8 | STWI-SYM-037 | Bind runtime provenance and safety thresholds to promoted artifacts | Depends on real/calibrated artifacts |
| 9 | STWI-SYM-038 | Harden T3 service boundary and redact internal errors | Depends on STWI-SYM-007 |
| 10 | Existing STWI-SYM-008 | Add Celery/Redis durable execution | Depends on 032 |
| 11 | STWI-SYM-039 | Prove measured end-to-end SLA | Depends on 005, 008, 037, 038 |
| 12 | STWI-SYM-040 | Implement approved auth/RBAC/tenant boundary | Blocked on approved STWI-SYM-017 design |
| 13 | STWI-SYM-041 | Build approved production deployment baseline | Depends on 008, 018, 021, 038, 040 |
| 14 | STWI-SYM-042 | Run production release-readiness QA | Final gate |

## Existing issues: amend instead of duplicating

### Vision and camera evidence

- `STWI-SYM-013` must finish the promotion metadata validator first.
- `STWI-SYM-001` then records the Human Review decision: downgrade the current
  artifact to provisional/rejected, or require retraining. Do not lower the
  `mAP50 >= 0.85` gate implicitly.
- If retraining is selected, run `STWI-SYM-015`; then run `STWI-SYM-014` with
  an approved recorded-camera input. `STWI-RTSP-003` remains Human Review.
- Add acceptance evidence that the runtime loader verifies checksum and the
  same calibration, benchmark, legal/privacy, and promotion criteria used by
  the promotion tool.

### Forecast and surrogate evidence

- Keep dependency order `STWI-SYM-003 -> STWI-SYM-004 -> STWI-SYM-005`.
- Add acceptance criteria that node order is fixed, splits are chronological,
  scenario families do not leak, scalers fit training data only, and benchmark
  evidence has `evidence_kind=measured` on the contract profile.

### Knowledge/RAG evidence

- `STWI-SYM-006` remains blocked until a human reviewer supplies approved SOP
  sources.
- Amend `STWI-SYM-007` so Gate P3 cannot pass on `FakeRetriever`; it must test
  Qdrant/BGE-m3, effective-date filtering, structured citations, and the
  Timescale read-only path. Service skips must be absent or explicitly blocked.

### Runtime and deployment prerequisites

- Amend `STWI-SYM-008` to depend on `STWI-SYM-032`; Redis/Celery must preserve
  the same terminal-state and hard-deadline rules.
- `STWI-SYM-017` and `STWI-SYM-021` remain Human Review inputs, not unattended
  implementation authorization.
- Reconcile and close/restate `STWI-SYM-026` through `STWI-SYM-029`; do not
  create duplicates for already merged TRA-23/24/25 work.

---

## STWI-SYM-030 — Reconcile Linear and Symphony state before next dispatch

**Priority / owner:** P1 / LeadCoordinator
**Labels:** `stwi-agent`, `lane:qa`, `lane:release`, `task:review`
**Dependencies:** none
**Expected state:** Human Review; add `symphony-approved` only for the selected
next implementation ticket.

**Original request:** prepare prioritized Linear tickets before running
Symphony.

**Goal:** Read current Linear state, remove stale assumptions from the local
mirror, and produce one unambiguous next dispatch packet.

**Allowed files:**

- `docs/project_management/symphony/board.json`
- `docs/project_management/symphony/board.md`
- `docs/project_management/symphony/status_report.md`
- `docs/project_management/symphony/current_dispatch_packet.md`

**Acceptance criteria:**

1. TRA-23/24/25/26 and every referenced open blocker match current Linear
   status and URL.
2. Closed/merged work is not left `Todo` or selected for dispatch.
3. The packet selects exactly one approved open issue with bounded files,
   checks, and expected final state.
4. No runtime, contract, Linear transition, commit, push, or PR action is mixed
   into this reconciliation diff.

**Exact checks:**

```powershell
python scripts/project_management/symphony_report.py
python scripts/project_management/hermes_runner_bridge.py --no-write
python scripts/project_management/worktree_intake.py --json
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
git diff --check
```

**Gap check:** `complete` after Linear readback; otherwise `blocked`.

## STWI-SYM-031 — Repair full-suite, phase-gate, and CI evidence integrity

**Priority / owner:** P1 / ReleaseQaAgent
**Labels:** `stwi-agent`, `lane:qa`, `lane:release`, `task:validate`
**Dependencies:** STWI-SYM-030
**Expected state:** Human Review.

**Goal:** Ensure local gates and CI cannot report green while the complete test
suite fails or a gate script cannot run from repository root.

**Allowed files:**

- `scripts/validation/validate_provisional_phase2_gate.py`
- `scripts/validation/gate_p3_validator.py`
- `scripts/validation/validate_surrogate_benchmark_evidence.py`
- `tests/t2_forecast/test_phase2_provisional_gate.py`
- `tests/validation/**`
- `.github/workflows/stwi-fast-ci.yml`
- `.github/workflows/stwi-manual-qa.yml`

**Acceptance criteria:**

1. Both phase-gate CLIs resolve repository paths correctly when invoked from
   root; no `ModuleNotFoundError` remains.
2. Benchmark tests distinguish measured evidence from simulated evidence and
   the current complete suite has no failing test.
3. Gate P3 does not assign unexecuted security/fake-adapter checks literal
   `True`; the report records measured pass/fail/not-verified evidence.
4. CI runs the complete lightweight suite with an explicit optional-service
   skip allowlist, while measured hardware/service gates remain Human Review.

**Exact checks:**

```powershell
python scripts/validation/validate_provisional_phase2_gate.py --help
python scripts/validation/gate_p3_validator.py --help
python -m unittest tests.t2_forecast.test_phase2_provisional_gate
python -m unittest discover -s tests -v
python scripts/validation/validate_ci_guardrails.py
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
git diff --check
```

**Gap check:** `complete`.

## STWI-SYM-032 — Enforce hard deadline and immutable terminal job states

**Priority / owner:** P1 / OrchestratorReleaseAgent
**Labels:** `stwi-agent`, `lane:api`, `phase:4`, `task:refactor`,
`contract-risk`, `reasoning:high`
**Dependencies:** STWI-SYM-030
**Expected state:** Human Review.

**Goal:** Make the 180-second hard deadline enforceable across blocking
dependencies and prevent a late worker from overwriting `expired`, `failed`,
or another terminal state.

**Allowed files:**

- `src/stwi/t4_orchestrator/orchestrator.py`
- `src/stwi/t4_orchestrator/api.py`
- `src/stwi/t4_orchestrator/job_store.py`
- `src/stwi/t4_orchestrator/interfaces.py`
- `tests/t4_orchestrator/**`
- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`

**Acceptance criteria:**

1. Every model/RAG/safety dependency has a bounded deadline or cancellation
   boundary; a deliberately hanging fake reaches `expired` within the test
   deadline.
2. Allowed status transitions are explicit and atomic; terminal states cannot
   transition back to `running` or be overwritten by a late result.
3. SSE observes job state and cannot create a conflicting second timeout state.
4. Timeout/dependency failures never return `recommended_action` and remain
   audit-only, fail-closed outcomes.

**Exact checks:**

```powershell
python -m unittest tests.t4_orchestrator.test_t4_deadline_state_machine
python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries
python -m unittest tests.t4_orchestrator.test_t4_api_http
python -m unittest tests.t4_orchestrator.test_t4_safety
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
git diff --check
```

**Gap check:** `inferred`; timeout implementation strategy requires Codex/Human
Review, but the contract thresholds do not change.

## STWI-SYM-033 — Type and validate scenario actions at the API boundary

**Priority / owner:** P1 / OrchestratorReleaseAgent
**Labels:** `stwi-agent`, `lane:api`, `phase:4`, `task:refactor`,
`needs-human-review`, `contract-risk`, `reasoning:high`
**Dependencies:** STWI-SYM-030
**Expected state:** Human Review before implementation; do not add
`symphony-approved` until the wire-compatible schema is approved.

**Goal:** Replace arbitrary action dictionaries with typed, bounded schemas
while preserving the existing POST path, status enum, and action-field
semantics.

**Allowed files:**

- `src/stwi/t4_orchestrator/contracts.py`
- `src/stwi/t4_orchestrator/interfaces.py`
- `src/stwi/t4_orchestrator/orchestrator.py`
- `tests/t4_orchestrator/**`
- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- `report/chapters/ch07_agent.tex`
- `report/chapters/appendix_api.tex`
- `slides/sections/03_02_e2e_flow.html`
- `slides/sections/07_01_multiagent.html`
- `slides/sections/07_02_safety_loop.html`

**Acceptance criteria:**

1. `candidate_action`, node ids, horizons, scenario time, tenant context, and
   policy values are validated at the API boundary with typed errors.
2. The accepted JSON shape remains wire-compatible unless a separate contract
   change is explicitly approved.
3. Unknown fields/nodes and out-of-range ratios fail closed and cannot produce
   `recommended_action`.
4. Tests prove safety/model adapters receive the validated action. Demo code
   must not claim a fabricated causal relationship between one UI field and a
   synthetic safety result.

**Exact checks:**

```powershell
python -m unittest tests.t4_orchestrator.test_t4_request_validation
python -m unittest tests.t4_orchestrator.test_t4_contracts
python -m unittest tests.t4_orchestrator.test_t4_api_http
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

**Gap check:** `inferred`; Human Review must confirm the typed action variants
before dispatch.

## STWI-SYM-034 — Fix dashboard async lifecycle and demo terminal branches

**Priority / owner:** P1 / FrontendAgent
**Labels:** `stwi-agent`, `lane:frontend`, `lane:api`, `phase:4`,
`task:refactor`
**Dependencies:** STWI-SYM-032, STWI-SYM-033
**Expected state:** Human Review after browser QA.

**Goal:** Make `/demo/` reliable with real asynchronous timing and provide
deterministic, clearly provisional evidence for every important terminal path.

**Allowed files:**

- `src/stwi/t4_orchestrator/static/**`
- `src/stwi/t4_orchestrator/api.py`
- `src/stwi/t4_orchestrator/fake_adapters.py`
- `scripts/demo/**`
- `tests/demo/**`
- `tests/t4_orchestrator/test_t4_api_http.py`
- `docs/guides/mvp_operator_dashboard.md`
- `docs/guides/mvp_demo_runbook.md`

**Acceptance criteria:**

1. The UI waits through `queued` and `running` via SSE with reconnect or a
   bounded polling fallback; `result=null`, non-2xx, invalid JSON, disconnect,
   and timeout states do not throw uncaught errors.
2. Approve/reject controls are enabled only for reviewable terminal results;
   `failed` and `expired` cannot be approved.
3. A test-only/provisional configuration demonstrates `succeeded`,
   `needs_review` from safety/OOD, missing-citation refusal, and
   `failed/expired` without changing the production API contract.
4. UI shows `trace_id`, model/data/policy versions, uncertainty/OOD, citations,
   fail-closed reason, and `applied_by_system=false`; keyboard and mobile checks
   pass.

**Exact checks:**

```powershell
python -m unittest tests.demo.test_mvp_smoke
python -m unittest tests.t4_orchestrator.test_t4_api_http
python scripts/demo/run_mvp_smoke.py
node --check src/stwi/t4_orchestrator/static/dashboard.js
python scripts/validation/validate_docs.py
git diff --check
```

Manual/browser evidence: desktop and 390x844 mobile viewport, zero console
errors, no horizontal overflow, keyboard submit/decision flow, and SSE
reconnect.

**Gap check:** `complete` after STWI-SYM-033 approval.

## STWI-SYM-035 — Reconcile API documentation, report claims, and PDF layout

**Priority / owner:** P2 / ReleaseQaAgent
**Labels:** `stwi-agent`, `lane:release`, `lane:qa`, `phase:4`, `task:review`,
`needs-human-review`
**Dependencies:** STWI-SYM-033, STWI-SYM-034
**Expected state:** Human Review.

**Goal:** Remove contract/API drift and misleading readiness claims from
presentation artifacts, then repair the visually broken report pages.

**Allowed files:**

- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- `docs/guides/mvp_operator_dashboard.md`
- `report/main.tex`
- `report/chapters/ch03_kien_truc.tex`
- `report/chapters/ch07_agent.tex`
- `report/chapters/appendix_api.tex`
- affected `slides/sections/**`
- `CHANGELOG.md` if it already records documentation corrections

**Acceptance criteria:**

1. E2E SLA, normalization policy, endpoints, request/response examples, and
   statuses match `project_contract.json` and implemented API behavior.
2. The report does not claim production readiness or measured SLA without
   evidence. Version/date/status wording changes require explicit Human Review;
   do not silently bump document version or publication date.
3. Header collision, appendix error-table overlap, and long endpoint overflow
   are removed at affected pages.
4. Report, appendix, slides, and dashboard guide use the same provisional MVP
   wording and retain human-approval/no-actuation semantics.

**Exact checks:**

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
python scripts/validation/validate_slides_static.py
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
git diff --check
```

Visual evidence: render and inspect cover, architecture constraints, agent/API
examples, appendix endpoint table, and error table.

**Gap check:** `inferred`; Human Review chooses the exact cover status wording.

## STWI-SYM-036 — Run hardened offline MVP demo acceptance

**Priority / owner:** P1 / ReleaseQaAgent and LeadCoordinator
**Labels:** `stwi-agent`, `lane:qa`, `lane:release`, `phase:4`, `task:qa`,
`needs-human-review`
**Dependencies:** STWI-SYM-031, 032, 033, 034, 035
**Expected state:** Human Review; only the human lead recommends Done.

**Goal:** Produce one reproducible acceptance record for the hardened offline
demo. This remains a provisional/synthetic demo, not a pilot or production
claim.

**Allowed files:**

- `docs/project_management/symphony/mvp_demo_acceptance.md`
- `docs/project_management/symphony/board.json`
- `docs/project_management/symphony/board.md`
- `docs/project_management/symphony/status_report.md`
- private/ignored demo evidence paths only

**Acceptance criteria:**

1. Full lightweight test suite and release verifier pass with all skips listed.
2. Browser and CLI evidence cover success, safety/OOD review, missing citation,
   and failure/expiry branches.
3. Every flow records `automatic_actuation=false`,
   `applied_by_system=false`, valid action-field semantics, trace/version data,
   and no raw video or secrets.
4. Acceptance explicitly lists all remaining real data, model, service,
   benchmark, auth, and deployment gates.

**Exact checks:**

```powershell
python -m unittest discover -s tests -v
python scripts/demo/run_mvp_smoke.py
python scripts/validation/validate_slides_static.py
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
git diff --check
```

**Gap check:** `complete` after dependencies pass.

## STWI-SYM-037 — Bind production runtime provenance and policy to promoted artifacts

**Priority / owner:** P1 / MLSimulationAgent and OrchestratorReleaseAgent
**Labels:** `stwi-agent`, `lane:ml`, `lane:simulation`, `lane:api`, `phase:4`,
`task:refactor`, `contract-risk`, `reasoning:high`
**Dependencies:** STWI-SYM-003, 004, 007, 013; vision dependency applies only
when camera evidence is enabled.
**Expected state:** Human Review.

**Goal:** Replace hard-coded mock provenance and thresholds with promoted,
checksum-verified model/data/calibration artifacts in production composition.

**Allowed files:**

- `src/stwi/t4_orchestrator/orchestrator.py`
- `src/stwi/app.py`
- `src/stwi/t1_pipeline/local_vision.py`
- relevant T2/T3 adapter and model-registry modules
- focused runtime/model-registry tests
- model registry and deployment runbooks

**Acceptance criteria:**

1. Production startup loads version, checksum, data version, calibration/OOD
   thresholds, and promotion status from validated artifacts; no mock constant
   is reported as production provenance.
2. Missing, stale, checksum-mismatched, uncalibrated, or provisional artifacts
   fail startup or return a fail-closed non-success result.
3. Provisional/demo composition remains isolated and visibly labeled.
4. Audit records use the exact model/data/policy versions used for inference.

**Exact checks:**

```powershell
python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries
python -m unittest tests.vision.test_vision_relabel_and_promotion
python -m unittest tests.t2_forecast.test_surrogate_safety
python -m unittest tests.contracts.test_project_contract
python scripts/validation/validate_docs.py
git diff --check
```

**Gap check:** `inferred`; exact production composition waits for promoted
artifact availability.

## STWI-SYM-038 — Harden T3 service boundary and redact internal errors

**Priority / owner:** P1 / KnowledgeRagAgent
**Labels:** `stwi-agent`, `lane:rag`, `lane:legal`, `lane:api`, `phase:3`,
`task:refactor`, `external-service`, `legal-review`
**Dependencies:** STWI-SYM-007
**Expected state:** Human Review after service-backed tests.

**Goal:** Make the Qdrant/Timescale path fail closed without default production
credentials, unsupported filter/fusion assumptions, or client-visible raw
exceptions.

**Allowed files:**

- `src/stwi/t3_knowledge/tier3_facade.py`
- `src/stwi/t3_knowledge/qdrant_retriever.py`
- `src/stwi/t3_knowledge/timescale_executor.py`
- `src/stwi/t3_knowledge/query_builder.py`
- `tests/t3_knowledge/**`
- `infra/harness/compose.phase3.yaml`
- `docs/03_Knowledge_Base_and_RAG_Design.md`

**Acceptance criteria:**

1. Production mode requires DSN/Qdrant configuration from environment or an
   approved secret boundary; no embedded dev password fallback is accepted.
2. Effective-date filtering and hybrid retrieval use APIs supported by the
   pinned Qdrant client and are proven by integration tests.
3. SQL remains typed, parameterized, allowlisted, tenant/job filtered, and
   read-only. Missing/expired citations abstain or return `needs_review`.
4. Client failures expose stable error codes and `trace_id`, not raw DB,
   Qdrant, DSN, SQL, or exception text.

**Exact checks:**

```powershell
python -m unittest discover -s tests/t3_knowledge -v
docker compose -f infra/harness/compose.phase3.yaml config --quiet
python scripts/validation/gate_p3_validator.py
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
git diff --check
```

Live service execution requires `external-service-approved` and must not log
credentials or private corpus content.

**Gap check:** `inferred`; exact service run is Human Review gated.

## STWI-SYM-039 — Prove measured end-to-end SLA on the contract profile

**Priority / owner:** P1 / ReleaseQaAgent and MLSimulationAgent
**Labels:** `stwi-agent`, `lane:qa`, `lane:release`, `lane:ml`, `phase:4`,
`task:validate`, `needs-human-review`, `external-service`
**Dependencies:** STWI-SYM-005, 008, 037, 038
**Expected state:** Human Review.

**Goal:** Measure POST-to-terminal latency and surrogate latency under the
contract hardware/profile and representative concurrency without simulated
evidence.

**Allowed files:** benchmark harness/scripts, benchmark documentation, focused
tests, and private/ignored benchmark output only.

**Acceptance criteria:**

1. Hardware profile records 8 CPU cores, 32 GB RAM, and 12–16 GB GPU VRAM.
2. Evidence is `measured`, records warmup/run counts, payload size, concurrency,
   versions, p50/p95/p99, and failure/timeout counts.
3. Surrogate P99 is below 500 ms, E2E P95 is at most 30 seconds, and hard
   deadline/P99 is at most 180 seconds—or the ticket reports FAIL without
   weakening thresholds.
4. Raw private results are not published; only reviewed aggregate claims reach
   docs/report/slides.

**Exact checks:** use the project benchmark CLI created/validated by this
ticket, then run:

```powershell
python scripts/validation/validate_surrogate_benchmark_evidence.py
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
git diff --check
```

**Gap check:** `blocked` until approved benchmark hardware is available.

## STWI-SYM-040 — Implement approved auth, RBAC, and tenant boundary

**Priority / owner:** P1 / OrchestratorReleaseAgent
**Labels:** `stwi-agent`, `lane:api`, `phase:4`, `task:refactor`,
`needs-human-review`, `contract-risk`
**Dependencies:** approved STWI-SYM-017 design
**Expected state:** Human Review; not Symphony-active before approval.

**Goal:** Implement only the identity/tenant mechanism approved in
STWI-SYM-017, deriving identity server-side and enforcing role/tenant boundaries
for API, SSE, decisions, and Timescale queries.

**Allowed files:** must be copied from the approved STWI-SYM-017 implementation
brief; do not infer a provider or add a dependency in this draft.

**Acceptance criteria:**

1. Request-body tenant/operator values cannot elevate privileges or cross
   tenant boundaries.
2. Operator, analyst, admin, and readonly permissions match the approved design
   across POST, GET, SSE, and operator-decision endpoints.
3. Auth failures are auditable and redact secrets; anonymous/dev behavior is
   impossible in production mode.
4. Focused negative tests cover spoofed tenant, wrong role, SSE reconnect, and
   decision submission.

**Exact checks:** defined after Human Review selects the approved mechanism;
minimum includes Tier-4 HTTP/security tests, T3 tenant-isolation tests, contract
tests, docs validation, and `git diff --check`.

**Gap check:** `blocked` pending STWI-SYM-017 Human Review.

## STWI-SYM-041 — Build the approved production deployment baseline

**Priority / owner:** P1 / OrchestratorReleaseAgent and ReleaseQaAgent
**Labels:** `stwi-agent`, `lane:release`, `lane:api`, `phase:4`,
`task:refactor`, `needs-human-review`, `contract-risk`
**Dependencies:** STWI-SYM-008, 018, approved 021, 038, 040
**Expected state:** Human Review.

**Goal:** Implement the deployment option approved by STWI-SYM-021 using the
existing stack, with durable execution, production secrets/configuration,
health/readiness, observability, backup/restore, and rollback evidence.

**Allowed files:** must be bounded after STWI-SYM-021 approval; expected scope
is `infra/**`, approved deployment/runbook docs, health/readiness composition,
and focused deployment tests.

**Acceptance criteria:**

1. Production mode starts with FastAPI, LangGraph, Celery, Redis, TimescaleDB,
   Qdrant, BGE-m3, and promoted adapters; no provisional/in-memory component is
   accepted.
2. No dev password/default secret, public database port, raw exception, or
   `/docs`-only health check is used as production readiness evidence.
3. Containers/processes use least privilege; dependencies/images are pinned
   reproducibly without introducing an unapproved platform or framework.
4. Backup/restore, migration, restart recovery, rate limiting, monitoring,
   audit retention, and rollback procedures have executable checks or a
   documented Human Review gate.

**Exact checks:** selected after deployment option approval; minimum includes
Compose/config validation, production-startup negative tests, auth/tenant tests,
restart/recovery tests, release verifier, and `git diff --check`.

**Gap check:** `blocked` pending STWI-SYM-021 and auth design approval.

## STWI-SYM-042 — Run final production release-readiness QA

**Priority / owner:** P1 / ReleaseQaAgent and LeadCoordinator
**Labels:** `stwi-agent`, `lane:qa`, `lane:release`, `task:qa`,
`needs-human-review`, `release-action-approved` only when explicitly granted
**Dependencies:** vision/camera gate (001/013/014 and 015 if required),
ML gates (003/004/005), RAG gates (006/007/038), runtime gates
(008/032/033/037/040/041), and measured SLA ticket 039
**Expected state:** Human Review; no automatic release or deployment.

**Goal:** Produce a single evidence-backed go/no-go recommendation for pilot or
production without changing contract thresholds or hiding skipped/failed gates.

**Allowed files:** release evidence, approved runbooks, board/status mirror, and
private/ignored result artifacts; no feature implementation.

**Acceptance criteria:**

1. Full tests, service integrations, security/tenant negatives, measured SLA,
   browser QA, PDF/slides QA, restart/recovery, backup/restore, and rollback
   evidence are attached with exact versions and commands.
2. `STWI_RUNTIME_MODE=production` rejects every provisional, missing,
   uncalibrated, unsigned/checksum-invalid, or expired dependency/artifact.
3. No open P1 blocker, unexplained service skip, raw-video/privacy breach,
   invalid citation, automatic actuation, or executable `needs_review` action
   remains.
4. Final output is a Human Review go/no-go recommendation; release, merge,
   push, and deployment require separate explicit approval.

**Exact checks:**

```powershell
python -m unittest discover -s tests -v
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
python scripts/validation/validate_slides_static.py
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
git diff --check
```

Add the approved service, benchmark, load, auth, recovery, and rollback commands
from dependency tickets; do not claim them passed from this generic list alone.

**Gap check:** `blocked` until all dependencies are reviewable.

## Recommended first Symphony batch

1. Run only `STWI-SYM-030` to reconcile tracker and packet state.
2. After Human Review, dispatch `STWI-SYM-031`.
3. Dispatch `STWI-SYM-032` next with `reasoning:high` and one active workspace.
4. Keep `STWI-SYM-033` in Human Review until the typed wire-compatible schema
   is approved.

Do not start data/ML/RAG, dashboard, and production work concurrently from this
draft. Their dependencies and allowed files overlap enough that sequential
review is safer for the first batch.
