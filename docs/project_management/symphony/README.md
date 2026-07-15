# STWI Symphony monitoring

This folder is a repository-side mirror for STWI project monitoring. The
primary unattended-agent control plane is OpenAI Symphony, configured under
`C:\Users\PC\.codex\symphony` and governed by the repository `WORKFLOW.md`.
This folder keeps a lightweight task ledger and generated reports for audit,
handoff, and comparison with the Symphony/Linear UI.

## How to use

1. Create Linear issues with the `stwi-agent` label so Symphony can dispatch
   them through `WORKFLOW.md`.
2. Add lane labels such as `lane:data`, `lane:ml`, `lane:rag`, `lane:api`,
   `lane:frontend`, or `lane:qa`.
3. Agents read `AGENTS.md`, `README.md`, `project_contract.json`, and the
   lane-specific canonical docs before updating any task.
4. Each agent owns only its assigned lane and reports evidence paths, test
   commands, blockers, and next action.
5. Status values follow the board columns:
   `Backlog`, `Todo`, `In Progress`, `Human Review`, `Rework`, `Merging`,
   `Done`, `Canceled`, `Duplicate`.
6. Run the report command after task updates:

```powershell
python scripts/project_management/symphony_report.py
```

Create or refresh only selected Linear seeds with the dispatch helper:

```powershell
python scripts/project_management/dispatch_linear_issues.py --seeds=STWI-SYM-016,STWI-SYM-017,STWI-SYM-018,STWI-SYM-019,STWI-SYM-020,STWI-SYM-021
```

Use `--dry-run` first when checking project/team/label resolution.

7. Do not mark a task `Done` unless its acceptance criteria and required
   checks are recorded in `board.json`.

For the Codex Desktop + Hermes Desktop operating model, use
[multi_agent_operating_model.md](./multi_agent_operating_model.md),
[agent_routing.json](./agent_routing.json), and
[hermes_worker_prompts.md](./hermes_worker_prompts.md). Hermes MCP is currently
treated as a messaging/session bridge, not a worker runner; use
[hermes_orchestrator_handoff.md](./hermes_orchestrator_handoff.md) when Hermes
orchestrates Step workers through its native tools.

## Nhập yêu cầu vấn đề linh hoạt

Bạn có thể nhập prompt dài tự do hoặc yêu cầu ngắn chung chung. Điểm quan
trọng là trước khi dispatch cho Codex/Symphony, yêu cầu đó được chuyển thành
brief nhỏ có các mục: ticket, goal, acceptance criteria, allowed files, exact
checks, branch, worktree expectation, và đặc biệt phải giữ lại yêu cầu gốc/bản
ghi yêu cầu gốc kèm interpretation notes nếu có suy luận thêm.

Quy trình chuẩn:
- Bạn nhập yêu cầu tự do.
- Tôi/Hermes chuẩn hóa brief, giữ nguyên yêu cầu gốc, ghi rõ giả định.
- Bạn duyệt khi brief có mục `inferred` hoặc chưa chắc chắn.
- Sau đó mới dispatch cho Codex/Symphony.

Dispatch không được diễn giải một mình; nếu brief ở trạng thái `inferred` về
phạm vi/safety/contract/pháp lý, phải xác nhận lại với người dùng trước khi
thực thi. Xem hướng dẫn tại
[`issue_request_brief_template.md`](./issue_request_brief_template.md).

## Branch/PR isolation

Mỗi ticket phải có một branch riêng theo pattern:
`ticket/<linear-seed>-<short-slug>`. Không push thẳng lên `main`.

- Mỗi ticket chạy trong workspace/branch checkout riêng, không dùng chung
  workspace bẩn giữa các ticket khác nhau.
- Nếu working tree đã có thay đổi không liên quan, dừng lại và chuyển về
  `Human Review` thay vì staging hỗn hợp.
- Khi một commit đã push bị lỗi, revert/fix-forward trên chính branch đó hoặc
  branch fix riêng. Không để một ticket lỗi chặn cả lịch sử clean của các
  ticket khác.

## CI/CD yêu cầu

