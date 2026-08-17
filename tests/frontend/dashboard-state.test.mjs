import test from "node:test";
import assert from "node:assert/strict";

import {
  createInitialState,
  deriveDecisionPolicy,
  deriveNetworkImpactViewModel,
  deriveRouteViewModel,
  evaluateEvidence,
  reduceDashboardState,
  validateAcceptedJob,
  validateJobEnvelope,
} from "../../src/stwi/t4_orchestrator/static/dashboard-state.js";

const routeEvaluation = Object.freeze({
  route: {
    route_id: "route-node_06-node_08-01",
    boundary_entry_node: "node_06",
    boundary_exit_node: "node_08",
    node_sequence: ["node_06", "node_01", "node_02", "node_03", "node_08"],
    edge_ids: ["edge-06-01", "edge-01-02", "edge-02-03", "edge-03-08"],
    base_cost: 4,
    distance_m: 400,
    topology_version: "synthetic-routing-20-v1",
  },
  max_vc_ratio: 0.78,
  avg_speed_kmh: 28.5,
  delay_proxy_seconds: 42,
  uncertainty_score: 0.12,
  ood_score: 0.08,
  passed: true,
  rejection_reasons: [],
  evidence_complete: true,
  model_version: "surrogate-v1",
  data_version: "sumo-v1",
  topology_version: "synthetic-routing-20-v1",
});

function routeEnvelope(status, routePayload) {
  const actionKey = status === "succeeded" ? "recommended_action" : "candidate_action";
  const routeKey = status === "succeeded" ? "route_recommendations" : "route_candidates";
  return {
    job_id: `job-${status}`,
    status,
    result: {
      [actionKey]: {
        executable: false,
        automatic_actuation: false,
        requires_operator_approval: true,
        [routeKey]: routePayload,
      },
    },
  };
}

test("succeeded route evidence becomes a normalized recommendation view model", () => {
  const recommendation = {
    route: routeEvaluation.route,
    evaluation: routeEvaluation,
    rank: 1,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  };

  const viewModel = deriveRouteViewModel(routeEnvelope("succeeded", [recommendation]));

  assert.equal(viewModel.status, "succeeded");
  assert.equal(viewModel.routeHeading, "Hành lang được khuyến nghị");
  assert.equal(viewModel.routes[0].routeId, "route-node_06-node_08-01");
  assert.equal(viewModel.routes[0].rank, 1);
  assert.equal(viewModel.routes[0].statusLabel, "Đã qua safety gate");
  assert.deepEqual(viewModel.routes[0].nodeSequence, routeEvaluation.route.node_sequence);
  assert.equal(viewModel.routes[0].provenance.topologyVersion, "synthetic-routing-20-v1");
  assert.equal(viewModel.hasValidEvidence, true);
});

test("accepts the exact RouteRecommendation model-dump shape", () => {
  const modelDump = {
    route: routeEvaluation.route,
    evaluation: routeEvaluation,
    rank: 1,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  };

  const route = deriveRouteViewModel(routeEnvelope("succeeded", [modelDump])).routes[0];

  assert.equal(route.baseCost, 4);
  assert.equal(route.distanceM, 400);
  assert.deepEqual(route.edgeIds, routeEvaluation.route.edge_ids);
});

test("needs_review exposes candidates and never recommendations", () => {
  const candidate = {
    ...routeEvaluation,
    passed: false,
    evidence_complete: false,
    rejection_reasons: ["uncertainty_threshold_exceeded"],
  };

  const viewModel = deriveRouteViewModel(routeEnvelope("needs_review", [candidate]));

  assert.equal(viewModel.routeHeading, "Hành lang cần xem xét");
  assert.equal(viewModel.routes[0].kind, "candidate");
  assert.equal(viewModel.routes[0].statusLabel, "Chưa qua safety gate");
  assert.deepEqual(viewModel.routes[0].reviewReasons, ["uncertainty_threshold_exceeded"]);
  assert.equal(viewModel.canApprove, false);
});

