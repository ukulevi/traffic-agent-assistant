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
    && action.requires_operator_approval === true
    && action.applied_by_system === false;
}

const isFiniteNonNegative = (value) => Number.isFinite(value) && value >= 0;
const isFinitePositive = (value) => Number.isFinite(value) && value > 0;

function isValidRoute(route) {
  return isObject(route)
    && isNonEmptyString(route.route_id)
    && isNonEmptyString(route.boundary_entry_node)
    && isNonEmptyString(route.boundary_exit_node)
    && Array.isArray(route.node_sequence)
    && route.node_sequence.length >= 2
    && route.node_sequence.every(isNonEmptyString)
    && new Set(route.node_sequence).size === route.node_sequence.length
    && route.node_sequence[0] === route.boundary_entry_node
    && route.node_sequence.at(-1) === route.boundary_exit_node
    && Array.isArray(route.edge_ids)
    && route.edge_ids.length === route.node_sequence.length - 1
    && route.edge_ids.every(isNonEmptyString)
    && isFinitePositive(route.base_cost)
    && isFinitePositive(route.distance_m)
    && isNonEmptyString(route.topology_version);
}

function isValidEvaluation(evaluation) {
  if (!isObject(evaluation) || !isValidRoute(evaluation.route)) return false;
  const reasons = evaluation.rejection_reasons;
  if (!Array.isArray(reasons) || !reasons.every(isNonEmptyString)) return false;
  if (
    !isFiniteNonNegative(evaluation.max_vc_ratio)
    || !isFiniteNonNegative(evaluation.avg_speed_kmh)
    || !isFiniteNonNegative(evaluation.delay_proxy_seconds)
    || !isFiniteNonNegative(evaluation.uncertainty_score)
    || !isFiniteNonNegative(evaluation.ood_score)
    || typeof evaluation.passed !== "boolean"
    || typeof evaluation.evidence_complete !== "boolean"
    || !isNonEmptyString(evaluation.model_version)
    || !isNonEmptyString(evaluation.data_version)
    || !isNonEmptyString(evaluation.topology_version)
    || evaluation.topology_version !== evaluation.route.topology_version
  ) return false;
  if (evaluation.passed) {
    return evaluation.evidence_complete && reasons.length === 0;
  }
  return reasons.length > 0;
}

function routesMatch(left, right) {
  return left.route_id === right.route_id
    && left.boundary_entry_node === right.boundary_entry_node
    && left.boundary_exit_node === right.boundary_exit_node
    && left.base_cost === right.base_cost
    && left.distance_m === right.distance_m
    && left.topology_version === right.topology_version
    && left.node_sequence.length === right.node_sequence.length
    && left.node_sequence.every((nodeId, index) => nodeId === right.node_sequence[index])
    && left.edge_ids.length === right.edge_ids.length
    && left.edge_ids.every((edgeId, index) => edgeId === right.edge_ids[index]);
}

function normalizedRoute(evaluation, { kind, rank = null } = {}) {
  return Object.freeze({
    routeId: evaluation.route.route_id,
    kind,
    rank,
    statusLabel: evaluation.passed ? "Đã qua safety gate" : "Chưa qua safety gate",
    nodeSequence: Object.freeze([...evaluation.route.node_sequence]),
    edgeIds: Object.freeze([...evaluation.route.edge_ids]),
    baseCost: evaluation.route.base_cost,
    distanceM: evaluation.route.distance_m,
    maxVcRatio: evaluation.max_vc_ratio,
    avgSpeedKmh: evaluation.avg_speed_kmh,
    delayProxySeconds: evaluation.delay_proxy_seconds,
    uncertaintyScore: evaluation.uncertainty_score,
    oodScore: evaluation.ood_score,
    reviewReasons: Object.freeze([...evaluation.rejection_reasons]),
    provenance: Object.freeze({
      modelVersion: evaluation.model_version,
      dataVersion: evaluation.data_version,
      topologyVersion: evaluation.topology_version,
    }),
  });
}

