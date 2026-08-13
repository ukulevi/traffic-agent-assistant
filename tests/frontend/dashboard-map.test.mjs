import test from "node:test";
import assert from "node:assert/strict";

import { createDashboardApi } from "../../src/stwi/t4_orchestrator/static/dashboard-api.js";
import { createDashboardCoordinator } from "../../src/stwi/t4_orchestrator/static/dashboard.js";
import {
  SYNTHETIC_NETWORK_CONTEXT,
  createDashboardMap,
} from "../../src/stwi/t4_orchestrator/static/dashboard-map.js";

function fakeDocument() {
  const createElement = (tagName) => {
    const element = {
      tagName: tagName.toUpperCase(),
      children: [],
      attributes: new Map(),
      dataset: {},
      className: "",
      textContent: "",
      listeners: new Map(),
      append(...children) { this.children.push(...children); },
      appendChild(child) { this.children.push(child); return child; },
      replaceChildren(...children) { this.children = children; },
      setAttribute(name, value) { this.attributes.set(name, String(value)); },
      getAttribute(name) { return this.attributes.get(name); },
      removeAttribute(name) { this.attributes.delete(name); },
      addEventListener(name, handler) { this.listeners.set(name, handler); },
      click() { this.listeners.get("click")?.({ currentTarget: this }); },
    };
    return element;
  };
  return { createElement };
}

function descendants(root, tagName) {
  const matches = [];
  const visit = (node) => {
    if (node.tagName === tagName.toUpperCase()) matches.push(node);
    for (const child of node.children || []) visit(child);
  };
  visit(root);
  return matches;
}

function fakeLeaflet() {
  const record = {
    mapOptions: null,
    mapRemoved: false,
    tileLayerCalls: 0,
    markerCalls: [],
    polylineCalls: [],
    groups: [],
  };
  const map = {
    setView() { return map; },
    fitBounds() { return map; },
    remove() { record.mapRemoved = true; },
  };
  const L = {
    CRS: { Simple: Symbol("CRS.Simple") },
    map(_element, options) { record.mapOptions = options; return map; },
    layerGroup() {
      const group = {
        layers: [],
        addTo() { record.groups.push(group); return group; },
        addLayer(layer) { group.layers.push(layer); return group; },
        clearLayers() { group.layers = []; },
      };
      return group;
    },
    circleMarker(position, options) {
      const marker = {
        position,
        options: { ...options },
        handlers: {},
        on(name, handler) { marker.handlers[name] = handler; return marker; },
        setStyle(style) { Object.assign(marker.options, style); return marker; },
        bindTooltip(label) { marker.tooltip = label; return marker; },
      };
      record.markerCalls.push(marker);
      return marker;
    },
    polyline(points, options) {
      const line = {
        points,
        options: { ...options },
        bindTooltip(label) { line.tooltip = label; return line; },
      };
      record.polylineCalls.push(line);
      return line;
    },
    latLngBounds(points) { return { points }; },
    tileLayer() { record.tileLayerCalls += 1; },
  };
  return { L, record };
}

function fixture() {
  const document = fakeDocument();
  const mapElement = document.createElement("div");
  mapElement.ownerDocument = document;
  const table = document.createElement("table");
  table.ownerDocument = document;
  const leaflet = fakeLeaflet();
  const selected = [];
  const view = createDashboardMap(mapElement, leaflet.L, {
    fallbackElement: table,
    onSelectNode: (nodeId) => selected.push(nodeId),
  });
  return { ...leaflet, document, mapElement, table, selected, view };
}

test("map is tile-free, uses CRS.Simple, and exposes the lifecycle contract", () => {
  const { L, record, view } = fixture();
  assert.equal(record.mapOptions.crs, L.CRS.Simple);
  assert.equal(record.mapOptions.attributionControl, false);
  assert.equal(record.tileLayerCalls, 0);
  for (const method of ["setTopology", "setSelection", "setJobState", "destroy"]) {
    assert.equal(typeof view[method], "function");
  }
});

test("synthetic fallback has 20 stable nodes and 62 directed edges", () => {
  assert.equal(SYNTHETIC_NETWORK_CONTEXT.nodes.length, 20);
  assert.equal(SYNTHETIC_NETWORK_CONTEXT.directed_edges.length, 62);
  assert.deepEqual(
    SYNTHETIC_NETWORK_CONTEXT.nodes.map((node) => node.node_id),
    Array.from({ length: 20 }, (_, index) => `node_${String(index).padStart(2, "0")}`),
  );
  assert.equal(SYNTHETIC_NETWORK_CONTEXT.synthetic, true);
});

