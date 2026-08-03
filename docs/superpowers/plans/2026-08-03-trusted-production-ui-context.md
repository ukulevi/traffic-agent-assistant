# Trusted Production UI Context Implementation Plan

**Goal:** Implement the approved `GET /api/v1/ui-context` production dashboard bootstrap contract without changing demo fallback or the human-approval boundary.

**Architecture:** Add a typed `UiContextProvider` boundary beside `PrincipalResolver`. Register the endpoint only in production, validate provider scope fail-closed, intersect decision capability with operator/admin roles, and normalize the snake_case wire payload in the dashboard.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, unittest, Node test runner, vanilla JavaScript, LaTeX.

---

## Task 1: Lock the contract and typed provider boundary

**Files:**
- Modify: `tests/contracts/test_project_contract.py`
- Create: `tests/t4_orchestrator/test_t4_ui_context.py`
- Create: `src/stwi/t4_orchestrator/ui_context.py`
- Modify: `project_contract.json`

1. Add a contract assertion that `api.ui_context` equals `GET /api/v1/ui-context`.
2. Add unit tests for valid stable node order and rejection of empty, duplicate, over-limit node IDs and non-boolean capability values.
3. Run the new tests and confirm RED because the contract key and module do not exist.
4. Implement immutable `UiContextScope`, strict Pydantic response/capability models, `UiContextProvider`, and provisional-provider detection.
5. Add the endpoint string to `project_contract.json`.
6. Run the focused tests and confirm GREEN.

## Task 2: Compose and expose the production endpoint fail-closed

**Files:**
- Modify: `src/stwi/t4_orchestrator/api.py`
- Modify: `tests/t4_orchestrator/test_t4_ui_context.py`
- Modify: `tests/t4_orchestrator/test_t4_auth_boundary.py`
- Modify: `tests/t4_orchestrator/test_t4_runtime_boundaries.py`

1. Add API tests for trusted production 200 response, `Cache-Control: no-store`, stable role/node serialization, and analyst decision-capability clamping.
2. Add composition/auth tests for missing provider, provisional provider, missing principal, provider failure, and demo/test 404 behavior.
3. Run those tests and confirm RED.
4. Extend `create_app` with an optional `ui_context_provider`; require a non-provisional provider in production.
5. Register `GET /api/v1/ui-context` only in production, reuse the trusted principal resolver, allow supported dashboard roles, resolve scope, clamp `record_decision` to operator/admin, and map provider/validation failures to 503 `UI_CONTEXT_UNAVAILABLE` with `trace_id`.
6. Run the focused API/auth/runtime tests and confirm GREEN.

## Task 3: Normalize the production wire payload in the dashboard

**Files:**
- Modify: `tests/frontend/dashboard-mode.test.mjs`
- Modify: `src/stwi/t4_orchestrator/static/dashboard-mode.js`

1. Extend frontend tests to assert `operatorId`, `nodeIds`, and `capabilities.recordDecision` normalization.
2. Add malformed-context cases for duplicate nodes, unsupported roles, unknown capability keys, and non-boolean `record_decision`.
3. Run frontend tests and confirm RED.
4. Implement exact response validation and snake_case-to-camelCase normalization without changing the exact-404 demo fallback.
5. Run frontend tests and `node --check` and confirm GREEN.

## Task 4: Synchronize canonical docs and report artifacts

**Files:**
- Modify: `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- Modify: `docs/design/auth_rbac_tenant_boundary.md`
- Modify: `docs/guides/operator_dashboard_demo_guide.md` or the existing canonical dashboard/operator guide discovered in the repository
- Modify: `report/chapters/appendix_api.tex`
- Modify: `report/chapters/ch07_agent.tex`

1. Document the production bootstrap response, `no-store`, 401/403/503 behavior, server-side node scope, decision capability clamp, and demo-only exact-404 fallback.
2. Add the endpoint and compact payload to the API appendix.
3. Document that the dashboard remains decision-support only and never receives an actuation capability.
4. Run documentation validation and contract tests.
5. Build the PDF and inspect the affected pages for overflow or encoding defects.

## Task 5: Release verification and handoff

**Files:** all changed files

1. Run focused UI-context, auth, runtime, HTTP, and frontend tests.
2. Run required project checks: docs validator, contract test, JavaScript syntax checks, and `git diff --check`.
3. Run the broad feasible Python suite; record private-artifact/environment exclusions exactly if the isolated worktree prevents the full suite.
4. Review `git diff` for unrelated changes, secrets, raw-video references, client-trusted scope, automatic actuation, and contract drift.
5. Use `stwi-release-qa` and `verification-before-completion`, then use `finishing-a-development-branch` for the handoff. Do not commit, push, or open a PR unless the user explicitly requests it.
