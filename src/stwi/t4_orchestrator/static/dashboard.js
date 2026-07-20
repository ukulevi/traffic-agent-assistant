const form = document.querySelector("#scenario-form");
const statusNode = document.querySelector("#job-status");
const errorNode = document.querySelector("#form-error");
const eventsNode = document.querySelector("#events");
const approveButton = document.querySelector("#approve");
const rejectButton = document.querySelector("#reject");
let activeJobId = null;
let eventSource = null;

const TERMINAL_STATUSES = new Set(["succeeded", "needs_review", "failed", "expired"]);

function text(id, value) { document.querySelector(id).textContent = value ?? "—"; }
function setStatus(value) { statusNode.textContent = value; statusNode.className = `status ${value}`; }
function addEvent(value) { const item = document.createElement("li"); item.textContent = value; eventsNode.append(item); }
function formatValue(value) { return typeof value === "number" ? value.toLocaleString("vi-VN", { maximumFractionDigits: 2 }) : (value ?? "—"); }
function validCitation(citation) { return Boolean(citation && (citation.source || citation.source_url || citation.title || citation.document_number) && (citation.provision || citation.article || !citation.document_number) && (citation.effective_from || !citation.document_number)); }
function provenanceIsComplete(result) { return Boolean(result?.trace_id || result?.audit_record?.trace_id) && Boolean(result?.model_version) && Boolean(result?.data_version) && Boolean(result?.completed_at || result?.created_at) && Array.isArray(result?.citations) && result.citations.length > 0 && result.citations.every(validCitation); }
function actionText(action) { if (!action) return ""; return Object.entries(action).filter(([key]) => !["executable", "automatic_actuation", "requires_operator_approval"].includes(key)).map(([key, value]) => `${key}: ${formatValue(value)}`).join(" · "); }
function metricsFrom(result) { return result.forecast_summary || result.scenario_metrics || result.baseline_summary || {}; }

function renderCitations(citations, valid) {
  const list = document.querySelector("#citations"); list.replaceChildren();
  text("#evidence-status", valid ? "Provenance đầy đủ" : "Thiếu provenance");
  document.querySelector("#evidence-status").className = `evidence-status ${valid ? "valid" : "invalid"}`;
  text("#evidence-message", valid ? "Citation có nguồn, mốc thời gian và thông tin hiệu lực để operator đối chiếu." : "Không đủ citation/provenance để xác nhận recommendation; kết quả được trình bày fail-closed.");
  for (const citation of citations || []) { const item = document.createElement("li"); const heading = document.createElement("strong"); heading.textContent = citation.title || citation.document_number || citation.source || "Citation"; const detail = document.createElement("div"); detail.textContent = [citation.provision || citation.article, citation.effective_from ? `Hiệu lực: ${citation.effective_from}` : null, citation.timestamp || citation.retrieved_at, citation.source || citation.source_url].filter(Boolean).join(" · "); item.append(heading, detail); list.append(item); }
}

