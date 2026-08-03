# STWI Production-Grade Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thiết kế lại dashboard STWI theo Solid Hybrid Command Center, tách state/API/view/mode thành native ES modules, harden lifecycle và decision gates, đồng thời giữ nguyên demo synthetic và static preview.

**Architecture:** Dashboard dùng ba miền trạng thái độc lập: canonical job, transport và decision. `dashboard.js` chỉ điều phối; pure rules nằm trong `dashboard-state.js`, network/reconnect trong `dashboard-api.js`, safe DOM/focus trong `dashboard-view.js`, còn production/demo/static compatibility nằm trong `dashboard-mode.js`. Không thêm frontend framework hoặc build step.

**Tech Stack:** HTML5, CSS, native ES modules, Fetch API, EventSource/SSE, AbortController, sessionStorage, Node built-in test runner, Python unittest, FastAPI static assets.

## Global Constraints

- STWI là decision-support; `automatic_actuation` luôn `false` và operator approval luôn bắt buộc.
- Chỉ dùng sáu canonical status: `queued`, `running`, `succeeded`, `needs_review`, `failed`, `expired`.
- Chỉ `succeeded` có `recommended_action`; chỉ `needs_review` có `candidate_action` không executable.
- Không hiển thị hoặc lưu raw video; không thêm camera playback, reroute, dispatch hoặc signal-control semantics.
- Giữ đúng 20 node demo `node_00`–`node_19` và toàn bộ preset deterministic hiện hành.
- Production không fallback im lặng sang demo; static preview không được submit hoặc record decision.
- Không dùng glass, translucent fill, `backdrop-filter`, acrylic blur, glow hoặc gradient trên data surface.
- Primary giữ `#006699`; dùng `Be Vietnam Pro` và `Azeret Mono`; target tối thiểu 44×44 px.
- Không render dữ liệu không tin cậy bằng `innerHTML`; dùng `textContent`, `replaceChildren` và DOM APIs.
- Không thêm dependency hoặc framework mới nếu chưa được người dùng chấp thuận.
- Không sửa `project_contract.json`; API dependency cần contract change phải được báo thành blocker riêng.
- Không stage hoặc commit nếu người dùng chưa cấp quyền Git rõ ràng.

---

## File map

| File | Responsibility |
|---|---|
| `src/stwi/t4_orchestrator/static/dashboard.js` | Bootstrap và coordinator; không chứa reducer hoặc fetch chi tiết |
| `src/stwi/t4_orchestrator/static/dashboard-state.js` | Pure state, payload guards và decision selectors |
| `src/stwi/t4_orchestrator/static/dashboard-api.js` | Fetch/SSE, abort, retry/backoff và safe error parsing |
| `src/stwi/t4_orchestrator/static/dashboard-view.js` | Safe DOM rendering, focus, drawer/dialog và form snapshot |
| `src/stwi/t4_orchestrator/static/dashboard-mode.js` | Production/demo/static runtime resolution và demo compatibility |
| `src/stwi/t4_orchestrator/static/dashboard.css` | Solid tokens, three-region IA và responsive behavior |
| `src/stwi/t4_orchestrator/static/index.html` | Semantic result-first structure và accessible controls |
| `src/stwi/t4_orchestrator/static/package.json` | Scoped Node ESM mode; không thêm package dependency |
| `tests/frontend/dashboard-state.test.mjs` | Pure reducer, guards, evidence và decision policy tests |
| `tests/frontend/dashboard-api.test.mjs` | Fetch/SSE/retry/stale-operation behavior tests |
| `tests/frontend/dashboard-mode.test.mjs` | Production/demo/static resolution tests |
| `tests/demo/test_dashboard_static.py` | Demo presets, static preview, DOM IDs và copy guardrails |
| `tests/t4_orchestrator/test_dashboard_static.py` | Contract/status/action/asset static checks |
| `docs/design/stwi_ui_design_system.md` | No-glass visual and interaction contract |
| `docs/guides/mvp_operator_dashboard.md` | Dual-mode operator workflow and limitations |

---

### Task 1: Pure dashboard state and contract guards

**Files:**
- Create: `src/stwi/t4_orchestrator/static/package.json`
- Create: `src/stwi/t4_orchestrator/static/dashboard-state.js`
- Create: `tests/frontend/dashboard-state.test.mjs`

**Interfaces:**
- Produces: `JOB_STATUSES`, `TERMINAL_STATUSES`, `createInitialState()`, `reduceDashboardState(state, event)`, `validateAcceptedJob(value)`, `validateJobEnvelope(value)`, `evaluateEvidence(result, mode)`, `deriveDecisionPolicy(state)`.
- Consumes: none; this module must remain pure and DOM/network-free.

- [ ] **Step 1: Add scoped ESM metadata**

```json
{
  "private": true,
  "type": "module"
}
```

- [ ] **Step 2: Write failing state and guard tests**

```javascript
// tests/frontend/dashboard-state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  createInitialState,
  deriveDecisionPolicy,
  evaluateEvidence,
  reduceDashboardState,
  validateAcceptedJob,
  validateJobEnvelope,
} from "../../src/stwi/t4_orchestrator/static/dashboard-state.js";

const safeAction = {
  node_id: "node_00",
  green_time_ratio: 0.7,
  executable: false,
  automatic_actuation: false,
  requires_operator_approval: true,
};

test("transport failure preserves authoritative running status", () => {
  let state = createInitialState();
  state = reduceDashboardState(state, {
    type: "job/accepted",
    accepted: { job_id: "job-1", status: "queued", tenant_id: "demo-operator" },
    epoch: 1,
  });
  state = reduceDashboardState(state, { type: "job/envelope", envelope: { job_id: "job-1", status: "running", tenant_id: "demo-operator" } });
  state = reduceDashboardState(state, { type: "transport/offline", code: "NETWORK_ERROR" });
  assert.equal(state.job.status, "running");
  assert.equal(state.transport.phase, "offline");
});

test("unknown status is rejected instead of becoming a job status", () => {
  const outcome = validateJobEnvelope({ job_id: "job-1", status: "complete" });
  assert.deepEqual(outcome, { ok: false, code: "JOB_STATUS_UNKNOWN" });
});

test("accepted response requires exact queued status and tenant", () => {
  assert.deepEqual(validateAcceptedJob({ job_id: "job-1", status: "queued", tenant_id: "demo-operator" }).ok, true);
  assert.deepEqual(validateAcceptedJob({ job_id: "job-1", status: "running", tenant_id: "demo-operator" }), { ok: false, code: "CREATE_STATUS_INVALID" });
});

test("approval requires succeeded, safe action, evidence, role and no prior decision", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "production", roles: ["operator"] },
    job: {
      id: "job-1",
      status: "succeeded",
      result: { recommended_action: safeAction },
      evidence: { phase: "valid" },
      decisionRecord: null,
    },
    transport: { phase: "online" },
  };
  assert.equal(deriveDecisionPolicy(state).canApprove, true);
  assert.equal(deriveDecisionPolicy({ ...state, job: { ...state.job, result: {} } }).canApprove, false);
});

test("demo evidence is provisional and production unknown is insufficient", () => {
  const result = {
    model_version: "model-v1",
    data_version: "data-v1",
    completed_at: "2026-07-20T00:00:00Z",
    audit_record: { trace_id: "trace-1" },
    citations: [{ source_url: "https://vanban.chinhphu.vn/example", provision: "Điều 1", effective_from: "2025-01-01" }],
  };
  assert.equal(evaluateEvidence(result, "demo").phase, "demo_provisional_valid");
  assert.equal(evaluateEvidence(result, "production").phase, "unknown");
});
```

- [ ] **Step 3: Run the state tests and verify they fail**

Run:

```powershell
node --test tests/frontend/dashboard-state.test.mjs
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `dashboard-state.js`.

- [ ] **Step 4: Implement the pure state module**

```javascript
// src/stwi/t4_orchestrator/static/dashboard-state.js
export const JOB_STATUSES = Object.freeze([
  "queued", "running", "succeeded", "needs_review", "failed", "expired",
]);
export const TERMINAL_STATUSES = new Set(["succeeded", "needs_review", "failed", "expired"]);

const isObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);
const isNonEmptyString = (value) => typeof value === "string" && value.trim().length > 0;