- CI kiểm tra từng PR branch, không chỉ `main`.
- Bật branch protection: yêu cầu checks pass trước khi merge và chặn direct
  push vào `main`.
- Dùng chung các lệnh kiểm tra trong workflow cho PR checks:
  `validate_docs.py`, focused unit tests, và lane tests liên quan.
- Các job cần private data, live services, training lớn, benchmark hardware,
  release actions, hoặc production credentials phải giữ ngoài unattended CI và
  ở `Human Review`.

## Hermes runner bridge

Use the repository bridge to validate a Codex-authored dispatch packet and
prepare a bounded Hermes prompt:

```powershell
python scripts/project_management/hermes_runner_bridge.py --no-write
python scripts/project_management/hermes_runner_bridge.py --allow-external-code-transfer
```

The first command validates the current packet without writing artifacts. The
second command writes a prompt and manifest under
`docs/project_management/symphony/hermes_runs/`, which is ignored by git because
run prompts are per-session evidence. Attach or paste the prompt into Hermes
Desktop when running manually.

When a stable Hermes CLI entrypoint is confirmed, pass it explicitly:

```powershell
python scripts/project_management/hermes_runner_bridge.py --runner-command hermes --oneshot {prompt_file}
```

The bridge does not change Linear state, restart Symphony, stage, commit, push,
or decide Done/Rework. Hermes must still return the required report fields and
stop at Human Review for Codex review.

## Local Symphony checks

The local MCP adapter is configured in `C:\Users\PC\.codex\config.toml` as
`mcp_servers.symphony`. A setup check can be run with:

```powershell
python C:\Users\PC\.codex\mcp\symphony_mcp_server.py --check
```

Use `.env.local` for project-local secrets. This file is ignored by git and
should contain values such as `STWI_RTSP_URL` and `LINEAR_API_KEY`. If the
key exists only in a PowerShell session but is not visible to
Codex, persist it once from that same session:

```powershell
& C:\Users\PC\.codex\symphony\persist-env.ps1
```

Do not use `.env.symphony.local` as a bootstrap path anymore.

The Symphony dashboard URL is printed when the service is started. The previous
local log showed a dashboard on `http://127.0.0.1:4011`, but the active port can
change per launch.

## Workspace creation and polling

`WORKFLOW.md` polls Linear every five minutes:

```yaml
polling:
  interval_ms: 300000
```

Do not lower this during low-quota periods. Manual coordinator checks are
cheaper than keeping Symphony in a tight background loop.

For issue workspaces, keep one isolated workspace per issue so diffs, tests,
and Human Review remain auditable. The workflow now prefers a local repository
reference when `SYMPHONY_REPO_REFERENCE` is configured:

```sh
git clone --shared "$SYMPHONY_REPO_REFERENCE" .
```

If that variable is absent, it falls back to the remote shallow clone. A single
fixed mutable workspace is not recommended for this project because it can mix
unrelated issue diffs and make cleanup/review unsafe.

## Dirty working tree intake

Before starting a new feature/config branch or resuming an old session in a
dirty checkout, run the read-only intake:

```powershell
python scripts/project_management/worktree_intake.py
```

JSON output is available for handoff notes:

```powershell
python scripts/project_management/worktree_intake.py --json
```

The report groups pending changes by review ownership such as
`project-management`, `ci-release`, `data-vision`, `source-of-truth-docs`,
`runtime-src`, and `tests`. It also flags untracked files, source-of-truth
documents, CI workflows, evidence manifests, generated/private paths, and large
release artifacts.

Use the intake output as a branch/session gate:

1. Review and stage one group at a time.
2. Keep generated manifests and private/generated artifacts separate from
   source changes.
3. Resolve `source-of-truth` and `ci-workflow` flags before broad implementation
   work.
4. Do not stash, delete, or revert another user's changes unless the human lead
   explicitly requests it.

## Token and rate-limit guard

Run the budget guard before dispatching a batch, every few minutes while
Symphony is running, and before restarting after a stop:

```powershell
python scripts/project_management/symphony_budget_guard.py
```

