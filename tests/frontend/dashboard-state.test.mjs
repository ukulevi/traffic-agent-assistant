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

const safeAction = Object.freeze({
  node_id: "node_00",
  green_time_ratio: 0.7,
  executable: false,
  automatic_actuation: false,
  requires_operator_approval: true,
});

test("transport failure preserves the authoritative job status", () => {
  let state = createInitialState();
  state = reduceDashboardState(state, {
    type: "job/accepted",
    accepted: { job_id: "job-1", status: "queued", tenant_id: "demo-operator" },
    epoch: 1,
  });
  state = reduceDashboardState(state, {
    type: "job/envelope",
    envelope: { job_id: "job-1", status: "running", tenant_id: "demo-operator" },
  });
  state = reduceDashboardState(state, { type: "transport/offline", code: "NETWORK_ERROR" });

  assert.equal(state.job.status, "running");
  assert.equal(state.transport.phase, "offline");
});

test("static preview never reports an online transport", () => {
  const state = reduceDashboardState(createInitialState(), {
    type: "context/resolved",
    context: { mode: "static_preview", roles: [], nodeIds: [] },
  });

  assert.equal(state.transport.phase, "unavailable");
});

test("resume does not fabricate a queued server status", () => {
  const state = reduceDashboardState(createInitialState(), {
    type: "job/resume_requested",
    jobId: "job-2",
    epoch: 2,
  });

  assert.equal(state.job.id, "job-2");
  assert.equal(state.job.status, null);
  assert.equal(state.creation.phase, "resuming");
});

test("unknown status is rejected at the client boundary", () => {
  assert.deepEqual(
    validateJobEnvelope({ job_id: "job-1", status: "complete" }),
    { ok: false, code: "JOB_STATUS_UNKNOWN" },
  );
});

test("accepted response requires queued status and tenant identity", () => {
  assert.equal(
    validateAcceptedJob({ job_id: "job-1", status: "queued", tenant_id: "demo-operator" }).ok,
    true,
  );
  assert.deepEqual(
    validateAcceptedJob({ job_id: "job-1", status: "running", tenant_id: "demo-operator" }),
    { ok: false, code: "CREATE_STATUS_INVALID" },
  );
});

test("approval requires succeeded, safe action, evidence, role and no prior decision", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "production", roles: ["operator"] },
    job: {
      ...createInitialState().job,
      id: "job-1",
      status: "succeeded",
      result: { recommended_action: safeAction },
      evidence: { phase: "valid" },
    },
    transport: { phase: "online" },
  };

  assert.equal(deriveDecisionPolicy(state).canApprove, true);
  assert.equal(
    deriveDecisionPolicy({ ...state, job: { ...state.job, result: {} } }).canApprove,
    false,
  );
  assert.equal(
    deriveDecisionPolicy({ ...state, job: { ...state.job, decisionRecord: { decision: "approved" } } }).canApprove,
    false,
  );
});

test("needs_review never permits approval", () => {
  const state = {
    ...createInitialState(),
    context: { mode: "demo", roles: ["operator"] },
    job: {
      ...createInitialState().job,
      id: "job-1",
      status: "needs_review",
      result: { candidate_action: safeAction },
      evidence: { phase: "demo_provisional_valid" },
    },
    transport: { phase: "online" },
  };

  const policy = deriveDecisionPolicy(state);
  assert.equal(policy.canApprove, false);
  assert.equal(policy.canRequestChanges, true);
});

test("demo evidence is provisional while production requires server validation", () => {
  const result = {
    model_version: "model-v1",
    data_version: "data-v1",
    completed_at: "2026-08-03T00:00:00Z",
    audit_record: { trace_id: "trace-1" },
    citations: [{ source_url: "https://vanban.chinhphu.vn/example", provision: "Điều 1", effective_from: "2025-01-01" }],
  };

  assert.equal(evaluateEvidence(result, "demo").phase, "demo_provisional_valid");
  assert.equal(evaluateEvidence(result, "production").phase, "unknown");
  assert.equal(
    evaluateEvidence({ ...result, citation_validation_outcome: "valid" }, "production").phase,
    "valid",
  );
});

test("duplicate SSE events are ignored by event id", () => {
  let state = reduceDashboardState(createInitialState(), {
    type: "job/resume_requested",
    jobId: "job-1",
    epoch: 1,
  });
  state = reduceDashboardState(state, {
    type: "job/event",
    jobId: "job-1",
    eventId: "4",
    payload: { status: "running" },
  });
  state = reduceDashboardState(state, {
    type: "job/event",
    jobId: "job-1",
    eventId: "4",
    payload: { status: "running" },
  });

  assert.equal(state.job.events.length, 1);
});