test("topology renders markers, edges, labels, and an accessible table", () => {
  const { record, table, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  assert.equal(record.markerCalls.length, 20);
  assert.equal(record.polylineCalls.length, 62);
  assert.equal(record.tileLayerCalls, 0);
  assert.equal(record.markerCalls[0].tooltip, "Nút 00 · node_00");
  assert.equal(descendants(table, "tbody")[0].children.length, 20);
  assert.equal(descendants(table, "button")[0].textContent, "Nút 00");
});

test("marker and fallback-table selection share one callback", () => {
  const { record, selected, table, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  record.markerCalls[3].handlers.click();
  descendants(table, "button")[4].click();
  assert.deepEqual(selected, ["node_03", "node_04"]);

  view.setSelection("node_04");
  assert.equal(record.markerCalls[4].options.color, "#b42318");
  assert.equal(descendants(table, "button")[4].getAttribute("aria-pressed"), "true");
});

test("job states never fabricate an overlay before typed route evidence exists", () => {
  const { record, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  const routeGroup = record.groups[2];
  routeGroup.addLayer({ untyped: true });
  view.setJobState({ status: "succeeded", recommended_route: ["node_00", "node_01", "node_02"] });
  assert.equal(routeGroup.layers.length, 0);
  routeGroup.addLayer({ untyped: true });
  view.setJobState({ status: "failed", recommended_route: ["node_00", "node_01"] });
  assert.equal(routeGroup.layers.length, 0);
  routeGroup.addLayer({ untyped: true });
  view.setJobState({ status: "expired", recommended_route: ["node_00", "node_01"] });
  assert.equal(routeGroup.layers.length, 0);
});

test("map renders normalized recommendations with route identity and solid evidence style", () => {
  const { record, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  view.setJobState({
    status: "succeeded",
    routes: [{
      routeId: "route-01",
      kind: "recommendation",
      rank: 1,
      statusLabel: "Đã qua safety gate",
      nodeSequence: ["node_00", "node_01", "node_02"],
      edgeIds: ["edge-node_00-node_01", "edge-node_01-node_02"],
    }],
  });

  const routeLine = record.groups[2].layers[0];
  assert.deepEqual(routeLine.points, [[0, 0], [0, 1], [0, 2]]);
  assert.equal(routeLine.options.dashArray, null);
  assert.equal(routeLine.options.className, "route-overlay route-overlay-recommendation");
  assert.match(routeLine.tooltip, /route-01/);
  assert.match(routeLine.tooltip, /Đã qua safety gate/);
});

test("candidate overlays use a non-color dashed pattern and failed states clear them", () => {
  const { record, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  view.setJobState({
    status: "needs_review",
    routes: [{
      routeId: "route-review",
      kind: "candidate",
      rank: null,
      statusLabel: "Chưa qua safety gate",
      nodeSequence: ["node_05", "node_06"],
      edgeIds: ["edge-node_05-node_06"],
    }],
  });
  assert.equal(record.groups[2].layers[0].options.dashArray, "8 6");
  assert.equal(record.groups[2].layers[0].options.className, "route-overlay route-overlay-candidate");

  view.setJobState({ status: "failed", routes: [{ routeId: "ignored", nodeSequence: ["node_00", "node_01"] }] });
  assert.equal(record.groups[2].layers.length, 0);
});

test("map rejects a route whose nodes do not form authorized directed hops", () => {
  const { record, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  view.setJobState({
    status: "succeeded",
    routes: [{
      routeId: "route-invalid-hop",
      kind: "recommendation",
      statusLabel: "Đã qua safety gate",
      nodeSequence: ["node_00", "node_06"],
      edgeIds: ["edge-node_00-node_06"],
    }],
  });

  assert.equal(record.groups[2].layers.length, 0);
});

test("map rejects a route whose edge identity does not match its node hop", () => {
  const { record, view } = fixture();
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  view.setJobState({
    status: "succeeded",
    routes: [{
      routeId: "route-wrong-edge",
      kind: "recommendation",
      statusLabel: "Đã qua safety gate",
      nodeSequence: ["node_00", "node_01"],
      edgeIds: ["edge-node_01-node_00"],
    }],
  });

  assert.equal(record.groups[2].layers.length, 0);
});

test("fallback table remains usable when Leaflet is unavailable", () => {
  const document = fakeDocument();
  const mapElement = document.createElement("div");
  mapElement.ownerDocument = document;
  const table = document.createElement("table");
  const selected = [];
  const view = createDashboardMap(mapElement, null, {
    fallbackElement: table,
    onSelectNode: (nodeId) => selected.push(nodeId),
  });
  view.setTopology(SYNTHETIC_NETWORK_CONTEXT);
  assert.equal(descendants(table, "button").length, 20);
  descendants(table, "button")[1].click();
  assert.deepEqual(selected, ["node_01"]);
});

test("destroy removes the Leaflet instance", () => {
  const { record, view } = fixture();
  view.destroy();
  assert.equal(record.mapRemoved, true);
});

test("dashboard API fetches the authorized network-context endpoint", async () => {
  const calls = [];
  const api = createDashboardApi({
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return {
        ok: true,
        status: 200,
        json: async () => SYNTHETIC_NETWORK_CONTEXT,
      };
    },
  });
  const controller = new AbortController();
  const result = await api.getNetworkContext({ signal: controller.signal });
  assert.equal(calls[0].url, "/api/v1/network-context");
  assert.ok(calls[0].options.signal instanceof AbortSignal);
  assert.equal(calls[0].options.signal.aborted, false);
  assert.equal(result.network_version, "synthetic-grid-20-v1");
});

function coordinatorFixture(mode, { networkError = false } = {}) {
  const calls = { getNetworkContext: 0, setTopology: [], selections: [], networkStatus: [] };
  let handlers = {};
  const map = {
    setTopology(value) { calls.setTopology.push(value); },
    setSelection(value) { calls.selections.push(value); },
    setJobState() {},
    destroy() {},
  };
  const view = {
    render() {},
    setContext() {},
    setScenario() {},
    setNode(value) { calls.viewNode = value; },
    setNetworkContext(value, status) { calls.networkStatus.push({ value, status }); },
    setHandlers(value) { handlers = value; },
  };
  const serverTopology = Object.freeze({
    ...SYNTHETIC_NETWORK_CONTEXT,
    mode: "production",
    nodes: SYNTHETIC_NETWORK_CONTEXT.nodes.slice(0, 2),
    directed_edges: SYNTHETIC_NETWORK_CONTEXT.directed_edges.slice(0, 2),
  });
  const api = {
    async getNetworkContext() {
      calls.getNetworkContext += 1;
      if (networkError) throw new Error("NETWORK_CONTEXT_UNAVAILABLE");
      return serverTopology;
    },
  };
  const coordinator = createDashboardCoordinator({
    api,
    view,
    mapFactory: ({ onSelectNode }) => {
      calls.onSelectNode = onSelectNode;
      return map;
    },
    resolveContext: async () => ({
      mode,
      tenantId: mode === "production" ? "tenant-a" : "demo-operator",
      operatorId: "operator-1",
      roles: ["operator"],
      nodeIds: ["node_00", "node_01"],
      capabilities: {},
    }),
    storage: { getItem: () => null, setItem() {}, removeItem() {} },
  });
  return { calls, coordinator, handlers, serverTopology };
}

test("production uses only authorized topology and fails closed on fetch error", async () => {
  const success = coordinatorFixture("production");
  await success.coordinator.bootstrap();
  assert.equal(success.calls.getNetworkContext, 1);
  assert.equal(success.calls.setTopology[0], success.serverTopology);
  assert.equal(success.calls.networkStatus[0].status, "ready");

  const failure = coordinatorFixture("production", { networkError: true });
  await failure.coordinator.bootstrap();
  assert.equal(failure.calls.getNetworkContext, 1);
  assert.equal(failure.calls.setTopology[0], null);
  assert.equal(failure.calls.networkStatus[0].status, "unavailable");
  assert.notEqual(failure.calls.setTopology[0], SYNTHETIC_NETWORK_CONTEXT);
});

test("demo and static preview use only the non-mutating synthetic display context", async () => {
  for (const mode of ["demo", "static_preview"]) {
    const current = coordinatorFixture(mode);
    await current.coordinator.bootstrap();
    assert.equal(current.calls.getNetworkContext, 0);
    assert.equal(current.calls.setTopology[0], SYNTHETIC_NETWORK_CONTEXT);
  }
});

test("map selection synchronizes the canonical form and map state", async () => {
  const current = coordinatorFixture("static_preview");
  await current.coordinator.bootstrap();
  current.calls.onSelectNode("node_01");
  assert.equal(current.calls.viewNode, "node_01");
  assert.equal(current.calls.selections.at(-1), "node_01");
});
