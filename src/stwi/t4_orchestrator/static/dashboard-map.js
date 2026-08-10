const NODE_COLOR = "#006699";
const NODE_FILL = "#dff2f7";
const SELECTED_COLOR = "#b42318";
const SELECTED_FILL = "#fde8e5";

function nodeId(index) {
  return `node_${String(index).padStart(2, "0")}`;
}

function buildSyntheticEdges() {
  const edges = [];
  const addPair = (sourceIndex, targetIndex) => {
    const source = nodeId(sourceIndex);
    const target = nodeId(targetIndex);
    for (const [from, to] of [[source, target], [target, source]]) {
      edges.push(Object.freeze({
        edge_id: `edge-${from}-${to}`,
        source_node_id: from,
        target_node_id: to,
        cost: 1,
        distance_m: 100,
        lane_count: 2,
      }));
    }
  };
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 5; column += 1) {
      const index = row * 5 + column;
      if (column < 4) addPair(index, index + 1);
      if (row < 3) addPair(index, index + 5);
    }
  }
  return edges;
}

export const SYNTHETIC_NETWORK_CONTEXT = Object.freeze({
  mode: "demo",
  synthetic: true,
  geographic_claim: "Mạng 4x5 hoàn toàn synthetic, không đại diện địa lý thực.",
  network_version: "synthetic-grid-20-v1",
  routing_graph_version: "synthetic-routing-20-v1",
  gcn_adjacency_version: "mock-adjacency-20-v1",
  capacity_version: "mock-capacity-20-v1",
  nodes: Object.freeze(Array.from({ length: 20 }, (_, index) => Object.freeze({
    node_id: nodeId(index),
    display_name: `Nút ${String(index).padStart(2, "0")}`,
    x: index % 5,
    y: Math.floor(index / 5),
  }))),
  directed_edges: Object.freeze(buildSyntheticEdges()),
});

function edgesOf(topology) {
  return topology?.directed_edges || topology?.edges || [];
}

export function createDashboardMap(
  element,
  L,
  { fallbackElement = null, onSelectNode = () => {} } = {},
) {
  const ownerDocument = element?.ownerDocument || fallbackElement?.ownerDocument || globalThis.document;
  const markerByNode = new Map();
  const buttonByNode = new Map();
  let topology = null;
  let selectedNodeId = null;
  let destroyed = false;
  let map = null;
  let edgeGroup = null;
  let nodeGroup = null;
  let routeGroup = null;

  try {
    if (element && L?.map && L?.CRS?.Simple) {
      map = L.map(element, { crs: L.CRS.Simple, attributionControl: false });
      edgeGroup = L.layerGroup().addTo(map);
      nodeGroup = L.layerGroup().addTo(map);
      routeGroup = L.layerGroup().addTo(map);
      map.setView?.([1.5, 2], 0);
      element.dataset.mapState = "ready";
    } else if (element) {
      element.dataset.mapState = "fallback";
    }
  } catch {
    map = null;
    edgeGroup = null;
    nodeGroup = null;
    routeGroup = null;
    if (element) element.dataset.mapState = "fallback";
  }

  function renderFallback() {
    if (!fallbackElement || !ownerDocument || !topology) return;
    fallbackElement.replaceChildren();
    buttonByNode.clear();

    const caption = ownerDocument.createElement("caption");
    caption.textContent = `Danh sách ${topology.nodes.length} nút · ${topology.network_version || "version unknown"}`;
    fallbackElement.append(caption);

    const head = ownerDocument.createElement("thead");
    const headRow = ownerDocument.createElement("tr");
    for (const label of ["Nút", "Tọa độ synthetic"]) {
      const cell = ownerDocument.createElement("th");
      cell.setAttribute("scope", "col");
      cell.textContent = label;
      headRow.append(cell);
    }
    head.append(headRow);
    fallbackElement.append(head);

    const body = ownerDocument.createElement("tbody");
    for (const node of topology.nodes) {
      const row = ownerDocument.createElement("tr");
      row.dataset.nodeId = node.node_id;
      const nameCell = ownerDocument.createElement("td");
      const button = ownerDocument.createElement("button");
      button.type = "button";
      button.className = "network-node-button";
      button.textContent = node.display_name || node.node_id;
      button.setAttribute("aria-label", `${node.display_name || node.node_id} · ${node.node_id}`);
      button.setAttribute("aria-pressed", String(node.node_id === selectedNodeId));
      button.addEventListener("click", () => onSelectNode(node.node_id));
      nameCell.append(button);
      const coordinateCell = ownerDocument.createElement("td");
      coordinateCell.textContent = `x=${node.x}, y=${node.y}`;
      row.append(nameCell, coordinateCell);
      body.append(row);
      buttonByNode.set(node.node_id, button);
    }
    fallbackElement.append(body);
  }

  function renderTopology() {
    markerByNode.clear();
    edgeGroup?.clearLayers();
    nodeGroup?.clearLayers();
    routeGroup?.clearLayers();
    if (!topology || !map) return;

    const nodeLookup = new Map(topology.nodes.map((node) => [node.node_id, node]));
    for (const edge of edgesOf(topology)) {
      const source = nodeLookup.get(edge.source_node_id);
      const target = nodeLookup.get(edge.target_node_id);
      if (!source || !target) continue;
      edgeGroup.addLayer(L.polyline(
        [[source.y, source.x], [target.y, target.x]],
        { color: "#9bb7c2", weight: 2, opacity: 0.7 },
      ));
    }
    for (const node of topology.nodes) {
      const marker = L.circleMarker([node.y, node.x], {
        radius: 7,
        color: NODE_COLOR,
        fillColor: NODE_FILL,
        fillOpacity: 1,
        weight: 2,
      });
      marker.bindTooltip?.(`${node.display_name || node.node_id} · ${node.node_id}`);
      marker.on?.("click", () => onSelectNode(node.node_id));
      nodeGroup.addLayer(marker);
      markerByNode.set(node.node_id, marker);
    }
    const points = topology.nodes.map((node) => [node.y, node.x]);
    if (points.length && L.latLngBounds && map.fitBounds) {
      map.fitBounds(L.latLngBounds(points), { padding: [24, 24] });
    }
  }

  function setSelection(nodeIdValue) {
    selectedNodeId = nodeIdValue || null;
    for (const [candidate, marker] of markerByNode) {
      const selected = candidate === selectedNodeId;
      marker.setStyle?.({
        color: selected ? SELECTED_COLOR : NODE_COLOR,
        fillColor: selected ? SELECTED_FILL : NODE_FILL,
        weight: selected ? 4 : 2,
      });
    }
    for (const [candidate, button] of buttonByNode) {
      const selected = candidate === selectedNodeId;
      button.setAttribute("aria-pressed", String(selected));
      if (selected) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
  }

  function setJobState(jobState = {}) {
    routeGroup?.clearLayers();
    // The current WhatIfJobResult contract has no typed route evidence.
    // Keep the lifecycle hook fail-closed; TRA-63 will add validated overlays.
    void jobState;
  }

  return Object.freeze({
    setTopology(nextTopology) {
      if (destroyed) return;
      topology = nextTopology?.nodes ? nextTopology : null;
      renderFallback();
      renderTopology();
      setSelection(selectedNodeId);
    },
    setSelection,
    setJobState,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      edgeGroup?.clearLayers();
      nodeGroup?.clearLayers();
      routeGroup?.clearLayers();
      map?.remove?.();
      markerByNode.clear();
      buttonByNode.clear();
      map = null;
    },
  });
}
