import test from "node:test";
import assert from "node:assert/strict";

import { resolveDashboardContext } from "../../src/stwi/t4_orchestrator/static/dashboard-mode.js";

const response = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

test("trusted runtime context enables production mode", async () => {
  const fetchImpl = async (url) => {
    assert.equal(url, "/api/v1/ui-context");
    return response(200, {
      mode: "production",
      tenant_id: "tenant-a",
      operator_id: "op-a",
      roles: ["operator"],
      node_ids: ["node_00"],
      capabilities: { record_decision: true },
    });
  };

  const context = await resolveDashboardContext({ fetchImpl });
  assert.equal(context.mode, "production");
  assert.equal(context.tenantId, "tenant-a");
  assert.deepEqual(context.roles, ["operator"]);
});

test("provisional STWI OpenAPI enables explicit demo compatibility", async () => {
  const fetchImpl = async (url) => url === "/api/v1/ui-context"
    ? response(404, {})
    : response(200, { info: { title: "STWI What-If API", version: "0.4.0-provisional" } });

  const context = await resolveDashboardContext({ fetchImpl });
  assert.equal(context.mode, "demo");
  assert.equal(context.nodeIds.length, 20);
  assert.equal(context.tenantId, "demo-operator");
});

test("invalid production context never falls back to demo", async () => {
  let calls = 0;
  const context = await resolveDashboardContext({
    fetchImpl: async () => {
      calls += 1;
      return response(200, { mode: "production", roles: [] });
    },
  });

  assert.equal(context.mode, "static_preview");
  assert.equal(context.reason, "CONTEXT_INVALID");
  assert.equal(calls, 1);
});

test("unknown or unreachable runtime becomes non-mutating static preview", async () => {
  const context = await resolveDashboardContext({
    fetchImpl: async () => { throw new TypeError("offline"); },
  });

  assert.equal(context.mode, "static_preview");
  assert.equal(context.roles.length, 0);
});

test("non-provisional OpenAPI cannot activate demo mode", async () => {
  const fetchImpl = async (url) => url === "/api/v1/ui-context"
    ? response(404, {})
    : response(200, { info: { title: "STWI What-If API", version: "1.0.0" } });

  const context = await resolveDashboardContext({ fetchImpl });
  assert.equal(context.mode, "static_preview");
  assert.equal(context.reason, "RUNTIME_UNTRUSTED");
});
