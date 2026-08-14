# Network-impact evidence and showcase video design

## Objective

Make the synthetic 20-node demo explain, for each selected incident location,
which modeled nodes are affected and why a route is recommended, withheld, or
kept for human review. Produce a 5–6 minute MP4 that is an auditable
demonstration of STWI decision support, not a claim of real-world traffic
optimality.

## Scope and boundary

- The topology remains the fixed synthetic 20-node network.
- The change adds typed, per-node scenario evidence to the asynchronous job
  result. It does not add field-device control, raw video, or a real-world
  traffic claim.
- Results remain synthetic and deterministic in demo mode. Every visual and
  narration identifies the topology, model/data versions, and uncertainty/OOD
  limits.
- A recommended route remains advisory: `requires_operator_approval=true` and
  `applied_by_system=false`. `needs_review`, failed, expired, incomplete, or
  malformed evidence cannot display a recommended route.

## Contract and API extension

Add an optional `network_impact` object to `WhatIfJobResult`, serialized by
the existing job-status API and SSE terminal envelope:

```text
network_impact = {
  topology_version: string,
  model_version: string,
  data_version: string,
  horizons_minutes: [5, 10, 15, 20, 25, 30],
  incident_node_ids: [node_id, ...],
  node_impacts: [{
    node_id: string,
    horizon_minutes: integer,
    traffic_volume_5m: number,
    avg_speed_kmh: number,
    vc_ratio: number,
    uncertainty_score: number,
    ood_score: number,
    impact_role: incident | adjacent | network,
  }]
}
```

The producer is the same typed, incident-aware scenario forecast used by the
safety loop. The result must contain exactly one finite row for every
`(allowlisted node_id, horizon)` pair, matching the result provenance and
expected topology. Missing rows, duplicate rows, version mismatch, invalid
node IDs, or non-finite metrics make the whole network-impact panel
unavailable. This is a display/evidence failure, not an invitation to infer
values on the client.

`impact_role` is derived only from the trusted directed topology: incident
nodes are `incident`; their direct inbound/outbound neighbors are `adjacent`;
all other allowlisted nodes are `network`. It does not mean observed physical
spillback in a real city.

## Dashboard behavior

The Leaflet synthetic map gains an evidence overlay and a compact legend.

- At the selected horizon (default 30 minutes), markers show an accessible
  text label with role, V/C, speed, uncertainty and OOD. Fill/pattern reflects
  impact role and metric threshold; color is never the sole carrier.
- A horizon selector updates only the already-validated evidence. It cannot
  create or change a job.
- The impact table mirrors the map as a keyboard-accessible fallback and lists
  all 20 nodes in stable topology order, with explicit incident/adjacent/
  network role labels.
- The route table keeps candidate-specific metrics. Solid routes are passing
  recommendations; dashed routes are review candidates. Both carry exact
  route ID and provenance. Route overlays are cleared unless the terminal
  result contains valid typed route evidence.
- The UI uses an explicit `Evidence unavailable` state if `network_impact` is
  absent or invalid. It never substitutes synthetic topology data in
  production mode or invents node metrics.

## Demo video sequence

1. State the synthetic scope and human-approval boundary.
2. Run `refinement` at `node_05`: show incident/adjacent roles, horizon 5 and
   30 metrics, V/C failure in loop 1, ratio refinement to 0.85, then a passing
   non-executable route recommendation.
3. Run the same typed signal-change preset at `node_14`: show that the
   incident and adjacent evidence move with the selected location, while the
   topology/provenance remain visible; compare the newly evaluated candidates,
   not a route copied from the prior job.
4. Run an unsafe incident or missing-evidence case at a third node: show the
   impact panel if evidence is valid, but emphasize that `needs_review` has no
   executable recommendation; if citation/evidence is missing, show the
   fail-closed reason and no route overlay.
5. Finish with the operator decision audit record and the statement that the
   system records a human decision only.

The voice-over and subtitles use `synthetic`, `candidate`, `safety gate`, and
`operator approval`; they never call a route “optimal”, “proven safe in the
field”, or a real-world traffic directive.

## Acceptance criteria

1. Contract/API tests reject malformed, incomplete, duplicated or provenance-
   mismatched network-impact grids.
2. Demo results expose a complete 20-by-6 typed impact grid with deterministic
   roles that change when the incident node changes.
3. Map and fallback table render exactly the same validated impact model; no
   impact panel is displayed from invalid evidence.
4. Route recommendations are still fail-closed and remain non-executable.
5. Frontend tests cover horizon switching, map/table parity, keyboard labels,
   location changes, and unavailable evidence.
6. The MP4 visibly covers the three scenarios above with readable provenance,
   uncertainty/OOD and no claim beyond a synthetic decision-support demo.

## Validation

Run contract/runtime/frontend tests, documentation validation, dashboard
static tests, JavaScript checks and release QA. Use browser inspection for
desktop and mobile map/table layout, keyboard operation and terminal state.
Review the rendered MP4 frame-by-frame for subtitle legibility, state accuracy
and the absence of automatic-actuation or real-world-optimality claims.
