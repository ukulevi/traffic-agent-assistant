# Symphony restart priority plan

Last reviewed: 2026-07-03

## Objective

Restart Symphony only after the active queue is ordered so agents work on small,
safe, high-signal tasks and do not resume broad or already-suspect work.

## Required preflight before restart

1. Keep live RTSP endpoint values out of Linear, repository files, logs, and
   manifests. Use only the source alias `edge_camera_1` in issue text.
2. Move or relabel previously active high-token issues before restart:
   - TRA-5 should be reviewed before any further unattended Symphony run.
   - If TRA-5 remains `Todo` with `symphony-approved`, Symphony may resume it
     before newer RTSP tasks.
3. Keep live RTSP smoke testing in `In Review` or equivalent Human Review state.
   It must not have `symphony-approved` until a human-supervised run is intended.
4. Start with only one auto-safe issue active whenever possible. Keep
   `agent.max_concurrent_agents: 1` and `agent.max_turns: 1`.
5. Confirm `WORKFLOW.stwi.md` contains the cost controls and improvement
   proposal protocol before restart.

## Recommended execution order

| Order | Issue | Action before restart | Why |
|---:|---|---|---|
| 0 | TRA-5 / STWI-SYM-002 derivative | Move to `In Review`, `Done`, or remove `symphony-approved` | It already produced a large diff and high token usage; review before continuing. |
| 1 | TRA-9 / STWI-RTSP-001 | Keep `Todo` + `symphony-approved` | Prepares RTSP guardrails offline without opening the live stream. |
| 2 | TRA-10 / STWI-RTSP-002 | Keep `Todo` + `symphony-approved` after TRA-9 finishes | Documents the supervised RTSP procedure after code guardrails are checked. |
| 3 | TRA-11 / STWI-RTSP-003 | Keep `In Review`; no `symphony-approved` | Requires external service access and human-supervised handling of live video evidence. |
| 4 | TRA-7 / STWI-SYM-009 | Run after RTSP guardrails if API runtime is next priority | Local fail-closed adapter validation; useful but less urgent than RTSP safety setup. |
| 5 | TRA-6 / STWI-SYM-005 | Run only when benchmark evidence path is clear | May consume tokens without approved hardware/profile evidence. |
| 6 | TRA-8 / STWI-SYM-011 | Run after implementation/review queue stabilizes | Release QA is valuable only after active changes stop moving. |

## Hold for Human Review

- TRA-11 live RTSP smoke test.
- Any task that requires reading/writing `data/quarantine`, private frames,
  private datasets, model weights, credentials, external services, or live
  network calls.
- Any task that changes contract invariants, safety policy, legal evidence
  rules, SLA, API status semantics, tensor shapes, feature order, or stack.

## Suggested restart sequence

1. Review TRA-5 workspace diff and decide whether to preserve, rework, or close.
2. Ensure TRA-5 is no longer Symphony-active.
3. Keep TRA-9 as the first active `Todo` issue.
4. Restart Symphony and monitor `/api/v1/state` after the first poll.
5. If token usage exceeds roughly 1M tokens for a narrow RTSP guardrail issue
   without a completed diff/test report, stop Symphony and move the issue to
   `In Review`.