test("failed and expired envelopes never expose route overlays", () => {
  for (const status of ["failed", "expired"]) {
    const viewModel = deriveRouteViewModel({
      ...routeEnvelope("succeeded", [{ route: routeEvaluation.route, evaluation: routeEvaluation, rank: 1 }]),
      status,
    });
    assert.deepEqual(viewModel.routes, []);
    assert.equal(viewModel.canApprove, false);
  }
});

test("malformed route arrays fail safely without changing terminal status", () => {
  for (const malformed of [null, {}, [null], [{ route: { route_id: "route-bad", node_sequence: "node_01" } }]]) {
    const viewModel = deriveRouteViewModel(routeEnvelope("succeeded", malformed));
    assert.equal(viewModel.status, "succeeded");
    assert.deepEqual(viewModel.routes, []);
    assert.equal(viewModel.hasMalformedRouteEvidence, true);
    assert.equal(viewModel.canApprove, false);
  }
});

test("recommendation wrapper must match its evaluated route exactly", () => {
  const mismatchedRoute = {
    ...routeEvaluation.route,
    boundary_exit_node: "node_03",
    node_sequence: ["node_06", "node_01", "node_02", "node_03"],
    edge_ids: ["edge-06-01", "edge-01-02", "edge-02-03"],
  };
  const recommendation = {
    route: mismatchedRoute,
    evaluation: routeEvaluation,
    rank: 1,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  };

  const viewModel = deriveRouteViewModel(routeEnvelope("succeeded", [recommendation]));

  assert.deepEqual(viewModel.routes, []);
  assert.equal(viewModel.hasMalformedRouteEvidence, true);
  assert.equal(viewModel.canApprove, false);
});

test("recommendation wrapper distance must match evaluated evidence", () => {
  const recommendation = {
    route: { ...routeEvaluation.route, distance_m: 401 },
    evaluation: routeEvaluation,
    rank: 1,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  };

  const viewModel = deriveRouteViewModel(routeEnvelope("succeeded", [recommendation]));

  assert.deepEqual(viewModel.routes, []);
  assert.equal(viewModel.hasMalformedRouteEvidence, true);
});

test("needs-review rejects a safety-passed evaluation masquerading as a candidate", () => {
  const viewModel = deriveRouteViewModel(routeEnvelope("needs_review", [routeEvaluation]));

  assert.deepEqual(viewModel.routes, []);
  assert.equal(viewModel.canApprove, false);
  assert.equal(viewModel.hasMalformedRouteEvidence, true);
});

test("recommendation ranks must start at one without gaps", () => {
  const recommendation = {
    route: routeEvaluation.route,
    evaluation: routeEvaluation,
    rank: 2,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  };

  const viewModel = deriveRouteViewModel(routeEnvelope("succeeded", [recommendation]));

  assert.deepEqual(viewModel.routes, []);
  assert.equal(viewModel.hasMalformedRouteEvidence, true);
});

test("route payload never promotes a running envelope to succeeded", () => {
  const envelope = routeEnvelope("succeeded", [{
    route: routeEvaluation.route,
    evaluation: routeEvaluation,
    rank: 1,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  }]);
  envelope.status = "running";

  const viewModel = deriveRouteViewModel(envelope);
  assert.equal(viewModel.status, "running");
  assert.deepEqual(viewModel.routes, []);
});

const safeAction = Object.freeze({
  node_id: "node_00",
  green_time_ratio: 0.7,
  executable: false,
  automatic_actuation: false,
  requires_operator_approval: true,
  applied_by_system: false,
});

test("transport failure preserves the authoritative job status", () => {
  let state = createInitialState();
  state = reduceDashboardState(state, {
    type: "job/accepted",
    accepted: { job_id: "job-1", status: "queued", tenant_id: "demo-operator" },
    epoch: 1,
  });
  state = reduceDashboardState(state, {
    type: "job/envelope",
    envelope: { job_id: "job-1", status: "running", tenant_id: "demo-operator" },
  });
  state = reduceDashboardState(state, { type: "transport/offline", code: "NETWORK_ERROR" });

  assert.equal(state.job.status, "running");
  assert.equal(state.transport.phase, "offline");
});

