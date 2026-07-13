# Current Dispatch Packet

Status: ready for Hermes Step Executor

## Model Route

Primary: Codex when quota is available.
Fallback: Step 3.7 Flash when Codex is unavailable or on cooldown.

Hermes role: bounded executor only, through:
```powershell
python scripts/project_management/hermes_runner_bridge.py --runner-command "C:\Users\PC\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" --oneshot <prompt_file>
```

Do not use Antigravity in this workflow.

## Original Request

<long free-form prompt or short note from user>

## Interpretation Notes

- <assumption 1>
- <assumption 2>
- ...

## Ticket

STWI-SYM-009 / TRA-7 - Replace provisional fake adapters in production runtime

## Branch

Expected ticket branch:
`codex/tra-7-fail-closed-provisional-adapters`

## Worktree Expectation

Run this ticket in an isolated workspace/branch checkout. Do not reuse a
dirty workspace from another ticket. If the working tree already has unrelated
changes, stop for `Human Review` instead of staging mixed changes.

## Phụ trách: Hermes Desktop

Hermes không được phép commit/push hay cập nhật Linear state. Nếu dispatch
gói tin này yêu cầu commit/push, phải là Codex/Step 3.7 Flash hoặc người
dùng trực tiếp thực thi.

## Goal

Recover TRA-7 from its stale clean workspace on a fresh branch from current main. Inventory provisional adapters reachable from production startup and make only the smallest fail-closed guard changes needed to prevent implicit fake/in-memory defaults in production. Preserve all job-status and human-approval semantics. Do not wire live services or introduce dependencies.

## Allowed Files

```text
src/stwi/config/runtime.py
src/stwi/t4_orchestrator/api.py
src/stwi/t4_orchestrator/orchestrator.py
src/stwi/t4_orchestrator/interfaces.py
src/stwi/t4_orchestrator/fake_adapters.py
src/stwi/t4_orchestrator/job_store.py
tests/t4_orchestrator/test_t4_runtime_boundaries.py
tests/t4_orchestrator/test_t4_api_http.py
docs/04_AI_Agent_Orchestrator_CF_VLA.md
docs/guides/production_adapter_replacement_runbook.md
```

Do not edit files outside this list for this ticket.

## Forbidden Changes

Do not commit, push, update Linear state, restart Symphony, change `project_contract.json`, wire live Celery, Redis, TimescaleDB, Qdrant, or model services, or edit files outside `Allowed Files`. Do not add dependencies, Kubernetes, secrets manager, tracing stack, model server, workflow, or CI deployment changes.

## Authorization

Codex or Step 3.7 Flash may:
- edit files within `Allowed Files`
- run validators and checks in this packet
- generate artifacts under `docs/project_management/symphony/`
- update Linear state transitions and comments
- restart Symphony if the ticket requires it
- run `git add`, `git commit`, and `git push` for accepted changes

Hermes may not:
- update Linear state
- restart Symphony
- run `git add`, `git commit`, or `git push`

Human review is supervisory and required for:
- final diff/report approval
- safety, legal, contract, privacy boundary decisions
- confirmation that evidence is sufficient before state transitions
- approval of any scope expansion beyond `Allowed Files`

## Acceptance Criteria

1. `STWI_RUNTIME_MODE=production` rejects implicit fake or in-memory adapters before a job can be accepted.
2. Missing real service wiring fails closed with an actionable, non-secret error; no live service is contacted.
3. Job statuses remain `queued`, `running`, `succeeded`, `needs_review`, `failed`, and `expired`; `recommended_action` remains limited to `succeeded`.
4. Focused runtime-boundary and API tests, contract tests, and docs validation pass.
5. No secrets, `.env`, raw video, private weights, private data, dependency, or unrelated implementation files are changed.

## Next Action

Run the bounded checks, then open a draft PR for Human Review before any merge.

## Exact Checks

Run the following before claiming completion:
```powershell
python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries
python -m unittest tests.t4_orchestrator.test_t4_api_http
python -m unittest tests.contracts.test_project_contract
python scripts/validation/validate_docs.py
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

## Required Final Report

A valid final report must contain exactly:
Result:
Changed files:
Checks:
Contract/artifact impact:
Risks/blockers:
Recommended next state:

Note:
- Hermes executor may not commit/push or update Linear state.
- Final commit and Linear state transitions require Codex/Step 3.7 Flash or human authorization.
