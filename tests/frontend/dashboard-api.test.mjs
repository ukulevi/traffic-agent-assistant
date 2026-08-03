import test from "node:test";
import assert from "node:assert/strict";

import { ApiError, createDashboardApi } from "../../src/stwi/t4_orchestrator/static/dashboard-api.js";

function jsonResponse(status, body) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

test("createJob sends the idempotency key and requires HTTP 202", async () => {
  let captured;
  const api = createDashboardApi({
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return jsonResponse(202, { job_id: "job-1", status: "queued", tenant_id: "demo-operator" });
    },
  });

  const result = await api.createJob(
    { tenant_id: "demo-operator" },
    { idempotencyKey: "idempotency-1" },
  );

  assert.equal(captured.url, "/api/v1/what-if-jobs");
  assert.equal(captured.options.method, "POST");
  assert.equal(captured.options.headers["Idempotency-Key"], "idempotency-1");
  assert.equal(result.job_id, "job-1");
});

test("unexpected HTTP response becomes a typed API error", async () => {
  const api = createDashboardApi({
    fetchImpl: async () => jsonResponse(409, {
      detail: { code: "JOB_NOT_TERMINAL", message: "Job is still running", trace_id: "trace-1" },
    }),
  });

  await assert.rejects(
    api.recordDecision("job-1", { decision: "approved" }),
    (error) => error instanceof ApiError
      && error.code === "JOB_NOT_TERMINAL"
      && error.httpStatus === 409
      && error.traceId === "trace-1",
  );
});

test("stream reconnect does not close EventSource or mutate job state", () => {
  class FakeEventSource {
    constructor(url) {
      this.url = url;
      this.closed = false;
      this.listeners = new Map();
      FakeEventSource.instance = this;
    }

    addEventListener(name, handler) {
      this.listeners.set(name, handler);
    }

    close() {
      this.closed = true;
    }
  }

  const phases = [];
  const api = createDashboardApi({ EventSourceImpl: FakeEventSource });
  const close = api.streamJob("job-1", { onTransport: (phase) => phases.push(phase) });
  FakeEventSource.instance.onerror();

  assert.equal(FakeEventSource.instance.url, "/api/v1/what-if-jobs/job-1/events");
  assert.deepEqual(phases, ["reconnecting"]);
  assert.equal(FakeEventSource.instance.closed, false);
  close();
  assert.equal(FakeEventSource.instance.closed, true);
});

test("stream parses named events and ignores duplicate event ids", () => {
  class FakeEventSource {
    constructor() {
      this.listeners = new Map();
      FakeEventSource.instance = this;
    }

    addEventListener(name, handler) {
      this.listeners.set(name, handler);
    }

    close() {}
  }

  const events = [];
  const api = createDashboardApi({ EventSourceImpl: FakeEventSource });
  api.streamJob("job-1", { onEvent: (payload, eventId) => events.push({ payload, eventId }) });
  const handler = FakeEventSource.instance.listeners.get("status");
  const event = { data: '{"status":"running"}', lastEventId: "2" };
  handler(event);
  handler(event);

  assert.deepEqual(events, [{ payload: { status: "running" }, eventId: "2" }]);
});

test("polling uses bounded exponential backoff instead of 250 ms", async () => {
  const delays = [];
  let calls = 0;
  const api = createDashboardApi({
    fetchImpl: async () => jsonResponse(200, {
      job_id: "job-1",
      status: ++calls < 3 ? "running" : "succeeded",
    }),
    timers: { sleep: async (ms) => delays.push(ms) },
    random: () => 0,
  });

  const terminal = await api.pollJob("job-1", {
    onEnvelope: () => {},
    isTerminal: (envelope) => envelope.status === "succeeded",
  });

  assert.equal(terminal.status, "succeeded");
  assert.deepEqual(delays, [1000, 2000]);
  assert.equal(calls, 3);
});

test("external abort is distinguished from a request timeout", async () => {
  const controller = new AbortController();
  const api = createDashboardApi({
    fetchImpl: async (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }),
  });
  const pending = api.getJob("job-1", { signal: controller.signal });
  controller.abort();

  await assert.rejects(pending, (error) => error.code === "REQUEST_ABORTED");
});
