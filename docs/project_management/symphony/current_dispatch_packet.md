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

- Linear is the operational source of truth; this repository snapshot and dispatch packet are generated evidence for the next safe dispatch.
- This packet is bounded read/execute evidence only; it does not authorize state changes outside the approved CI/docs boundary.

## Ticket

STWI-SYM-026 / TRA-23 - Make Tier-4 HTTP API tests mandatory for MVP demo CI

## Branch

Expected ticket branch:
`codex/tra-23-mandatory-http-api-ci`

## Worktree Expectation

Run this ticket in an isolated workspace/branch checkout. Do not reuse a
dirty workspace from another ticket. If the working tree already has unrelated
changes, stop for `Human Review` instead of staging mixed changes.

## Phụ trách: Hermes Desktop

Hermes không được phép commit/push hay cập nhật Linear state. Nếu dispatch
gói tin này yêu cầu commit/push, phải là Codex/Step 3.7 Flash hoặc người
dùng trực tiếp thực thi.

## Goal

This is the first bounded demo wave ticket. Make the Tier-4 HTTP API tests a
mandatory CI gate using only the existing orchestrator extra. Do not weaken
tests, skip categories, or expand dependencies.

## Allowed Files

```text
.github/workflows/stwi-fast-ci.yml
.github/workflows/stwi-manual-qa.yml
```

## Forbidden Changes

Do not commit, push, update Linear transitions or comments, restart
Symphony, change `project_contract.json`, API docs, or runtime behavior.
Do not add dependencies, Kubernetes, secrets manager, tracing stack, model
server, workflow changes outside the exact CI gating boundary, or unrelated
files.

## Authorization

Codex or Step 3.7 Flash may:
- edit files within `Allowed Files`
- run validators and checks in this packet
- run `git add`, `git commit`, and `git push` for accepted changes

Hermes may not:
- update Linear transitions or comments
- restart Symphony
- run `git add`, `git commit`, or `git push`

The worker may only report evidence; it may not update Linear.

Human review is supervisory and required for:
- final diff/report approval
- safety, legal, contract, privacy boundary decisions
- confirmation that evidence is sufficient before any state transition
- approval of any scope expansion beyond `Allowed Files`

## Acceptance Criteria

1. Fast CI installs the existing orchestrator extra and runs
   `tests.t4_orchestrator.test_t4_api_http`.
2. The 36 HTTP tests run with no dependency-only skips.
3. No code, dependency, test-file, API, runtime, contract, or deployment
   boundary is weakened.

## Next Action

Run the bounded checks and submit evidence to Codex for a draft PR.

## Exact Checks

Run the following before claiming completion:
```powershell
python scripts/validation/validate_ci_guardrails.py
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
python -m unittest tests.t4_orchestrator.test_t4_api_http
python -m unittest tests.t4_orchestrator.test_t4_contracts tests.t4_orchestrator.test_t4_safety tests.t4_orchestrator.test_t4_runtime_boundaries
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