export function createInitialState() {
  return {
    context: { mode: "checking", tenantId: null, operatorId: null, roles: [] },
    creation: { phase: "idle", idempotencyKey: null },
    job: { id: null, status: null, result: null, evidence: { phase: "pending" }, decisionRecord: null, events: [] },
    transport: { phase: "checking", code: null, lastEventId: null },
    decision: { phase: "unavailable", error: null },
    operationEpoch: 0,
  };
}

export function validateAcceptedJob(value) {
  if (!isObject(value) || !isNonEmptyString(value.job_id)) return { ok: false, code: "CREATE_JOB_ID_MISSING" };
  if (value.status !== "queued") return { ok: false, code: "CREATE_STATUS_INVALID" };
  if (!isNonEmptyString(value.tenant_id)) return { ok: false, code: "CREATE_TENANT_MISSING" };
  return { ok: true, value };
}

export function validateJobEnvelope(value) {
  if (!isObject(value) || !isNonEmptyString(value.job_id)) return { ok: false, code: "JOB_ID_MISSING" };
  if (!JOB_STATUSES.includes(value.status)) return { ok: false, code: "JOB_STATUS_UNKNOWN" };
  return { ok: true, value };
}

function isSafeAction(action) {
  return isObject(action)
    && action.executable === false
    && action.automatic_actuation === false
    && action.requires_operator_approval === true;
}

function hasDemoEvidence(result) {
  const traceId = result?.trace_id || result?.audit_record?.trace_id;
  return isNonEmptyString(traceId)
    && isNonEmptyString(result?.model_version)
    && isNonEmptyString(result?.data_version)
    && isNonEmptyString(result?.completed_at || result?.created_at)
    && Array.isArray(result?.citations)
    && result.citations.length > 0
    && result.citations.every((citation) => isNonEmptyString(citation?.source_url || citation?.source)
      && isNonEmptyString(citation?.provision || citation?.article)
      && isNonEmptyString(citation?.effective_from));
}

export function evaluateEvidence(result, mode) {
  if (!result) return { phase: "pending" };
  if (result.citation_validation_outcome === "valid") return { phase: "valid" };
  if (result.citation_validation_outcome === "invalid") return { phase: "invalid" };
  if (result.citation_validation_outcome === "insufficient") return { phase: "insufficient" };
  if (mode === "demo" && hasDemoEvidence(result)) return { phase: "demo_provisional_valid" };
  return { phase: "unknown" };
}

export function deriveDecisionPolicy(state) {
  const roles = new Set(state.context.roles || []);
  const canDecide = roles.has("operator") || roles.has("admin");
  const evidenceAllowed = state.job.evidence?.phase === "valid"
    || (state.context.mode === "demo" && state.job.evidence?.phase === "demo_provisional_valid");
  const noDecision = !state.job.decisionRecord;
  const protocolSafe = state.transport.phase !== "protocol_error";
  return {
    canApprove: canDecide && noDecision && protocolSafe && evidenceAllowed
      && state.job.status === "succeeded" && isSafeAction(state.job.result?.recommended_action),
    canReject: canDecide && noDecision && ["succeeded", "needs_review", "failed", "expired"].includes(state.job.status),
    canRequestChanges: canDecide && noDecision && ["succeeded", "needs_review"].includes(state.job.status),
  };
}

export function reduceDashboardState(state, event) {
  switch (event.type) {
    case "context/resolved":
      return { ...state, context: event.context, transport: { ...state.transport, phase: "online" } };
    case "creation/submitting":
      return { ...state, operationEpoch: event.epoch, creation: { phase: "submitting", idempotencyKey: event.idempotencyKey } };
    case "job/accepted":
      return { ...state, operationEpoch: event.epoch, creation: { ...state.creation, phase: "accepted" }, job: { ...state.job, id: event.accepted.job_id, status: "queued" } };
    case "job/resume_requested":
      return { ...state, operationEpoch: event.epoch, creation: { ...state.creation, phase: "resuming" }, job: { ...state.job, id: event.jobId, status: null } };
    case "job/envelope":
      if (state.job.id && event.envelope.job_id !== state.job.id) return state;
      return { ...state, job: { ...state.job, id: event.envelope.job_id, status: event.envelope.status, result: event.envelope.result || null, decisionRecord: event.envelope.operator_decision || null } };
    case "job/event": {
      if (state.job.id !== event.jobId) return state;
      const duplicate = event.eventId && state.job.events.some((item) => item.eventId === event.eventId);
      return duplicate ? state : { ...state, job: { ...state.job, events: [...state.job.events, { eventId: event.eventId || null, payload: event.payload }].slice(-100) } };
    }
    case "transport/phase":
      return { ...state, transport: { ...state.transport, phase: event.phase, code: event.code || null, lastEventId: event.lastEventId ?? state.transport.lastEventId } };
    case "transport/offline":
      return { ...state, transport: { ...state.transport, phase: "offline", code: event.code } };
    case "transport/protocol_error":
      return { ...state, transport: { ...state.transport, phase: "protocol_error", code: event.code } };
    case "decision/submitting":
      return { ...state, decision: { phase: "submitting", error: null } };
    case "decision/recorded":
      return { ...state, decision: { phase: "recorded", error: null } };
    case "decision/conflict":
      return { ...state, decision: { phase: "conflict", error: event.code } };
    case "decision/error":
      return { ...state, decision: { phase: "error", error: event.code } };
    default:
      return state;
  }
}
```

- [ ] **Step 5: Run state tests and syntax validation**

Run:

```powershell
node --test tests/frontend/dashboard-state.test.mjs
node --check src/stwi/t4_orchestrator/static/dashboard-state.js
```

Expected: all state tests PASS; syntax check exits 0.

- [ ] **Step 6: Review checkpoint and conditional commit**

Run `git diff --check` and inspect only Task 1 files. If the user explicitly authorized commits, commit with:

```powershell
git add src/stwi/t4_orchestrator/static/package.json src/stwi/t4_orchestrator/static/dashboard-state.js tests/frontend/dashboard-state.test.mjs
git commit -m "feat: add fail-closed dashboard state model"
```

Otherwise do not stage or commit.

---

### Task 2: Production, demo and static runtime modes

**Files:**
- Create: `src/stwi/t4_orchestrator/static/dashboard-mode.js`
- Create: `tests/frontend/dashboard-mode.test.mjs`
- Modify: `tests/demo/test_dashboard_static.py`

**Interfaces:**
- Consumes: injected `fetchImpl` only.
- Produces: `resolveDashboardContext({ fetchImpl }) -> Promise<DashboardContext>` where mode is `production`, `demo`, or `static_preview`.

- [ ] **Step 1: Write failing mode-resolution tests**

```javascript
// tests/frontend/dashboard-mode.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { resolveDashboardContext } from "../../src/stwi/t4_orchestrator/static/dashboard-mode.js";

const response = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test("trusted context enables production mode", async () => {
  const fetchImpl = async (url) => {
    assert.equal(url, "/api/v1/ui-context");
    return response(200, { mode: "production", tenant_id: "tenant-a", operator_id: "op-a", roles: ["operator"], node_ids: ["node_00"] });
  };
  const context = await resolveDashboardContext({ fetchImpl });
  assert.equal(context.mode, "production");
  assert.deepEqual(context.roles, ["operator"]);
});

test("provisional STWI OpenAPI enables demo compatibility", async () => {
  const fetchImpl = async (url) => url === "/api/v1/ui-context"
    ? response(404, {})
    : response(200, { info: { title: "STWI What-If API", version: "0.4.0-provisional" } });
  assert.equal((await resolveDashboardContext({ fetchImpl })).mode, "demo");
});

test("invalid production context never falls back to demo", async () => {
  const fetchImpl = async () => response(200, { mode: "production", roles: [] });
  const context = await resolveDashboardContext({ fetchImpl });
  assert.equal(context.mode, "static_preview");
  assert.equal(context.reason, "CONTEXT_INVALID");
});

test("missing runtime becomes static preview", async () => {
  const fetchImpl = async () => { throw new TypeError("offline"); };
  assert.equal((await resolveDashboardContext({ fetchImpl })).mode, "static_preview");
});
```

- [ ] **Step 2: Run tests and verify failure**

Run `node --test tests/frontend/dashboard-mode.test.mjs`.

Expected: FAIL with missing `dashboard-mode.js`.

- [ ] **Step 3: Implement fail-closed mode resolution**

```javascript
// src/stwi/t4_orchestrator/static/dashboard-mode.js
const DEMO_NODES = Object.freeze(Array.from({ length: 20 }, (_, index) => `node_${String(index).padStart(2, "0")}`));

