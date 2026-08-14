import test from "node:test";
import assert from "node:assert/strict";

import { createDashboardView } from "../../src/stwi/t4_orchestrator/static/dashboard-view.js";
import { createInitialState } from "../../src/stwi/t4_orchestrator/static/dashboard-state.js";

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.textContent = "";
    this.children = [];
    this.dataset = {};
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.checked = false;
    this.className = "";
    this.listeners = new Map();
    this.open = false;
  }

  addEventListener(name, handler) { this.listeners.set(name, handler); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  focus() { this.focused = true; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}

class FakeDocument {
  constructor() {
    this.nodes = new Map();
    this.documentElement = new FakeElement("html");
    this.activeElement = new FakeElement("button");
    this.radios = ["approved", "rejected", "request_changes"].map((value) => {
      const radio = new FakeElement("input");
      radio.value = value;
      return radio;
    });
    this.listeners = new Map();
  }

  getElementById(id) {
    if (!this.nodes.has(id)) this.nodes.set(id, new FakeElement());
    return this.nodes.get(id);
  }

  createElement(tagName) { return new FakeElement(tagName); }
  querySelectorAll(selector) { return selector === 'input[name="decision"]' ? this.radios : []; }
  addEventListener(name, handler) { this.listeners.set(name, handler); }
}

function succeededState() {
  const state = createInitialState();
  return {
    ...state,
    context: { ...state.context, mode: "demo", tenantId: "demo-operator" },
    job: {
      ...state.job,
      id: "job-1",
      status: "succeeded",
      evidence: { phase: "demo_provisional_valid" },
      result: {
        model_version: "model-v1",
        data_version: "data-v1",
        completed_at: "2026-08-03T00:00:00Z",
        scenario_summary: { traffic_volume_5m: 120, avg_speed_kmh: 31, max_vc_ratio: 0.72, capacity_version: "cap-v1" },
        audit_record: { trace_id: "trace-1" },
        safety_iterations: 2,
        safety_checks: [
          { iteration: 1, passed: false, max_vc_ratio: 0.94, vc_threshold: 0.9, fail_reason: "vc_ratio" },
          { iteration: 2, passed: true, max_vc_ratio: 0.84, vc_threshold: 0.9, fail_reason: null },
        ],
        citations: [{ title: "<img src=x>", provision: "Điều 1", effective_from: "2025-01-01", source_url: "https://example.test" }],
        recommended_action: { node_id: "node_00", executable: false, automatic_actuation: false, requires_operator_approval: true, applied_by_system: false },
      },
    },
    transport: { phase: "streaming" },
  };
}

test("render treats citation markup as text and exposes result metrics", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  view.render(succeededState(), { canApprove: true, canReject: true, canRequestChanges: true });

  const citations = doc.getElementById("citations");
  assert.equal(citations.children.length, 1);
  assert.equal(citations.children[0].children[0].textContent, "<img src=x>");
  assert.equal(doc.getElementById("forecast-volume").textContent, "120");
  assert.equal(doc.getElementById("forecast-speed").textContent, "31");
  assert.equal(doc.getElementById("open-decision").disabled, false);
  assert.equal(doc.getElementById("safety-iterations").textContent, "2 / 3 vòng");
  assert.equal(doc.getElementById("safety-checks").children.length, 4);
});

test("long citation evidence is collapsed accessibly and resets for a new job", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  const state = succeededState();
  state.job.result.citations = Array.from({ length: 5 }, (_item, index) => ({
    title: `Citation ${index + 1}`,
    provision: "Điều 1",
  }));
  view.render(state, { canApprove: true, canReject: true, canRequestChanges: true });

  assert.equal(doc.getElementById("citations").children.length, 3);
  assert.equal(doc.getElementById("citation-summary").textContent, "Đang hiển thị 3/5 citation");
  assert.equal(doc.getElementById("toggle-citations").hidden, false);
  assert.equal(doc.getElementById("toggle-citations").textContent, "Xem tất cả (5)");
  doc.getElementById("toggle-citations").listeners.get("click")();
  assert.equal(doc.getElementById("citations").children.length, 5);
  assert.equal(doc.getElementById("toggle-citations").textContent, "Thu gọn");

  state.job.id = "job-2";
  view.render(state, { canApprove: true, canReject: true, canRequestChanges: true });
  assert.equal(doc.getElementById("citations").children.length, 3);
  assert.equal(doc.getElementById("toggle-citations").getAttribute?.("aria-expanded") ?? doc.getElementById("toggle-citations")["aria-expanded"], "false");
});

