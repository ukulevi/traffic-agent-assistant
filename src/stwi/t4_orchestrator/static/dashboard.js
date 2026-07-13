const form = document.querySelector("#scenario-form");
const statusNode = document.querySelector("#job-status");
const errorNode = document.querySelector("#form-error");
const eventsNode = document.querySelector("#events");
const approveButton = document.querySelector("#approve");
const rejectButton = document.querySelector("#reject");
let activeJobId = null;

function text(id, value) { document.querySelector(id).textContent = value || "—"; }
function setStatus(value) { statusNode.textContent = value; statusNode.className = `status ${value}`; }
function addEvent(value) { const item = document.createElement("li"); item.textContent = value; eventsNode.append(item); }
function actionFor(result) { return result.status === "needs_review" ? result.candidate_action : result.recommended_action; }

async function loadEvents(jobId) {
  const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(jobId)}/events`);
  const body = await response.text();
  for (const line of body.split("\n")) { if (line.startsWith("event: ")) addEvent(line.slice(7)); }
}

async function submitScenario(event) {
  event.preventDefault(); errorNode.textContent = ""; eventsNode.replaceChildren(); approveButton.disabled = true; rejectButton.disabled = true;
  const nodeId = document.querySelector("#node-id").value;
  const response = await fetch("/api/v1/what-if-jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tenant_id: document.querySelector("#tenant-id").value, scenario_time: "2025-06-01T08:00:00+00:00", candidate_action: { node_id: nodeId, green_time_ratio: Number(document.querySelector("#green-time").value) }, node_ids: [nodeId], scenario_query: document.querySelector("#scenario-query").value }) });
  if (!response.ok) { errorNode.textContent = "Không thể tạo job."; return; }
  const accepted = await response.json(); activeJobId = accepted.job_id; text("#job-id", activeJobId); setStatus("queued"); addEvent("queued");
  const terminal = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(activeJobId)}`); const job = await terminal.json(); const result = job.result;
  setStatus(job.status); text("#terminal-status", job.status); text("#trace-id", result.audit_record.trace_id); text("#versions", `${result.model_version} / ${result.data_version}`); text("#review-reason", result.needs_review_reason || "Safety checks passed; operator approval is still required."); document.querySelector("#action-view").textContent = JSON.stringify(actionFor(result), null, 2);
  await loadEvents(activeJobId); approveButton.disabled = false; rejectButton.disabled = false;
}

async function decide(decision) {
  if (!activeJobId) return;
  const response = await fetch(`/api/v1/what-if-jobs/${encodeURIComponent(activeJobId)}/operator-decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operator_id: "demo-operator", decision, comment: "Recorded from the demo dashboard." }) });
  const body = await response.json(); document.querySelector("#decision-result").textContent = response.ok ? `Đã ghi quyết định ${body.operator_decision.decision}; không có hành động tự động.` : "Không thể ghi quyết định.";
}

form.addEventListener("submit", submitScenario); approveButton.addEventListener("click", () => decide("approved")); rejectButton.addEventListener("click", () => decide("rejected"));
