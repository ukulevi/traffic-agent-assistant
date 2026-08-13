import test from "node:test";
import assert from "node:assert/strict";

import { createDashboardCoordinator } from "../../src/stwi/t4_orchestrator/static/dashboard.js";

const scenario = Object.freeze({
  tenant_id: "demo-operator",
  scenario_time: "2026-08-03T00:00:00Z",
  candidate_action: { node_id: "node_00", green_time_ratio: 0.7 },
  node_ids: ["node_00"],
  scenario_query: "Đánh giá node_00",
  jurisdiction: "VN",
});

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    value: (key) => values.get(key),
  };
}

function createView() {
  return {
    handlers: {},
    renders: [],
    context: null,
    render(state, policy, routeViewModel) { this.renders.push({ state, policy, routeViewModel }); },
    readScenario: () => ({ ...scenario }),
    setContext(context) { this.context = context; },
    setScenario() {},
    setFormError() {},
    setCopyStatus(message) { this.copyStatus = message; },
    focusLifecycle() {},
    focusResult() {},
    closeDecisionDialog() {},
    openDecisionDialog() {},
    setHandlers(next) { this.handlers = { ...this.handlers, ...next }; },
    focusLifecycleCalled: false,
    focusResultCalled: false,
  };
}

test("coordinator shares one derived route view model with table and map", async () => {
  const view = createView();
  const mapModels = [];
  let streamHandlers;
  const recommendation = {
    route: {
      route_id: "route-01",
      boundary_entry_node: "node_00",
      boundary_exit_node: "node_01",
      node_sequence: ["node_00", "node_01"],
      edge_ids: ["edge-node_00-node_01"],
      base_cost: 1,
      distance_m: 100,
      topology_version: "synthetic-routing-20-v1",
    },
    evaluation: {
      route: {
        route_id: "route-01",
        boundary_entry_node: "node_00",
        boundary_exit_node: "node_01",
        node_sequence: ["node_00", "node_01"],
        edge_ids: ["edge-node_00-node_01"],
        base_cost: 1,
        distance_m: 100,
        topology_version: "synthetic-routing-20-v1",
      },
      max_vc_ratio: 0.7,
      avg_speed_kmh: 30,
      delay_proxy_seconds: 20,
      uncertainty_score: 0.1,
      ood_score: 0.1,
      passed: true,
      rejection_reasons: [],
      evidence_complete: true,
      model_version: "m1",
      data_version: "d1",
      topology_version: "synthetic-routing-20-v1",
    },
    rank: 1,
    executable: false,
    requires_operator_approval: true,
    applied_by_system: false,
  };
  const envelope = {
    ...succeededEnvelope,
    result: {
      ...succeededEnvelope.result,
      recommended_action: {
        ...succeededEnvelope.result.recommended_action,
        route_recommendations: [recommendation],
      },
    },
  };
  const api = {
    createJob: async () => ({ job_id: "job-1", status: "queued", tenant_id: "demo-operator" }),
    streamJob(_jobId, handlers) { streamHandlers = handlers; return () => {}; },
    getJob: async () => envelope,
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    resolveContext: async () => demoContext,
    storage: createStorage(),
    cryptoImpl: { randomUUID: () => "idem-route" },
    mapFactory: () => ({
      setTopology() {}, setSelection() {}, destroy() {},
      setJobState(model) { mapModels.push(model); },
    }),
  });

  await coordinator.bootstrap();
  await coordinator.submitScenario({ preventDefault() {} });
  await streamHandlers.onEvent({ job_id: "job-1", status: "succeeded" }, "route-evt");

  const tableModel = view.renders.at(-1).routeViewModel;
  assert.equal(tableModel.routes[0].routeId, "route-01");
  assert.equal(mapModels.at(-1), tableModel);
});

const demoContext = Object.freeze({
  mode: "demo",
  tenantId: "demo-operator",
  operatorId: "demo-operator",
  roles: ["operator"],
  nodeIds: ["node_00"],
  capabilities: { demoPresets: true },
});

const succeededEnvelope = Object.freeze({
  job_id: "job-1",
  status: "succeeded",
  tenant_id: "demo-operator",
  result: {
    model_version: "model-v1",
    data_version: "data-v1",
    completed_at: "2026-08-03T00:00:00Z",
    audit_record: { trace_id: "trace-1" },
    citations: [{
      source_url: "https://example.test",
      provision: "Điều 1",
      effective_from: "2025-01-01",
    }],
    recommended_action: {
      executable: false,
      automatic_actuation: false,
      requires_operator_approval: true,
      applied_by_system: false,
    },
  },
});

const decisionForm = (decision, rationale) => ({
  get(name) {
    return { decision, rationale }[name];
  },
});

