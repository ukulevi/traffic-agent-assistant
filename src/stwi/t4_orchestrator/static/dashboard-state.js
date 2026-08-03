export const JOB_STATUSES = Object.freeze([
  "queued",
  "running",
  "succeeded",
  "needs_review",
  "failed",
  "expired",
]);

export const TERMINAL_STATUSES = new Set([
  "succeeded",
  "needs_review",
  "failed",
  "expired",
]);

const isObject = (value) => Boolean(value)
  && typeof value === "object"
  && !Array.isArray(value);

const isNonEmptyString = (value) => typeof value === "string"
  && value.trim().length > 0;

export function createInitialState() {
  return {
    context: {
      mode: "checking",
      tenantId: null,
      operatorId: null,
      roles: [],
      nodeIds: [],
      capabilities: {},
    },
    creation: { phase: "idle", idempotencyKey: null },
    job: {
      id: null,
      status: null,
      result: null,
      evidence: { phase: "pending" },
      decisionRecord: null,
      events: [],
    },
    transport: { phase: "checking", code: null, lastEventId: null },
    decision: { phase: "unavailable", error: null },
    operationEpoch: 0,
  };
}

export function validateAcceptedJob(value) {
  if (!isObject(value) || !isNonEmptyString(value.job_id)) {
    return { ok: false, code: "CREATE_JOB_ID_MISSING" };
  }
  if (value.status !== "queued") {
    return { ok: false, code: "CREATE_STATUS_INVALID" };
  }
  if (!isNonEmptyString(value.tenant_id)) {
    return { ok: false, code: "CREATE_TENANT_MISSING" };
  }
  return { ok: true, value };
}

export function validateJobEnvelope(value) {
  if (!isObject(value) || !isNonEmptyString(value.job_id)) {
    return { ok: false, code: "JOB_ID_MISSING" };
  }
  if (!JOB_STATUSES.includes(value.status)) {
    return { ok: false, code: "JOB_STATUS_UNKNOWN" };
  }
  return { ok: true, value };
}

function isSafeAction(action) {
  return isObject(action)
    && action.executable === false
    && action.automatic_actuation === false
    && action.requires_operator_approval === true;
}

function isCompleteCitation(citation) {
  return isObject(citation)
    && isNonEmptyString(citation.source_url || citation.source)
    && isNonEmptyString(citation.provision || citation.article)
    && isNonEmptyString(citation.effective_from);
}

function hasDemoEvidence(result) {
  const traceId = result?.trace_id || result?.audit_record?.trace_id;
  return isNonEmptyString(traceId)
    && isNonEmptyString(result?.model_version)
    && isNonEmptyString(result?.data_version)
    && isNonEmptyString(result?.completed_at || result?.created_at)
    && Array.isArray(result?.citations)
    && result.citations.length > 0
    && result.citations.every(isCompleteCitation);
}

export function evaluateEvidence(result, mode) {
  if (!result) return { phase: "pending" };
  if (result.citation_validation_outcome === "valid") return { phase: "valid" };
  if (result.citation_validation_outcome === "invalid") return { phase: "invalid" };
  if (result.citation_validation_outcome === "insufficient") return { phase: "insufficient" };
  if (mode === "demo" && hasDemoEvidence(result)) {
    return { phase: "demo_provisional_valid" };
  }
  return { phase: "unknown" };
}

export function deriveDecisionPolicy(state) {
  const roles = new Set(state.context.roles || []);
  const canDecide = roles.has("operator") || roles.has("admin");
  const evidenceAllowed = state.job.evidence?.phase === "valid"
    || (state.context.mode === "demo"
      && state.job.evidence?.phase === "demo_provisional_valid");
  const noDecision = !state.job.decisionRecord;
  const transportSafe = state.transport.phase !== "protocol_error";

  return {
    canApprove: canDecide
      && noDecision
      && transportSafe
      && evidenceAllowed
      && state.job.status === "succeeded"
      && isSafeAction(state.job.result?.recommended_action),
    canReject: canDecide
      && noDecision
      && ["succeeded", "needs_review", "failed", "expired"].includes(state.job.status),
    canRequestChanges: canDecide
      && noDecision
      && ["succeeded", "needs_review"].includes(state.job.status),
  };
}

export function reduceDashboardState(state, event) {
  switch (event.type) {
    case "context/resolved":
      return {
        ...state,
        context: event.context,
        transport: {
          ...state.transport,
          phase: event.context.mode === "static_preview" ? "unavailable" : "online",
          code: event.context.reason || null,
        },
      };
    case "creation/submitting":
      return {
        ...state,
        operationEpoch: event.epoch,
        creation: { phase: "submitting", idempotencyKey: event.idempotencyKey },
        job: { ...createInitialState().job },
        decision: { phase: "unavailable", error: null },
      };
    case "job/accepted":
      return {
        ...state,
        operationEpoch: event.epoch,
        creation: { ...state.creation, phase: "accepted" },
        job: {
          ...createInitialState().job,
          id: event.accepted.job_id,
          status: "queued",
        },
      };
    case "job/resume_requested":
      return {
        ...state,
        operationEpoch: event.epoch,
        creation: { ...state.creation, phase: "resuming" },
        job: { ...createInitialState().job, id: event.jobId },
      };
    case "job/envelope":
      if (state.job.id && event.envelope.job_id !== state.job.id) return state;
      return {
        ...state,
        job: {
          ...state.job,
          id: event.envelope.job_id,
          status: event.envelope.status,
          result: event.envelope.result || null,
          decisionRecord: event.envelope.operator_decision || null,
        },
      };
    case "job/event": {
      if (state.job.id !== event.jobId) return state;
      const duplicate = event.eventId
        && state.job.events.some((item) => item.eventId === event.eventId);
      if (duplicate) return state;
      const item = { eventId: event.eventId || null, payload: event.payload };
      return {
        ...state,
        job: { ...state.job, events: [...state.job.events, item].slice(-100) },
      };
    }
    case "transport/phase":
      return {
        ...state,
        transport: {
          ...state.transport,
          phase: event.phase,
          code: event.code || null,
          lastEventId: event.lastEventId ?? state.transport.lastEventId,
        },
      };
    case "transport/offline":
      return {
        ...state,
        transport: { ...state.transport, phase: "offline", code: event.code },
      };
    case "transport/protocol_error":
      return {
        ...state,
        transport: { ...state.transport, phase: "protocol_error", code: event.code },
      };
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
