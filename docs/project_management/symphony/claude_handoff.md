# Claude handoff and MCP sync

Last reviewed: 2026-07-03

## Objective

Let a Claude-side operator continue the same STWI/Symphony workflow when the
interactive Codex quota is unavailable, without copying secrets or re-creating
every local MCP declaration by hand.

## What can be synced

Portable MCP server declarations can be mirrored from:

```text
C:\Users\PC\.codex\config.toml
```

to Claude Desktop's local config:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

Use the repository script:

```powershell
$PY = "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $PY scripts/project_management/sync_codex_claude_mcp.py
```

The default command renders JSON to stdout only. To write the Claude Desktop
config, run:

```powershell
$PY = "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $PY scripts/project_management/sync_codex_claude_mcp.py --write
```

The script merges existing `mcpServers`, backs up an existing Claude config as
`claude_desktop_config.json.bak`, and copies environment variable references
such as `${LINEAR_API_KEY}` rather than secret values.

By default it includes local stdio MCP servers such as:

- `symphony`
- `data-science`

By default it skips:

- Codex-internal servers such as `node_repl`;
- package-manager launched servers such as `npx` unless explicitly allowed;
- remote HTTP MCP servers, which should be added in Claude through connectors
  or included only when the Claude client/config explicitly supports HTTP MCP
  JSON entries.

To render remote HTTP entries for a compatible Claude client, use:

```powershell
& $PY scripts/project_management/sync_codex_claude_mcp.py --include-remote-http
```

## What cannot be synced 1:1

Codex plugins and skills are not the same thing as Claude Desktop MCP servers.
The sync script does not copy:

- Codex plugin manifests or cached plugin code;
- Codex-only skills and app affordances;
- OAuth sessions, bearer tokens, API keys, or secrets;
- browser/app state from the Codex desktop runtime.

For remote tools such as Figma, Firecrawl, Roboflow, Composio, GitHub, or
Hugging Face, prefer adding the matching Claude connector/OAuth integration in
Claude. If a remote MCP endpoint is supported directly by the Claude client,
keep the token in the user environment and use `--include-remote-http`.

## Symphony provider fallback reality check

The installed Symphony runtime currently launches a Codex app-server through
the single `codex.command` setting in `WORKFLOW.md`. It expects Codex app-server
protocol events. Claude Desktop does not expose a drop-in Codex app-server
protocol endpoint, so Symphony cannot automatically switch from Codex quota to
Claude Sonnet 5 by changing only `WORKFLOW.md`.

Use this safe handoff policy until a real provider adapter or wrapper exists:

1. Run Symphony with Codex as the primary unattended agent runtime.
2. Poll the budget guard:

   ```powershell
   $PY = "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
   & $PY scripts/project_management/symphony_budget_guard.py
   ```

3. If the guard says `stop`, Codex quota is exhausted, or rate-limit pressure is
   high, stop dispatching new Codex issues and move active issues to
   `Human Review` or leave them ready for handoff with a short status note.
4. Open Claude Desktop, use the synced `symphony` MCP server to inspect
   `symphony_status`, `symphony_list_workflows`, and logs, then continue
   coordination from the same Linear issue state.
5. Keep Claude-side work under the same `AGENTS.md`, `project_contract.json`,
   and `$stwi-*` workflow constraints. Do not approve live RTSP, private data,
   secrets, destructive actions, or release actions from an unattended run.
6. If Claude continues coordination, keep the same cost posture: one active
   issue, one pass, targeted reads, and Human Review for broad or risky work.
   Do not ask Claude to re-read the whole Codex workspace history unless a
   specific path or diff is needed.

## Path to true automatic model fallback

True automatic fallback requires one of these implementation tracks:

- a Symphony provider adapter that can launch Claude/Anthropic as an agent
  runtime and normalize its events to Symphony's expected protocol;
- a wrapper command that exposes the Codex app-server-compatible protocol while
  routing turns to Codex first and Claude Sonnet 5 second;
- a coordinator service that stops the Codex-backed Symphony batch, rewrites the
  provider workflow safely, and starts a Claude-backed batch with equivalent
  guardrails.

Until then, treat "Codex first, Claude second" as an explicit handoff, not an
unattended automatic switch.

## Environment checklist

Keep secrets in the user environment, not in repo files or config JSON:

- `LINEAR_API_KEY`
- `SOURCE_REPO_URL`
- `SYMPHONY_HOME`
- `SYMPHONY_WORKSPACE_ROOT`
- `SYMPHONY_LOGS_ROOT`
- `SYMPHONY_WORKFLOWS_ROOT`
- `SYMPHONY_COMMAND`
- `SYMPHONY_ROOT`
- tool-specific tokens such as `FIRECRAWL_API_KEY`, `ROBOFLOW_MCP_TOKEN`, or
  `HF_TOKEN`

If a future Claude provider adapter is added, configure the exact Claude model
identifier there. Do not hard-code a marketing name such as "Sonnet 5" in a
runtime command until the installed Claude/Anthropic client confirms the
accepted model id.
