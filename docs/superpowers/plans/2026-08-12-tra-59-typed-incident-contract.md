# TRA-59 Typed Incident Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backward-compatible, typed single-node incident input whose bounds come from `project_contract.json`, and reject production job scopes that are not authorized by the server-side principal allowlist.

**Architecture:** Define shared immutable incident models in `stwi.contracts`, re-export them through the T4 contract surface, and add `incident: IncidentVector | None` to `WhatIfJobRequest`. Pydantic validates event-specific fields and request-local scope; the FastAPI create-job boundary separately validates every requested node against `UiContextProvider` in production. The request remains incident-free when `incident=None`, while `candidate_action` remains the required non-executable what-if hypothesis.

**Tech Stack:** Python 3.11+, Pydantic 2, FastAPI, unittest, JSON machine-readable contract, Markdown and XeLaTeX report sources.

## Global Constraints

- Keep `POST /api/v1/what-if-jobs` at HTTP 202 and preserve all existing job statuses and action-field semantics.
- Support exactly `accident`, `flood`, `lane_closure`, `demand_surge`, and `signal_change`.
- Support exactly one affected node per incident in the MVP.
- Use contract bounds: duration 1–180 minutes, lane-closure ratio 0–1, demand multiplier greater than 1 and at most 3, and green-time ratio delta -1–1.
- `signal_change` supports only `green_time_ratio_delta`; signal offset is explicitly deferred.
- `incident=None` means incident-free input; `candidate_action` remains required.
- Free text never selects simulation behavior, and no field is executable or sent to infrastructure.
- `project_contract.json` is the single source of truth for incident bounds.

---

### Task 1: Machine-readable incident contract and shared models

**Files:**
- Modify: `project_contract.json`
- Create: `src/stwi/contracts/incident.py`
- Modify: `src/stwi/contracts/__init__.py`
- Test: `tests/contracts/test_project_contract.py`
- Test: `tests/t4_orchestrator/test_t4_contracts.py`

**Interfaces:**
- Consumes: `load_project_contract() -> dict[str, Any]`
- Produces: `IncidentType`, `IncidentSeverity`, `SignalPlanDelta`, `IncidentVector`

- [ ] **Step 1: Write failing contract and model tests**

Add literal assertions for the five event types and exact bounds in `project_contract.json`. Add construction tests proving that valid event-specific payloads parse, unknown fields fail, irrelevant parameters fail, and `signal_change` accepts only `green_time_ratio_delta`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.contracts.test_project_contract tests.t4_orchestrator.test_t4_contracts -v
```

Expected: failure because `incident_contract` and the shared incident types do not exist.

- [ ] **Step 3: Add the source-of-truth contract and minimal models**

Add `incident_contract` with `event_types`, `severity_levels`, `affected_nodes_min/max`, and a `bounds` object. Load those values in `incident.py`; use `ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)` and a model validator to require only the parameter belonging to the selected event type.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the same unittest command and confirm all focused tests pass.

### Task 2: Optional incident request field and serialization round-trip

**Files:**
- Modify: `src/stwi/t4_orchestrator/contracts.py`
- Modify: `src/stwi/t4_orchestrator/__init__.py`
- Modify: `tests/t4_orchestrator/test_t4_contracts.py`
- Modify: `tests/t4_orchestrator/test_t4_redis_celery.py`

**Interfaces:**
- Consumes: shared `IncidentVector`
- Produces: `WhatIfJobRequest.incident: IncidentVector | None`

- [ ] **Step 1: Write failing request and round-trip tests**

Test that existing bodies default to `incident=None`; a valid incident survives `model_dump(mode="json")`, `WhatIfJobRequest.model_validate`, `JobEnvelope`, Redis store serialization, and Celery task deserialization; incident node outside `request.node_ids` fails.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m unittest tests.t4_orchestrator.test_t4_contracts tests.t4_orchestrator.test_t4_redis_celery -v
```

Expected: failure because `WhatIfJobRequest` rejects the unknown `incident` field.

- [ ] **Step 3: Add the optional field and local-scope validator**

Import and re-export the shared types. Add `incident: IncidentVector | None = None`; when non-null, require its sole affected node to be present in `node_ids`. Preserve the candidate-action scope check unchanged.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the same unittest command and confirm all focused tests pass.

### Task 3: Production server-side node authorization

**Files:**
- Modify: `src/stwi/t4_orchestrator/api.py`
- Modify: `tests/t4_orchestrator/test_t4_api_http.py`
- Modify: `tests/t4_orchestrator/test_t4_auth_boundary.py`

**Interfaces:**
- Consumes: `UiContextProvider.resolve(principal=principal) -> UiContextScope`
- Produces: fail-closed create-job authorization before `_store.create()`

- [ ] **Step 1: Write failing production HTTP tests**

Build a production client with a trusted principal and `UiContextProvider`. Assert that an in-scope request returns 202; a request containing any node outside the trusted scope returns 403 `AUTH_NODE_SCOPE_DENIED`; and a provider exception or invalid scope returns 503 `UI_CONTEXT_UNAVAILABLE`. Include an incident whose node is client-listed but server-forbidden.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
python -m unittest tests.t4_orchestrator.test_t4_api_http tests.t4_orchestrator.test_t4_auth_boundary -v
```

Expected: unauthorized client-supplied nodes are currently accepted.

- [ ] **Step 3: Add one create-job authorization helper**

In production, resolve `UiContextScope` using the already-authenticated principal, validate its type, and require `set(request.node_ids).issubset(scope.node_ids)`. Map unavailable/invalid provider output to redacted 503 and scope excess to 403 with a trace ID; do not disclose the server allowlist and do not add demo fallback.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the same unittest command and confirm all focused tests pass.

### Task 4: Canonical documentation and report synchronization

**Files:**
- Modify: `docs/02_ML_and_Simulation_Specification.md`
- Modify: `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- Modify: `report/chapters/ch07_agent.tex`
- Modify: `report/chapters/appendix_api.tex`
- Modify: `report/chapters/appendix_schema.tex`

**Interfaces:**
- Consumes: the finalized JSON/Pydantic request schema
- Produces: canonical request examples and explicit incident semantics

- [ ] **Step 1: Update source documents**

Document the exact fields/bounds, single-node rule, green-ratio-only MVP decision, deferred offset, untrusted-description boundary, incident-free meaning of `incident=None`, required candidate hypothesis, and server-side production scope validation.

- [ ] **Step 2: Update API and report examples**

Add one typed `lane_closure` example to the canonical API section and Chapter 7, while noting that omitting `incident` preserves the existing incident-free request.

- [ ] **Step 3: Run documentation validation**

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
```

Expected: both commands pass.

### Task 5: Full verification and PR preparation

**Files:**
- Verify all modified files only; do not include workspace-local Symphony artifacts.

- [ ] **Step 1: Run full runtime suite**

```powershell
python -m unittest discover -s tests -v
```

- [ ] **Step 2: Run mandatory release checks**

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

- [ ] **Step 3: Visually inspect affected Chapter 7 PDF pages**

Render the pages containing the create-job example and confirm no overflow, clipping, broken monospace blocks, or encoding regression.

- [ ] **Step 4: Review scope and commit**

Confirm the branch contains only TRA-59 plan, contract, shared models, API boundary, tests, canonical docs, and report source. Commit with `feat: add typed incident job contract`, push, create a ready PR, monitor CI, and merge only when the exact head is green.
