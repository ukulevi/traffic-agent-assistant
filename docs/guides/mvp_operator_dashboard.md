# MVP Operator Dashboard

Run the API with the existing orchestrator extra, then open `/demo/` on the
same origin. The dashboard follows a five-region operator workflow:

1. **Input** — configuration at the top: tenant, node, green-time ratio,
   scenario description, and demo presets.
2. **Job lifecycle** — monitor `queued`/`running`/terminal status, events,
   `trace_id`, model/data versions, and timestamps.
3. **Result** — read the terminal simulation envelope, aggregate forecast
   metrics, and Vietnamese interpretation before moving to evidence.
4. **Safety/evidence** — review uncertainty/OOD checks, counterfactual safety
   iterations, citations, and the non-executable action payload.
5. **Operator review** — explicitly approve, reject, or request changes for
   audit only.

The dashboard is provisional and aggregate-only. It never displays raw video,
credentials, or an executable field action. For `needs_review`, it renders
only `candidate_action`; a recommendation is shown only for `succeeded`.
Failed and expired jobs also remain non-executable and expose no recommended
action.

In demo mode, the input panel groups deterministic presets into `Safety cơ bản`
and `Tình huống vận hành`. The first group covers `succeeded`, V/C policy
failure, OOD, high uncertainty, missing legal evidence, and an extreme
green-time ratio. The operational group maps accident, flood, lane closure, and
demand surge to bounded aggregate synthetic profiles, while environmental
anomaly maps to OOD/uncertainty review. The canonical synthetic network
identifiers are `node_00` through `node_19`, matching `mock-network-20-v1`. The
API rejects a node outside that registry before creating a demo job.

The environmental preset is an explicitly synthetic correlation signal. It
does not claim that CO, CO2, NOx, PM2.5, or PM10 causes congestion; it does not
forecast air quality, water depth, rainfall, or health impacts. Free text gives
operator context and legal/SOP retrieval only: it is not parsed into simulation
parameters, and the UI never determines the terminal status itself.

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

The UI uses SSE as the primary lifecycle transport. If SSE is unavailable it
starts bounded polling; during reconnect it waits five seconds before enabling
the polling fallback and stops polling when streaming returns. Transport state
is displayed separately from canonical job status, so an offline/reconnecting
condition never fabricates `failed`. The browser stores only the active
`job_id` and tenant identity in `sessionStorage`; refresh retrieves the
authoritative job before resuming monitoring and never stores the scenario
payload.

At startup, the dashboard first requests trusted same-origin
`/api/v1/ui-context`. A valid response activates production mode with immutable
tenant/operator identity, supported roles, the server node allowlist, and the
typed `capabilities.record_decision` value. The server clamps decision
capability to `operator`/`admin`, returns `Cache-Control: no-store`, and never
exposes an actuation capability. Production deployments must inject trusted
`PrincipalResolver` and `UiContextProvider` implementations; browser values are
not authorization evidence. Only a `404` on that endpoint followed by the exact
provisional STWI OpenAPI activates demo compatibility. A `401`, `403`, `503`,
malformed 200, unreachable or untrusted runtime response becomes
`UI preview · chưa có API`; static preview disables job submission and decision
recording and never falls back silently to demo.

Every decision remains human-controlled. “Ghi nhận quyết định” opens a modal
that shows immutable job/trace/operator context and requires a rationale for
approve, reject or request-changes. Approval is available only for `succeeded`
with a safe non-executable recommendation and sufficient evidence;
`needs_review` may only be rejected or returned for changes. After POST, the UI
requires `automatic_actuation=false` and `applied_by_system=false`, then performs
GET reconciliation before displaying the immutable audit record. A `409`
conflict is a decision-state error and does not overwrite job or transport
state.

Production legal evidence must include an explicit server validation outcome;
the UI does not infer legal validity from citation shape. Demo mode may label a
complete deterministic citation set as provisional demo evidence, and states
clearly that this is not production legal validation. Authentication provider,
durable multi-instance job storage, production corpus governance and runtime
observability remain backend/deployment dependencies outside this UI scope.

Keyboard progression follows the five-region workflow. Skip links jump to input
configuration or the result envelope. `/` focuses the node search, `C` copies
the current `trace_id` when focus is outside an editable field, and `Enter`
activates the focused button or form control. After a job is accepted, focus
moves to the lifecycle panel for monitoring; on a terminal envelope, focus moves
once to the result conclusion. The node rail uses ordinary buttons with
`aria-pressed`, so `Tab` stays consistent and screen readers announce selected
state without incomplete listbox semantics. `Esc` closes the decision dialog
and returns focus to its opener. If the browser denies clipboard permission, the
dashboard contains the error and asks the operator to select the visible trace
ID and copy it manually.
