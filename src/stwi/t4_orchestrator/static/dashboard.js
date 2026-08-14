import { createDashboardApi } from "./dashboard-api.js";
import { resolveDashboardContext } from "./dashboard-mode.js";
import {
  createInitialState,
  deriveDecisionPolicy,
  deriveRouteViewModel,
  evaluateEvidence,
  reduceDashboardState,
  TERMINAL_STATUSES,
  validateAcceptedJob,
  validateJobEnvelope,
} from "./dashboard-state.js";
import { createDashboardView } from "./dashboard-view.js";
import {
  SYNTHETIC_NETWORK_CONTEXT,
  createDashboardMap,
} from "./dashboard-map.js";

export const DEMO_PRESETS = Object.freeze({
  safe: {
    eventType: "", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá trạng thái giao thông synthetic bình thường.",
    expectation: "Kỳ vọng: kết quả synthetic đạt các kiểm tra của profile mô phỏng.",
  },
  refinement: {
    eventType: "signal_change", severity: "medium", durationMinutes: 30,
    signalPlanDelta: 0.10, ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá thay đổi tín hiệu synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng: vòng 1 vượt policy V/C; hệ thống thử một candidate khác, vòng 2 pass và vẫn cần operator phê duyệt.",
  },
  "unsafe-vc": {
    eventType: "accident", severity: "medium", durationMinutes: 30,
    ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá tai nạn synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng: V/C vượt policy 0.90 và job chuyển needs_review.",
  },
  "missing-evidence": {
    eventType: "", ratio: 0.70, jurisdiction: "DEMO-NONE",
    query: "Tình huống synthetic không có căn cứ trong corpus được phép.",
    expectation: "Kỳ vọng: thiếu citation hợp lệ nên job dừng ở needs_review.",
  },
  extreme: {
    eventType: "", ratio: 0.00, jurisdiction: "VN",
    query: "Đánh giá giả định synthetic không có pha xanh tại nút đã chọn.",
    expectation: "Kỳ vọng: giá trị cực trị bị safety gate giữ lại để review.",
  },
  accident: {
    eventType: "accident", severity: "medium", durationMinutes: 30,
    ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá tai nạn synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng synthetic: giảm năng lực hiệu dụng làm V/C vượt policy 0.90; job cần operator review.",
  },
  flood: {
    eventType: "flood", severity: "medium", durationMinutes: 45,
    ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá ngập lụt synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng synthetic: tốc độ thấp nhất nhóm incident và V/C vượt policy; hệ thống không mô phỏng mực nước.",
  },
  "lane-closure": {
    eventType: "lane_closure", severity: "medium", durationMinutes: 30,
    laneClosureRatio: 0.50, ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá đóng làn synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng synthetic: năng lực giảm tương đương đóng một phần làn và job chuyển needs_review.",
  },
  "demand-surge": {
    eventType: "demand_surge", severity: "medium", durationMinutes: 30,
    demandMultiplier: 1.50, ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá nhu cầu tăng synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng synthetic: lưu lượng cao và V/C vượt policy 0.90; không phải dự báo production.",
  },
  "signal-change": {
    eventType: "signal_change", severity: "medium", durationMinutes: 30,
    signalPlanDelta: 0.10, ratio: 0.85, jurisdiction: "VN",
    query: "Đánh giá thay đổi tín hiệu synthetic tại nút đã chọn.",
    expectation: "Kỳ vọng synthetic: profile signal_change được đánh giá độc lập với nút giao.",
  },
});

const ACTIVE_JOB_KEY = "stwi.activeJob";

function defaultTimers() {
  return {
    setTimeout: (callback, delay) => globalThis.setTimeout(callback, delay),
    clearTimeout: (timer) => globalThis.clearTimeout(timer),
  };
}

