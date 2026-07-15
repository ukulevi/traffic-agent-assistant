# Current Dispatch Packet

Status: completed - user accepted TRA-40; TRA-41 is active but not yet dispatched

## Model Route

Executor: Hermes native through Nous Portal.
Mandatory reviewer/coordinator: Codex.
Final approver: the user after Codex accepts the implementation evidence.

Hermes runtime configuration is verified as provider `nous`, model
`stepfun/step-3.7-flash:free`, and `agent.reasoning_effort: xhigh`.

Hermes role: bounded executor only, through:

```powershell
python scripts/project_management/hermes_runner_bridge.py --runner-command "C:\Users\PC\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" --oneshot <prompt_file>
```

Do not use Antigravity in this workflow.

## Original Request

The user reviewed the blocker backlog, authorized creation of the prioritized
Linear tickets, requested reconciliation of old tickets first, and then asked
Symphony to begin implementation immediately.

## Interpretation Notes

- Linear is the operational source of truth; this repository snapshot and dispatch packet are generated evidence for the next safe dispatch.
- Exactly one implementation ticket is dispatchable through native Hermes:
  `STWI-SYM-031 / TRA-40`.
- Native Symphony/Codex must remain stopped for the entire sidecar run.
- Hermes native smoke returned `HERMES_NATIVE_OK`; Portal reports provider
  `nous` and model `stepfun/step-3.7-flash:free`.
- The issue must carry `hermes-approved`, never `codex-symphony-approved`.
- The first Hermes turn produced an in-scope but invalid diff. This is one
  explicit Rework continuation, not an automatic retry.

## Rework Evidence

- `validate_provisional_phase2_gate.py` now has an unterminated mixed-quote
  module docstring and broken multiline `ValueError` string.
- The first turn also rewrote most double quotes to single quotes without need.
- Restore the original file formatting and make only the smallest import-path
  repair required for repository-root execution.
- Preserve the focused measured-evidence fixture addition if its test remains
  necessary and passing.
- Do not touch any new file and do not broaden the ticket.
- The explicit Rework turn repaired syntax and passed bridge scope/report
  validation, but retained broad quote-style churn in the validator. Do not run
  another worker until a reviewer narrows the desired final diff.
- Independent verification also found
  `gate_p3_validator.py --help` still fails with
  `ModuleNotFoundError: No module named 'tests'`; the worker report claiming
  this check passed is not accepted as release evidence.
- This is the third and final bounded Hermes turn for `TRA-40`. Codex has
  narrowed the repair below; do not broaden or perform unrelated cleanup.
- The user explicitly approved transmitting the three allowed files and bounded
  prompt to Hermes/Nous for this final Rework turn.
- The final turn completed, but independent Codex verification still fails
  `gate_p3_validator.py --help` with `ModuleNotFoundError: No module named
  'tests'`.
- On 2026-07-15, the user explicitly approved a new Hermes Rework cycle limited
  to repository-root/import repair in the two validators below. This approval
  resets the bounded cycle only for this exact scope; no third file or unrelated
  cleanup is authorized.
- The attempted Hermes dispatch was rejected before transmission because the
  repository is not clearly public and Nous Portal is an untrusted external
  destination under the active tenant policy. Do not retry or route around this
  control. A new user decision is required after disclosure of this export risk.
- The user subsequently confirmed they understand and accept transmission
  outside the tenant, have authority to share both validator files, and confirm
  that neither contains secrets or prohibited data. This informed approval is
  limited to this TRA-40 repair cycle and the two allowed files.
- The first checkout for this cycle inherited stale HEAD `71a44c6` and lacked
  `tests/t3_knowledge/test_t3_retrieval_questions.py`; Hermes correctly stopped
  before editing. The replacement worktree is based on current main `9354ec6`,
  contains that test module, and has only the two allowed validator files dirty.
  Execute the repair immediately; do not ask for another pre-edit confirmation.
