# STWI MVP Readiness Symphony

Last reviewed: 2026-07-04

## Summary

| Status | Count |
|---|---:|
| Backlog | 8 |
| Todo | 8 |
| In Progress | 1 |
| Human Review | 4 |
| Rework | 0 |
| Merging | 0 |
| Done | 3 |
| Canceled | 0 |
| Duplicate | 0 |

## Lane Health

| Lane | Owner | Completion | Health |
|---|---|---:|---|
| Data/Vision | DataVisionAgent | 72% | yellow |
| ML/Simulation | MLSimulationAgent | 60% | yellow |
| Knowledge/RAG | KnowledgeRagAgent | 65% | yellow |
| Orchestrator/API/Release | OrchestratorReleaseAgent | 55% | red |

## Tasks

### Backlog

- `STWI-SYM-003` [P1] Replace Phase 2 mock observations with real aggregate dataset (ML/Simulation, MLSimulationAgent)
  Next: Select approved aggregate dataset and run Phase 2 start readiness again.
- `STWI-SYM-005` / TRA-6 [P1] Prove surrogate P99 under the contract benchmark profile (ML/Simulation, MLSimulationAgent)
  Next: Rerun benchmark on approved profile or mark KPI claim provisional.
- `STWI-SYM-006` [P1] Ingest approved SOP corpus and validate citation coverage (Knowledge/RAG, KnowledgeRagAgent)
  Next: Obtain approved SOP sources from human reviewer.
- `STWI-SYM-008` [P1] Implement production job persistence with Celery and Redis (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Next: Design minimal Redis-backed job store and Celery worker slice.
- `STWI-SYM-009` / TRA-7 [P1] Replace provisional fake adapters in production runtime (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Next: Audit adapter wiring and add integration test around production mode.
- `STWI-SYM-017` / TRA-13 [P2] Draft auth, RBAC, and tenant-boundary design (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Next: Draft a minimal production-boundary proposal and keep it in Human Review before implementation.
- `STWI-SYM-021` / TRA-17 [P2] Review production deployment options without changing the approved stack (Orchestrator/API/Release, ReleaseQaAgent)
  Next: Prepare an options review after MVP gate gaps are stable; keep implementation blocked pending user approval.
- `STWI-RTSP-002` / TRA-10 [P1] Document supervised RTSP-to-quarantine smoke test procedure (Data/Vision, DataVisionAgent)
  Next: Keep in Backlog until the next RTSP documentation pass is intentionally dispatched.

### Todo

- `STWI-SYM-004` [P1] Rerun surrogate calibration and OOD thresholds on non-mock validation data (ML/Simulation, MLSimulationAgent)
  Next: Prepare validation split and rerun provisional gate with standard evidence.
- `STWI-SYM-007` [P1] Switch Phase 3 validation from fake retriever to Qdrant/BGE path (Knowledge/RAG, KnowledgeRagAgent)
  Next: Run Phase 3 harness and capture integration results.
- `STWI-SYM-014` [P1] Validate recorded-camera or RTSP calibration and aggregate extraction path (Data/Vision, DataVisionAgent)
  Next: Run the recorded-camera calibration path on approved non-published demo evidence.
- `STWI-SYM-015` [P2] Improve detector AP toward current MVP promotion threshold (Data/Vision, DataVisionAgent)
  Next: Analyze low-precision classes and select retraining or class-scope adjustment.
- `STWI-SYM-016` / TRA-12 [P1] Reconcile readiness scoring and progress evidence (Orchestrator/API/Release, LeadCoordinator)
  Next: Define one gate-backed readiness score and update the status report without changing contract invariants.
- `STWI-SYM-018` / TRA-14 [P2] Specify observability minimum for trace, logs, and metrics (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Next: Write the observability minimum as a docs/testable contract proposal before adding tooling.
- `STWI-SYM-019` / TRA-15 [P1] Define project-native model registry evidence format (ML/Simulation, MLSimulationAgent)
  Next: Specify the project-native evidence format and map current provisional artifacts to it.
- `STWI-SYM-020` / TRA-16 [P1] Document fail-closed resilience policy for dependency failures (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Next: Write the policy and identify the smallest tests needed before any runtime hardening issue.

### In Progress

- `STWI-SYM-012` [P1] Resolve dirty working tree into reviewable change groups (Orchestrator/API/Release, LeadCoordinator)
  Next: Review diff grouping before any staging or commit.

### Human Review

- `STWI-SYM-001` [P1] Reconcile official vision artifact with current promotion gate (Data/Vision, DataVisionAgent)
  Next: User/lead decides whether to lower gate, retrain, or mark artifact provisional.
- `STWI-SYM-010` [P2] Build operator dashboard or explicitly scope it out of demo (Orchestrator/API/Release, FrontendAgent)
  Next: User decides whether to build a minimal dashboard or keep API/slides demo.
- `STWI-SYM-013` / TRA-5 [P1] Complete vision artifact metadata for latency, thresholds, ROI policy, and license/source (Data/Vision, DataVisionAgent)
  Next: Resolve review findings: promotion validator does not yet require latency, thresholds, ROI policy, or source/license metadata.
- `STWI-RTSP-003` / TRA-11 [P1] Run supervised live RTSP smoke test for edge_camera_1 (Data/Vision, DataVisionAgent with human supervision)
  Next: Keep in Human Review; do not add `symphony-approved` because this requires live external service access and human supervision.

### Rework

- None

### Merging

- None

### Done

- `STWI-SYM-002` [P1] Close Phase 1 camera aggregate evidence gap (Data/Vision, DataVisionAgent)
  Next: Keep current mock gate evidence; split real camera calibration into a separate task.
- `STWI-SYM-011` / TRA-8 [P1] Run full release QA after current refactor changes are settled (Orchestrator/API/Release, ReleaseQaAgent)
  Next: Keep QA evidence attached to Linear and rerun release QA after the remaining staged batch changes.
- `STWI-RTSP-001` / TRA-9 [P1] Prepare RTSP source alias and capture guardrails for edge_camera_1 (Data/Vision, DataVisionAgent)
  Next: Keep done evidence on Linear; live capture remains gated by STWI-RTSP-003.

### Canceled

- None

### Duplicate

- None
