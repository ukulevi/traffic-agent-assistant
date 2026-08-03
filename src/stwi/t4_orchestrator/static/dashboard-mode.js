const DEMO_NODES = Object.freeze(
  Array.from({ length: 20 }, (_, index) => `node_${String(index).padStart(2, "0")}`),
);

function staticPreview(reason) {
  return {
    mode: "static_preview",
    tenantId: null,
    operatorId: null,
    roles: [],
    nodeIds: DEMO_NODES,
    capabilities: {},
    reason,
  };
}

function validTrustedContext(body) {
  return body?.mode === "production"
    && typeof body.tenant_id === "string"
    && body.tenant_id.trim().length > 0
    && typeof body.operator_id === "string"
    && body.operator_id.trim().length > 0
    && Array.isArray(body.roles)
    && body.roles.length > 0
    && body.roles.every((role) => typeof role === "string" && role.length > 0)
    && Array.isArray(body.node_ids)
    && body.node_ids.every((nodeId) => typeof nodeId === "string" && nodeId.length > 0);
}

export async function resolveDashboardContext({ fetchImpl = globalThis.fetch } = {}) {
  try {
    const contextResponse = await fetchImpl("/api/v1/ui-context", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    if (contextResponse.ok) {
      const body = await contextResponse.json();
      if (!validTrustedContext(body)) return staticPreview("CONTEXT_INVALID");
      return {
        mode: "production",
        tenantId: body.tenant_id,
        operatorId: body.operator_id,
        roles: body.roles,
        nodeIds: body.node_ids,
        capabilities: body.capabilities || {},
      };
    }

    if (contextResponse.status !== 404) {
      return staticPreview("CONTEXT_UNAVAILABLE");
    }

    const openApiResponse = await fetchImpl("/openapi.json", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!openApiResponse.ok) return staticPreview("RUNTIME_UNAVAILABLE");

    const openApi = await openApiResponse.json();
    const provisional = openApi?.info?.title === "STWI What-If API"
      && String(openApi?.info?.version || "").includes("provisional");
    if (!provisional) return staticPreview("RUNTIME_UNTRUSTED");

    return {
      mode: "demo",
      tenantId: "demo-operator",
      operatorId: "demo-operator",
      roles: ["operator"],
      nodeIds: DEMO_NODES,
      capabilities: { demoPresets: true, recordDecision: true },
    };
  } catch {
    return staticPreview("RUNTIME_UNAVAILABLE");
  }
}