- Codex rejected the next output because it still used `parents[1]`. For files
  under `scripts/validation/`, repository root is exactly
  `Path(__file__).resolve().parents[2]`; `parents[1]` is only `scripts`.
  In both validators define/use the repository root from `parents[2]`, insert
  that root and `<root>/src` into `sys.path` as needed, and make no other change.
  Restore the unrelated multiline `ValueError` formatting to HEAD. This is the
  final Rework turn in the newly approved cycle; execute without confirmation.
- The final Hermes turn used `parents[2]`; Codex independently verified both
  CLI help paths, merged the previously produced measured-evidence test fixture,
  and ran the full suite with the existing ignored/private mock gate artifacts.
  Result: 309 tests pass with 13 explicit skips, CI guardrails pass, release QA
  passes, and `git diff --check` passes. No further Hermes dispatch is allowed;
  TRA-40 now waits for user final acceptance.

## Ticket

STWI-SYM-031 / TRA-40 - Repair full-suite, phase-gate, and CI evidence integrity

## Next Activation

The user accepted TRA-40 on 2026-07-15. Linear TRA-40 is `Done`; TRA-41 is
`In Progress` with `reasoning:high`. TRA-41 defaults to the in-tenant Codex
worker route `gpt-5.6-terra` at medium reasoning effort. Hermes/Nous source
code transmission is denied by default; it requires separate ticket-specific
informed approval after a data-classification review.

## Branch

Use the existing isolated Symphony workspace for `TRA-40`. The Hermes worker
must not create or switch branches; branch/commit/PR actions remain coordinator
or human-owned.

## Worktree Expectation

Run this ticket in an isolated workspace/branch checkout. Do not reuse a dirty
workspace from another ticket. If the working tree already has unrelated
changes, stop for `Human Review` instead of staging mixed changes.

## Phụ trách: Hermes Desktop

Hermes không được phép commit/push hay cập nhật Linear state. Nếu dispatch gói
tin này yêu cầu commit/push, phải là Codex/Step 3.7 Flash hoặc người dùng trực
tiếp thực thi.

## Goal

Produce a minimal reviewable diff that fixes only repository-root/import setup
in both validators. Preserve all other behavior and formatting already present.

## Allowed Files

```text
scripts/validation/validate_provisional_phase2_gate.py
scripts/validation/gate_p3_validator.py
```

## Forbidden Changes

Do not change `project_contract.json`, API/runtime behavior, schemas, dependencies,
model artifacts, benchmark thresholds, or unrelated files. Do not weaken tests,
turn failures into skips, or suppress failing evidence. The worker may not commit,
push, update Linear state, transitions, or comments, or restart Symphony.
Use the HEAD version as a read-only formatting reference; do not use checkout,
reset, clean, or other destructive Git commands. Remove quote-style churn.

## Acceptance Criteria

1. Both phase-gate validator entrypoints execute from repository root without
   syntax/import failure; `ROOT` resolves to the repository root, not `scripts`.
2. `python -m unittest discover -s tests -v` completes with a real pass/fail verdict instead of aborting during discovery or setup.
3. CI guardrails invoke commands that exist and preserve mandatory HTTP/runtime checks.
4. Existing focused regression tests remain passing; do not modify tests in this cycle.
5. No test, threshold, contract, API, or runtime boundary is weakened.

## Expected State

Hermes returns to Codex Review. Codex may dispatch bounded Rework inside this
ticket scope. After Codex accepts the result, the ticket waits for user final
approval before Codex changes Linear state or activates the next ticket.

## Exact Checks

Run the following before claiming completion:

```powershell
python scripts/validation/validate_provisional_phase2_gate.py --help
python scripts/validation/gate_p3_validator.py --help
python -m unittest tests.t2_forecast.test_phase2_provisional_gate
python -m unittest discover -s tests -v
python scripts/validation/validate_ci_guardrails.py
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
git diff --check
```

## Required Final Report

A valid final report must contain exactly:

```text
Result:
Changed files:
Checks:
Contract/artifact impact:
Risks/blockers:
Recommended next state:
```

Note:
- Hermes executor may not commit/push or update Linear state.
- Hermes never commits or changes Linear state.
- Codex owns review and bounded Rework dispatch.
- Linear `Done` and next-ticket activation require explicit user confirmation.
