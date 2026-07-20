# MVP Operator Dashboard

Run the API with the existing orchestrator extra, then open `/demo/` on the
same origin. The dashboard is organized as a four-step operator workflow:

1. **Input** — create a What-If scenario with tenant, node, green-time ratio,
   and a short incident description.
2. **Observe** — follow `queued`/`running`/terminal status, lifecycle events,
   `trace_id`, and model/data versions.
3. **Safety** — read the fail-closed explanation and inspect the non-executable
   action payload.
4. **Human decision** — explicitly approve or reject the result for audit only.

The dashboard is provisional and aggregate-only. It never displays raw video,
credentials, or an executable field action. For `needs_review`, it renders
only `candidate_action`; a recommendation is shown only for `succeeded`.
Failed and expired jobs also remain non-executable and expose no recommended
action.

In demo mode, the input panel exposes deterministic presets for `succeeded`,
V/C policy failure, OOD, high uncertainty, missing legal evidence, and an
extreme green-time ratio. The canonical synthetic network identifiers are
`node_00` through `node_19`, matching `mock-network-20-v1`. The API rejects a
node outside that registry before creating a demo job.

The request boundary uses a typed candidate action. Its node must be present in
`node_ids`, green-time ratio remains bounded to `[0, 1]`, and blank identifiers
or queries are rejected. Ratio extremes remain valid What-If questions but are
mapped to `needs_review` by the demo safety profile rather than producing a
recommendation.

Before the technical action payload, the Safety panel includes a Vietnamese
plain-language interpretation. It explains the outcome, summarizes available
aggregate changes in traffic volume (`vehicles/5min`), speed (`km/h`), and V/C,
and states the next operator step. `needs_review`, OOD, high uncertainty,
missing legal evidence, V/C policy failure, timeout, and runtime failure use
distinct fail-closed explanations. The interpretation is deterministic from
typed API fields; it does not invent metrics that are absent from the result.

An expandable Vietnamese variable guide explains `tenant_id`, `node_id`,
`green_time_ratio`, `scenario_query`, job/trace identifiers, model/data
versions, V/C, and the non-executable action payload. The green-time input is
shown both as a ratio and a percentage (for example `0.70 · 70%`). The guide
explicitly states that the V/C threshold of 0.9 is a configurable MVP policy,
not a legal requirement.

The UI polls the status endpoint until a terminal state and then reads SSE
events for the timeline. Each SSE status is translated into an operator-facing
Vietnamese event. A timeline transport error does not overwrite a successful
job result. Network and runtime errors are shown as operational messages rather
than raw exceptions. Keyboard focus, responsive breakpoints, and reduced-motion
preferences are supported by the static dashboard. Failed and expired jobs can
be rejected for audit, but the UI does not allow them to be approved.

At startup, the dashboard checks same-origin `/openapi.json`. When the page is
served by a static-only preview server, the top bar explicitly shows
`UI preview · chưa có API`, disables job submission, and explains that the
operator must open `/demo/` from the FastAPI runtime origin. HTTP validation,
authorization, and missing-runtime failures are reported separately.

Every decision remains human-controlled: the UI requires an explicit approve
or reject action and records `applied_by_system=false`. Approval is available
only for `succeeded`; the API rejects approval of `needs_review`, `failed`, or
`expired` jobs.
