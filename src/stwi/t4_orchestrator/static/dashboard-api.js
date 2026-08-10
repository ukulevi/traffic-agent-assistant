export class ApiError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    Object.assign(this, details);
  }
}

const defaultTimers = {
  sleep: (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)),
};

async function safeJson(response) {
  try {
    return await response.json();
  } catch {
    throw new ApiError(
      "INVALID_JSON",
      "STWI runtime trả dữ liệu không hợp lệ.",
      { httpStatus: response.status },
    );
  }
}

export function createDashboardApi({
  fetchImpl = globalThis.fetch,
  EventSourceImpl = globalThis.EventSource,
  timers = defaultTimers,
  random = Math.random,
} = {}) {
  async function requestJson(
    url,
    { expectedStatus = 200, timeoutMs = 10000, signal, ...options } = {},
  ) {
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
    const abortFromCaller = () => controller.abort();
    signal?.addEventListener("abort", abortFromCaller, { once: true });

    try {
      const response = await fetchImpl(url, {
        ...options,
        signal: controller.signal,
        cache: "no-store",
      });
      const body = await safeJson(response);
      if (response.status !== expectedStatus) {
        const detail = body?.detail || {};
        throw new ApiError(
          detail.code || `HTTP_${response.status}`,
          detail.message || `HTTP ${response.status}`,
          { httpStatus: response.status, traceId: detail.trace_id },
        );
      }
      return body;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (signal?.aborted) {
        throw new ApiError("REQUEST_ABORTED", "Yêu cầu đã được thay thế hoặc hủy.");
      }
      if (controller.signal.aborted) {
        throw new ApiError("REQUEST_TIMEOUT", "Yêu cầu quá thời gian chờ.");
      }
      throw new ApiError("NETWORK_ERROR", "Không thể kết nối STWI runtime.");
    } finally {
      globalThis.clearTimeout(timeout);
      signal?.removeEventListener("abort", abortFromCaller);
    }
  }

  const getJob = (jobId, { signal } = {}) => requestJson(
    `/api/v1/what-if-jobs/${encodeURIComponent(jobId)}`,
    { signal },
  );

  const getNetworkContext = ({ signal } = {}) => requestJson(
    "/api/v1/network-context",
    { signal },
  );

  return {
    createJob(payload, { idempotencyKey, signal } = {}) {
      return requestJson("/api/v1/what-if-jobs", {
        expectedStatus: 202,
        timeoutMs: 15000,
        signal,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      });
    },

    getJob,

    getNetworkContext,

    recordDecision(jobId, payload, { signal } = {}) {
      return requestJson(
        `/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/operator-decision`,
        {
          signal,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
    },

    streamJob(jobId, { onEvent = () => {}, onTransport = () => {} } = {}) {
      if (typeof EventSourceImpl !== "function") {
        onTransport("unavailable");
        return () => {};
      }

      const source = new EventSourceImpl(
        `/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/events`,
      );
      const seen = new Set();
      const handle = (event) => {
        if (event.lastEventId && seen.has(event.lastEventId)) return;
        if (event.lastEventId) seen.add(event.lastEventId);
        try {
          onEvent(JSON.parse(event.data), event.lastEventId || null);
        } catch {
          onTransport("protocol_error");
        }
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