test("static preview never reports an online transport", () => {
  const state = reduceDashboardState(createInitialState(), {
    type: "context/resolved",
    context: { mode: "static_preview", roles: [], nodeIds: [] },
  });

  assert.equal(state.transport.phase, "unavailable");
});

test("resume does not fabricate a queued server status", () => {
  const state = reduceDashboardState(createInitialState(), {
    type: "job/resume_requested",
    jobId: "job-2",
    epoch: 2,
  });

  assert.equal(state.job.id, "job-2");
  assert.equal(state.job.status, null);
  assert.equal(state.creation.phase, "resuming");
});

test("unknown status is rejected at the client boundary", () => {
  assert.deepEqual(
    validateJobEnvelope({ job_id: "job-1", status: "complete" }),
    { ok: false, code: "JOB_STATUS_UNKNOWN" },
  );
});

test("accepted response requires queued status and tenant identity", () => {
  assert.equal(
    validateAcceptedJob({ job_id: "job-1", status: "queued", tenant_id: "demo-operator" }).ok,
    true,
  );
  assert.deepEqual(
    validateAcceptedJob({ job_id: "job-1", status: "running", tenant_id: "demo-operator" }),
    { ok: false, code: "CREATE_STATUS_INVALID" },
  );
});

test("approval requires succeeded, safe action, evidence, role and no prior decision", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "production", roles: ["operator"] },
    job: {
      ...createInitialState().job,
      id: "job-1",
      status: "succeeded",
      result: { recommended_action: safeAction },
      evidence: { phase: "valid" },
    },
    transport: { phase: "online" },
  };

  assert.equal(deriveDecisionPolicy(state).canApprove, true);
  assert.equal(
    deriveDecisionPolicy({ ...state, job: { ...state.job, result: {} } }).canApprove,
    false,
  );
  assert.equal(
    deriveDecisionPolicy({ ...state, job: { ...state.job, decisionRecord: { decision: "approved" } } }).canApprove,
    false,
  );
});

test("approval fails closed when a declared route recommendation is malformed", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "production", roles: ["operator"] },
    job: {
      ...createInitialState().job,
      id: "job-1",
      status: "succeeded",
      result: {
        recommended_action: {
          ...safeAction,
          route_recommendations: [{ route: { route_id: "route-bad" } }],
        },
      },
      evidence: { phase: "valid" },
    },
    transport: { phase: "online" },
  };

  assert.equal(deriveDecisionPolicy(state).canApprove, false);
});

test("approval requires applied_by_system to be explicitly false", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "production", roles: ["operator"] },
    job: {
      ...createInitialState().job,
      id: "job-1",
      status: "succeeded",
      result: { recommended_action: { ...safeAction, applied_by_system: true } },
      evidence: { phase: "valid" },
    },
    transport: { phase: "online" },
  };

  assert.equal(deriveDecisionPolicy(state).canApprove, false);
});

test("needs_review never permits approval", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "demo", roles: ["operator"] },
    job: {
      ...createInitialState().job,
      id: "job-1",
      status: "needs_review",
      result: { candidate_action: safeAction },
      evidence: { phase: "demo_provisional_valid" },
    },
    transport: { phase: "online" },
  };

  const policy = deriveDecisionPolicy(state);
  assert.equal(policy.canApprove, false);
  assert.equal(policy.canRequestChanges, true);
});

test("demo evidence is provisional while production requires server validation", () => {
  const result = {
    model_version: "model-v1",
    data_version: "data-v1",
    completed_at: "2026-08-03T00:00:00Z",
    audit_record: { trace_id: "trace-1" },
    citations: [{ source_url: "https://vanban.chinhphu.vn/example", provision: "Điều 1", effective_from: "2025-01-01" }],
  };

  assert.equal(evaluateEvidence(result, "demo").phase, "demo_provisional_valid");
  assert.equal(evaluateEvidence(result, "production").phase, "unknown");
  assert.equal(
    evaluateEvidence({ ...result, citation_validation_outcome: "valid" }, "production").phase,
    "valid",
  );
});