const staticPreview = (reason) => ({ mode: "static_preview", tenantId: null, operatorId: null, roles: [], nodeIds: DEMO_NODES, reason });

function validTrustedContext(body) {
  return body?.mode === "production"
    && typeof body.tenant_id === "string" && body.tenant_id.length > 0
    && typeof body.operator_id === "string" && body.operator_id.length > 0
    && Array.isArray(body.roles) && body.roles.length > 0
    && Array.isArray(body.node_ids);
}

export async function resolveDashboardContext({ fetchImpl = fetch } = {}) {
  try {
    const contextResponse = await fetchImpl("/api/v1/ui-context", { headers: { Accept: "application/json" }, cache: "no-store" });
    if (contextResponse.ok) {
      const body = await contextResponse.json();
      if (!validTrustedContext(body)) return staticPreview("CONTEXT_INVALID");
      return { mode: "production", tenantId: body.tenant_id, operatorId: body.operator_id, roles: body.roles, nodeIds: body.node_ids, capabilities: body.capabilities || {} };
    }
    if (contextResponse.status !== 404) return staticPreview("CONTEXT_UNAVAILABLE");

    const openApiResponse = await fetchImpl("/openapi.json", { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!openApiResponse.ok) return staticPreview("RUNTIME_UNAVAILABLE");
    const openApi = await openApiResponse.json();
    const provisional = openApi?.info?.title === "STWI What-If API"
      && String(openApi?.info?.version || "").includes("provisional");
    if (!provisional) return staticPreview("RUNTIME_UNTRUSTED");
    return { mode: "demo", tenantId: "demo-operator", operatorId: "demo-operator", roles: ["operator"], nodeIds: DEMO_NODES, capabilities: { demoPresets: true } };
  } catch {
    return staticPreview("RUNTIME_UNAVAILABLE");
  }
}
```

- [ ] **Step 4: Add static demo-contract assertions**

Add to `tests/demo/test_dashboard_static.py`:

```python
def test_dashboard_mode_adapter_preserves_demo_and_static_preview(self) -> None:
    mode_script = (STATIC / "dashboard-mode.js").read_text(encoding="utf-8")
    self.assertIn('mode: "demo"', mode_script)
    self.assertIn('mode: "static_preview"', mode_script)
    self.assertIn('"/openapi.json"', mode_script)
    self.assertIn("RUNTIME_UNTRUSTED", mode_script)
```

- [ ] **Step 5: Run mode and demo tests**

```powershell
node --test tests/frontend/dashboard-mode.test.mjs
python -m unittest tests.demo.test_dashboard_static -v
node --check src/stwi/t4_orchestrator/static/dashboard-mode.js
```

Expected: all PASS.

- [ ] **Step 6: Review checkpoint and conditional commit**

If commits are authorized:

```powershell
git add src/stwi/t4_orchestrator/static/dashboard-mode.js tests/frontend/dashboard-mode.test.mjs tests/demo/test_dashboard_static.py
git commit -m "feat: separate production demo and preview modes"
```

Otherwise do not stage or commit.

---

### Task 3: Reliable API, SSE and polling transport

**Files:**
- Create: `src/stwi/t4_orchestrator/static/dashboard-api.js`
- Create: `tests/frontend/dashboard-api.test.mjs`

**Interfaces:**
- Produces: `ApiError`, `createDashboardApi({ fetchImpl, EventSourceImpl, storage, timers, random })`.
- Returned client methods: `createJob(payload, options)`, `getJob(jobId, options)`, `recordDecision(jobId, payload, options)`, `streamJob(jobId, handlers)`, `pollJob(jobId, handlers)`.
- Consumes: state guards from Task 1 in the coordinator, not inside this transport module.

- [ ] **Step 1: Write failing API behavior tests**

```javascript
// tests/frontend/dashboard-api.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createDashboardApi } from "../../src/stwi/t4_orchestrator/static/dashboard-api.js";

const jsonResponse = (status, body) => ({ ok: status >= 200 && status < 300, status, headers: new Headers(), json: async () => body });

test("create requires HTTP 202 and sends idempotency key", async () => {
  let request;
  const api = createDashboardApi({
    fetchImpl: async (_url, options) => { request = options; return jsonResponse(202, { job_id: "job-1", status: "queued", tenant_id: "demo-operator" }); },
  });
  await api.createJob({ tenant_id: "demo-operator" }, { idempotencyKey: "request-1" });
  assert.equal(request.headers["Idempotency-Key"], "request-1");
});

test("transport failure is reported without a canonical job status", async () => {
  const api = createDashboardApi({ fetchImpl: async () => { throw new TypeError("offline"); } });
  await assert.rejects(() => api.getJob("job-1"), (error) => error.code === "NETWORK_ERROR" && error.jobStatus === undefined);
});

test("EventSource error reports reconnecting and does not close the stream", () => {
  class FakeEventSource {
    constructor() { FakeEventSource.instance = this; this.closed = false; }
    addEventListener() {}
    close() { this.closed = true; }
  }
  const phases = [];
  const api = createDashboardApi({ EventSourceImpl: FakeEventSource });
  api.streamJob("job-1", { onTransport: (phase) => phases.push(phase) });
  FakeEventSource.instance.onerror();
  assert.deepEqual(phases, ["reconnecting"]);
  assert.equal(FakeEventSource.instance.closed, false);
});

test("polling backs off instead of using 250 ms", async () => {
  const delays = [];
  let calls = 0;
  const api = createDashboardApi({
    fetchImpl: async () => jsonResponse(200, { job_id: "job-1", status: ++calls < 3 ? "running" : "succeeded" }),
    timers: { sleep: async (ms) => delays.push(ms) },
    random: () => 0,
  });
  await api.pollJob("job-1", { onEnvelope: () => {}, isTerminal: (envelope) => envelope.status === "succeeded" });
  assert.deepEqual(delays, [1000, 2000]);
});
```

- [ ] **Step 2: Run tests and verify failure**

Run `node --test tests/frontend/dashboard-api.test.mjs`.

Expected: FAIL with missing `dashboard-api.js`.

- [ ] **Step 3: Implement the API client**

```javascript
// src/stwi/t4_orchestrator/static/dashboard-api.js
export class ApiError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    Object.assign(this, details);
  }
}

const defaultTimers = { sleep: (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)) };

async function safeJson(response) {
  try { return await response.json(); } catch { throw new ApiError("INVALID_JSON", "Runtime trả dữ liệu không hợp lệ.", { httpStatus: response.status }); }
}

