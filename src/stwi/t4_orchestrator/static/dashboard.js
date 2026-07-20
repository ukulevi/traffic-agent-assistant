const form = document.querySelector("#scenario-form");
const statusNode = document.querySelector("#job-status");
const errorNode = document.querySelector("#form-error");
const eventsNode = document.querySelector("#events");
const eventCountNode = document.querySelector("#event-count");
const emptyEventsNode = document.querySelector("#empty-events");
const approveButton = document.querySelector("#approve");
const rejectButton = document.querySelector("#reject");
const submitButton = document.querySelector("#submit-button");
const greenTime = document.querySelector("#green-time");
const greenValue = document.querySelector("#green-value");
const demoPreset = document.querySelector("#demo-preset");
const nodeInput = document.querySelector("#node-id");
const scenarioQuery = document.querySelector("#scenario-query");
const presetExpectation = document.querySelector("#preset-expectation");
const safetyState = document.querySelector("#safety-state");
const safetyReason = document.querySelector("#review-reason");
const interpretationState = document.querySelector("#result-interpretation");
const interpretationTitle = document.querySelector("#interpretation-title");
const interpretationSummary = document.querySelector("#interpretation-summary");
const interpretationImpact = document.querySelector("#interpretation-impact");
const interpretationNextStep = document.querySelector("#interpretation-next-step");
const actionView = document.querySelector("#action-view");
const decisionResult = document.querySelector("#decision-result");
const runtimeState = document.querySelector("#runtime-state");
const runtimeLabel = document.querySelector("#runtime-label");

const TERMINAL_STATUSES = new Set(["succeeded", "needs_review", "failed", "expired"]);
const STATUS_LABELS = {
  idle: "Chưa gửi",
  queued: "Đang xếp hàng",
  running: "Đang mô phỏng",
  succeeded: "Đã hoàn tất",
  needs_review: "Cần operator review",
  failed: "Thất bại",
  expired: "Hết thời gian",
};
const EVENT_LABELS = {
  queued: "Job đã được tiếp nhận",
  running: "Đang chạy các bước phân tích",
  succeeded: "Đã tạo kết quả an toàn",
  needs_review: "Chuyển sang operator review",
  failed: "Job kết thúc với lỗi an toàn",
  expired: "Job vượt hard deadline",
  result: "Đã nhận kết quả terminal",
  operator_decision: "Đã ghi quyết định operator",
  error: "Luồng sự kiện báo lỗi",
  timeline_unavailable: "Không thể tải timeline; kết quả job vẫn được giữ nguyên",
};
let activeJobId = null;
let activeStatus = "idle";
let runtimeAvailable = null;
let activeJurisdiction = "VN";

const DEMO_PRESETS = {
  safe: {
    nodeId: "node_00", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá quyền và nghĩa vụ người sử dụng đường tại node_00.",
    expectation: "Kỳ vọng: kết quả synthetic đạt các kiểm tra của profile mô phỏng.",
  },
  "unsafe-vc": {
    nodeId: "node_01", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá quyền và nghĩa vụ người sử dụng đường khi nhu cầu vượt năng lực tại node_01.",
    expectation: "Kỳ vọng: V/C vượt policy 0.90 và job chuyển needs_review.",
  },
  ood: {
    nodeId: "node_02", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá tình huống khác đáng kể dữ liệu kiểm tra tại node_02.",
    expectation: "Kỳ vọng: OOD gate fail-closed và chỉ trả candidate_action.",
  },
  uncertainty: {
    nodeId: "node_03", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá tình huống có độ bất định cao tại node_03.",
    expectation: "Kỳ vọng: uncertainty gate fail-closed và cần operator review.",
  },
  "missing-evidence": {
    nodeId: "node_04", ratio: 0.70, jurisdiction: "DEMO-NONE",
    query: "Tình huống synthetic không có căn cứ trong corpus được phép.",
    expectation: "Kỳ vọng: thiếu citation hợp lệ nên job dừng ở needs_review.",
  },
  extreme: {
    nodeId: "node_00", ratio: 0.00, jurisdiction: "VN",
    query: "Đánh giá giả định không có pha xanh tại node_00.",
    expectation: "Kỳ vọng: giá trị cực trị bị safety gate giữ lại để review.",
  },
};

