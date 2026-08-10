# STWI Comprehensive Hybrid Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic comprehensive offline demo plus an optional tri-state service lab and synchronized presenter documentation.

**Architecture:** A typed scenario catalog drives both the CLI evidence runner and dashboard presets. A versioned evidence manifest records each capability as pass/fail/not_verified without leaking secrets or upgrading mock evidence.

**Tech Stack:** Python 3.11, FastAPI TestClient, unittest, existing vanilla JavaScript dashboard, JSON evidence.

## Global Constraints

- Offline profile must require no Docker, network, credentials, RTSP or GPU.
- Services profile never replaces unavailable service evidence with mocks.
- No raw video, secrets, automatic actuation or production SLA claim.
- Keep canonical statuses and action semantics unchanged.
- Do not commit, stage, push or change branches.

---

### Task 1: Typed scenario catalog

**Files:**
- Create: `src/stwi/demo/__init__.py`
- Create: `src/stwi/demo/scenarios.py`
- Modify: `src/stwi/t4_orchestrator/demo_adapters.py`
- Test: `tests/demo/test_demo_scenarios.py`

**Interfaces:**
- Produces: `DemoScenario` and `offline_scenarios()`

- [ ] **Step 1: Write a failing catalog test**

```python
self.assertEqual(
    {item.name for item in offline_scenarios()},
    {"safe_approval", "safe_rejection", "refinement_success", "unsafe_vc",
     "ood", "high_uncertainty", "missing_citation", "dependency_failure",
     "deadline_exceeded", "invalid_scenario", "tenant_scope_denied",
     "sse_reconnect", "static_preview"},
)
```

- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement immutable catalog records and validate unique names, canonical statuses and node scope.**
- [ ] **Step 4: Verify GREEN.**

### Task 2: Versioned evidence schema and atomic writer

**Files:**
- Create: `src/stwi/demo/evidence.py`
- Test: `tests/demo/test_demo_evidence.py`

**Interfaces:**
- Produces: `CapabilityStatus`, `CapabilityEvidence`, `DemoEvidence`
- Produces: `write_evidence_atomic(path, evidence)`

- [ ] **Step 1:** Write failing tests for invalid executable actions, duplicate terminal events, missing trace/version and atomic replacement.
- [ ] **Step 2:** Verify RED.
- [ ] **Step 3:** Implement strict Pydantic models and a same-directory temporary-file replace.
- [ ] **Step 4:** Verify GREEN and JSON round-trip.

### Task 3: Comprehensive offline runner

**Files:**
- Modify: `scripts/demo/run_mvp_smoke.py`
- Modify: `tests/demo/test_mvp_smoke.py`
- Test: `tests/demo/test_comprehensive_demo.py`

**Interfaces:**
- Produces: CLI `--profile offline` and versioned comprehensive manifest

- [ ] **Step 1:** Add failing tests for every catalog case and expected invariant.
- [ ] **Step 2:** Verify RED against the existing six-case runner.
- [ ] **Step 3:** Refactor the runner to use the catalog and evidence schema; add typed failure/expiry/auth/SSE/static-preview probes.
- [ ] **Step 4:** Verify GREEN and confirm the CLI exits non-zero on mandatory capability failure.

### Task 4: Optional service preflight and lab runner

**Files:**
- Create: `src/stwi/demo/service_lab.py`
- Modify: `scripts/demo/run_mvp_smoke.py`
- Test: `tests/demo/test_demo_service_lab.py`

**Interfaces:**
- Produces: `--profile services`
- Produces: independent tri-state capability evidence

- [ ] **Step 1:** Write failing tests for unavailable, failed and passing injected probes.
- [ ] **Step 2:** Verify RED.
- [ ] **Step 3:** Implement bounded probes for Docker, Redis/Celery, Qdrant and TimescaleDB without printing configuration values.
- [ ] **Step 4:** Verify GREEN; absent services yield `not_verified` and non-zero incomplete verdict.

### Task 5: Dashboard preset and copy synchronization

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/index.html`
- Modify: `src/stwi/t4_orchestrator/static/dashboard.js`
- Modify: `src/stwi/t4_orchestrator/static/dashboard-view.js`
- Test: `tests/frontend/dashboard-controller.test.mjs`
- Test: `tests/frontend/dashboard-view.test.mjs`

- [ ] **Step 1:** Add failing tests for refinement history, failed/expired rendering and non-mutating static preview.
- [ ] **Step 2:** Verify RED with Node test runner.
- [ ] **Step 3:** Add only the UI fields needed to present the new evidence; use text APIs and existing CSS tokens.
- [ ] **Step 4:** Verify GREEN, keyboard behavior and no executable needs_review control.

### Task 6: Rewrite the demo runbook as an operational script

**Files:**
- Modify: `docs/guides/mvp_demo_runbook.md`
- Modify: `docs/guides/mvp_dashboard_demo_walkthrough.md`
- Modify: `docs/project_management/symphony/mvp_demo_acceptance.md`
- Modify: `README.md`

- [ ] **Step 1:** Add 7-minute and 15-minute presenter paths, exact commands, expected outputs and recovery steps.
- [ ] **Step 2:** Add the complete scenario/capability matrix and service `not_verified` semantics.
- [ ] **Step 3:** Add pre-demo, live-demo, cleanup and Q&A checklists; keep RTSP/GPU as Human Review appendices.
- [ ] **Step 4:** Validate links and canonical terminology.

### Task 7: Reconcile tracker and derived artifacts

**Files:**
- Modify carefully: `docs/project_management/symphony/board.json`
- Regenerate: `docs/project_management/symphony/board.md`
- Regenerate: `docs/project_management/symphony/status_report.md`
- Modify: `docs/project_management/symphony/current_dispatch_packet.md`

- [ ] **Step 1:** Preserve the user's existing board/status changes and mark TRA-50 from repository merge evidence.
- [ ] **Step 2:** Add the approved CSL, production-composition and hybrid-demo work items with explicit external gates.
- [ ] **Step 3:** Regenerate mirrors and verify counts/next dispatch are consistent.

### Task 8: Final demo and release verification

- [ ] Run all demo Python and frontend Node tests.
- [ ] Run offline CLI and inspect the generated manifest.
- [ ] Run the optional services profile and report pass/fail/not_verified honestly.
- [ ] Serve `/demo/` over loopback and inspect console, navigation, status branches and overflow.
- [ ] Run full Python discovery, release verifier, docs validation and `git diff --check`.
