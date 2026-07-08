# STWI Multi-Agent Operating Model

This runbook lets Codex Desktop, Hermes Desktop, and Symphony work together
without weakening STWI contract, privacy, or safety constraints.

## Control Plane

Linear remains the source of truth for issue state. Symphony is the queue and
workspace control plane. Codex Desktop is the lead engineer and final review
gate. Hermes Desktop is the Step 3.7 Flash orchestrator and worker surface for
bounded execution.

Do not let desktop agents coordinate by editing the same checkout at the same
time. Each issue needs an isolated workspace, a clear file scope, and a final
Human Review handoff before merge.

## Role Split

| Surface | Role | Default model route | Allowed decisions |
|---|---|---|---|
| Symphony | Queue and workspace coordinator | n/a | Dispatch, stop, and state hygiene only |
| Codex Desktop | Planner, reviewer, release gate | GPT-5.5 or high-reasoning model | Scope, safety, Rework/Done recommendation, commit/push when user asks |
| Hermes Desktop | Step orchestrator and worker UI | Step 3.7 Flash through Nous Portal only | Execute exact plan and report evidence |

Codex should write the plan before Hermes executes. Hermes should not broaden
scope or decide that a task is Done by itself.

## Hermes MCP Reality Check

The Hermes MCP server is currently treated as a conversation bridge, not a
worker runner. Its observed tool surface is messaging/session/event oriented:

```text
conversations_list
conversation_get
messages_read
attachments_fetch
events_poll
events_wait
messages_send
channels_list
permissions_list_open
permissions_respond
```

This is enough for handoff notes, session observation, and permission response,
but not enough for Codex/Symphony to start a structured Hermes agent run with
workspace, prompt, model override, timeout, and result schema.

Therefore the selected integration direction is:

```text
Hermes orchestrates Step workers through its native tools.
Codex prepares issue briefs and reviews the resulting diff.
Symphony/Linear provide state and queue discipline.
Hermes MCP is optional messaging glue, not the execution runner.
```

## Model Routing

Use Step 3.7 Flash through Nous Portal for low-reasoning executor work:

- bounded implementation from a complete plan;
- documentation or generated-artifact sync;
- small test updates;
- focused test execution and evidence collection;
- mechanical refactor inside listed files.

Use GPT-5.5 through Codex Desktop for:

- issue planning and decomposition;
- ambiguous failures or root-cause analysis;
- code review and release gate decisions;
- API/status, safety, legal, RAG, or contract semantics;
- merge readiness and Linear state decisions.

Hermes Desktop does not perform high-reasoning review in this setup. If a
Hermes worker hits ambiguity, unclear test failures, contract/safety/legal
questions, or any gated authority boundary, it must stop and return the issue
to Codex Desktop review.

## Dispatch Gate

Before a worker starts, the issue brief must include:

```text
linear_identifier:
goal:
allowed_files:
forbidden_changes:
acceptance_criteria:
exact_checks:
expected_final_state:
```

Stop for Human Review if any field is missing or if the task asks for secrets,
private data, raw video, live services, new dependencies, release actions,
contract changes, API status changes, safety policy changes, or destructive
operations.

## Concurrency

Default mode is one active implementation issue at a time. Parallel work is
allowed only when all conditions hold:

- each issue has a separate workspace;
- file scopes do not overlap;
- no issue touches contract, API status, safety, legal, private data, live
  services, or release actions;
- each worker stops at reviewable diff;
- Codex or the human lead reviews before merge.

For the current STWI state, keep Symphony stopped until TRA-12 leaves Human
Review. After TRA-12 is accepted or moved to Rework with no active worker,
dispatch TRA-14 before TRA-15.

## Worker Lifecycle

1. Codex prepares the issue brief and model route.
2. Symphony/Linear identify exactly one eligible issue; keep retry-prone
   Symphony runs stopped until the workspace is ready.
3. Hermes executes only the brief through its native worker tools, such as
   terminal/file/browser/delegate_task/chat or oneshot surfaces when available.
4. Worker runs exact checks or records why a check cannot run.
5. Worker reports and stops at `Human Review`.
6. Codex Desktop reviews the diff and decides `Done`, `Rework`, or further Human
   Review.
7. User asks Codex to stage, commit, or push only after review passes.

## Current First Use

Use Hermes Step Executor for the TRA-12 Rework P2 only if the allowed scope is:

```text
scripts/project_management/symphony_report.py
docs/project_management/symphony/board.json
docs/project_management/symphony/board.md
docs/project_management/symphony/status_report.md
```

The worker must update the renderer so generated board/status output preserves
the Readiness Handoff Summary, then regenerate the markdown reports and stop.

## Restart Checklist

Before restarting Symphony:

```powershell
python scripts/validation/validate_ci_guardrails.py
python scripts/project_management/symphony_budget_guard.py --url http://127.0.0.1:4000/api/v1/state
```

If the dashboard is stopped or unreachable, treat it as stopped state, not a
reason to dispatch blindly. Confirm Linear has no stale `In Progress` issue
from a previous retry loop.