function setText(selector, value, fallback = "—") {
  const node = document.querySelector(selector);
  if (node) node.textContent = value || fallback;
}

function statusClass(status) {
  return String(status || "idle").toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function setStatus(status) {
  activeStatus = status || "idle";
  statusNode.textContent = STATUS_LABELS[activeStatus] || activeStatus;
  statusNode.className = `status status-${statusClass(activeStatus)}`;
}

function addEvent(label) {
  const item = document.createElement("li");
  item.textContent = EVENT_LABELS[label] || label || "Đã nhận event";
  eventsNode.append(item);
  const count = eventsNode.children.length;
  eventCountNode.textContent = `${count} sự kiện`;
  emptyEventsNode.hidden = count > 0;
}

function resetEvents() {
  eventsNode.replaceChildren();
  eventCountNode.textContent = "0 sự kiện";
  emptyEventsNode.hidden = false;
}

function setError(message = "") {
  errorNode.textContent = message;
}

function setBusy(isBusy) {
  submitButton.disabled = isBusy || runtimeAvailable === false;
  submitButton.querySelector("span").textContent = isBusy ? "Đang xử lý…" : "Chạy mô phỏng";
  form.setAttribute("aria-busy", String(isBusy));
}

async function checkRuntimeAvailability() {
  try {
    const response = await fetch("/openapi.json", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("API discovery failed");
    runtimeAvailable = true;
    runtimeState.classList.remove("runtime-offline");
    runtimeLabel.textContent = "Runtime demo sẵn sàng";
    setError();
  } catch {
    runtimeAvailable = false;
    runtimeState.classList.add("runtime-offline");
    runtimeLabel.textContent = "UI preview · chưa có API";
    setError("Static preview chỉ hiển thị giao diện. Hãy chạy STWI FastAPI runtime và mở /demo/ trên cùng cổng.");
  }
  setBusy(false);
}

async function createJobError(response) {
  if ([404, 405, 501].includes(response.status)) {
    return `Runtime API chưa sẵn sàng (HTTP ${response.status}). Không thể tạo job từ static preview.`;
  }
  if (response.status === 401 || response.status === 403) {
    return "Runtime từ chối principal/tenant demo. Kiểm tra auth boundary trước khi thử lại.";
  }
  if (response.status === 422) {
    return "Dữ liệu kịch bản chưa hợp lệ. Kiểm tra tenant, node và mô tả tình huống.";
  }
  return `Không thể tạo job (HTTP ${response.status}). Kiểm tra runtime demo.`;
}

function setDecisionEnabled(enabled, status = activeStatus) {
  approveButton.disabled = !enabled || status !== "succeeded";
  rejectButton.disabled = !enabled;
}

function markCustomPreset() {
  demoPreset.value = "custom";
  activeJurisdiction = "VN";
  presetExpectation.textContent = "Tùy chỉnh: kết quả phụ thuộc input nhưng vẫn bị ràng buộc bởi safety gate.";
}

function applyPreset(presetName) {
  const preset = DEMO_PRESETS[presetName];
  if (!preset) {
    markCustomPreset();
    return;
  }
  nodeInput.value = preset.nodeId;
  greenTime.value = String(preset.ratio);
  scenarioQuery.value = preset.query;
  activeJurisdiction = preset.jurisdiction;
  presetExpectation.textContent = preset.expectation;
  greenValue.textContent = `${preset.ratio.toFixed(2)} · ${Math.round(preset.ratio * 100)}%`;
}

function actionFor(result) {
  if (!result) return null;
  return result.status === "needs_review" ? result.candidate_action : result.recommended_action;
}

function readableReviewReason(reason) {
  const normalized = String(reason || "").toLowerCase();
  if (normalized.includes("out_of_distribution") || normalized.includes("ood")) {
    return "Tình huống này khác đáng kể so với dữ liệu mà mô hình đã được kiểm tra, nên kết quả chưa đủ tin cậy.";
  }
  if (normalized.includes("uncertainty")) {
    return "Mức độ không chắc chắn đang cao, nên hệ thống chưa thể coi phương án là một khuyến nghị an toàn.";
  }
  if (normalized.includes("legal") || normalized.includes("citation")) {
    return "Hệ thống chưa tìm thấy đủ căn cứ pháp lý hoặc SOP hợp lệ để hỗ trợ phương án.";
  }
  if (normalized.includes("vc_ratio") || normalized.includes("vc threshold")) {
    return "Mức sử dụng năng lực giao thông dự kiến vượt ngưỡng policy của demo, nên phương án bị giữ lại để xem xét.";
  }
  if (normalized.includes("timeout")) {
    return "Quá trình phân tích không hoàn thành trong thời hạn cho phép, nên hệ thống không đưa ra khuyến nghị.";
  }
  return "Một hoặc nhiều kiểm tra an toàn chưa đạt; hệ thống chủ động dừng để operator xem xét thêm.";
}

function metricText(result) {
  const baseline = result?.baseline_summary || {};
  const scenario = result?.scenario_summary || {};
  const baselineVolume = Number(baseline.avg_volume);
  const scenarioVolume = Number(scenario.avg_volume);
  const baselineSpeed = Number(baseline.avg_speed);
  const scenarioSpeed = Number(scenario.avg_speed);
  const vcRatio = Number(scenario.max_vc_ratio);
  const checks = Array.isArray(result?.safety_checks) ? result.safety_checks : [];
  const vcThreshold = Number(checks.find((check) => Number.isFinite(Number(check?.vc_threshold)))?.vc_threshold);
  const parts = [];
  if (Number.isFinite(baselineVolume) && Number.isFinite(scenarioVolume)) {
    parts.push(`lưu lượng trung bình ${baselineVolume.toFixed(1)} → ${scenarioVolume.toFixed(1)} xe/5 phút`);
  }
  if (Number.isFinite(baselineSpeed) && Number.isFinite(scenarioSpeed)) {
    parts.push(`tốc độ trung bình ${baselineSpeed.toFixed(1)} → ${scenarioSpeed.toFixed(1)} km/h`);
  }
  if (Number.isFinite(vcRatio)) {
    const thresholdText = Number.isFinite(vcThreshold) ? `, ngưỡng policy ${vcThreshold.toFixed(2)}` : "";
    parts.push(`V/C cao nhất ${vcRatio.toFixed(2)}${thresholdText}`);
  }
  return parts.length
    ? `Ước tính từ dữ liệu mô phỏng: ${parts.join("; ")}.`
    : "API chưa trả đủ số liệu tổng hợp để so sánh tác động; hãy xem model/data version và audit record trước khi kết luận.";
}

function setInterpretation(result, status) {
  interpretationState.className = "interpretation";
  const action = actionFor(result) || {};
  const nodeId = String(action.node_id || "nút giao đã chọn");
  const ratio = Number(action.green_time_ratio);
  const ratioText = Number.isFinite(ratio) ? `${Math.round(ratio * 100)}% chu kỳ xanh` : "phương án đã nhập";

  if (status === "succeeded") {
    interpretationState.classList.add("interpretation-success");
    interpretationTitle.textContent = "Phương án đạt kiểm tra trong profile mô phỏng";
    interpretationSummary.textContent = `Theo dữ liệu mô phỏng, phương án ${ratioText} tại ${nodeId} đủ điều kiện để operator xem xét. Đây chưa phải bằng chứng về hiệu quả ngoài thực địa.`;
    interpretationImpact.textContent = metricText(result);
    interpretationNextStep.textContent = "Đọc các số liệu, kiểm tra nguồn model/data, rồi phê duyệt hoặc từ chối để ghi audit. Không có lệnh nào được gửi đến đèn tín hiệu.";
  } else if (status === "needs_review") {
    interpretationState.classList.add("interpretation-review");
    interpretationTitle.textContent = "Chưa đủ điều kiện để đưa ra khuyến nghị";
    interpretationSummary.textContent = `${readableReviewReason(result?.needs_review_reason)} Phương án ${ratioText} tại ${nodeId} chỉ được giữ dưới dạng candidate_action.`;
    interpretationImpact.textContent = metricText(result);
    interpretationNextStep.textContent = "Không phê duyệt như một khuyến nghị. Operator cần kiểm tra thêm dữ liệu, căn cứ hoặc điều chỉnh kịch bản trước khi chạy lại.";
  } else if (status === "failed" || status === "expired") {
    interpretationState.classList.add("interpretation-failed");
    interpretationTitle.textContent = status === "expired" ? "Phân tích đã hết thời gian" : "Không tạo được kết quả an toàn";
    interpretationSummary.textContent = status === "expired"
      ? "Job không hoàn thành trong thời hạn cho phép. Hệ thống đã dừng và không tạo action."
      : "Job gặp lỗi và hệ thống đã fail-closed. Không có phương án nào được đề xuất hoặc thực thi.";
    interpretationImpact.textContent = "Không nên suy luận tác động giao thông từ lượt chạy này.";
    interpretationNextStep.textContent = "Kiểm tra lỗi runtime/audit, sửa nguyên nhân rồi tạo một job mới.";
  } else {
    interpretationState.classList.add("interpretation-idle");
    interpretationTitle.textContent = "Chưa có kết quả để diễn giải";
    interpretationSummary.textContent = "Sau khi mô phỏng hoàn tất, khu vực này sẽ giải thích kết quả bằng ngôn ngữ thông thường.";
    interpretationImpact.textContent = "Các thông số kỹ thuật vẫn được giữ phía dưới để phục vụ kiểm tra và audit.";
    interpretationNextStep.textContent = "Hãy chạy một kịch bản What-If.";
  }
}

function setSafety(result, status) {
  safetyState.className = "safety-state";
  const stateIcon = safetyState.querySelector(".state-icon");
  const stateTitle = safetyState.querySelector("strong");
  if (status === "succeeded") {
    safetyState.classList.add("safety-success");
    stateIcon.textContent = "✓";
    stateTitle.textContent = "Đạt kiểm tra trong profile mô phỏng";
    safetyReason.textContent = "Đây là kết quả synthetic; operator vẫn phải xem model/data version trước khi quyết định.";
  } else if (status === "needs_review") {
    safetyState.classList.add("safety-review");
    stateIcon.textContent = "!";
    stateTitle.textContent = "Cần operator review";
    safetyReason.textContent = result?.needs_review_reason || "Safety loop chưa đủ bằng chứng để đưa ra recommendation.";
  } else if (status === "failed" || status === "expired") {
    safetyState.classList.add("safety-failed");
    stateIcon.textContent = "×";
    stateTitle.textContent = status === "expired" ? "Job đã hết thời gian" : "Không tạo được kết quả";
    safetyReason.textContent = "Hệ thống fail-closed; không có action nào được đưa ra.";
  } else {
    safetyState.classList.add("safety-idle");
    stateIcon.textContent = "○";
    stateTitle.textContent = "Đang chờ kết quả";
    safetyReason.textContent = "Safety checks sẽ xuất hiện sau khi job hoàn tất.";
  }
  setInterpretation(result, status);
  const action = actionFor(result);
  actionView.textContent = action ? JSON.stringify(action, null, 2) : "Không có action được trả về.";
}

async function loadEvents(jobId) {
  try {
    const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/events`);
    if (!response.ok) {
      addEvent("timeline_unavailable");
      return;
    }
    const body = await response.text();
    for (const block of body.split(/\r?\n\r?\n/)) {
      let eventName = "";
      let eventData = null;
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event: ")) eventName = line.slice(7).trim();
        if (line.startsWith("data: ")) {
          try {
            eventData = JSON.parse(line.slice(6));
          } catch {
            eventData = null;
          }
        }
      }
      const label = eventData?.status || eventData?.event || eventName;
      if (label) addEvent(label);
    }
  } catch {
    addEvent("timeline_unavailable");
  }
}

async function fetchTerminalJob(jobId) {
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) throw new Error("Không thể đọc trạng thái job.");
    const job = await response.json();
    setStatus(job.status);
    if (TERMINAL_STATUSES.has(job.status)) return job;
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
  throw new Error("Job chưa trả về trong thời gian cho phép.");
}

async function submitScenario(event) {
  event.preventDefault();
  if (runtimeAvailable === false) {
    setError("Không thể tạo job: tab này là static preview và chưa kết nối STWI API.");
    return;
  }
  activeJobId = null;
  setError();
  resetEvents();
  setDecisionEnabled(false);
  setBusy(true);
  setStatus("queued");
  setSafety(null, "idle");
  setText("#job-id", "");
  setText("#trace-id", "", "Chưa có trace");
  setText("#versions", "");
  decisionResult.className = "decision-result";
  decisionResult.textContent = "Đang chờ operator xem xét.";

  const nodeId = nodeInput.value.trim();
  const payload = {
    tenant_id: document.querySelector("#tenant-id").value.trim(),
    scenario_time: new Date().toISOString(),
    candidate_action: { node_id: nodeId, green_time_ratio: Number(greenTime.value) },
    node_ids: [nodeId],
    scenario_query: scenarioQuery.value.trim(),
    jurisdiction: activeJurisdiction,
  };

  try {
    const response = await fetch("/api/v1/what-if-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await createJobError(response));
    const accepted = await response.json();
    activeJobId = accepted.job_id;
    setText("#job-id", activeJobId);
    const job = await fetchTerminalJob(activeJobId);
    const result = job.result || null;
    setText("#trace-id", result?.audit_record?.trace_id, "Không có trace");
    setText("#versions", result ? `${result.model_version} / ${result.data_version}` : "—");
    setSafety(result, job.status);
    await loadEvents(activeJobId);
    if (eventsNode.children.length === 0) addEvent(job.status);
    setDecisionEnabled(true, job.status);
  } catch (error) {
    setStatus("failed");
    setSafety(null, "failed");
    setError(error instanceof Error ? error.message : "Không thể hoàn thành job.");
  } finally {
    setBusy(false);
  }
}

async function decide(decision) {
  if (!activeJobId || !TERMINAL_STATUSES.has(activeStatus)) return;
  approveButton.disabled = true;
  rejectButton.disabled = true;
  try {
    const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(activeJobId)}/operator-decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator_id: "demo-operator", decision, comment: "Recorded from the demo dashboard." }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error("Không thể ghi quyết định operator.");
    decisionResult.className = "decision-result success";
    decisionResult.textContent = `Đã ghi quyết định ${body.operator_decision.decision}; không có hành động tự động.`;
  } catch (error) {
    decisionResult.className = "decision-result";
    decisionResult.textContent = error instanceof Error ? error.message : "Không thể ghi quyết định.";
    setDecisionEnabled(true);
  }
}

greenTime.addEventListener("input", () => {
  const ratio = Number(greenTime.value);
  greenValue.textContent = `${ratio.toFixed(2)} · ${Math.round(ratio * 100)}%`;
  markCustomPreset();
});
demoPreset.addEventListener("change", () => applyPreset(demoPreset.value));
nodeInput.addEventListener("change", markCustomPreset);
scenarioQuery.addEventListener("input", markCustomPreset);
checkRuntimeAvailability();
form.addEventListener("submit", submitScenario);
approveButton.addEventListener("click", () => decide("approved"));
rejectButton.addEventListener("click", () => decide("rejected"));
