# MVP Demo Acceptance Evidence

**Linear ticket:** `TRA-26`  
**Baseline:** `main` at `cfa12e58977f451f4e7978efc419b6b47c7ebc7f`  
**Scope:** Integrated, offline Demo MVP acceptance only. This is not a
production-readiness claim.

## Integrated Components

The acceptance baseline includes the merged work from:

- `TRA-23` / PR #10: mandatory Tier-4 HTTP API CI coverage.
- `TRA-24` / PR #12: operator review dashboard at `/demo/`.
- `TRA-25` / PR #11: reproducible offline MVP smoke harness.

## Evidence

The following commands ran from the baseline workspace on 2026-07-13:

```text
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
python -m unittest tests.t4_orchestrator.test_t4_api_http
python -m unittest discover -s tests/t4_orchestrator
python -m unittest tests.demo.test_mvp_smoke
python scripts/demo/run_mvp_smoke.py --output C:\tmp\stwi-tra-26-mvp-smoke-evidence.json
node --check src/stwi/t4_orchestrator/static/dashboard.js
git diff --check
```

Results:

- Release verifier passed: documentation validator, contract tests,
  presentation JavaScript syntax, and whitespace check.
- Tier-4 HTTP suite passed: 36 tests with no dependency skip.
- Tier-4 discovery passed: 103 tests.
- Offline smoke unit test passed: 1 test.
- Offline smoke CLI produced two terminal flows: `succeeded` with an approved
  operator decision and `needs_review` with a rejected operator decision.
- Both smoke flows recorded `automatic_actuation: false`,
  `applied_by_system: false`, `human_decision_only: true`, and no retained raw
  video.
- Dashboard JavaScript syntax and `git diff --check` passed.

The smoke evidence is intentionally written outside the repository at
`C:\tmp\stwi-tra-26-mvp-smoke-evidence.json`; it contains only synthetic,
aggregate demo data.

## Operator Review Evidence

Before PR #12 was merged, the dashboard was checked locally at `/demo/` on
the same dashboard commit (`43238ec`): job creation reached a terminal state,
SSE events were visible, and approve/reject remained audit-only. The UI showed
`executable: false` and `automatic_actuation: false`. No browser console error
was observed. This acceptance run did not repeat that browser interaction
because the local server launch was unavailable in the sandbox; the prior
browser result remains the recorded UI evidence.

## Contract and Privacy Boundary

The integrated demo preserves the decision-support boundary:

- `POST /api/v1/what-if-jobs` remains asynchronous and returns `202`.
- Only `succeeded` presents a recommended action; `needs_review` remains
  non-executable and requires a human decision.
- The offline harness uses provisional synthetic adapters only, contacts no
  live services, and retains no raw video or credentials.
- No automatic traffic-signal or field-device action is implemented.

## Remaining Human Review Gates

This acceptance does not close the following work:

- `TRA-5`: complete vision artifact metadata.
- `TRA-6`: surrogate P99 evidence on the contract benchmark hardware profile.
- `TRA-11`: human-supervised live RTSP smoke test.
- `TRA-13`: approved auth/RBAC and tenant-boundary design.
- `TRA-17`: approved production deployment option.
- `TRA-27`: global Symphony continuation-loop remediation.

Production Celery/Redis/TimescaleDB/Qdrant wiring, an approved SOP corpus,
and production identity controls are also outside this offline MVP acceptance.

## Recommended State

Move `TRA-26` to `In Review`. A human reviewer must approve this evidence and
the corresponding PR before the ticket can move to `Done`.