test("render derives result and safety presentation from the authoritative job status", () => {
  const expectations = {
    idle: ["Chưa có kết quả mô phỏng", "Chờ kết quả", "safety-idle"],
    queued: ["Kịch bản đang chờ xử lý", "Đang chờ safety checks", "safety-queued"],
    running: ["Đang chạy mô phỏng", "Đang đánh giá safety", "safety-running"],
    succeeded: ["Kết quả mô phỏng đã sẵn sàng", "Đã qua safety gate", "safety-succeeded"],
    needs_review: ["Kết quả cần operator xem xét", "Cần xem xét", "safety-needs_review"],
    failed: ["Mô phỏng thất bại", "Không có đề xuất khả dụng", "safety-failed"],
    expired: ["Kết quả đã hết hạn", "Cần chạy lại", "safety-expired"],
  };
  for (const [status, [title, safety, className]] of Object.entries(expectations)) {
    const doc = new FakeDocument();
    const state = succeededState();
    state.job.status = status;
    if (state.job.result) state.job.result.status = status;
    createDashboardView(doc).render(state, { canApprove: false, canReject: false, canRequestChanges: false });

    assert.equal(doc.getElementById("result-title").textContent, title);
    assert.equal(doc.getElementById("safety-label").textContent, safety);
    assert.equal(doc.getElementById("safety-state").className, `safety-state ${className}`);
  }
});

test("render falls back to trusted capacity context without changing the job schema", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  const state = succeededState();
  delete state.job.result.scenario_summary.capacity_version;
  view.setNetworkContext({ network_version: "network-v1", capacity_version: "capacity-context-v2", nodes: [] });
  view.render(state, { canApprove: true, canReject: true, canRequestChanges: true });
  assert.equal(doc.getElementById("capacity-version").textContent, "capacity-context-v2");

  view.setNetworkContext(null, "unavailable");
  view.render(state, { canApprove: true, canReject: true, canRequestChanges: true });
  assert.equal(doc.getElementById("capacity-version").textContent, "—");
});

test("route table renders the same normalized route identity and complete evidence", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  const routeViewModel = {
    status: "succeeded",
    routeHeading: "Hành lang được khuyến nghị",
    routes: [{
      routeId: "route-01",
      kind: "recommendation",
      rank: 1,
      statusLabel: "Đã qua safety gate",
      nodeSequence: ["node_06", "node_01", "node_02", "node_08"],
      maxVcRatio: 0.78,
      avgSpeedKmh: 28.5,
      delayProxySeconds: 42,
      uncertaintyScore: 0.12,
      oodScore: 0.08,
      reviewReasons: [],
      provenance: {
        modelVersion: "surrogate-v1",
        dataVersion: "sumo-v1",
        topologyVersion: "synthetic-routing-20-v1",
      },
    }],
  };

  view.render(succeededState(), { canApprove: true, canReject: true, canRequestChanges: true }, routeViewModel);

  assert.equal(doc.getElementById("route-heading").textContent, "Hành lang được khuyến nghị");
  const rows = doc.getElementById("route-rows").children;
  assert.equal(rows.length, 1);
  assert.equal(rows[0].dataset.routeId, "route-01");
  assert.equal(rows[0].children[0].textContent, "#1 · Đã qua safety gate");
  assert.match(rows[0].children[1].textContent, /node_06 → node_01 → node_02 → node_08/);
  assert.match(rows[0].children[2].textContent, /V\/C 0.78/);
  assert.match(rows[0].children[3].textContent, /surrogate-v1/);
});

