# Demo UI truthfulness — implementation plan

> **Goal:** Make the dashboard's visible result, safety and connection state faithfully reflect the canonical job state, and make the demo refinement preset demonstrate its stated two-pass safety loop.

> **Architecture:** Keep API schemas and production composition unchanged. Select the existing deterministic refinement surrogate only in demo runtime. Let the view derive presentation strings from the existing state-machine status, retain trusted network-context capacity metadata locally, and make the coordinator ignore stale SSE transport events after terminal completion.

> **Tech stack:** Python/FastAPI runtime, vanilla ES modules, Node test runner, Python unittest.

> **Global constraints:** No automatic actuation; `succeeded` remains advisory and non-executable. Do not alter `project_contract.json`, the public job schema, or production runtime wiring. Preserve fail-closed production network-context behavior.

## Task 1 — Demonstrate the refinement loop in demo runtime

**Files:** `tests/t4_orchestrator/test_t4_demo_profiles.py` (or nearest runtime test), `src/stwi/t4_orchestrator/orchestrator.py`

1. Add a regression that constructs demo runtime, submits a typed `signal_change` at ratio `0.70`, and asserts exactly two safety iterations, a final recommended ratio `0.85`, and a non-executable action.
2. Add a companion assertion that a non-`signal_change` demo scenario keeps its existing deterministic profile.
3. Run the focused test and confirm it fails while demo composition uses `DemoSurrogateForecaster`.
4. Change only demo composition to instantiate `RefinementDemoSurrogateForecaster`.
5. Re-run the focused test, then relevant safety/demo test modules.

## Task 2 — Derive result and safety presentation from authoritative state

**Files:** `tests/frontend/dashboard-view.test.mjs`, `src/stwi/t4_orchestrator/static/dashboard-view.js`

1. Add table-driven tests for idle, queued, running, succeeded, needs_review, failed and expired states. Assert `result-title`, safety label/icon/class and no action-execution implication.
2. Run the focused frontend test and confirm failure against static placeholder strings.
3. Add one local status-to-presentation mapping in the view and update DOM text/class on every render.
4. Re-run the focused test and full frontend suite.

## Task 3 — Keep terminal connection state truthful

**Files:** `tests/frontend/dashboard-coordinator.test.mjs`, `src/stwi/t4_orchestrator/static/dashboard.js`

1. Add a coordinator regression: terminal envelope closes stream and presents online; a subsequent reconnecting callback cannot overwrite it. Preserve protocol-error behavior before terminal.
2. Run that test as RED.
3. In terminal acceptance, dispatch online unless transport is already protocol error; guard `onTransport` against terminal state.
4. Re-run focused coordinator and full frontend tests.

## Task 4 — Display trusted capacity-version context without schema drift

**Files:** `tests/frontend/dashboard-view.test.mjs`, `src/stwi/t4_orchestrator/static/dashboard-view.js`

1. Add tests for fallback order: scenario summary, compatibility result field, trusted network context, then dash; test no synthetic replacement on unavailable context.
2. Run RED, retain the capacity version received by `setNetworkContext`, then implement the fallback in `render`.
3. Re-run focused/full frontend tests.

## Task 5 — Synchronize demo guidance and verify release readiness

**Files:** `docs/guides/mvp_operator_dashboard.md`, `docs/guides/mvp_dashboard_demo_walkthrough.md` only if behavior text is inaccurate; related static tests if changed.

1. Compare the runbook wording with the implemented two-pass refinement and advisory state labels; make only necessary Vietnamese-first corrections.
2. Run `python scripts/validation/validate_docs.py`, `python -m unittest tests.contracts.test_project_contract`, bundled Node syntax checks for dashboard and slides, targeted runtime/frontend tests, and `git diff --check`.
3. Restart the local demo server, exercise safe/refinement/review states through the browser, and capture any discrepancy before commit.