async function createSucceededCoordinator({ recordDecision, reconcileEnvelope, navigatorImpl } = {}) {
  const view = createView();
  let streamHandlers;
  let getCalls = 0;
  const api = {
    createJob: async () => ({ job_id: "job-1", status: "queued", tenant_id: "demo-operator" }),
    streamJob(_jobId, handlers) { streamHandlers = handlers; return () => {}; },
    getJob: async () => {
      getCalls += 1;
      return getCalls > 1 && reconcileEnvelope ? reconcileEnvelope : succeededEnvelope;
    },
    recordDecision: recordDecision || (async () => ({
      job_id: "job-1",
      operator_decision: {
        decision: "approved",
        operator_id: "demo-operator",
        applied_by_system: false,
      },
      automatic_actuation: false,
    })),
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    resolveContext: async () => demoContext,
    storage: createStorage(),
    cryptoImpl: { randomUUID: () => "idem-1" },
    navigatorImpl,
  });
  await coordinator.bootstrap();
  await coordinator.submitScenario({ preventDefault() {} });
  await streamHandlers.onEvent({ job_id: "job-1", status: "succeeded" }, "5");
  return { coordinator, view, api };
}

test("clipboard denial is contained and announced to the operator", async () => {
  const { view } = await createSucceededCoordinator({
    navigatorImpl: {
      clipboard: {
        writeText: async () => { throw new Error("permission denied"); },
      },
    },
  });

  await view.handlers.copyTrace();

  assert.equal(
    view.copyStatus,
    "Trình duyệt đã chặn clipboard. Hãy chọn trace ID và sao chép thủ công.",
  );
});

test("static preview disables mutation without calling create API", async () => {
  let creates = 0;
  const view = createView();
  const coordinator = createDashboardCoordinator({
    api: { createJob: async () => { creates += 1; } },
    view,
    resolveContext: async () => ({ ...demoContext, mode: "static_preview", roles: [] }),
    storage: createStorage(),
  });

  await coordinator.bootstrap();
  await coordinator.submitScenario({ preventDefault() {} });

  assert.equal(creates, 0);
  assert.equal(coordinator.getState().context.mode, "static_preview");
});

test("submit persists active job and uses SSE as primary monitor", async () => {
  const view = createView();
  const storage = createStorage();
  let streamHandlers;
  let pollCalls = 0;
  const api = {
    createJob: async () => ({ job_id: "job-1", status: "queued", tenant_id: "demo-operator" }),
    streamJob(_jobId, handlers) { streamHandlers = handlers; return () => {}; },
    pollJob: async () => { pollCalls += 1; },
    getJob: async () => ({
      job_id: "job-1",
      status: "succeeded",
      tenant_id: "demo-operator",
      result: {
        model_version: "model-v1",
        data_version: "data-v1",
        completed_at: "2026-08-03T00:00:00Z",
        audit_record: { trace_id: "trace-1" },
        citations: [{ source_url: "https://example.test", provision: "Điều 1", effective_from: "2025-01-01" }],
        recommended_action: { executable: false, automatic_actuation: false, requires_operator_approval: true, applied_by_system: false },
      },
    }),
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    resolveContext: async () => demoContext,
    storage,
    cryptoImpl: { randomUUID: () => "idem-1" },
  });

  await coordinator.bootstrap();
  await coordinator.submitScenario({ preventDefault() {} });

  assert.equal(coordinator.getState().job.status, "queued");
  assert.equal(JSON.parse(storage.value("stwi.activeJob")).jobId, "job-1");
  assert.equal(pollCalls, 0);
  await streamHandlers.onEvent({ job_id: "job-1", status: "succeeded" }, "5");
  assert.equal(coordinator.getState().job.status, "succeeded");
  assert.equal(coordinator.getState().job.events.length, 1);
});

test("resume fetches authoritative status instead of showing queued", async () => {
  const view = createView();
  const storage = createStorage({
    "stwi.activeJob": JSON.stringify({ jobId: "job-2", tenantId: "demo-operator" }),
  });
  const api = {
    getJob: async () => ({ job_id: "job-2", status: "running", tenant_id: "demo-operator" }),
    streamJob: () => () => {},
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    resolveContext: async () => demoContext,
    storage,
  });

  await coordinator.bootstrap();

  assert.equal(coordinator.getState().job.id, "job-2");
  assert.equal(coordinator.getState().job.status, "running");
});

test("operator approval records trusted identity and reconciles authoritative decision", async () => {
  let submittedPayload;
  const decisionRecord = {
    decision: "approved",
    operator_id: "demo-operator",
    rationale: "Đã kiểm tra bằng chứng và giới hạn an toàn.",
    applied_by_system: false,
  };
  const { coordinator, view } = await createSucceededCoordinator({
    recordDecision: async (_jobId, payload) => {
      submittedPayload = payload;
      return {
        job_id: "job-1",
        operator_decision: decisionRecord,
        automatic_actuation: false,
      };
    },
    reconcileEnvelope: { ...succeededEnvelope, operator_decision: decisionRecord },
  });

  await coordinator.submitDecision(decisionForm(
    "approved",
    "Đã kiểm tra bằng chứng và giới hạn an toàn.",
  ));

  assert.deepEqual(submittedPayload, {
    decision: "approved",
    operator_id: "demo-operator",
    comment: "Đã kiểm tra bằng chứng và giới hạn an toàn.",
  });
  assert.equal(coordinator.getState().decision.phase, "recorded");
  assert.deepEqual(coordinator.getState().job.decisionRecord, decisionRecord);
  assert.equal(view.renders.at(-1).state.job.status, "succeeded");
});