export function createDashboardApi({ fetchImpl = fetch, EventSourceImpl = EventSource, timers = defaultTimers, random = Math.random } = {}) {
  async function requestJson(url, { expectedStatus = 200, timeoutMs = 10000, signal, ...options } = {}) {
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    try {
      const response = await fetchImpl(url, { ...options, signal: controller.signal, cache: "no-store" });
      const body = await safeJson(response);
      if (response.status !== expectedStatus) {
        const detail = body?.detail || {};
        throw new ApiError(detail.code || `HTTP_${response.status}`, detail.message || `HTTP ${response.status}`, { httpStatus: response.status, traceId: detail.trace_id });
      }
      return body;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (controller.signal.aborted) throw new ApiError("REQUEST_TIMEOUT", "Yêu cầu quá thời gian chờ.");
      throw new ApiError("NETWORK_ERROR", "Không thể kết nối STWI runtime.");
    } finally {
      globalThis.clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
    }
  }

  const getJob = (jobId, { signal } = {}) => requestJson(
    `/api/v1/what-if-jobs/${encodeURIComponent(jobId)}`,
    { signal },
  );

  return {
    createJob(payload, { idempotencyKey, signal } = {}) {
      return requestJson("/api/v1/what-if-jobs", {
        expectedStatus: 202,
        timeoutMs: 15000,
        signal,
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(payload),
      });
    },
    getJob,
    recordDecision(jobId, payload, { signal } = {}) {
      return requestJson(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/operator-decision`, {
        signal, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
    },
    streamJob(jobId, { onEvent = () => {}, onTransport = () => {} } = {}) {
      const source = new EventSourceImpl(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/events`);
      const seen = new Set();
      const handle = (event) => {
        if (event.lastEventId && seen.has(event.lastEventId)) return;
        if (event.lastEventId) seen.add(event.lastEventId);
        try { onEvent(JSON.parse(event.data), event.lastEventId || null); }
        catch { onTransport("protocol_error"); }
      };
      source.onopen = () => onTransport("streaming");
      source.onmessage = handle;
      source.addEventListener("status", handle);
      source.addEventListener("result", handle);
      source.onerror = () => onTransport("reconnecting");
      return () => source.close();
    },
    async pollJob(jobId, { onEnvelope, isTerminal, signal } = {}) {
      let delay = 1000;
      while (!signal?.aborted) {
        const envelope = await getJob(jobId, { signal });
        onEnvelope(envelope);
        if (isTerminal(envelope)) return envelope;
        const jitter = Math.floor(delay * 0.1 * random());
        await timers.sleep(delay + jitter);
        delay = Math.min(delay * 2, 5000);
      }
      throw new ApiError("MONITOR_ABORTED", "Đã dừng theo dõi job.");
    },
  };
}
```

- [ ] **Step 4: Run API tests and syntax check**

```powershell
node --test tests/frontend/dashboard-api.test.mjs
node --check src/stwi/t4_orchestrator/static/dashboard-api.js
```

Expected: all PASS.

- [ ] **Step 5: Review checkpoint and conditional commit**

If commits are authorized:

```powershell
git add src/stwi/t4_orchestrator/static/dashboard-api.js tests/frontend/dashboard-api.test.mjs
git commit -m "feat: harden dashboard job transport"
```

Otherwise do not stage or commit.

---

### Task 4: Result-first Solid Hybrid HTML and CSS

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/index.html`
- Modify: `src/stwi/t4_orchestrator/static/dashboard.css`
- Modify: `tests/demo/test_dashboard_static.py`
- Modify: `tests/t4_orchestrator/test_dashboard_static.py`

**Interfaces:**
- Produces DOM IDs consumed by Task 5: `app-main`, `node-drawer`, `result-conclusion`, `uncertainty-panel`, `evidence-panel`, `decision-dialog`, `decision-form`, `decision-rationale`, `connection-state`.
- Preserves existing IDs required by tests/API rendering: `scenario-form`, `job-status`, `forecast-volume`, `forecast-speed`, `vc-ratio`, `capacity-version`, `citations`, `trace-id`, `versions`, `json-view`.

- [ ] **Step 1: Replace lexical layout tests with explicit IA assertions**

Add these assertions before changing markup/CSS:

```python
def test_dashboard_is_result_first_and_has_decision_dialog(self) -> None:
    result_at = self.html.index('id="result-conclusion"')
    scenario_at = self.html.index('id="scenario-form"')
    self.assertLess(result_at, scenario_at)
    for element_id in (
        "app-main", "node-drawer", "uncertainty-panel", "evidence-panel",
        "decision-dialog", "decision-form", "decision-rationale", "connection-state",
    ):
        self.assertIn(f'id="{element_id}"', self.html)

def test_dashboard_uses_solid_accessible_tokens(self) -> None:
    self.assertIn("--stwi-primary: #006699", self.css)
    self.assertIn("min-height: 44px", self.css)
    self.assertNotIn("backdrop-filter", self.css)
    self.assertNotIn("rgba(255,255,255,.72)", self.css)
    self.assertNotIn("rgba(255,255,255,.76)", self.css)
```

Update the asset assertion to require:

```python
self.assertIn('type="module" src="dashboard.js"', self.html)
```

- [ ] **Step 2: Run static tests and verify failure**

Run:

```powershell
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
```

Expected: FAIL for missing result-first IDs, module script and solid tokens.

- [ ] **Step 3: Implement semantic result-first structure**

Use this exact top-level order inside `<body>`; move existing field markup into the indicated sections without changing field names or preset values:

```html
<a class="skip-link" href="#result-conclusion">Bỏ qua đến kết quả</a>
<div class="app-shell" data-runtime-mode="checking">
  <header class="app-header">
    <a class="brand" href="/demo/" aria-label="STWI What-If Operator"><span class="brand-mark" aria-hidden="true">ST</span><span><strong>SmartTraffic</strong><small>What-If Operator</small></span></a>
    <div class="header-context">
      <span id="runtime-state" class="context-pill"><span id="runtime-label">Đang kiểm tra runtime</span></span>
      <span id="connection-state" class="context-pill" role="status">Đang kết nối</span>
      <span class="human-badge">Human approval required</span>
    </div>
  </header>

  <main id="app-main" class="command-layout">
    <aside id="node-drawer" class="node-rail" aria-label="Chọn một trong 20 node đăng ký">
      <label for="node-search">Tìm node</label><input id="node-search" type="search" autocomplete="off">
      <div id="node-list"></div>
    </aside>

    <div class="workspace">
      <section id="result-conclusion" class="panel result-panel" aria-labelledby="result-title" tabindex="-1">
        <p class="section-kicker">KẾT QUẢ · 30 PHÚT</p><h1 id="result-title">Chưa có kết quả mô phỏng</h1>
        <p id="interpretation-summary">Chọn một node và tạo kịch bản What-If.</p>
        <div class="forecast-metrics"><article><span>Lưu lượng giao thông</span><strong id="forecast-volume">—</strong><small>xe/5 phút</small></article><article><span>Tốc độ trung bình</span><strong id="forecast-speed">—</strong><small>km/h</small></article><article><span>V/C tối đa</span><strong id="vc-ratio">—</strong><small>Policy MVP: 0.9</small></article><article><span>Phiên bản năng lực</span><strong id="capacity-version">—</strong><small>capacity_version</small></article></div>
      </section>
      <section class="panel lifecycle-panel" aria-labelledby="lifecycle-title"><div class="panel-heading"><h2 id="lifecycle-title" tabindex="-1">Theo dõi job</h2><span id="job-status" class="status">Chưa gửi</span></div><div class="job-summary"><div><span>Job ID</span><code id="job-id">—</code></div><div><span>Trace ID</span><code id="trace-id">—</code></div><div><span>Model / data</span><code id="versions">—</code></div><div><span>Server status</span><code id="terminal-status">—</code></div><div><span>Timestamp</span><code id="result-timestamp">—</code></div></div><ol id="events" class="timeline"></ol><span id="event-count">0 sự kiện</span><div id="empty-events">Chưa có job đang chạy</div></section>
      <section class="panel scenario-panel" aria-labelledby="scenario-title">
        <h2 id="scenario-title">Tạo kịch bản What-If</h2>
        <form id="scenario-form">
          <label>Bộ kiểm thử demo
            <select id="demo-preset" name="preset" aria-describedby="preset-expectation">
              <optgroup label="Safety cơ bản"><option value="safe">Luồng bình thường · succeeded</option><option value="unsafe-vc">V/C vượt policy · needs_review</option><option value="ood">Ngoài phân phối · needs_review</option><option value="uncertainty">Độ bất định cao · needs_review</option><option value="missing-evidence">Thiếu căn cứ · needs_review</option><option value="extreme">Green time cực trị · needs_review</option></optgroup>
              <optgroup label="Tình huống vận hành"><option value="accident">Tai nạn · nghẽn do giảm năng lực</option><option value="flood">Ngập lụt · tốc độ rất thấp</option><option value="lane-closure">Đóng làn · V/C vượt policy</option><option value="demand-surge">Nhu cầu tăng · lưu lượng cao</option><option value="environmental-anomaly">Tín hiệu môi trường bất thường · OOD</option></optgroup>
              <option value="custom">Tùy chỉnh thủ công</option>
            </select>
            <small id="preset-expectation">Kỳ vọng: kết quả synthetic đạt các kiểm tra của profile mô phỏng.</small>
          </label>
          <div class="field-grid">
            <label>Tenant<input id="tenant-id" name="tenant" autocomplete="off" required readonly><small>Được runtime cấp; demo dùng demo-operator.</small></label>
            <label>Nút giao<select id="node-id" name="node" required></select><small>Danh sách được runtime cấp; demo giữ node_00–node_19.</small></label>
          </div>
          <label>Green time ratio <output id="green-value" for="green-time">0.70 · 70%</output><input id="green-time" name="green" type="range" min="0" max="1" step="0.05" value="0.7" aria-describedby="green-help"><small id="green-help">Chỉ dùng trong mô phỏng; không phải lệnh điều khiển.</small></label>
          <label>Mô tả tình huống<textarea id="scenario-query" name="query" required>Đánh giá quyền và nghĩa vụ người sử dụng đường tại node_00.</textarea><small>Dùng cho phân tích và truy xuất bằng chứng pháp lý/SOP.</small></label>
          <div class="form-footer"><p class="privacy-note">Chỉ aggregate · Không lưu hình ảnh thô</p><button id="submit-button" type="submit">Chạy mô phỏng</button></div>
          <p id="form-error" class="error" role="alert"></p>
        </form>
      </section>
      <details class="help-panel"><summary>Giải thích biến và dữ liệu demo</summary><div class="glossary-grid"><article><code>tenant_id</code><strong>Phạm vi dữ liệu</strong><p>Production lấy từ trusted context; demo dùng định danh synthetic.</p></article><article><code>node_id</code><strong>Nút giao cần đánh giá</strong><p>Production dùng allowlist runtime; demo dùng 20 node synthetic.</p></article><article><code>green_time_ratio</code><strong>Tỷ lệ thời gian đèn xanh</strong><p>Giá trị 0–1 chỉ dành cho kịch bản mô phỏng.</p></article><article><code>scenario_query</code><strong>Câu hỏi phân tích</strong><p>Mô tả sự cố hoặc thay đổi cần đánh giá.</p></article><article><code>job_id / trace_id</code><strong>Định danh và truy vết</strong><p>Dùng để theo dõi job và audit trail.</p></article><article><code>model / data</code><strong>Phiên bản tái lập</strong><p>Ghi lại model và dataset tạo kết quả.</p></article><article><code>V/C</code><strong>Mức sử dụng năng lực</strong><p>0.9 là policy MVP, không phải quy định pháp luật.</p></article><article><code>action payload</code><strong>Kết quả không thực thi</strong><p>Operator luôn quyết định; hệ thống không gửi lệnh hiện trường.</p></article></div></details>
    </div>

    <aside class="evidence-rail">
      <section id="uncertainty-panel" class="panel"><h2>Uncertainty và OOD</h2><div id="safety-state"><span class="state-icon" aria-hidden="true">○</span><div><strong>Chờ kết quả</strong><p id="review-reason">Safety checks sẽ xuất hiện sau khi job hoàn tất.</p></div></div><dl id="safety-checks"></dl></section>
      <section id="evidence-panel" class="panel"><h2>Evidence và provenance</h2><span id="evidence-status">Chờ kết quả</span><p id="evidence-message">Citation hợp lệ mới cho phép recommendation.</p><ul id="citations"></ul><div id="action-kind">NON-EXECUTABLE</div><pre id="action-view">—</pre><details><summary>JSON audit</summary><pre id="json-view">—</pre></details></section>
      <section class="panel decision-panel"><h2>Quyết định operator</h2><p>Kết quả chỉ hỗ trợ quyết định; không gửi lệnh hiện trường.</p><button id="open-decision" type="button" disabled>Ghi nhận quyết định</button><div id="decision-result" role="status" aria-live="polite">Đang chờ operator xem xét.</div></section>
    </aside>
  </main>
</div>

<dialog id="decision-dialog" aria-labelledby="decision-dialog-title">
  <form id="decision-form" method="dialog"><h2 id="decision-dialog-title">Ghi nhận quyết định</h2><div id="decision-context"></div><fieldset><legend>Quyết định</legend><label><input type="radio" name="decision" value="approved"> Phê duyệt</label><label><input type="radio" name="decision" value="rejected"> Từ chối</label><label><input type="radio" name="decision" value="request_changes"> Yêu cầu chỉnh sửa</label></fieldset><label for="decision-rationale">Lý do</label><textarea id="decision-rationale" name="rationale"></textarea><p id="decision-error" role="alert"></p><div class="dialog-actions"><button id="cancel-decision" type="button" class="secondary">Hủy</button><button id="submit-decision" type="submit">Xác nhận audit-only</button></div></form>
</dialog>
<script type="module" src="dashboard.js"></script>
```