The guard reads the local dashboard `/api/v1/state`, estimates tokens per
minute, projects the next 10 minutes, checks visible rate-limit pressure, and
prints one of `ok`, `watch`, `throttle`, or `stop`. It cannot read provider
billing quota directly, so use rate-limit percentage as the live remaining
capacity signal.

Default operating thresholds:

- `watch`: continue observing; do not increase concurrency yet.
- `throttle`: do not dispatch new issues; let the current batch finish.
- `stop`: stop Symphony or move active issues to `Human Review`.

Default thresholds are intentionally conservative for low-quota periods:

- issue `throttle` around 300k tokens;
- issue `stop` around 900k tokens without useful progress;
- batch `throttle` around 750k tokens;
- batch `stop` around 1.5M tokens;
- rate-limit `throttle` at 35% and `stop` at 50%.

Use JSON output for automation:

```powershell
python scripts/project_management/symphony_budget_guard.py --json
```

## Context caching posture

OpenAI/Codex context caching is provider-managed; this repository cannot force
provider billing behavior from `WORKFLOW.md`. The workflow is tuned to improve
cache hit rate by keeping repeated context stable:

- agents read `AGENTS.md`, `README.md`, `project_contract.json`, `WORKFLOW.md`,
  and the lane doc in a consistent order;
- agents avoid pasting full logs, generated reports, large diffs, vendored
  trees, or broad search output into context;
- repeated turns inspect changed ranges and command summaries instead of
  reloading unchanged files.

If a task needs broad whole-repo context, keep it one-agent, one-turn, and move
the issue to `Human Review` after the first inconclusive pass.

The repository also includes a best-effort `.codexignore` at the project root.
It excludes cache/build folders, private STWI data, media, logs, archives, and
model weights while keeping canonical source-of-truth files visible. Do not add
blanket patterns such as `*.json`, because `project_contract.json` and the
Symphony board JSON are required operating context.

Startup reads are intentionally bounded. After `AGENTS.md`, `README.md`,
`project_contract.json`, `WORKFLOW.md`, and the relevant lane-doc section, an
agent may inspect at most about three additional files or 600 lines before it
must edit, narrow the scope, or stop for `Human Review`.

Avoid frequent edits to `WORKFLOW.md`, `AGENTS.md`, or other repeated startup
instructions during a batch. Change them deliberately, then restart with a
small batch so context caching can stabilize again.

## Codex Desktop configuration notes

This Windows setup uses the global Codex config at:

```text
C:\Users\PC\.codex\config.toml
```

Current Symphony limits are controlled by `WORKFLOW.md` and the synced global
workflow copy under `C:\Users\PC\.codex\symphony\workflows\WORKFLOW.stwi.md`,
not by generic `max_iterations`, `max_retries`, or `auto_approve` keys in the
Codex config. Do not add unsupported keys to `config.toml`; prefer the workflow
controls that the installed Symphony runtime already reads:

- `agent.max_concurrent_agents: 1`
- `agent.max_turns: 1`
- `agent.on_max_turns: human_review`
- `agent.max_retry_backoff_ms: 900000`
- `polling.interval_ms: 300000`
- `codex.approval_policy: never`
- `codex.turn_timeout_ms: 900000`

For unattended Symphony runs, `approval_policy: never` is intentionally safer
than auto-approving privileged actions: agents cannot request escalation and
must stop for `Human Review` on PR creation, release, destructive actions,
secrets, private data, live services, and contract changes.

The installed Symphony runtime names its generic terminal handoff state
`Human Review`, while this Linear team exposes `In Review`. After every
one-turn batch, the Codex coordinator must map that stop to `In Review` and
review the worker transcript/diff before any user final acceptance. It must
never leave an active ticket running solely because its Linear state was not
updated, and it must never mark `Done` automatically.

## Provider budget caps

If Symphony is backed by an OpenAI API key or a future provider adapter, set the
hard daily spend cap in the provider dashboard or organization billing controls.
The repository budget guard is only a local operational signal; it cannot
prevent API billing by itself.

Recommended operating mode while quota is low:

1. Dispatch at most one `In Progress` issue.
2. Run the budget guard before and during the batch.
3. Stop Symphony or move the issue to `Human Review` when the guard prints
   `stop`.
4. Continue coordination from Claude Desktop only after the Linear/Symphony
   state is updated, not as an unattended automatic model switch.

## GitHub Actions quota posture

GitHub Actions is used as a deterministic verification layer, not as a
Symphony/LLM agent runtime.

Automatic workflows:

- `stwi-fast-ci.yml`: lightweight PR/main guard for docs validation, contract
  tests, CI hygiene, project-management tooling tests, JavaScript syntax, and
  whitespace.
- `build.yml`: report PDF build only when report/docs/contract validation paths
  change, plus manual dispatch.
- `pages.yml`: GitHub Pages deploy only when `slides/**` or the Pages workflow
  changes, plus manual dispatch.

Manual workflow:

- `stwi-manual-qa.yml`: `workflow_dispatch` suites for `core`,
  `project-management`, `tier3-offline`, `tier4-contracts`, or `all-light`.

Quota controls:

- Use `ubuntu-latest` only.
- Keep fast CI timeout at 10 minutes and manual QA timeout at 20 minutes.
- Use `concurrency.cancel-in-progress: true` for non-Pages verification jobs.
- Keep default `permissions: contents: read`; do not grant write permissions to
  agent-like jobs.
- Do not store Linear/OpenAI/Roboflow/HF/production secrets in these workflows.
  Jobs that require private data, live services, model training, benchmark
  hardware, commits, PR creation, or release actions stay in `Human Review`.

## Workspace cleanup

Each issue can leave an independent workspace under
`%USERPROFILE%\.codex\symphony\workspaces`. Start with a dry-run inventory:

```powershell
python scripts/project_management/symphony_workspace_cleanup.py
```

JSON output:

```powershell
python scripts/project_management/symphony_workspace_cleanup.py --json
```

The script marks only stale, clean git workspaces as deletion candidates. It
keeps workspaces with uncommitted changes, unknown git status, protected names,
or paths outside the configured root. Actual deletion requires both
`--execute` and `--yes` and should happen only after Human Review of the dry-run
report.

## Claude handoff

When Codex interactive quota or Symphony rate-limit headroom is too low, keep
the same Linear board state and hand off coordination to Claude Desktop through
the local `symphony` MCP server. The MCP sync and provider limitations are
documented in [claude_handoff.md](./claude_handoff.md).

Quick dry-run:

```powershell
python scripts/project_management/sync_codex_claude_mcp.py
```

Quick write to Claude Desktop config:

```powershell
python scripts/project_management/sync_codex_claude_mcp.py --write
```

This mirrors portable MCP declarations only. It does not copy secrets, Codex
plugins, skills, OAuth sessions, browser state, or a Claude model runtime for
Symphony.

## Reasoning effort policy

The STWI Symphony workflow explicitly runs approved in-tenant Codex workers
with the configured Terra route:

```text
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
model_reasoning_summary = "auto"
```

Use this bounded medium-reasoning route only for issues carrying
`codex-symphony-approved`, with explicit acceptance criteria and one active
issue. Do not leave broad or ambiguous tasks in `In Progress`; split them
first.

Safety/legal semantics, contract changes, cross-artifact release decisions,
and multi-subsystem root-cause analysis remain Codex lead-review work. Do not
raise worker reasoning beyond Medium or broaden the batch without an explicit
workflow change and a new cost/safety review.

## Reporting cadence

- Daily: agents update lane status, blockers, and next action.
- Before handoff: lead agent compares Symphony/Linear status with this mirror
  and runs the report script plus required QA checks.
- Before release: run `$stwi-release-qa` and attach its result to the board.

## Agent report intake

Progress and production-readiness reports generated by external agents are
roadmap signals, not source-of-truth updates. Convert them through
[roadmap_intelligence_2026-07-03.md](./roadmap_intelligence_2026-07-03.md)
before changing the board, contract, issue plan, implementation docs, or
runtime architecture.