test("decision requires a non-empty rationale before any API mutation", async () => {
  let decisionCalls = 0;
  const { coordinator } = await createSucceededCoordinator({
    recordDecision: async () => { decisionCalls += 1; },
  });

  await coordinator.submitDecision(decisionForm("approved", "   "));

  assert.equal(decisionCalls, 0);
  assert.equal(coordinator.getState().decision.error, "RATIONALE_REQUIRED");
});

test("needs_review can never be approved", async () => {
  let decisionCalls = 0;
  const { coordinator } = await createSucceededCoordinator({
    recordDecision: async () => { decisionCalls += 1; },
  });
  coordinator.getState().job.status = "needs_review";

  await coordinator.submitDecision(decisionForm("approved", "Đã xem xét."));

  assert.equal(decisionCalls, 0);
  assert.equal(coordinator.getState().decision.error, "DECISION_NOT_ALLOWED");
});

test("decision conflict is isolated from job transport state", async () => {
  const { coordinator } = await createSucceededCoordinator({
    recordDecision: async () => {
      const error = new Error("Conflict");
      error.code = "DECISION_ALREADY_RECORDED";
      error.httpStatus = 409;
      throw error;
    },
  });
  const transportBefore = coordinator.getState().transport.phase;

  await coordinator.submitDecision(decisionForm(
    "approved",
    "Đã xem xét.",
  ));

  assert.equal(coordinator.getState().decision.phase, "conflict");
  assert.equal(coordinator.getState().transport.phase, transportBefore);
});

test("submit focuses lifecycle after accepted creation", async () => {
  let streamHandlers;
  let focusLifecycleCalls = 0;
  const view = createView();
  view.focusLifecycle = () => { focusLifecycleCalls += 1; };
  const api = {
    createJob: async () => ({ job_id: "job-lifecycle", status: "queued", tenant_id: "demo-operator" }),
    streamJob(_jobId, handlers) { streamHandlers = handlers; return () => {}; },
    getJob: async () => ({
      job_id: "job-lifecycle",
      status: "running",
      tenant_id: "demo-operator",
    }),
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    resolveContext: async () => demoContext,
    storage: createStorage(),
    cryptoImpl: { randomUUID: () => "idem-lifecycle" },
  });

  await coordinator.bootstrap();
  await coordinator.submitScenario({ preventDefault() {} });

  assert.equal(focusLifecycleCalls, 1);
  assert.equal(view.focusResultCalled, false);
});

test("terminal envelope focuses result only once", async () => {
  let streamHandlers;
  const view = createView();
  let focusResultCalls = 0;
  view.focusResult = () => { focusResultCalls += 1; };
  const api = {
    createJob: async () => ({ job_id: "job-terminal", status: "queued", tenant_id: "demo-operator" }),
    streamJob(_jobId, handlers) { streamHandlers = handlers; return () => {}; },
    getJob: async () => ({
      job_id: "job-terminal",
      status: "succeeded",
      tenant_id: "demo-operator",
      result: {
        model_version: "model-v1",
        data_version: "data-v1",
        completed_at: "2026-08-03T00:00:00Z",
        audit_record: { trace_id: "trace-terminal" },
        citations: [{ source_url: "https://example.test", provision: "Điều 1", effective_from: "2025-01-01" }],
        recommended_action: { executable: false, automatic_actuation: false, requires_operator_approval: true, applied_by_system: false },
      },
    }),
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    resolveContext: async () => demoContext,
    storage: createStorage(),
    cryptoImpl: { randomUUID: () => "idem-terminal" },
  });

  await coordinator.bootstrap();
  await coordinator.submitScenario({ preventDefault() {} });
  await streamHandlers.onEvent({ job_id: "job-terminal", status: "succeeded" }, "6");

  assert.equal(focusResultCalls, 1);
});

test("decision response that claims actuation fails closed", async () => {
  const { coordinator } = await createSucceededCoordinator({
    recordDecision: async () => ({
      job_id: "job-1",
      operator_decision: {
        decision: "approved",
        operator_id: "demo-operator",
        applied_by_system: true,
      },
      automatic_actuation: true,
    }),
  });

  await coordinator.submitDecision(decisionForm("approved", "Đã xem xét."));

  assert.equal(coordinator.getState().transport.phase, "protocol_error");
  assert.equal(coordinator.getState().transport.code, "AUTOMATIC_ACTUATION_FORBIDDEN");
});