function normalizeRecommendation(value) {
  if (
    !isObject(value)
    || !isValidRoute(value.route)
    || !isValidEvaluation(value.evaluation)
    || !routesMatch(value.route, value.evaluation.route)
    || !Number.isInteger(value.rank)
    || value.rank < 1
    || value.rank > 3
    || value.executable !== false
    || value.requires_operator_approval !== true
    || value.applied_by_system !== false
    || value.evaluation.passed !== true
  ) return null;
  return normalizedRoute(value.evaluation, { kind: "recommendation", rank: value.rank });
}

function normalizeCandidate(value) {
  if (!isValidEvaluation(value) || value.passed !== false) return null;
  return normalizedRoute(value, { kind: "candidate" });
}

export function deriveRouteViewModel(envelope) {
  const status = JOB_STATUSES.includes(envelope?.status) ? envelope.status : null;
  const empty = {
    status,
    routeHeading: status === "needs_review" ? "Hành lang cần xem xét" : "Hành lang điều hướng",
    routes: Object.freeze([]),
    hasValidEvidence: false,
    hasMalformedRouteEvidence: false,
    canApprove: false,
  };
  if (!TERMINAL_STATUSES.has(status) || ["failed", "expired"].includes(status)) {
    return Object.freeze(empty);
  }

  const action = status === "succeeded"
    ? envelope?.result?.recommended_action
    : envelope?.result?.candidate_action;
  const routeKey = status === "succeeded" ? "route_recommendations" : "route_candidates";
  if (!isObject(action) || !Object.hasOwn(action, routeKey)) return Object.freeze(empty);

  const rawRoutes = action[routeKey];
  const normalize = status === "succeeded" ? normalizeRecommendation : normalizeCandidate;
  if (!Array.isArray(rawRoutes) || rawRoutes.length === 0 || rawRoutes.length > 3) {
    return Object.freeze({ ...empty, hasMalformedRouteEvidence: true });
  }
  const routes = rawRoutes.map(normalize);
  const routeIds = routes.filter(Boolean).map((route) => route.routeId);
  const ranks = routes.filter(Boolean).map((route) => route.rank).filter((rank) => rank !== null);
  const collectionValid = routes.every(Boolean)
    && new Set(routeIds).size === routeIds.length
    && new Set(ranks).size === ranks.length
    && (status !== "succeeded"
      || ranks.every((rank, index) => rank === index + 1));
  if (!collectionValid) {
    return Object.freeze({ ...empty, hasMalformedRouteEvidence: true });
  }

  const hasValidEvidence = routes.every((route) => route.kind === "recommendation");
  return Object.freeze({
    ...empty,
    routeHeading: status === "succeeded"
      ? "Hành lang được khuyến nghị"
      : "Hành lang cần xem xét",
    routes: Object.freeze(routes),
    hasValidEvidence,
    canApprove: status === "succeeded" && hasValidEvidence,
  });
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
  const routeViewModel = deriveRouteViewModel({
    status: state.job.status,
    result: state.job.result,
  });
  const action = state.job.result?.recommended_action;
  const declaresRoutes = isObject(action)
    && Object.hasOwn(action, "route_recommendations");
  const routeEvidenceAllowed = !declaresRoutes || routeViewModel.canApprove;

  return {
    canApprove: canDecide
      && noDecision
      && transportSafe
      && evidenceAllowed
      && routeEvidenceAllowed
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

export function deriveNetworkImpactViewModel({
  status = null,
  networkImpact = null,
  authorizedNodeIds = null,
  topology = null,
  selectedHorizon = null,
} = {}) {
  const normalizedStatus = JOB_STATUSES.includes(status) ? status : null;
  const empty = Object.freeze({
    status: normalizedStatus,
    topologyVersion: null,
    horizons: Object.freeze([]),
    selectedHorizon: null,
    incidentNodeIds: Object.freeze([]),
    rows: Object.freeze([]),
    available: false,
  });

  if (!["succeeded", "needs_review"].includes(normalizedStatus)) {
    return empty;
  }

  if (!isObject(networkImpact)) {
    return empty;
  }

  const topologyVersion = networkImpact.topology_version;
  if (!isNonEmptyString(topologyVersion)) {
    return empty;
  }

  if (topology && isNonEmptyString(topology.network_version) && topologyVersion !== topology.network_version) {
    return empty;
  }

  const rawHorizons = networkImpact.horizons_minutes;
  if (!Array.isArray(rawHorizons) || rawHorizons.length === 0) {
    return empty;
  }
  const horizons = rawHorizons.map((h) => Number(h));
  if (!horizons.every((h) => Number.isInteger(h) && h > 0)) {
    return empty;
  }
  if (new Set(horizons).size !== horizons.length) {
    return empty;
  }

  const rawIncidentNodeIds = networkImpact.incident_node_ids;
  const incidentNodeIds = Array.isArray(rawIncidentNodeIds)
    ? rawIncidentNodeIds.filter(isNonEmptyString)
    : [];

  const rawImpacts = networkImpact.node_impacts;
  if (!Array.isArray(rawImpacts) || rawImpacts.length === 0) {
    return empty;
  }

  const validRoles = new Set(["incident", "adjacent", "network"]);
  const rowsByHorizon = new Map();

  for (const point of rawImpacts) {
    if (!isObject(point)) return empty;
    const {
      node_id: nodeId,
      horizon_minutes: horizonMinutes,
      traffic_volume_5m: trafficVolume5m,
      avg_speed_kmh: avgSpeedKmh,
      vc_ratio: vcRatio,
      uncertainty_score: uncertaintyScore,
      ood_score: oodScore,
      impact_role: impactRole,
    } = point;

    if (!isNonEmptyString(nodeId)) return empty;
    if (authorizedNodeIds && Array.isArray(authorizedNodeIds) && authorizedNodeIds.length > 0) {
      if (!authorizedNodeIds.includes(nodeId)) return empty;
    }
    if (!horizons.includes(horizonMinutes)) return empty;
    if (!isFiniteNonNegative(trafficVolume5m)) return empty;
    if (!isFiniteNonNegative(avgSpeedKmh)) return empty;
    if (!isFiniteNonNegative(vcRatio)) return empty;
    if (!Number.isFinite(uncertaintyScore) || uncertaintyScore < 0.0 || uncertaintyScore > 1.0) return empty;
    if (!Number.isFinite(oodScore) || oodScore < 0.0 || oodScore > 1.0) return empty;
    if (!validRoles.has(impactRole)) return empty;

    let horizonMap = rowsByHorizon.get(horizonMinutes);
    if (!horizonMap) {
      horizonMap = new Map();
      rowsByHorizon.set(horizonMinutes, horizonMap);
    }
    if (horizonMap.has(nodeId)) return empty;

    horizonMap.set(
      nodeId,
      Object.freeze({
        nodeId,
        horizonMinutes,
        trafficVolume5m,
        avgSpeedKmh,
        vcRatio,
        uncertaintyScore,
        oodScore,
        impactRole,
      })
    );
  }

  if (rowsByHorizon.size !== horizons.length) return empty;

  let expectedNodeCount = 0;
  let expectedNodesSet = null;
  for (const horizonMap of rowsByHorizon.values()) {
    if (expectedNodesSet === null) {
      expectedNodeCount = horizonMap.size;
      expectedNodesSet = new Set(horizonMap.keys());
    } else {
      if (horizonMap.size !== expectedNodeCount) return empty;
      for (const k of horizonMap.keys()) {
        if (!expectedNodesSet.has(k)) return empty;
      }
    }
  }

  const activeHorizon = horizons.includes(selectedHorizon)
    ? selectedHorizon
    : horizons[0];

  const selectedMap = rowsByHorizon.get(activeHorizon);
  const rows = selectedMap ? Array.from(selectedMap.values()) : [];

  return Object.freeze({
    status: normalizedStatus,
    topologyVersion,
    horizons: Object.freeze([...horizons]),
    selectedHorizon: activeHorizon,
    incidentNodeIds: Object.freeze([...incidentNodeIds]),
    rows: Object.freeze(rows),
    available: true,
  });
}
