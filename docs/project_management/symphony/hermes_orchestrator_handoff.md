# Hermes Orchestrator Handoff

Use this when Hermes Desktop is the active Step 3.7 Flash executor and the
human-approved dispatch packet is the single source of truth. Antigravity is
explicitly excluded from this workflow.

## Current Integration Decision

Use option C:

```text
Step 3.7 Flash or Codex execute bounded allowed-file work through the bridge.
Hermes Desktop remains the bounded executor only.
Hermes MCP is used only for messaging/session/event bridge tasks.
```

Reason: Hermes MCP currently exposes conversation tools, not a complete
worker-runner contract. There is no verified MCP tool to create a new agent run,
set workspace, select model, or return a structured run result. The bridge is
the verified executor wrapper because it reuses the stable Hermes CLI.

## Model Route

Primary: Codex when quota is available.
Fallback: Step 3.7 Flash when Codex is unavailable or on cooldown.

Both executors must follow the same `current_dispatch_packet.md`, `Allowed Files`,
validators, final report contract, and authorization boundaries.

## Default Automation Entrypoint

The canonical sequence for a human-approved dispatch is:

```powershell
python scripts/project_management/hermes_runner_bridge.py --no-write
python scripts/project_management/hermes_runner_bridge.py --runner-command "C:\\Users\\PC\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\hermes.exe" --oneshot {prompt_file}
```

The bridge:
- validates `current_dispatch_packet.md`
- writes prompt and manifest artifacts under `docs/project_management/symphony/hermes_runs`
- runs Hermes in constrained oneshot mode
- writes a machine-readable result for executor review

## Authorization

Codex/Step 3.7 Flash may execute:
- bounded allowed-file changes
- validators and the board/status regeneration commands
- `python scripts/project_management/symphony_report.py`
- `python scripts/project_management/hermes_runner_bridge.py ...`
- Linear state transitions and comments matching `Recommended next state`
- Symphony restart when the ticket explicitly requires it
- `git add`, `git commit`, and `git push` for accepted ticket artifacts

Hermes must not:
- update Linear state
- restart Symphony
- commit, push, or create PRs
- approve outside-allowed-scope work, secrets, live services, or raw video access

## Human Control Points

Human review is supervisory and required for:
- final diff/report approval
- safety, legal, contract, privacy boundary decisions
- confirmation that evidence is sufficient before ticket state changes
- approval of any scope expansion beyond `Allowed Files`
