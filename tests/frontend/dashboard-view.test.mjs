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
        recommended_action: { node_id: "node_00", executable: false, automatic_actuation: false, requires_operator_approval: true },
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
