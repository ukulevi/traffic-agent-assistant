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

STWI-SYM-024 / TRA-20 - Synchronize Symphony board snapshot after PR #5 tracker backfill

## Branch

Expected ticket branch:
`codex/tra-20-sync-symphony-board-snapshot`

## Worktree Expectation

Run this ticket in an isolated workspace/branch checkout. Do not reuse a
dirty workspace from another ticket. If the working tree already has unrelated
changes, stop for `Human Review` instead of staging mixed changes.

## Phụ trách: Hermes Desktop

Hermes không được phép commit/push hay cập nhật Linear state. Nếu dispatch
gói tin này yêu cầu commit/push, phải là Codex/Step 3.7 Flash hoặc người
dùng trực tiếp thực thi.

## Goal

Synchronize the local Symphony board snapshot after PR #5 tracker backfill. Update only the bounded board artifacts for TRA-6, TRA-19, and TRA-20; regenerate the derived Markdown reports; and prepare evidence for Human Review. Do not commit, push, update Linear, or restart Symphony in this executor pass.

## Allowed Files

```text
docs/project_management/symphony/board.json
docs/project_management/symphony/board.md
docs/project_management/symphony/status_report.md
docs/project_management/symphony/current_dispatch_packet.md
scripts/project_management/symphony_report.py
```

Do not edit files outside this list for this ticket.

## Forbidden Changes

Do not commit, push, update Linear state, restart Symphony, change `project_contract.json`, or edit files outside `Allowed Files`. Do not add Kubernetes, secrets manager, tracing stack, model server, workflow, or CI deployment changes.

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

1. TRA-6 is recorded as `Todo` with the required 12-16 GB GPU benchmark blocker.
2. TRA-19 is recorded as `Done` with the PR #5 retrospective evidence.
3. TRA-20 is recorded as `In Progress`, and `board.md` plus `status_report.md` are regenerated from `board.json`.
4. No secrets, `.env`, raw video, private weights, private data, or unrelated implementation files are changed.

## Next Action

Run the bounded checks, then open a draft PR for Human Review before any merge.

## Exact Checks

Run the following before claiming completion:
```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
python scripts/project_management/symphony_report.py --write-markdown docs/project_management/symphony/board.md
python scripts/project_management/symphony_report.py --write-markdown docs/project_management/symphony/status_report.md
python scripts/project_management/symphony_report.py
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
