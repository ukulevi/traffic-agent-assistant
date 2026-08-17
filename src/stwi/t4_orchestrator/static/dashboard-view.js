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

const RESULT_PRESENTATION = Object.freeze({
  idle: { title: "Chưa có kết quả mô phỏng", safety: "Chờ kết quả", icon: "○" },
  queued: { title: "Kịch bản đang chờ xử lý", safety: "Đang chờ safety checks", icon: "◌" },
  running: { title: "Đang chạy mô phỏng", safety: "Đang đánh giá safety", icon: "◌" },
  succeeded: { title: "Kết quả mô phỏng đã sẵn sàng", safety: "Đã qua safety gate", icon: "✓" },
  needs_review: { title: "Kết quả cần operator xem xét", safety: "Cần xem xét", icon: "!" },
  failed: { title: "Mô phỏng thất bại", safety: "Không có đề xuất khả dụng", icon: "×" },
  expired: { title: "Kết quả đã hết hạn", safety: "Cần chạy lại", icon: "↻" },
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
  let authorizedNodeIds = [];
  let trustedCapacityVersion = null;
  let citationsExpanded = false;
  let citationJobId = null;
  let lastRenderedCitations = [];

  function renderCitations(citations = []) {
    const list = byId("citations");
    const summary = byId("citation-summary");
    const toggle = byId("toggle-citations");
    lastRenderedCitations = citations;
    const visibleCitations = citationsExpanded ? citations : citations.slice(0, 3);
    list.replaceChildren();
    for (const citation of visibleCitations) {
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
    const hasHiddenCitations = citations.length > 3;
    toggle.hidden = !hasHiddenCitations;
    toggle.setAttribute("aria-expanded", String(citationsExpanded));
    toggle.textContent = citationsExpanded ? "Thu gọn" : `Xem tất cả (${citations.length})`;
    text(
      summary,
      citations.length ? `Đang hiển thị ${visibleCitations.length}/${citations.length} citation` : "Không có citation",
    );
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

  function renderSafetyChecks(checks = [], iterations = 0) {
    const list = byId("safety-checks");
    list.replaceChildren();
    text(byId("safety-iterations"), `${iterations} / 3 vòng`, "0 / 3 vòng");
    for (const check of checks) {
      const term = doc.createElement("dt");
      const detail = doc.createElement("dd");
      term.textContent = `Vòng ${check.iteration} · ${check.passed ? "PASS" : "REVIEW"}`;
      detail.textContent = [
        check.max_vc_ratio == null ? null : `V/C ${check.max_vc_ratio}`,
        check.vc_threshold == null ? null : `policy ${check.vc_threshold}`,
        check.fail_reason,
      ].filter(Boolean).join(" · ");
      list.append(term, detail);
    }
  }

  function renderRoutes(routeViewModel = {}) {
    const routes = Array.isArray(routeViewModel.routes) ? routeViewModel.routes : [];
    text(byId("route-heading"), routeViewModel.routeHeading || "Hành lang điều hướng");
    const rows = byId("route-rows");
    rows.replaceChildren();
    for (const route of routes) {
      const row = doc.createElement("tr");
      row.className = `route-row route-row-${route.kind}`;
      row.dataset.routeId = route.routeId;

      const verdict = doc.createElement("td");
      verdict.textContent = `${route.rank ? `#${route.rank}` : "Candidate"} · ${route.statusLabel}`;
      verdict.dataset.status = route.kind;

      const path = doc.createElement("td");
      path.textContent = `${route.routeId} · ${route.nodeSequence.join(" → ")}`;

      const metrics = doc.createElement("td");
      metrics.textContent = [
        `V/C ${route.maxVcRatio}`,
        `Tốc độ ${route.avgSpeedKmh} km/h`,
        `Trễ ${route.delayProxySeconds} giây`,
        `Uncertainty ${route.uncertaintyScore}`,
        `OOD ${route.oodScore}`,
        route.reviewReasons.length ? `Lý do: ${route.reviewReasons.join(", ")}` : null,
      ].filter(Boolean).join(" · ");

      const provenance = doc.createElement("td");
      provenance.textContent = [
        `model ${route.provenance.modelVersion}`,
        `data ${route.provenance.dataVersion}`,
        `topology ${route.provenance.topologyVersion}`,
      ].join(" · ");

      row.append(verdict, path, metrics, provenance);
      rows.append(row);
    }
    byId("route-empty").hidden = routes.length > 0;
    byId("route-table").hidden = routes.length === 0;
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

  function render(state, policy, routeViewModel = {}) {
    const status = state.job.status;
    const result = state.job.result;
    const metrics = metricsFrom(result);
    const traceId = result?.trace_id || result?.audit_record?.trace_id;
    const action = resultAction(result, status);
    const presentation = RESULT_PRESENTATION[status] || RESULT_PRESENTATION.idle;
    if (state.job.id !== citationJobId) {
      citationJobId = state.job.id;
      citationsExpanded = false;
    }

    text(byId("runtime-label"), RUNTIME_LABELS[state.context.mode] || state.context.mode);
    text(byId("connection-state"), TRANSPORT_LABELS[state.transport.phase] || state.transport.phase);
    text(byId("job-status"), STATUS_LABELS[status] || "Chưa gửi");
    byId("job-status").className = `status status-${status || "idle"}`;
    text(byId("result-title"), presentation.title);
    text(byId("safety-label"), presentation.safety);
    text(byId("safety-icon"), presentation.icon);
    byId("safety-state").className = `safety-state safety-${status || "idle"}`;
    text(byId("job-id"), state.job.id);
    text(byId("trace-id"), traceId);
    text(byId("versions"), result ? `${result.model_version || "—"} / ${result.data_version || "—"}` : null);
    text(byId("terminal-status"), status);
    text(byId("result-timestamp"), result?.completed_at || result?.created_at);
    text(byId("forecast-volume"), metrics.traffic_volume_5m ?? metrics.avg_volume);
    text(byId("forecast-speed"), metrics.avg_speed_kmh ?? metrics.avg_speed);
    text(byId("vc-ratio"), metrics.max_vc_ratio ?? metrics.vc_ratio);
    text(
      byId("capacity-version"),
      metrics.capacity_version || result?.capacity_version || trustedCapacityVersion,
    );
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
    renderSafetyChecks(result?.safety_checks || [], result?.safety_iterations || 0);
    renderRoutes(routeViewModel);
    renderInterpretation(result, status);
    doc.documentElement.dataset.runtimeMode = state.context.mode;
  }

  function readScenario() {
    const nodeId = byId("node-id").value.trim();
    const eventType = byId("event-type").value;
    let incident = null;
    if (eventType) {
      incident = {
        event_type: eventType,
        affected_node_ids: [nodeId],
        severity: byId("incident-severity").value,
        duration_minutes: Number(byId("incident-duration").value),
        description: byId("scenario-query").value.trim(),
      };
      if (eventType === "lane_closure") {
        incident.lane_closure_ratio = Number(byId("lane-closure-ratio").value);
      } else if (eventType === "demand_surge") {
        incident.demand_multiplier = Number(byId("demand-multiplier").value);
      } else if (eventType === "signal_change") {
        incident.signal_plan_delta = {
          green_time_ratio_delta: Number(byId("signal-plan-delta").value),
        };
      }
    }
    return {
      tenant_id: byId("tenant-id").value.trim(),
      scenario_time: new Date().toISOString(),
      candidate_action: {
        node_id: nodeId,
        green_time_ratio: Number(byId("green-time").value),
      },
      node_ids: authorizedNodeIds.length > 0 ? [...authorizedNodeIds] : [nodeId],
      incident,
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
    list.setAttribute("role", "group");
    list.setAttribute("aria-label", "Danh sách node");
    authorizedNodeIds = [...(context.nodeIds || [])];
    for (const nodeId of context.nodeIds || []) {
      const option = doc.createElement("option");
      option.value = nodeId;
      option.textContent = nodeId;
      select.append(option);
      const button = doc.createElement("button");
      button.type = "button";
      button.textContent = nodeId;
      button.dataset.nodeId = nodeId;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => handlers.selectNode?.(nodeId));
      list.append(button);
    }
    byId("demo-preset").parentElement && (byId("demo-preset").parentElement.hidden = context.mode === "production");
  }

  function syncIncidentFields(eventType = byId("event-type").value) {
    byId("lane-closure-field").hidden = eventType !== "lane_closure";
    byId("demand-multiplier-field").hidden = eventType !== "demand_surge";
    byId("signal-delta-field").hidden = eventType !== "signal_change";
  }

  function setScenario({
    eventType = "",
    severity = "medium",
    durationMinutes = 30,
    laneClosureRatio = 0.5,
    demandMultiplier = 1.5,
    signalPlanDelta = 0.1,
    ratio,
    query,
    expectation,
  }) {
    byId("event-type").value = eventType;
    byId("incident-severity").value = severity;
    byId("incident-duration").value = String(durationMinutes);
    byId("lane-closure-ratio").value = String(laneClosureRatio);
    byId("demand-multiplier").value = String(demandMultiplier);
    byId("signal-plan-delta").value = String(signalPlanDelta);
    syncIncidentFields(eventType);
    byId("green-time").value = String(ratio);
    text(byId("green-value"), `${Number(ratio).toFixed(2)} · ${Math.round(Number(ratio) * 100)}%`);
    byId("scenario-query").value = query;
    text(byId("preset-expectation"), expectation);
  }

  function setNode(nodeId) {
    byId("node-id").value = nodeId;
    for (const button of byId("node-list").children) {
      const selected = button.dataset.nodeId === nodeId;
      button.setAttribute("aria-pressed", String(selected));
      if (selected) {
        button.setAttribute("aria-current", "true");
      } else {
        button.removeAttribute("aria-current");
      }
    }
  }

  function setNetworkContext(context, status = "ready") {
    trustedCapacityVersion = status === "ready" ? context?.capacity_version || null : null;
    const version = context?.network_version || "không khả dụng";
    text(byId("network-version"), version);
    text(
      byId("network-status"),
      status === "ready"
        ? `${context?.nodes?.length || 0} nút được hiển thị · ${context?.synthetic === true ? "synthetic" : "authorized context"}.`
        : "Không tải được topology đã xác thực; bảng và bản đồ không được suy diễn từ dữ liệu production.",
    );
  }

  function renderNetworkImpact(impactViewModel = {}) {
    const horizonSelect = byId("impact-horizon-select");
    const table = byId("impact-table");
    const empty = byId("impact-empty");
    const rowsElement = byId("impact-rows");

    const available = impactViewModel && impactViewModel.available === true && Array.isArray(impactViewModel.rows) && impactViewModel.rows.length > 0;

    if (!available) {
      if (horizonSelect) horizonSelect.replaceChildren();
      if (rowsElement) rowsElement.replaceChildren();
      if (table) table.hidden = true;
      if (empty) empty.hidden = false;
      return;
    }

    const horizons = Array.isArray(impactViewModel.horizons) ? impactViewModel.horizons : [];
    horizonSelect.replaceChildren();
    for (const h of horizons) {
      const option = doc.createElement("option");
      option.value = String(h);
      option.textContent = `${h} phút`;
      if (h === impactViewModel.selectedHorizon) {
        option.selected = true;
      }
      horizonSelect.append(option);
    }
    horizonSelect.value = String(impactViewModel.selectedHorizon);

    const roleLabels = {
      incident: "Nút sự cố",
      adjacent: "Nút lân cận",
      network: "Nút mạng lưới",
    };

    rowsElement.replaceChildren();
    for (const rowData of impactViewModel.rows) {
      const tr = doc.createElement("tr");
      tr.className = `impact-row impact-row-${rowData.impactRole}`;
      tr.dataset.nodeId = rowData.nodeId;

      const tdNode = doc.createElement("td");
      tdNode.textContent = rowData.nodeId;

      const tdHorizon = doc.createElement("td");
      tdHorizon.textContent = `${rowData.horizonMinutes}p`;

      const tdRole = doc.createElement("td");
      tdRole.textContent = roleLabels[rowData.impactRole] || rowData.impactRole;

      const tdVolume = doc.createElement("td");
      tdVolume.textContent = `${rowData.trafficVolume5m}`;

      const tdSpeed = doc.createElement("td");
      tdSpeed.textContent = `${rowData.avgSpeedKmh}`;

      const tdVc = doc.createElement("td");
      tdVc.textContent = typeof rowData.vcRatio === "number" ? rowData.vcRatio.toFixed(2) : String(rowData.vcRatio);

      const tdUnc = doc.createElement("td");
      tdUnc.textContent = typeof rowData.uncertaintyScore === "number" ? rowData.uncertaintyScore.toFixed(2) : String(rowData.uncertaintyScore);

      const tdOod = doc.createElement("td");
      tdOod.textContent = typeof rowData.oodScore === "number" ? rowData.oodScore.toFixed(2) : String(rowData.oodScore);

      tr.append(tdNode, tdHorizon, tdRole, tdVolume, tdSpeed, tdVc, tdUnc, tdOod);
      rowsElement.append(tr);
    }

    table.hidden = false;
    empty.hidden = true;
  }

  byId("impact-horizon-select")?.addEventListener("change", (event) => {
    const val = (event.currentTarget || event.target)?.value;
    if (val !== undefined) {
      handlers.selectHorizon?.(Number(val));
    }
  });

  byId("toggle-citations").addEventListener("click", () => {
    citationsExpanded = !citationsExpanded;
    renderCitations(lastRenderedCitations);
  });

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
  byId("event-type").addEventListener("change", (event) => {
    syncIncidentFields(event.currentTarget.value);
    handlers.changeScenario?.();
  });
  byId("incident-severity").addEventListener("change", () => handlers.changeScenario?.());
  for (const fieldId of [
    "incident-duration",
    "lane-closure-ratio",
    "demand-multiplier",
    "signal-plan-delta",
  ]) {
    byId(fieldId).addEventListener("input", () => handlers.changeScenario?.());
  }
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
    renderNetworkImpact,
    readScenario,
    setContext,
    setScenario,
    setNode,
    setNetworkContext,
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
