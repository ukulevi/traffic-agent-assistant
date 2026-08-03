const STATUS_LABELS = Object.freeze({
  queued: "Đang xếp hàng",
  running: "Đang chạy",
  succeeded: "Đã hoàn tất",
  needs_review: "Cần xem xét",
  failed: "Thất bại",
  expired: "Hết hạn",
});

const TRANSPORT_LABELS = Object.freeze({
  checking: "Đang kết nối",
  online: "Đã kết nối",
  streaming: "SSE trực tuyến",
  reconnecting: "Đang kết nối lại",
  polling_fallback: "Polling dự phòng",
  offline: "Mất kết nối",
  protocol_error: "Lỗi giao thức",
  unavailable: "SSE không khả dụng",
});

const RUNTIME_LABELS = Object.freeze({
  checking: "Đang kiểm tra runtime",
  production: "Production runtime",
  demo: "Demo synthetic",
  static_preview: "UI preview · chưa có API",
});

function text(node, value, fallback = "—") {
  node.textContent = value === null || value === undefined || value === ""
    ? fallback
    : String(value);
}

function metricsFrom(result) {
  return result?.scenario_summary
    || result?.forecast_summary
    || result?.scenario_metrics
    || {};
}

function readableReason(result, status) {
  if (status === "succeeded") return "Các safety gate đã cho phép chuyển kết quả sang operator phê duyệt.";
  if (status === "failed") return "Job thất bại và không có phương án để phê duyệt.";
  if (status === "expired") return "Job hết hạn; cần chạy lại trước khi đưa ra quyết định.";
  return result?.needs_review_reason
    || result?.review_reason
    || result?.audit_record?.status_reason
    || "Kết quả cần operator và reviewer kiểm tra thêm.";
}