Populate `#node-id` from `context.nodeIds`; do not hard-code the production allowlist. Keep all 11 deterministic demo preset values exactly as shown and preserve every API-bound ID.

- [ ] **Step 4: Replace visual tokens and responsive layout**

Start `dashboard.css` with:

```css
:root {
  color: #14232c;
  background: #eff4f6;
  font-family: "Be Vietnam Pro", "Segoe UI", sans-serif;
  --stwi-shell: #072b38;
  --stwi-primary: #006699;
  --stwi-primary-hover: #004d73;
  --stwi-canvas: #eff4f6;
  --stwi-surface: #ffffff;
  --stwi-subtle: #f5f8fa;
  --stwi-border: #c9d7df;
  --stwi-text: #14232c;
  --stwi-muted: #52636d;
  --stwi-success: #166534;
  --stwi-warning: #9a6700;
  --stwi-danger: #b42318;
  --stwi-radius: 12px;
  --stwi-shadow: 0 2px 10px rgb(20 35 44 / 10%);
}
* { box-sizing: border-box; }
body { margin: 0; min-width: 320px; background: var(--stwi-canvas); color: var(--stwi-text); }
button, input, select, textarea, summary { min-height: 44px; font: inherit; }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, summary:focus-visible, a:focus-visible { outline: 3px solid #0b7fab; outline-offset: 2px; }
.skip-link { position: absolute; left: 12px; top: -80px; z-index: 20; padding: 10px 14px; color: #fff; background: var(--stwi-primary); }
.skip-link:focus { top: 12px; }
.app-header { display: flex; justify-content: space-between; align-items: center; gap: 20px; min-height: 72px; padding: 12px 24px; color: #fff; background: var(--stwi-shell); }
.command-layout { display: grid; grid-template-columns: 240px minmax(560px, 1fr) 300px; gap: 16px; width: min(1440px, calc(100% - 32px)); margin: 16px auto; align-items: start; }
.node-rail, .evidence-rail { position: sticky; top: 16px; }
.workspace, .evidence-rail { display: grid; gap: 16px; }
.panel { min-width: 0; padding: 20px; border: 1px solid var(--stwi-border); border-radius: var(--stwi-radius); background: var(--stwi-surface); box-shadow: var(--stwi-shadow); }
code, pre, .job-summary strong { font-family: "Azeret Mono", Consolas, monospace; overflow-wrap: anywhere; }
@media (max-width: 1023px) { .command-layout { grid-template-columns: 1fr; } .node-rail, .evidence-rail { position: static; } .node-rail { display: none; } .result-panel { order: 1; } .evidence-rail { order: 2; } .lifecycle-panel { order: 3; } .scenario-panel { order: 4; } }
@media (max-width: 389px) { .forecast-metrics { grid-template-columns: 1fr; } }
@media (min-width: 390px) { .forecast-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; } }
```

Map each existing component class to the tokens above. Add explicit solid rules for `.scenario-panel`, `.lifecycle-panel`, `.result-panel`, `.evidence-rail .panel`, `.status`, `.context-pill`, `.timeline`, `.dialog-actions` and form controls; every data surface uses `var(--stwi-surface)` or `var(--stwi-subtle)`, with no alpha background, gradient or `backdrop-filter`.

- [ ] **Step 5: Run static tests**

Run:

```powershell
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
git diff --check
```

Expected: all static tests PASS; diff check exits 0.

- [ ] **Step 6: Review checkpoint and conditional commit**

If commits are authorized:

```powershell
git add src/stwi/t4_orchestrator/static/index.html src/stwi/t4_orchestrator/static/dashboard.css tests/demo/test_dashboard_static.py tests/t4_orchestrator/test_dashboard_static.py
git commit -m "feat: add solid result-first dashboard shell"
```

Otherwise do not stage or commit.

---

### Task 5: Safe view renderer and accessible interaction primitives

**Files:**
- Create: `src/stwi/t4_orchestrator/static/dashboard-view.js`
- Modify: `tests/t4_orchestrator/test_dashboard_static.py`

**Interfaces:**
- Consumes: `DashboardState` and `DecisionPolicy` from Task 1.
- Produces: `createDashboardView(document)`, returning `render(state, policy)`, `readScenario()`, `openDecisionDialog(context, policy)`, `closeDecisionDialog()`, `focusLifecycle()`, `focusResult()`, `setHandlers(handlers)`.

- [ ] **Step 1: Add failing safe-view static tests**

