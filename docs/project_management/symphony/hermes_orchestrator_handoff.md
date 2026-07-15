# Hermes Orchestrator Handoff

Use this when Hermes Desktop is the active Step 3.7 Flash executor and the
human-approved dispatch packet is the single source of truth. Antigravity is
explicitly excluded from this workflow.

## Current Integration Decision

Use the Hermes native sidecar architecture:

```text
Linear remains the queue source of truth.
The workspace stays under the Symphony workspace root.
Hermes native CLI executes the bounded packet through the bridge.
Codex reviews the resulting diff; native Symphony/Codex stays stopped.
```

Reason: Symphony requires the Codex app-server protocol, while Hermes exposes a
native oneshot/ACP surface rather than a Codex app-server-compatible worker.
Pointing `codex.command` at Hermes would fail the protocol handshake. The bridge
therefore invokes Hermes directly with prompt content and the isolated ticket
workspace as `cwd`, then validates changed-file scope and report structure.

## Model Route

Primary executor: Hermes native route configured in Hermes/Nous Portal as
`stepfun/step-3.7-flash:free` with `agent.reasoning_effort: xhigh`.
Mandatory reviewer and coordinator: Codex reviews every Hermes output.
Final approver: the user, after Codex presents a consolidated accepted result.

External-code policy: Hermes/Nous is denied by default. It may receive source
code only after a ticket-specific informed approval confirms the allowed files
contain no secret, private, or prohibited data. Otherwise use the in-tenant
Codex app-server worker with `gpt-5.6-terra` at medium reasoning effort.

Both executors must follow the same `current_dispatch_packet.md`, `Allowed Files`,
validators, final report contract, and authorization boundaries.

## Default Automation Entrypoint

The canonical sequence for a human-approved dispatch is:

```powershell
python scripts/project_management/hermes_runner_bridge.py --no-write --repo-root "C:\\Users\\PC\\.codex\\symphony\\workspaces\\TRA-XX"
python scripts/project_management/hermes_runner_bridge.py --allow-external-code-transfer --repo-root "C:\\Users\\PC\\.codex\\symphony\\workspaces\\TRA-XX"
```

The bridge:
- validates `current_dispatch_packet.md`
- writes prompt and manifest artifacts under `~/.codex/symphony/logs/hermes_runs/<TRA-ID>`
- runs Hermes in constrained oneshot mode
- uses prompt content rather than passing a prompt-file path as the prompt
- fails closed when the workspace is dirty, a changed file is outside
  `Allowed Files`, or the final report contract is incomplete
- writes machine-readable evidence for Codex/human review

## Executor Labels

- `hermes-approved`: native Hermes sidecar only.
- `codex-symphony-approved`: native Symphony/Codex app-server only.
- `symphony-approved`: legacy label; not dispatchable.

Never apply both active executor labels to one issue. Keep native Symphony
stopped for the entire Hermes sidecar run.

## Authorization

Codex may:
- review diffs and independently rerun validators;
- prepare narrower same-ticket Rework packets;
- invoke `hermes_runner_bridge.py` for bounded Hermes execution;
- update local review evidence and executor labels;
- present the consolidated accepted result to the user.

Codex may change the ticket to `Done`, activate the next ticket, stage, commit,
push, or create a PR only after the corresponding explicit user confirmation.

Hermes must not:
- update Linear state
- restart Symphony
- commit, push, or create PRs
- approve outside-allowed-scope work, secrets, live services, or raw video access

## Review Loop and Human Control Points

1. Hermes returns evidence to Codex, never directly as a final user handoff.
2. Codex reviews the real diff and reruns decisive checks.
3. If correction remains inside the approved ticket scope, Codex prepares a
   narrower packet and runs Hermes again without asking the user to review the
   intermediate failure.
4. Codex stops after at most three bounded turns or immediately when a contract,
   safety, legal, privacy, credential, live-service, destructive, or scope
   decision is required.
5. Once Codex accepts the result, the user performs the final review. Only the
   user's confirmation authorizes Codex to mark the ticket Done and move to the
   next ticket.