test("duplicate SSE events are ignored by event id", () => {
  let state = reduceDashboardState(createInitialState(), {
    type: "job/resume_requested",
    jobId: "job-1",
    epoch: 1,
  });
  state = reduceDashboardState(state, {
    type: "job/event",
    jobId: "job-1",
    eventId: "4",
    payload: { status: "running" },
  });
  assert.equal(state.job.events.length, 1);
});

const sampleImpactEvidence = Object.freeze({
  topology_version: "synthetic-grid-20-v1",
  model_version: "surrogate-v1",
  data_version: "sumo-v1",
  horizons_minutes: [5, 30],
  incident_node_ids: ["node_05"],
  node_impacts: [
    {
      node_id: "node_05",
      horizon_minutes: 5,
      traffic_volume_5m: 120,
      avg_speed_kmh: 25,
      vc_ratio: 0.95,
      uncertainty_score: 0.1,
      ood_score: 0.05,
      impact_role: "incident",
    },
    {
      node_id: "node_05",
      horizon_minutes: 30,
      traffic_volume_5m: 110,
      avg_speed_kmh: 28,
      vc_ratio: 0.88,
      uncertainty_score: 0.12,
      ood_score: 0.05,
      impact_role: "incident",
    },
    {
      node_id: "node_06",
      horizon_minutes: 5,
      traffic_volume_5m: 80,
      avg_speed_kmh: 35,
      vc_ratio: 0.65,
      uncertainty_score: 0.08,
      ood_score: 0.04,
      impact_role: "adjacent",
    },
    {
      node_id: "node_06",
      horizon_minutes: 30,
      traffic_volume_5m: 75,
      avg_speed_kmh: 38,
      vc_ratio: 0.60,
      uncertainty_score: 0.09,
      ood_score: 0.04,
      impact_role: "adjacent",
    },
  ],
});

test("deriveNetworkImpactViewModel accepts exact complete grid and filters selected horizon", () => {
  const vm = deriveNetworkImpactViewModel({
    status: "succeeded",
    networkImpact: sampleImpactEvidence,
    selectedHorizon: 30,
  });

  assert.equal(vm.available, true);
  assert.equal(vm.status, "succeeded");
  assert.equal(vm.topologyVersion, "synthetic-grid-20-v1");
  assert.deepEqual(vm.horizons, [5, 30]);
  assert.equal(vm.selectedHorizon, 30);
  assert.deepEqual(vm.incidentNodeIds, ["node_05"]);
  assert.equal(vm.rows.length, 2);
  assert.equal(vm.rows.find((r) => r.nodeId === "node_05").vcRatio, 0.88);
});

test("deriveNetworkImpactViewModel defaults selectedHorizon to first horizon if omitted or invalid", () => {
  const vm = deriveNetworkImpactViewModel({
    status: "succeeded",
    networkImpact: sampleImpactEvidence,
    selectedHorizon: 99,
  });

  assert.equal(vm.available, true);
  assert.equal(vm.selectedHorizon, 5);
  assert.equal(vm.rows.find((r) => r.nodeId === "node_05").vcRatio, 0.95);
});

test("deriveNetworkImpactViewModel fails closed on non-terminal or failed/expired status", () => {
  for (const status of ["running", "queued", "failed", "expired", null]) {
    const vm = deriveNetworkImpactViewModel({
      status,
      networkImpact: sampleImpactEvidence,
    });
    assert.equal(vm.available, false);
  }
});

test("deriveNetworkImpactViewModel fails closed on malformed network impact evidence", () => {
  const malformedList = [
    null,
    {},
    { ...sampleImpactEvidence, topology_version: "" },
    { ...sampleImpactEvidence, horizons_minutes: [] },
    {
      ...sampleImpactEvidence,
      node_impacts: sampleImpactEvidence.node_impacts.map((p) => ({ ...p, impact_role: "unknown" })),
    },
    {
      ...sampleImpactEvidence,
      node_impacts: sampleImpactEvidence.node_impacts.slice(0, 3), // incomplete grid
    },
  ];

  for (const malformed of malformedList) {
    const vm = deriveNetworkImpactViewModel({
      status: "succeeded",
      networkImpact: malformed,
    });
    assert.equal(vm.available, false);
  }
});