test("needs-review table uses explicit candidate labels and no-route state is announced", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  const state = succeededState();
  state.job.status = "needs_review";
  const candidateModel = {
    status: "needs_review",
    routeHeading: "Hành lang cần xem xét",
    routes: [{
      routeId: "route-review",
      kind: "candidate",
      rank: null,
      statusLabel: "Chưa qua safety gate",
      nodeSequence: ["node_06", "node_01"],
      maxVcRatio: 0.94,
      avgSpeedKmh: 12,
      delayProxySeconds: 80,
      uncertaintyScore: 0.4,
      oodScore: 0.2,
      reviewReasons: ["vc_threshold_exceeded"],
      provenance: { modelVersion: "m1", dataVersion: "d1", topologyVersion: "t1" },
    }],
  };

  view.render(state, { canApprove: false, canReject: true, canRequestChanges: true }, candidateModel);
  assert.equal(doc.getElementById("route-rows").children[0].className, "route-row route-row-candidate");
  assert.match(doc.getElementById("route-rows").children[0].children[2].textContent, /Lý do: vc_threshold_exceeded/);

  view.render(state, { canApprove: false, canReject: true, canRequestChanges: true }, { ...candidateModel, routes: [] });
  assert.equal(doc.getElementById("route-empty").hidden, false);
});

test("failed and expired branches expose no decision or action", () => {
  for (const status of ["failed", "expired"]) {
    const doc = new FakeDocument();
    const view = createDashboardView(doc);
    const state = succeededState();
    state.job.status = status;
    state.job.result.status = status;
    state.job.result.recommended_action = null;
    view.render(state, { canApprove: false, canReject: false, canRequestChanges: false });

    assert.equal(doc.getElementById("action-view").textContent, "—");
    assert.equal(doc.getElementById("open-decision").disabled, true);
  }
});

test("readScenario reads trusted tenant and typed candidate action", () => {
  const doc = new FakeDocument();
  doc.getElementById("tenant-id").value = "tenant-a";
  doc.getElementById("node-id").value = "node_03";
  doc.getElementById("green-time").value = "0.65";
  doc.getElementById("scenario-query").value = "Đánh giá node_03";
  const payload = createDashboardView(doc).readScenario();

  assert.equal(payload.tenant_id, "tenant-a");
  assert.deepEqual(payload.candidate_action, { node_id: "node_03", green_time_ratio: 0.65 });
  assert.deepEqual(payload.node_ids, ["node_03"]);
});

test("incident preset preserves the selected node and builds typed incident", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  view.setContext({
    tenantId: "demo-operator",
    nodeIds: ["node_00", "node_14", "node_19"],
    mode: "demo",
  });
  view.setNode("node_14");
  doc.getElementById("scenario-query").value = "Original";

  view.setScenario({
    eventType: "lane_closure",
    severity: "high",
    durationMinutes: 45,
    laneClosureRatio: 0.6,
    ratio: 0.7,
    query: "Synthetic lane closure",
    expectation: "needs_review",
  });
  const payload = view.readScenario();

  assert.equal(doc.getElementById("node-id").value, "node_14");
  assert.deepEqual(payload.node_ids, ["node_00", "node_14", "node_19"]);
  assert.deepEqual(payload.incident, {
    event_type: "lane_closure",
    affected_node_ids: ["node_14"],
    severity: "high",
    duration_minutes: 45,
    description: "Synthetic lane closure",
    lane_closure_ratio: 0.6,
  });
});

test("normal preset emits an explicit no-incident request", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  view.setContext({ tenantId: "demo-operator", nodeIds: ["node_00"], mode: "demo" });
  view.setNode("node_00");
  view.setScenario({
    eventType: "",
    ratio: 0.7,
    query: "Normal baseline",
    expectation: "succeeded",
  });

  assert.equal(view.readScenario().incident, null);
});

test("editing typed incident parameters marks the preset as custom", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  let changes = 0;
  view.setHandlers({ changeScenario: () => { changes += 1; } });

  doc.getElementById("incident-severity").listeners.get("change")({});
  for (const id of [
    "incident-duration",
    "lane-closure-ratio",
    "demand-multiplier",
    "signal-plan-delta",
  ]) {
    doc.getElementById(id).listeners.get("input")({});
  }

  assert.equal(changes, 5);
});

