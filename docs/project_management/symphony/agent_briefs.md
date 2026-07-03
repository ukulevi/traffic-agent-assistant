# Symphony agent briefs

## Lead coordinator

- Owns board integrity and cross-lane priority.
- Keeps project contract unchanged unless the user explicitly approves a
  contract decision.
- Moves tasks to `Human Review` when evidence, policy, legal input, or
  production credentials are required.

## Data/Vision agent

- Scope: Phase 1, Tier 1, camera aggregate evidence, detector artifact,
  dataset manifest, privacy review, and local/Roboflow workflow boundaries.
- Must never store or publish raw video, image base64, or private weights.
- Key checks: vision dataset validation, detector promotion gate, privacy
  review manifest, aggregate-only output contract.

## ML/Simulation agent

- Scope: Phase 2, GCN-LSTM baseline, SUMO scenario data, surrogate ensemble,
  uncertainty calibration, OOD handling, and SLA benchmark.
- Must not blend retrieved cases into online surrogate input.
- Key checks: chronological split, scenario-family leakage, calibration report,
  P99 surrogate benchmark under the contract profile.

## Knowledge/RAG agent

- Scope: Phase 3, legal corpus, Qdrant/BGE retrieval path, typed
  `SimulationQuery`, citation validator, and constrained query security.
- Must abstain/fail closed when citation evidence is missing or invalid.
- Key checks: effective-date filtering, source allowlist, content hash,
  unanswerable prompts, prompt/SQL injection tests.

## Orchestrator/API/Release agent

- Scope: Phase 4, LangGraph/Celery/Redis path, FastAPI job API, SSE progress,
  safety loop, dashboard gap, release QA, docs/slides/report alignment.
- Must preserve decision-support-only behavior and human approval.
- Key checks: HTTP 202 create job, status contract, SSE reconnect behavior,
  fail-closed safety cases, no actuator/device API.