function resultAction(result, status) {
  if (status === "succeeded") return result?.recommended_action || null;
  if (status === "needs_review") return result?.candidate_action || null;
  return null;
}

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
      heading.textContent = citation.title
        || citation.document_number
        || citation.source
        || "Citation";
      detail.textContent = [
        citation.provision || citation.article,
        citation.effective_from,
        citation.source_url || citation.source,
      ].filter(Boolean).join(" · ");
      item.append(heading, detail);
      list.append(item);
    }
  }

  function renderEvents(events = []) {
    const list = byId("events");
    list.replaceChildren();
    for (const event of events) {
      const item = doc.createElement("li");
      const label = event.payload?.status || event.payload?.event || event.payload?.type || "event";
      item.textContent = event.eventId ? `${event.eventId} · ${label}` : label;
      list.append(item);
    }
    text(byId("event-count"), `${events.length} sự kiện`, "0 sự kiện");
  }

  function renderInterpretation(result, status) {
    const interpretation = byId("result-interpretation");
    interpretation.className = `interpretation interpretation-${
      status === "succeeded" ? "success"
        : status === "needs_review" ? "review"
          : ["failed", "expired"].includes(status) ? "failed" : "idle"
    }`;
    text(
      byId("interpretation-title"),
      status === "succeeded" ? "Có thể chuyển sang operator phê duyệt"
        : status === "needs_review" ? "Kết quả cần xem xét thêm"
          : ["failed", "expired"].includes(status) ? "Không có đề xuất khả dụng"
            : "Chưa có kết quả để diễn giải",
    );
    text(byId("interpretation-summary"), result ? readableReason(result, status) : "Chọn một node và tạo kịch bản What-If.");
    text(
      byId("interpretation-impact"),
      result
        ? "Chỉ số là dữ liệu mô phỏng tổng hợp; không phải quan sát hay điều khiển hiện trường."
        : "Các chỉ số kỹ thuật và bằng chứng sẽ xuất hiện sau khi job hoàn tất.",
    );
    text(
      byId("interpretation-next-step"),
      status === "succeeded" ? "Đối chiếu evidence rồi ghi nhận quyết định."
        : status === "needs_review" ? "Kiểm tra uncertainty, OOD và citation trước khi yêu cầu chỉnh sửa."
          : ["failed", "expired"].includes(status) ? "Xem lỗi vận hành và chạy lại khi phù hợp."
            : "Hãy chạy một kịch bản mô phỏng.",
    );
  }

  function render(state, policy) {
    const status = state.job.status;
    const result = state.job.result;
    const metrics = metricsFrom(result);
    const traceId = result?.trace_id || result?.audit_record?.trace_id;
    const action = resultAction(result, status);

    text(byId("runtime-label"), RUNTIME_LABELS[state.context.mode] || state.context.mode);
    text(byId("connection-state"), TRANSPORT_LABELS[state.transport.phase] || state.transport.phase);
    text(byId("job-status"), STATUS_LABELS[status] || "Chưa gửi");
    byId("job-status").className = `status status-${status || "idle"}`;
    text(byId("job-id"), state.job.id);
    text(byId("trace-id"), traceId);
    text(byId("versions"), result ? `${result.model_version || "—"} / ${result.data_version || "—"}` : null);
    text(byId("terminal-status"), status);
    text(byId("result-timestamp"), result?.completed_at || result?.created_at);
    text(byId("forecast-volume"), metrics.traffic_volume_5m ?? metrics.avg_volume);
    text(byId("forecast-speed"), metrics.avg_speed_kmh ?? metrics.avg_speed);
    text(byId("vc-ratio"), metrics.max_vc_ratio ?? metrics.vc_ratio);
    text(byId("capacity-version"), metrics.capacity_version || result?.capacity_version);
    text(byId("review-reason"), readableReason(result, status));
    text(byId("evidence-status"), state.job.evidence?.phase || "pending");
    text(
      byId("evidence-message"),
      state.job.evidence?.phase === "valid"
        ? "Citation đã được runtime xác nhận hợp lệ."
        : state.job.evidence?.phase === "demo_provisional_valid"
          ? "Evidence demo đủ để trình diễn nhưng không phải xác nhận pháp lý production."
          : "Chưa có bằng chứng server-validated để cho phép recommendation production.",
    );
    text(byId("action-kind"), action ? `${status === "succeeded" ? "recommended_action" : "candidate_action"} · NON-EXECUTABLE` : "NON-EXECUTABLE");
    text(byId("action-view"), action ? JSON.stringify(action, null, 2) : null);
    text(byId("json-view"), result ? JSON.stringify(result, null, 2) : null);
    text(
      byId("decision-result"),
      state.job.decisionRecord
        ? `${state.job.decisionRecord.decision} · ${state.job.decisionRecord.operator_id || "operator"} · applied_by_system=false`
        : state.decision.error || "Đang chờ operator xem xét.",
    );
    byId("open-decision").disabled = !(policy.canApprove || policy.canReject || policy.canRequestChanges);
    byId("copy-trace").disabled = !traceId;
    byId("submit-button").disabled = state.context.mode === "static_preview"
      || state.creation.phase === "submitting";
    renderCitations(result?.citations || []);
    renderEvents(state.job.events || []);
    renderInterpretation(result, status);
    doc.documentElement.dataset.runtimeMode = state.context.mode;
  }

  function readScenario() {
    const nodeId = byId("node-id").value.trim();
    return {
      tenant_id: byId("tenant-id").value.trim(),
      scenario_time: new Date().toISOString(),
      candidate_action: {
        node_id: nodeId,
        green_time_ratio: Number(byId("green-time").value),
      },
      node_ids: [nodeId],
      scenario_query: byId("scenario-query").value.trim(),
      jurisdiction: "VN",
    };
  }

  function setContext(context) {
    byId("tenant-id").value = context.tenantId || "";
    byId("tenant-id").readOnly = true;
    const select = byId("node-id");
    const list = byId("node-list");
    select.replaceChildren();
    list.replaceChildren();
    for (const nodeId of context.nodeIds || []) {
      const option = doc.createElement("option");
      option.value = nodeId;
      option.textContent = nodeId;
      select.append(option);
      const button = doc.createElement("button");
      button.type = "button";
      button.textContent = nodeId;
      button.dataset.nodeId = nodeId;
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", "false");
      button.addEventListener("click", () => handlers.selectNode?.(nodeId));
      list.append(button);
    }
    byId("demo-preset").parentElement && (byId("demo-preset").parentElement.hidden = context.mode === "production");
  }

  function setScenario({ nodeId, ratio, query, expectation }) {
    byId("node-id").value = nodeId;
    byId("green-time").value = String(ratio);
    text(byId("green-value"), `${Number(ratio).toFixed(2)} · ${Math.round(Number(ratio) * 100)}%`);
    byId("scenario-query").value = query;
    text(byId("preset-expectation"), expectation);
  }

  function setNode(nodeId) {
    byId("node-id").value = nodeId;
    for (const button of byId("node-list").children) {
      button.setAttribute("aria-selected", String(button.dataset.nodeId === nodeId));
    }
  }

  function setRatio(ratio) {
    byId("green-time").value = String(ratio);
    text(byId("green-value"), `${Number(ratio).toFixed(2)} · ${Math.round(Number(ratio) * 100)}%`);
  }

  function filterNodes(query) {
    const normalized = String(query || "").trim().toLowerCase();
    for (const button of byId("node-list").children) {
      button.hidden = normalized.length > 0
        && !String(button.dataset.nodeId || "").toLowerCase().includes(normalized);
    }
  }

  function markCustomPreset() {
    byId("demo-preset").value = "custom";
    text(
      byId("preset-expectation"),
      "Kịch bản tùy chỉnh · kiểm tra dữ liệu, uncertainty, OOD và citation trước khi quyết định.",
    );
  }

  function openDecisionDialog(context, policy) {
    returnFocus = doc.activeElement;
    const radios = [...doc.querySelectorAll('input[name="decision"]')];
    for (const radio of radios) {
      radio.disabled = radio.value === "approved" ? !policy.canApprove
        : radio.value === "rejected" ? !policy.canReject
          : !policy.canRequestChanges;
      radio.checked = false;
    }
    rationale.value = "";
    text(byId("decision-error"), "", "");
    text(byId("decision-context"), `${context.jobId} · ${context.traceId} · ${context.operatorId}`);
    dialog.showModal();
    radios.find((radio) => !radio.disabled)?.focus();
  }

  function closeDecisionDialog() {
    dialog.close();
    returnFocus?.focus();
  }

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDecisionDialog();
  });
  byId("cancel-decision").addEventListener("click", closeDecisionDialog);
  byId("dialog-cancel").addEventListener("click", closeDecisionDialog);
  byId("open-decision").addEventListener("click", () => handlers.openDecision?.());
  byId("copy-trace").addEventListener("click", () => handlers.copyTrace?.());
  byId("decision-form").addEventListener("submit", (event) => {
    event.preventDefault();
    handlers.submitDecision?.(new FormData(event.currentTarget));
  });
  byId("scenario-form").addEventListener("submit", (event) => handlers.submitScenario?.(event));
  byId("demo-preset").addEventListener("change", (event) => handlers.selectPreset?.(event.currentTarget.value));
  byId("green-time").addEventListener("input", (event) => handlers.changeRatio?.(Number(event.currentTarget.value)));
  byId("node-id").addEventListener("change", (event) => handlers.selectNode?.(event.currentTarget.value));
  byId("scenario-query").addEventListener("input", () => handlers.changeScenario?.());
  byId("node-search").addEventListener("input", (event) => handlers.searchNodes?.(event.currentTarget.value));
  doc.addEventListener("keydown", (event) => {
    const editableTags = new Set(["INPUT", "TEXTAREA", "SELECT"]);
    const targetIsEditable = editableTags.has(event.target?.tagName)
      || event.target?.isContentEditable === true;
    if (
      event.key === "/"
      && !targetIsEditable
      && !event.altKey
      && !event.ctrlKey
      && !event.metaKey
    ) {
      event.preventDefault();
      byId("node-search").focus();
    } else if (
      String(event.key || "").toLowerCase() === "c"
      && !targetIsEditable
      && !event.altKey
      && !event.ctrlKey
      && !event.metaKey
      && !event.repeat
      && !byId("copy-trace").disabled
    ) {
      event.preventDefault();
      handlers.copyTrace?.();
    }
  });

  return {
    render,
    readScenario,
    setContext,
    setScenario,
    setNode,
    setRatio,
    filterNodes,
    markCustomPreset,
    openDecisionDialog,
    closeDecisionDialog,
    setFormError: (message = "") => text(byId("form-error"), message, ""),
    setCopyStatus: (message = "") => text(byId("copy-status"), message, ""),
    focusLifecycle: () => byId("lifecycle-title").focus(),
    focusResult: () => byId("result-conclusion").focus(),
    setHandlers: (next) => { handlers = { ...handlers, ...next }; },
  };
}