function renderResult(job) {
  const result = job.result || {}; const serverStatus = job.status || result.status || "failed";
  const complete = provenanceIsComplete(result); const displayStatus = serverStatus === "succeeded" && !complete ? "needs_review" : serverStatus;
  const action = displayStatus === "succeeded" ? result.recommended_action : (displayStatus === "needs_review" ? result.candidate_action : null);
  const metrics = metricsFrom(result);
  setStatus(displayStatus); text("#terminal-status", serverStatus); text("#result-timestamp", result.completed_at || result.created_at); text("#trace-id", result.trace_id || result.audit_record?.trace_id); text("#versions", [result.model_version, result.data_version].filter(Boolean).join(" / ") || "—");
  text("#result-title", displayStatus === "succeeded" ? "Đề xuất đã qua safety gate" : displayStatus === "needs_review" ? "Cần operator xem xét" : `Job ${displayStatus}`);
  text("#plain-language-result", displayStatus === "succeeded" ? "Kịch bản đã qua các kiểm tra hiện có. Đây là đề xuất hỗ trợ quyết định, không phải lệnh điều khiển." : displayStatus === "needs_review" ? "Không thể đưa recommendation an toàn. Operator cần xem lý do, evidence và candidate không thực thi bên dưới." : "Job không tạo được kết quả có thể sử dụng; không có hành động nào được đề xuất.");
  text("#review-reason", displayStatus === "succeeded" ? "Safety checks pass; operator approval is still required." : (result.needs_review_reason || result.error?.message || "Kết quả không đạt điều kiện an toàn hoặc evidence cần thiết."));
  text("#forecast-volume", formatValue(metrics.traffic_volume_5m ?? metrics.avg_volume)); text("#forecast-speed", formatValue(metrics.avg_speed_kmh ?? metrics.avg_speed)); text("#vc-ratio", formatValue(metrics.max_vc_ratio ?? metrics.vc_ratio)); text("#capacity-version", metrics.capacity_version || result.capacity_version || "—");
  renderCitations(result.citations, complete);
  const card = document.querySelector("#action-card"); card.classList.toggle("is-hidden", !action); text("#action-label", displayStatus === "succeeded" ? "recommended_action · non-executable" : "candidate_action · non-executable"); text("#action-text", actionText(action));
  text("#json-view", JSON.stringify(result, null, 2)); approveButton.disabled = !["succeeded", "needs_review"].includes(displayStatus); rejectButton.disabled = !["succeeded", "needs_review"].includes(displayStatus);
}

async function refreshJob(jobId) {
  const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) { errorNode.textContent = "Không thể tải kết quả job."; return null; }
  const job = await response.json();
  if (TERMINAL_STATUSES.has(job.status)) renderResult(job); else setStatus(job.status);
  return job;
}

function closeEventStream() { if (eventSource) { eventSource.close(); eventSource = null; } }

function streamJobEvents(jobId) {
  closeEventStream();
  eventSource = new EventSource(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/events`);
  const handleEvent = async (event) => {
    try {
      const payload = JSON.parse(event.data);
      addEvent(payload.event || payload.status || "progress");
      if (payload.status && TERMINAL_STATUSES.has(payload.status)) { await refreshJob(jobId); closeEventStream(); }
    } catch { addEvent("SSE event không hợp lệ"); }
  };
  eventSource.onmessage = handleEvent;
  eventSource.addEventListener("status", handleEvent);
  eventSource.addEventListener("result", handleEvent);
  eventSource.onerror = () => { closeEventStream(); };
}

async function submitScenario(event) {
  event.preventDefault(); errorNode.textContent = ""; eventsNode.replaceChildren(); closeEventStream(); approveButton.disabled = true; rejectButton.disabled = true;
  const nodeId = document.querySelector("#node-id").value;
  const response = await fetch("/api/v1/what-if-jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tenant_id: document.querySelector("#tenant-id").value, scenario_time: "2025-06-01T08:00:00+00:00", candidate_action: { node_id: nodeId, green_time_ratio: Number(document.querySelector("#green-time").value) }, node_ids: [nodeId], scenario_query: document.querySelector("#scenario-query").value }) });
  if (!response.ok) { errorNode.textContent = "Không thể tạo job."; return; }
  const accepted = await response.json(); activeJobId = accepted.job_id; text("#job-id", activeJobId); setStatus("queued"); addEvent("queued");
  const job = await refreshJob(activeJobId); if (job && !TERMINAL_STATUSES.has(job.status)) streamJobEvents(activeJobId);
}
async function decide(decision) { if (!activeJobId) return; const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(activeJobId)}/operator-decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operator_id: "demo-operator", decision, comment: "Recorded from the demo dashboard." }) }); const body = await response.json(); text("#decision-result", response.ok ? `Đã ghi quyết định ${body.operator_decision.decision}; không có hành động tự động.` : "Không thể ghi quyết định."); }
form.addEventListener("submit", submitScenario); approveButton.addEventListener("click", () => decide("approved")); rejectButton.addEventListener("click", () => decide("rejected"));
