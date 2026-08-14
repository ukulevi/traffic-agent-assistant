# Demo UI citation density — implementation plan

> **Goal:** Keep the operator decision visible on compact screens while preserving every citation and the full audit payload.

> **Architecture:** Add an accessible citation summary/control to existing dashboard markup. The view renders only the first three citations by default for lists larger than three and toggles the remaining DOM nodes with native text APIs; a new job resets the collapsed state.

> **Tech stack:** Static HTML/CSS, vanilla ES modules, Node test runner.

> **Global constraints:** Do not change citation data, decision/audit API payloads, safety policy, or automatic-actuation boundary. Do not use `innerHTML`; preserve keyboard and screen-reader semantics.

## Task 1 — Define and test the accessible citation states

**Files:** `tests/frontend/dashboard-view.test.mjs`, `src/stwi/t4_orchestrator/static/index.html`

1. Add tests for 0–3 citations (all visible, no redundant control), >3 citations (first three visible, `Đang hiển thị 3/N citation`, accessible toggle), expanded state, and reset after a new job.
2. Add the small summary/status and button elements with stable IDs/accessible labels to the citation region.
3. Run the focused test as RED.

## Task 2 — Implement DOM-safe progressive disclosure

**Files:** `src/stwi/t4_orchestrator/static/dashboard-view.js`, `tests/frontend/dashboard-view.test.mjs`

1. Store citation-expanded state within the view and reset it when the job id changes.
2. Render citation nodes with `createElement`/`textContent`, update `aria-expanded`, and wire the button without event-handler duplication.
3. Run focused tests as GREEN, then full frontend tests.

## Task 3 — Preserve layout, focus and non-color affordance

**Files:** `src/stwi/t4_orchestrator/static/dashboard.css`, `tests/demo/test_dashboard_static.py` if needed

1. Add minimal styles for the status and disclosure button using existing tokens, visible focus state and responsive wrapping.
2. Add static/accessibility assertions only where they protect the new control contract.
3. Run syntax/static tests and inspect mobile-width browser layout; ensure the operator decision remains reachable without hiding citation evidence.

## Task 4 — Documentation and release QA

**Files:** operator demo guide/walkthrough only if exact on-screen instructions change.

1. State that the collapsed list is a display optimization and all citations remain available; retain audit JSON instructions.
2. Run docs validator, contract tests, dashboard/slides syntax checks, full frontend suite, `git diff --check`, and relevant release QA.
3. Exercise a long-citation result in the browser before commit.