```python
def test_view_module_uses_safe_dom_and_accessible_dialog(self) -> None:
    view = (STATIC_ROOT / "dashboard-view.js").read_text(encoding="utf-8")
    self.assertNotIn("innerHTML", view)
    self.assertIn("textContent", view)
    self.assertIn("replaceChildren", view)
    self.assertIn("showModal()", view)
    self.assertIn("returnFocus", view)
    self.assertIn("decision-rationale", view)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```powershell
python -m unittest tests.t4_orchestrator.test_dashboard_static.TestDashboardStatic.test_view_module_uses_safe_dom_and_accessible_dialog -v
```

Expected: ERROR because `dashboard-view.js` does not exist.

- [ ] **Step 3: Implement the view boundary**

```javascript
// src/stwi/t4_orchestrator/static/dashboard-view.js
const text = (node, value, fallback = "—") => { node.textContent = value ?? fallback; };

export function createDashboardView(doc = document) {
  const byId = (id) => doc.getElementById(id);
  const dialog = byId("decision-dialog");
  const rationale = byId("decision-rationale");
  let returnFocus = null;
  let handlers = {};

  function renderCitations(citations = []) {
    const list = byId("citations");
    list.replaceChildren();
    for (const citation of citations) {
      const item = doc.createElement("li");
      const heading = doc.createElement("strong");
      const detail = doc.createElement("span");
      heading.textContent = citation.title || citation.document_number || citation.source || "Citation";
      detail.textContent = [citation.provision || citation.article, citation.effective_from, citation.source_url || citation.source].filter(Boolean).join(" · ");
      item.append(heading, detail);
      list.append(item);
    }
  }

  function render(state, policy) {
    text(byId("connection-state"), state.transport.phase);
    text(byId("runtime-label"), state.context.mode);
    text(byId("job-status"), state.job.status || "Chưa gửi");
    text(byId("job-id"), state.job.id);
    const result = state.job.result;
    text(byId("trace-id"), result?.trace_id || result?.audit_record?.trace_id);
    text(byId("versions"), result ? `${result.model_version || "—"} / ${result.data_version || "—"}` : null);
    text(byId("terminal-status"), state.job.status);
    text(byId("result-timestamp"), result?.completed_at || result?.created_at);
    text(byId("forecast-volume"), result?.forecast?.traffic_volume_5m);
    text(byId("forecast-speed"), result?.forecast?.avg_speed_kmh);
    text(byId("vc-ratio"), result?.safety?.max_vc_ratio);
    text(byId("capacity-version"), result?.capacity_version);
    text(byId("review-reason"), result?.review_reason || result?.safety?.reason || "Chưa có đánh giá safety.");
    text(byId("evidence-status"), state.job.evidence?.phase || "pending");
    text(byId("evidence-message"), result?.citation_validation_message || "Chờ bằng chứng được runtime xác nhận.");
    renderCitations(result?.citations || []);
    const action = state.job.status === "succeeded" ? result?.recommended_action
      : state.job.status === "needs_review" ? result?.candidate_action : null;
    text(byId("action-view"), action ? JSON.stringify(action, null, 2) : null);
    text(byId("json-view"), result ? JSON.stringify(result, null, 2) : null);
    text(byId("decision-result"), state.job.decisionRecord
      ? `${state.job.decisionRecord.decision} · ${state.job.decisionRecord.operator_id || "operator"}`
      : "Đang chờ operator xem xét.");
    byId("open-decision").disabled = !(policy.canApprove || policy.canReject || policy.canRequestChanges);
    doc.documentElement.dataset.runtimeMode = state.context.mode;
  }

  function readScenario() {
    const nodeId = byId("node-id").value.trim();
    return {
      tenant_id: byId("tenant-id").value.trim(),
      scenario_time: new Date().toISOString(),
      candidate_action: { node_id: nodeId, green_time_ratio: Number(byId("green-time").value) },
      node_ids: [nodeId],
      scenario_query: byId("scenario-query").value.trim(),
      jurisdiction: "VN",
    };
  }

  function openDecisionDialog(context, policy) {
    returnFocus = doc.activeElement;
    const radios = [...doc.querySelectorAll('input[name="decision"]')];
    for (const radio of radios) {
      radio.disabled = radio.value === "approved" ? !policy.canApprove
        : radio.value === "rejected" ? !policy.canReject : !policy.canRequestChanges;
      radio.checked = false;
    }
    rationale.value = "";
    text(byId("decision-context"), `${context.jobId} · ${context.traceId} · ${context.operatorId}`);
    dialog.showModal();
  }

  function closeDecisionDialog() {
    dialog.close();
    returnFocus?.focus();
  }

  byId("cancel-decision").addEventListener("click", closeDecisionDialog);
  byId("open-decision").addEventListener("click", () => handlers.openDecision?.());
  byId("decision-form").addEventListener("submit", (event) => { event.preventDefault(); handlers.submitDecision?.(new FormData(event.currentTarget)); });

  return {
    render,
    readScenario,
    openDecisionDialog,
    closeDecisionDialog,
    focusLifecycle: () => byId("lifecycle-title").focus(),
    focusResult: () => byId("result-conclusion").focus(),
    setHandlers: (next) => { handlers = next; },
  };
}
```

All untrusted values above flow only through `textContent`; `JSON.stringify` output is assigned to `<pre>.textContent`, never parsed as markup.

- [ ] **Step 4: Run static and syntax tests**

```powershell
python -m unittest tests.t4_orchestrator.test_dashboard_static -v
node --check src/stwi/t4_orchestrator/static/dashboard-view.js
```

Expected: all PASS.

- [ ] **Step 5: Review checkpoint and conditional commit**

If commits are authorized:

```powershell
git add src/stwi/t4_orchestrator/static/dashboard-view.js tests/t4_orchestrator/test_dashboard_static.py
git commit -m "feat: add safe accessible dashboard renderer"
```

Otherwise do not stage or commit.

---

### Task 6: Coordinator integration, demo presets and refresh resume

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/dashboard.js`
- Modify: `tests/demo/test_dashboard_static.py`
- Modify: `tests/frontend/dashboard-state.test.mjs`

**Interfaces:**
- Consumes all interfaces from Tasks 1–5.
- Produces one active coordinator scoped by `operationEpoch`, one active `AbortController`, one active EventSource cleanup function and `sessionStorage["stwi.activeJob"]` containing only `{jobId, tenantId}`.

- [ ] **Step 1: Add failing coordinator contract tests**

Add to `tests/demo/test_dashboard_static.py`:

```python
def test_coordinator_imports_modules_and_preserves_demo_presets(self) -> None:
    for module in ("dashboard-state.js", "dashboard-api.js", "dashboard-view.js", "dashboard-mode.js"):
        self.assertIn(f'from "./{module}"', self.js)
    for profile in ("safe", "unsafe-vc", "ood", "uncertainty", "missing-evidence", "extreme", "accident", "flood", "lane-closure", "demand-surge", "environmental-anomaly"):
        self.assertIn(f'"{profile}"', self.js)
    self.assertIn('sessionStorage.setItem("stwi.activeJob"', self.js)
    self.assertIn("operationEpoch", self.js)

def test_static_preview_disables_mutations(self) -> None:
    self.assertIn('context.mode === "static_preview"', self.js)
    self.assertIn("submitButton.disabled", self.js)
    self.assertIn("openDecisionButton.disabled", self.js)
```

- [ ] **Step 2: Run focused tests and verify failure**

Run `python -m unittest tests.demo.test_dashboard_static -v`.

Expected: FAIL for missing module imports, session resume and mode gating.

- [ ] **Step 3: Replace orchestration with module-based coordinator**

Start `dashboard.js` with these exact imports and lifecycle helpers; keep the current `DEMO_PRESETS` object values unchanged:

```javascript
import { createInitialState, deriveDecisionPolicy, evaluateEvidence, reduceDashboardState, TERMINAL_STATUSES, validateAcceptedJob, validateJobEnvelope } from "./dashboard-state.js";
import { createDashboardApi } from "./dashboard-api.js";
import { createDashboardView } from "./dashboard-view.js";
import { resolveDashboardContext } from "./dashboard-mode.js";

const api = createDashboardApi();
const view = createDashboardView(document);
let state = createInitialState();
let operationEpoch = 0;
let activeController = null;
let closeStream = null;
let fallbackTimer = null;
let pollingActive = false;

function dispatch(event) {
  state = reduceDashboardState(state, event);
  if (state.job.result) state = { ...state, job: { ...state.job, evidence: evaluateEvidence(state.job.result, state.context.mode) } };
  view.render(state, deriveDecisionPolicy(state));
}

function currentOperation(jobId, epoch) {
  return state.job.id === jobId && state.operationEpoch === epoch;
}

function persistActiveJob() {
  if (!state.job.id) return;
  sessionStorage.setItem("stwi.activeJob", JSON.stringify({ jobId: state.job.id, tenantId: state.context.tenantId }));
}

async function acceptEnvelope(envelope, epoch) {
  const validated = validateJobEnvelope(envelope);
  if (!validated.ok || !currentOperation(envelope.job_id, epoch)) return;
  dispatch({ type: "job/envelope", envelope: validated.value });
  if (TERMINAL_STATUSES.has(envelope.status)) {
    globalThis.clearTimeout(fallbackTimer);
    closeStream?.();
    sessionStorage.removeItem("stwi.activeJob");
    view.focusResult();
  }
}

async function startPollingFallback(jobId, epoch) {
  if (pollingActive || !currentOperation(jobId, epoch)) return;
  pollingActive = true;
  dispatch({ type: "transport/phase", phase: "polling_fallback" });
  try {
    await api.pollJob(jobId, {
      signal: activeController.signal,
      onEnvelope: (envelope) => acceptEnvelope(envelope, epoch),
      isTerminal: (envelope) => TERMINAL_STATUSES.has(envelope.status),
    });
  } catch (error) {
    if (currentOperation(jobId, epoch) && error.code !== "MONITOR_ABORTED") {
      dispatch({ type: "transport/offline", code: error.code || "NETWORK_ERROR" });
    }
  } finally {
    pollingActive = false;
  }
}

function monitorJob(jobId, epoch) {
  closeStream = api.streamJob(jobId, {
    onEvent: async (payload, eventId) => {
      if (!currentOperation(jobId, epoch)) return;
      dispatch({ type: "job/event", jobId, eventId, payload });
      if (TERMINAL_STATUSES.has(payload?.status)) {
        await acceptEnvelope(await api.getJob(jobId, { signal: activeController.signal }), epoch);
      }
    },
    onTransport: (phase) => {
      if (!currentOperation(jobId, epoch)) return;
      if (phase === "protocol_error") return dispatch({ type: "transport/protocol_error", code: "SSE_PAYLOAD_INVALID" });
      dispatch({ type: "transport/phase", phase });
      if (phase === "streaming") globalThis.clearTimeout(fallbackTimer);
      if (phase === "reconnecting") {
        globalThis.clearTimeout(fallbackTimer);
        fallbackTimer = globalThis.setTimeout(() => void startPollingFallback(jobId, epoch), 5000);
      }
    },
  });
}
```

Implement submit in this order:

```javascript
async function submitScenario(event) {
  event.preventDefault();
  if (state.context.mode === "static_preview") return;
  operationEpoch += 1;
  const epoch = operationEpoch;
  activeController?.abort();
  activeController = new AbortController();
  closeStream?.();
  globalThis.clearTimeout(fallbackTimer);
  pollingActive = false;
  const idempotencyKey = crypto.randomUUID();
  dispatch({ type: "creation/submitting", epoch, idempotencyKey });
  try {
    const accepted = await api.createJob(view.readScenario(), { idempotencyKey, signal: activeController.signal });
    const validated = validateAcceptedJob(accepted);
    if (!validated.ok) return dispatch({ type: "transport/protocol_error", code: validated.code });
    dispatch({ type: "job/accepted", accepted: validated.value, epoch });
    persistActiveJob();
    view.focusLifecycle();
    monitorJob(accepted.job_id, epoch);
  } catch (error) {
    if (epoch !== operationEpoch) return;
    dispatch({ type: "transport/offline", code: error.code || "NETWORK_ERROR" });
  }
}
```

Implement refresh resume without storing the scenario payload:

```javascript
async function resumeActiveJob() {
  const raw = sessionStorage.getItem("stwi.activeJob");
  if (!raw || state.context.mode === "static_preview") return;
  let saved;
  try { saved = JSON.parse(raw); } catch { sessionStorage.removeItem("stwi.activeJob"); return; }
  if (!saved.jobId || saved.tenantId !== state.context.tenantId) return;
  operationEpoch += 1;
  const epoch = operationEpoch;
  activeController?.abort();
  activeController = new AbortController();
  dispatch({ type: "job/resume_requested", jobId: saved.jobId, epoch });
  const envelope = await api.getJob(saved.jobId, { signal: activeController.signal });
  await acceptEnvelope(envelope, epoch);
  if (!TERMINAL_STATUSES.has(envelope.status)) monitorJob(saved.jobId, epoch);
}
```

Bootstrap with:

```javascript
async function bootstrap() {
  const context = await resolveDashboardContext();
  dispatch({ type: "context/resolved", context });
  const submitButton = document.getElementById("submit-button");
  const openDecisionButton = document.getElementById("open-decision");
  if (context.mode === "static_preview") { submitButton.disabled = true; openDecisionButton.disabled = true; }
  document.getElementById("demo-preset").closest("label").hidden = context.mode === "production";
  const tenantInput = document.getElementById("tenant-id");
  tenantInput.value = context.tenantId || "";
  tenantInput.readOnly = context.mode === "production";
  await resumeActiveJob();
}
```

- [ ] **Step 4: Run demo and frontend tests**

```powershell
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
node --test tests/frontend/dashboard-state.test.mjs tests/frontend/dashboard-api.test.mjs tests/frontend/dashboard-mode.test.mjs
node --check src/stwi/t4_orchestrator/static/dashboard.js
```

Expected: all PASS.

- [ ] **Step 5: Run the existing deterministic demo smoke**

Run:

```powershell
python scripts/demo/run_mvp_smoke.py
```

Expected: exit 0; safe scenario remains `succeeded`, unsafe/OOD branches remain fail closed, no raw video or automatic actuation claim.

- [ ] **Step 6: Review checkpoint and conditional commit**

If commits are authorized:

```powershell
git add src/stwi/t4_orchestrator/static/dashboard.js tests/demo/test_dashboard_static.py tests/frontend/dashboard-state.test.mjs
git commit -m "feat: integrate resilient dual-mode dashboard"
```

Otherwise do not stage or commit.

---

### Task 7: Decision dialog, evidence gate and stale-response protection

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/dashboard.js`
- Modify: `src/stwi/t4_orchestrator/static/dashboard-view.js`
- Modify: `tests/frontend/dashboard-state.test.mjs`
- Modify: `tests/demo/test_dashboard_static.py`

**Interfaces:**
- Consumes: `deriveDecisionPolicy(state)` and immutable `{jobId, traceId, operatorId, epoch}`.
- Produces: confirmed decision request; GET reconciliation; immutable rendered decision record.

- [ ] **Step 1: Add failing decision-policy and static tests**

Add to `tests/frontend/dashboard-state.test.mjs`:

```javascript
test("needs_review can never approve but may request changes", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "demo", roles: ["operator"] },
    job: { id: "job-1", status: "needs_review", result: { candidate_action: safeAction }, evidence: { phase: "demo_provisional_valid" }, decisionRecord: null },
    transport: { phase: "online" },
  };
  const policy = deriveDecisionPolicy(state);
  assert.equal(policy.canApprove, false);
  assert.equal(policy.canRequestChanges, true);
});

test("existing decision disables every mutation", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "demo", roles: ["operator"] },
    job: { id: "job-1", status: "succeeded", result: { recommended_action: safeAction }, evidence: { phase: "demo_provisional_valid" }, decisionRecord: { decision: "approved" } },
    transport: { phase: "online" },
  };
  assert.deepEqual(deriveDecisionPolicy(state), { canApprove: false, canReject: false, canRequestChanges: false });
});
```

Add to `tests/demo/test_dashboard_static.py`:

```python
def test_decision_requires_confirmation_and_reconciliation(self) -> None:
    self.assertIn("openDecisionDialog", self.js)
    self.assertIn("recordDecision", self.js)
    self.assertIn("reconcileDecision", self.js)
    self.assertIn("applied_by_system", self.js)
    self.assertNotIn('comment: "Recorded from the demo dashboard."', self.js)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