test("decision dialog disables choices not allowed by policy", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  view.openDecisionDialog(
    { jobId: "job-1", traceId: "trace-1", operatorId: "operator-1" },
    { canApprove: false, canReject: true, canRequestChanges: false },
  );

  assert.equal(doc.radios[0].disabled, true);
  assert.equal(doc.radios[1].disabled, false);
  assert.equal(doc.radios[2].disabled, true);
  assert.equal(doc.getElementById("decision-dialog").open, true);
});

test("slash shortcut focuses node search without hijacking editable controls", () => {
  const doc = new FakeDocument();
  createDashboardView(doc);
  let prevented = false;

  doc.listeners.get("keydown")({
    key: "/",
    target: new FakeElement("div"),
    preventDefault() { prevented = true; },
  });
  assert.equal(prevented, true);
  assert.equal(doc.getElementById("node-search").focused, true);

  doc.getElementById("node-search").focused = false;
  doc.listeners.get("keydown")({
    key: "/",
    target: new FakeElement("textarea"),
    preventDefault() { throw new Error("must not intercept typing"); },
  });
  assert.equal(doc.getElementById("node-search").focused, false);
});

test("C shortcut copies the trace without hijacking editable controls", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  let copied = 0;
  view.setHandlers({ copyTrace: () => { copied += 1; } });
  let prevented = false;

  doc.listeners.get("keydown")({
    key: "c",
    target: new FakeElement("div"),
    preventDefault() { prevented = true; },
  });
  assert.equal(copied, 1);
  assert.equal(prevented, true);

  doc.listeners.get("keydown")({
    key: "C",
    target: new FakeElement("input"),
    preventDefault() { throw new Error("must not intercept typing"); },
  });
  doc.listeners.get("keydown")({
    key: "c",
    ctrlKey: true,
    target: new FakeElement("div"),
    preventDefault() { throw new Error("must preserve browser copy"); },
  });
  assert.equal(copied, 1);
});

test("decision dialog focuses the first enabled decision", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);

  view.openDecisionDialog(
    { jobId: "job-1", traceId: "trace-1", operatorId: "operator-1" },
    { canApprove: false, canReject: true, canRequestChanges: true },
  );

  assert.equal(doc.radios[0].focused, undefined);
  assert.equal(doc.radios[1].focused, true);
});
test("dialog cancel restores focus to the control that opened it", () => {
  const doc = new FakeDocument();
  const trigger = doc.activeElement;
  const view = createDashboardView(doc);

  view.openDecisionDialog(
    { jobId: "job-1", traceId: "trace-1", operatorId: "operator-1" },
    { canApprove: true, canReject: true, canRequestChanges: true },
  );
  let prevented = false;
  doc.getElementById("decision-dialog").listeners.get("cancel")({
    preventDefault() { prevented = true; },
  });

  assert.equal(prevented, true);
  assert.equal(doc.getElementById("decision-dialog").open, false);
  assert.equal(trigger.focused, true);
});

test("node list uses pressed semantics instead of listbox", () => {
  const doc = new FakeDocument();
  const view = createDashboardView(doc);
  view.setContext({
    tenantId: "demo-operator",
    nodeIds: ["node_00", "node_01"],
    mode: "demo",
  });

  const list = doc.getElementById("node-list");
  assert.equal(list.role, "group");
  assert.equal(list["aria-label"], "Danh sách node");
  assert.equal(list.children.length, 2);
  assert.equal(list.children[0].role, undefined);
  assert.equal(list.children[0]["aria-pressed"], "false");
  assert.equal(list.children[0]["aria-selected"], undefined);

  view.setNode("node_01");
  assert.equal(list.children[0]["aria-pressed"], "false");
  assert.equal(list.children[0]["aria-current"], undefined);
  assert.equal(list.children[1]["aria-pressed"], "true");
  assert.equal(list.children[1]["aria-current"], "true");
});