export function createDashboardCoordinator({
  api = createDashboardApi(),
  view = createDashboardView(document),
  resolveContext = () => resolveDashboardContext(),
  storage = globalThis.sessionStorage,
  cryptoImpl = globalThis.crypto,
  navigatorImpl = globalThis.navigator,
  timers = defaultTimers(),
  mapFactory = null,
} = {}) {
  let state = createInitialState();
  let operationEpoch = 0;
  let activeController = null;
  let pollingController = null;
  let closeStream = null;
  let fallbackTimer = null;
  let pollingActive = false;
  let activeJurisdiction = "VN";
  let networkMap = null;

  function dispatch(event) {
    state = reduceDashboardState(state, event);
    if (state.job.result) {
      state = {
        ...state,
        job: {
          ...state.job,
          evidence: evaluateEvidence(state.job.result, state.context.mode),
        },
      };
    }
    const routeViewModel = deriveRouteViewModel({
      status: state.job.status,
      result: state.job.result,
    });
    view.render(state, deriveDecisionPolicy(state), routeViewModel);
    networkMap?.setJobState(routeViewModel);
  }

  function currentOperation(jobId, epoch) {
    return state.job.id === jobId && state.operationEpoch === epoch;
  }

  function persistActiveJob() {
    if (!state.job.id || !storage) return;
    storage.setItem(ACTIVE_JOB_KEY, JSON.stringify({
      jobId: state.job.id,
      tenantId: state.context.tenantId,
    }));
  }

  function clearMonitoring() {
    timers.clearTimeout(fallbackTimer);
    activeController?.abort();
    pollingController?.abort();
    closeStream?.();
    activeController = null;
    pollingController = null;
    closeStream = null;
    pollingActive = false;
  }

  async function acceptEnvelope(envelope, epoch) {
    const validated = validateJobEnvelope(envelope);
    if (!validated.ok) {
      dispatch({ type: "transport/protocol_error", code: validated.code });
      return;
    }
    if (!currentOperation(envelope.job_id, epoch)) return;
    if (envelope.tenant_id && envelope.tenant_id !== state.context.tenantId) {
      dispatch({ type: "transport/protocol_error", code: "JOB_TENANT_MISMATCH" });
      return;
    }

    dispatch({ type: "job/envelope", envelope: validated.value });
    if (TERMINAL_STATUSES.has(envelope.status)) {
      timers.clearTimeout(fallbackTimer);
      pollingController?.abort();
      closeStream?.();
      storage?.removeItem(ACTIVE_JOB_KEY);
      if (state.transport.phase !== "protocol_error") {
        dispatch({ type: "transport/phase", phase: "online" });
      }
      view.focusResult();
    }
  }

  async function startPollingFallback(jobId, epoch) {
    if (pollingActive || !currentOperation(jobId, epoch)) return;
    pollingActive = true;
    pollingController?.abort();
    pollingController = new AbortController();
    dispatch({ type: "transport/phase", phase: "polling_fallback" });
    try {
      await api.pollJob(jobId, {
        signal: pollingController.signal,
        onEnvelope: (envelope) => acceptEnvelope(envelope, epoch),
        isTerminal: (envelope) => TERMINAL_STATUSES.has(envelope.status),
      });
    } catch (error) {
      if (
        currentOperation(jobId, epoch)
        && !["MONITOR_ABORTED", "REQUEST_ABORTED"].includes(error.code)
      ) {
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
          try {
            const envelope = await api.getJob(jobId, { signal: activeController?.signal });
            await acceptEnvelope(envelope, epoch);
          } catch (error) {
            if (currentOperation(jobId, epoch)) {
              dispatch({ type: "transport/offline", code: error.code || "NETWORK_ERROR" });
            }
          }
        } else if (["queued", "running"].includes(payload?.status)) {
          await acceptEnvelope({ ...payload, job_id: payload.job_id || jobId }, epoch);
        }
      },
      onTransport: (phase) => {
        if (!currentOperation(jobId, epoch)) return;
        if (TERMINAL_STATUSES.has(state.job.status)) return;
        if (phase === "protocol_error") {
          dispatch({ type: "transport/protocol_error", code: "SSE_PAYLOAD_INVALID" });
          return;
        }
        dispatch({ type: "transport/phase", phase });
        if (phase === "streaming") {
          timers.clearTimeout(fallbackTimer);
          pollingController?.abort();
        } else if (phase === "unavailable") {
          void startPollingFallback(jobId, epoch);
        } else if (phase === "reconnecting") {
          timers.clearTimeout(fallbackTimer);
          fallbackTimer = timers.setTimeout(
            () => void startPollingFallback(jobId, epoch),
            5000,
          );
        }
      },
    });
  }

  async function submitScenario(event) {
    event?.preventDefault?.();
    if (state.context.mode === "static_preview") {
      view.setFormError("Static preview không thể tạo job. Hãy mở /demo/ từ STWI runtime.");
      return;
    }

    operationEpoch += 1;
    const epoch = operationEpoch;
    clearMonitoring();
    activeController = new AbortController();
    const idempotencyKey = cryptoImpl?.randomUUID?.() || `stwi-${Date.now()}-${epoch}`;
    dispatch({ type: "creation/submitting", epoch, idempotencyKey });
    view.setFormError();

    try {
      const payload = { ...view.readScenario(), jurisdiction: activeJurisdiction };
      const accepted = await api.createJob(payload, {
        idempotencyKey,
        signal: activeController.signal,
      });
      if (epoch !== operationEpoch) return;
      const validated = validateAcceptedJob(accepted);
      if (!validated.ok) {
        dispatch({ type: "transport/protocol_error", code: validated.code });
        return;
      }
      if (validated.value.tenant_id !== state.context.tenantId) {
        dispatch({ type: "transport/protocol_error", code: "CREATE_TENANT_MISMATCH" });
        return;
      }

      dispatch({ type: "job/accepted", accepted: validated.value, epoch });
      persistActiveJob();
      view.focusLifecycle();
      monitorJob(accepted.job_id, epoch);
    } catch (error) {
      if (epoch !== operationEpoch || error.code === "REQUEST_ABORTED") return;
      dispatch({ type: "transport/offline", code: error.code || "NETWORK_ERROR" });
      view.setFormError(error.message || "Không thể tạo job.");
    }
  }

  async function resumeActiveJob() {
    const raw = storage?.getItem(ACTIVE_JOB_KEY);
    if (!raw || state.context.mode === "static_preview") return;
    let saved;
    try {
      saved = JSON.parse(raw);
    } catch {
      storage.removeItem(ACTIVE_JOB_KEY);
      return;
    }
    if (!saved.jobId || saved.tenantId !== state.context.tenantId) return;

    operationEpoch += 1;
    const epoch = operationEpoch;
    clearMonitoring();
    activeController = new AbortController();
    dispatch({ type: "job/resume_requested", jobId: saved.jobId, epoch });
    try {
      const envelope = await api.getJob(saved.jobId, { signal: activeController.signal });
      await acceptEnvelope(envelope, epoch);
      if (!TERMINAL_STATUSES.has(envelope.status)) monitorJob(saved.jobId, epoch);
    } catch (error) {
      if (currentOperation(saved.jobId, epoch)) {
        dispatch({ type: "transport/offline", code: error.code || "NETWORK_ERROR" });
      }
    }
  }

  function selectPreset(name) {
    if (name === "custom") {
      activeJurisdiction = "VN";
      return;
    }
    const preset = DEMO_PRESETS[name];
    if (!preset) return;
    activeJurisdiction = preset.jurisdiction;
    view.setScenario(preset);
  }

  function selectNode(nodeId) {
    view.setNode(nodeId);
    networkMap?.setSelection(nodeId);
  }

  function markCustomPreset() {
    activeJurisdiction = "VN";
    view.markCustomPreset?.();
  }

  async function copyTrace() {
    const traceId = state.job.result?.trace_id || state.job.result?.audit_record?.trace_id;
    if (!traceId) return;
    try {
      if (!navigatorImpl?.clipboard?.writeText) throw new Error("CLIPBOARD_UNAVAILABLE");
      await navigatorImpl.clipboard.writeText(traceId);
      view.setCopyStatus?.("Đã sao chép trace ID.");
    } catch {
      view.setCopyStatus?.(
        "Trình duyệt đã chặn clipboard. Hãy chọn trace ID và sao chép thủ công.",
      );
    }
  }

  function openDecision() {
    const policy = deriveDecisionPolicy(state);
    if (!policy.canApprove && !policy.canReject && !policy.canRequestChanges) return;
    view.openDecisionDialog({
      jobId: state.job.id,
      traceId: state.job.result?.trace_id || state.job.result?.audit_record?.trace_id || "—",
      operatorId: state.context.operatorId,
    }, policy);
  }

  async function reconcileDecision(jobId, epoch) {
    const envelope = await api.getJob(jobId, { signal: activeController?.signal });
    if (!currentOperation(jobId, epoch)) return null;
    if (!envelope.operator_decision) {
      const error = new Error("Không thể xác nhận quyết định từ trạng thái job.");
      error.code = "DECISION_RECONCILIATION_MISSING";
      throw error;
    }
    await acceptEnvelope(envelope, epoch);
    return envelope.operator_decision;
  }

  async function submitDecision(formData) {
    const decision = String(formData?.get?.("decision") || "");
    const rationale = String(formData?.get?.("rationale") || "").trim();
    const policy = deriveDecisionPolicy(state);
    const allowed = decision === "approved" ? policy.canApprove
      : decision === "rejected" ? policy.canReject
        : decision === "request_changes" ? policy.canRequestChanges
          : false;

    if (!allowed) {
      dispatch({ type: "decision/error", code: "DECISION_NOT_ALLOWED" });
      return;
    }
    if (!rationale) {
      dispatch({ type: "decision/error", code: "RATIONALE_REQUIRED" });
      return;
    }

    const jobId = state.job.id;
    const epoch = state.operationEpoch;
    const operatorId = state.context.operatorId;
    dispatch({ type: "decision/submitting" });
    try {
      const response = await api.recordDecision(jobId, {
        decision,
        operator_id: operatorId,
        comment: rationale,
      }, { signal: activeController?.signal });
      if (!currentOperation(jobId, epoch)) return;
      const record = response?.operator_decision;
      if (
        response?.job_id !== jobId
        || response?.automatic_actuation !== false
        || record?.applied_by_system !== false
        || record?.operator_id !== operatorId
        || record?.decision !== decision
      ) {
        dispatch({
          type: "transport/protocol_error",
          code: "AUTOMATIC_ACTUATION_FORBIDDEN",
        });
        return;
      }

      await reconcileDecision(jobId, epoch);
      if (!currentOperation(jobId, epoch)) return;
      dispatch({ type: "decision/recorded" });
      view.closeDecisionDialog();
    } catch (error) {
      if (!currentOperation(jobId, epoch) || error.code === "REQUEST_ABORTED") return;
      dispatch({
        type: error.httpStatus === 409 ? "decision/conflict" : "decision/error",
        code: error.code || "DECISION_FAILED",
      });
    }
  }

  async function bootstrap() {
    const context = await resolveContext();
    dispatch({ type: "context/resolved", context });
    view.setContext(context);
    if (mapFactory) {
      networkMap = mapFactory({ onSelectNode: selectNode });
      try {
        const topology = context.mode === "production"
          ? await api.getNetworkContext()
          : SYNTHETIC_NETWORK_CONTEXT;
        networkMap?.setTopology(topology);
        networkMap?.setSelection(context.nodeIds?.[0] || topology.nodes?.[0]?.node_id);
        view.setNetworkContext?.(topology, "ready");
      } catch {
        networkMap?.setTopology(null);
        view.setNetworkContext?.(null, "unavailable");
      }
    }
    if (context.mode === "demo") selectPreset("safe");
    await resumeActiveJob();
    return state;
  }

  view.setHandlers({
    submitScenario,
    selectPreset,
    selectNode,
    changeRatio: (ratio) => { view.setRatio(ratio); markCustomPreset(); },
    changeScenario: markCustomPreset,
    searchNodes: (query) => view.filterNodes(query),
    copyTrace,
    openDecision,
    submitDecision,
  });

  return {
    bootstrap,
    submitScenario,
    submitDecision,
    resumeActiveJob,
    getState: () => state,
    destroy: () => {
      clearMonitoring();
      networkMap?.destroy();
      networkMap = null;
    },
  };
}

if (typeof document !== "undefined") {
  const coordinator = createDashboardCoordinator({
    mapFactory: ({ onSelectNode }) => createDashboardMap(
      document.getElementById("network-map"),
      globalThis.L,
      {
        fallbackElement: document.getElementById("network-fallback"),
        onSelectNode,
      },
    ),
  });
  void coordinator.bootstrap();
}