node --test tests/frontend/dashboard-state.test.mjs
python -m unittest tests.demo.test_dashboard_static -v
```

Expected: FAIL until decision integration is added.

- [ ] **Step 3: Bind the confirmation dialog**

Add to the coordinator:

```javascript
function openDecision() {
  const policy = deriveDecisionPolicy(state);
  const traceId = state.job.result?.trace_id || state.job.result?.audit_record?.trace_id || "—";
  view.openDecisionDialog({ jobId: state.job.id, traceId, operatorId: state.context.operatorId }, policy);
}

async function reconcileDecision(jobId, epoch) {
  const envelope = await api.getJob(jobId);
  if (!currentOperation(jobId, epoch) || !envelope.operator_decision) throw new Error("DECISION_NOT_PERSISTED");
  dispatch({ type: "job/envelope", envelope });
  return envelope.operator_decision;
}

async function submitDecision(formData) {
  const decision = String(formData.get("decision") || "");
  const rationale = String(formData.get("rationale") || "").trim();
  const policy = deriveDecisionPolicy(state);
  const allowed = decision === "approved" ? policy.canApprove : decision === "rejected" ? policy.canReject : decision === "request_changes" ? policy.canRequestChanges : false;
  if (!allowed) return;
  if (decision !== "approved" && !rationale) return;
  const context = { jobId: state.job.id, epoch: state.operationEpoch, operatorId: state.context.operatorId };
  dispatch({ type: "decision/submitting" });
  try {
    const response = await api.recordDecision(context.jobId, { operator_id: context.operatorId, decision, comment: rationale || "Confirmed audit-only by operator." });
    if (!currentOperation(context.jobId, context.epoch) || response.automatic_actuation !== false || response.operator_decision?.applied_by_system !== false) return dispatch({ type: "transport/protocol_error", code: "DECISION_RESPONSE_INVALID" });
    await reconcileDecision(context.jobId, context.epoch);
    dispatch({ type: "decision/recorded" });
    view.closeDecisionDialog();
  } catch (error) {
    if (!currentOperation(context.jobId, context.epoch)) return;
    dispatch({ type: error.httpStatus === 409 ? "decision/conflict" : "decision/error", code: error.code || "DECISION_FAILED" });
  }
}

view.setHandlers({ openDecision, submitDecision });
```

The production UI still sends `operator_id` only because the current API schema requires it; the field must come from trusted context and is never editable. Removing it from the request is a separate API-contract decision.

- [ ] **Step 4: Run decision, static and API tests**

```powershell
node --test tests/frontend/dashboard-state.test.mjs
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static tests.t4_orchestrator.test_t4_api_http tests.t4_orchestrator.test_t4_auth_boundary -v
node --check src/stwi/t4_orchestrator/static/dashboard.js
node --check src/stwi/t4_orchestrator/static/dashboard-view.js
```

Expected: all PASS; needs_review approval remains rejected; `applied_by_system=false` is preserved.

- [ ] **Step 5: Review checkpoint and conditional commit**

If commits are authorized:

```powershell
git add src/stwi/t4_orchestrator/static/dashboard.js src/stwi/t4_orchestrator/static/dashboard-view.js tests/frontend/dashboard-state.test.mjs tests/demo/test_dashboard_static.py
git commit -m "feat: add audited operator decision flow"
```

Otherwise do not stage or commit.

---

### Task 8: Documentation synchronization and full QA

**Files:**
- Modify: `docs/design/stwi_ui_design_system.md`
- Modify: `docs/guides/mvp_operator_dashboard.md`
- Modify: `docs/design/stwi_ui_manifest.json` only if its deliverable paths or acceptance metadata change
- Test: all dashboard/frontend/API/contract suites

**Interfaces:**
- Consumes final behavior from Tasks 1–7.
- Produces synchronized operator guidance, acceptance evidence and handoff notes.

- [ ] **Step 1: Update the design system with exact final rules**

Replace the visual and interaction guidance with these explicit statements:

```markdown
- Dashboard dùng Solid Hybrid Command Center với dark opaque shell và solid data surfaces.
- Không dùng glass, translucent fill, backdrop blur hoặc gradient trên panel dữ liệu.
- UI tách canonical job status khỏi transport và decision state; lỗi kết nối không được hiển thị như job `failed`.
- Production, demo và static preview dùng cùng IA; demo preset chỉ xuất hiện trong demo/static preview.
- Thứ tự mobile là result → uncertainty/OOD → evidence → citations/audit → decision → scenario/history.
- “Ghi nhận quyết định” mở confirmation dialog; không có CTA mang nghĩa điều khiển hiện trường.
```

- [ ] **Step 2: Update the operator guide**

Document:

- how mode is shown in the header;
- how demo presets remain deterministic;
- how reconnect/offline differs from canonical job status;
- how refresh resumes the active job;
- why production evidence must be server-validated;
- how decision confirmation/rationale works;
- which production dependencies remain outside UI scope.

- [ ] **Step 3: Run all automated verification**

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
python -m unittest tests.t4_orchestrator.test_t4_api_http tests.t4_orchestrator.test_t4_auth_boundary -v
node --test tests/frontend/dashboard-state.test.mjs tests/frontend/dashboard-api.test.mjs tests/frontend/dashboard-mode.test.mjs
node --check src/stwi/t4_orchestrator/static/dashboard.js
node --check src/stwi/t4_orchestrator/static/dashboard-state.js
node --check src/stwi/t4_orchestrator/static/dashboard-api.js
node --check src/stwi/t4_orchestrator/static/dashboard-view.js
node --check src/stwi/t4_orchestrator/static/dashboard-mode.js
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Expected: all commands exit 0. Report the Starlette/httpx deprecation warning if it still appears; do not call it a failure.

- [ ] **Step 4: Run dashboard through local HTTP**

Start the existing FastAPI demo runtime using the repository runbook. Verify:

1. safe preset → `succeeded`, recommendation non-executable, approve dialog available;
2. V/C, OOD, uncertainty and missing-evidence presets → `needs_review`, approve unavailable;
3. failed/expired → no proposal and no approve;
4. all five operational presets remain available and non-causal;
5. SSE disconnect → reconnecting/polling fallback without changing job status;
6. refresh during running → current job resumes;
7. static preview → submit and decision disabled;
8. no console errors.

- [ ] **Step 5: Perform responsive and accessibility QA**

Check 360, 390, 430, 768, 1024 and 1280 px. Verify no horizontal overflow, result-first order, ID wrap/copy, keyboard-only navigation, skip link, drawer/dialog focus trap and return, zoom 200%, reduced motion, visible focus and status labels independent of color.

If Firefox/WebKit automation is not already available without adding a dependency, record them as residual production evidence rather than installing a new framework silently.

- [ ] **Step 6: Inspect final scope and user changes**

Run:

```powershell
git status --short
git diff -- src/stwi/t4_orchestrator/static tests/frontend tests/demo/test_dashboard_static.py tests/t4_orchestrator/test_dashboard_static.py docs/design/stwi_ui_design_system.md docs/guides/mvp_operator_dashboard.md
```

Expected: only intended dashboard/test/doc changes plus clearly identified pre-existing user changes. No cache, log, PDF or generated artifact is staged.

- [ ] **Step 7: Final review checkpoint and conditional commit**

If and only if the user explicitly authorized commits, stage only reviewed files and commit:

```powershell
git add src/stwi/t4_orchestrator/static tests/frontend tests/demo/test_dashboard_static.py tests/t4_orchestrator/test_dashboard_static.py docs/design/stwi_ui_design_system.md docs/guides/mvp_operator_dashboard.md docs/design/stwi_ui_manifest.json
git commit -m "feat: deliver production-grade dual-mode dashboard"
```

Otherwise leave all changes unstaged and report verification evidence, demo compatibility and remaining backend production gates.

---

## Plan self-review checklist

- [x] Every spec section maps to at least one task.
- [x] Demo presets and static preview have explicit regression coverage.
- [x] Canonical job, transport and decision states remain separate.
- [x] Production never falls back silently to demo.
- [x] Approval requires validated action, evidence, role and immutable operation context.
- [x] UI does not claim server-enforced idempotency or production legal validation when unavailable.
- [x] No task adds a framework, dependency, raw video or automatic actuation.
- [x] All Git steps remain conditional on explicit user authorization.

Self-review resolved the initial draft's ambiguous HTML placeholders, simultaneous SSE/polling load, temporary fabricated `queued` status during resume, `this`-bound API call, browser-only timer default and decision-error/transport-error conflation.
