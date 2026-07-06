# STWI MVP Readiness Symphony

Last reviewed: 2026-07-04

## Readiness Handoff Summary

- Evidence base: project_contract.json
- Todo: 7 | In Progress: 1 | Human Review: 4 | Rework: 1 | Done: 3
- Requires human review for: contract changes, dashboard scope changes, legal/SOP source approval, vision promotion threshold changes, production credentials or external services
- Report command: python scripts/project_management/symphony_report.py
- Daily agent update: enabled
- Handoff note: readiness is derived from board/state, gate acceptance criteria, and verified checks; not raw agentReport percentages.

## Summary

| Status | Count |
|---|---:|
| Backlog | 8 |
| Todo | 7 |
| In Progress | 1 |
| Human Review | 4 |
| Rework | 1 |
| Merging | 0 |
| Done | 3 |
| Canceled | 0 |
| Duplicate | 0 |

## Lane Readiness Evidence

| Lane | Owner | Completion | Health | Readiness Evidence |
|---|---|---:|---|---|
| Data/Vision | DataVisionAgent | 40% | yellow | Phase 1 mock/tensor gate is strong; vision tooling is useful, but detector promotion criteria, metadata, and real camera evidence still need reconciliation. |
| ML/Simulation | MLSimulationAgent | 20% | yellow | Baseline, SUMO, surrogate, and benchmarks have provisional artifacts; real aggregate data and standard-profile calibration remain open. |
| Knowledge/RAG | KnowledgeRagAgent | 25% | yellow | Contracts and validators are strong, while real retrieval quality, SOP corpus, and service-backed tests need hardening. |
| Orchestrator/API/Release | OrchestratorReleaseAgent | 30% | red | API and safety loop are demo-capable, but production Celery/Redis persistence, dashboard, and full release QA are not complete. |

## Tasks

### Backlog

- `STWI-SYM-003` [P1] Replace Phase 2 mock observations with real aggregate dataset (ML/Simulation, MLSimulationAgent)
  Evidence: data/derived/private/phase2_forecast/phase2_readiness_report.json, docs/02_ML_and_Simulation_Specification.md
  Acceptance: Chronological split is recorded.; Scaler is fit only on training split.; Forecast metrics are reported by horizon/node/missing bucket.
  Next: Select approved aggregate dataset and run Phase 2 start readiness again.
- `STWI-SYM-005` / TRA-6 [P1] Prove surrogate P99 under the contract benchmark profile (ML/Simulation, MLSimulationAgent)
  Evidence: project_contract.json, data/derived/private/phase2_surrogate/v3/benchmark_report.json
  Acceptance: Benchmark machine profile matches 8 CPU, 32 GB RAM, 12-16 GB GPU VRAM.; Surrogate P99 is below 500 ms.; Raw benchmark result is retained as private artifact.
  Next: Rerun benchmark on approved profile or mark KPI claim provisional.
- `STWI-SYM-006` [P1] Ingest approved SOP corpus and validate citation coverage (Knowledge/RAG, KnowledgeRagAgent)
  Evidence: docs/03_Knowledge_Base_and_RAG_Design.md, data/derived/private/phase3_knowledge/gate_p3_report.json
  Acceptance: SOP corpus has source registry, effective date, and content hash.; Unsupported claim rate is zero after validator/abstention.; Citation precision target is measured against the evaluation set.
  Next: Obtain approved SOP sources from human reviewer.
- `STWI-SYM-008` [P1] Implement production job persistence with Celery and Redis (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/job_store.py, src/stwi/t4_orchestrator/api.py, infra/harness/compose.phase4.yaml
  Acceptance: Jobs are queued and executed by Celery worker.; Progress and events are persisted in Redis.; SSE reconnect does not duplicate execution.
  Next: Design minimal Redis-backed job store and Celery worker slice.
- `STWI-SYM-009` / TRA-7 [P1] Replace provisional fake adapters in production runtime (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/config/runtime.py, src/stwi/t4_orchestrator/orchestrator.py, src/stwi/t3_knowledge/tier3_facade.py
  Acceptance: `STWI_RUNTIME_MODE=production` rejects fake adapters.; Real adapters have documented required environment variables.; Production startup fails closed when services are missing.
  Next: Audit adapter wiring and add integration test around production mode.
- `STWI-SYM-017` / TRA-13 [P2] Draft auth, RBAC, and tenant-boundary design (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: project_contract.json, docs/04_AI_Agent_Orchestrator_CF_VLA.md, src/stwi/t4_orchestrator/contracts.py
  Acceptance: Design derives operator identity and tenant context server-side instead of trusting request body fields.; Role boundaries for operator, analyst, admin, and readonly are specified without choosing a new identity provider.; No auth dependency, external IdP, or API schema change is implemented before Human Review approval.
  Next: Draft a minimal production-boundary proposal and keep it in Human Review before implementation.
- `STWI-SYM-021` / TRA-17 [P2] Review production deployment options without changing the approved stack (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: project_contract.json, infra/harness, docs/05_Implementation_Plan.md, docs/project_management/symphony/roadmap_intelligence_2026-07-03.md
  Acceptance: Docker Compose production, Kubernetes, and managed-service options are compared as deployment options only.; No Kubernetes, secrets manager, tracing, or model-serving framework is added to active architecture.; The recommendation lists cost, complexity, safety, rollback, and Human Review requirements for a later decision.
  Next: Prepare an options review after MVP gate gaps are stable; keep implementation blocked pending user approval.
- `STWI-RTSP-002` / TRA-10 [P1] Document supervised RTSP-to-quarantine smoke test procedure (Data/Vision, DataVisionAgent)
  Evidence: docs/guides/vision_local_training_runbook.md, docs/01_System_Architecture_Data_Pipeline.md, README.md
  Acceptance: Runbook explains how an operator sets `STWI_RTSP_URL` locally without writing it to repo, Linear, logs, or manifests.; Procedure captures only sparse frames into `data/quarantine/rtsp_frames` and never stores a raw video container.; Procedure lists privacy review, retention, cleanup, and aggregate-only next steps before any frame leaves quarantine.; Procedure includes exact offline verification commands that can run after supervised capture.
  Next: Keep in Backlog until the next RTSP documentation pass is intentionally dispatched.

### Todo

- `STWI-SYM-004` [P1] Rerun surrogate calibration and OOD thresholds on non-mock validation data (ML/Simulation, MLSimulationAgent)
  Evidence: data/derived/private/phase2_surrogate/provisional_gate_p2_report.json, tests/t2_forecast/test_surrogate_safety.py
  Acceptance: Calibration report uses held-out validation data.; OOD/high uncertainty returns `needs_review`.; Retrieved cases are never blended into online input.
  Next: Prepare validation split and rerun provisional gate with standard evidence.
- `STWI-SYM-007` [P1] Switch Phase 3 validation from fake retriever to Qdrant/BGE path (Knowledge/RAG, KnowledgeRagAgent)
  Evidence: src/stwi/t3_knowledge, infra/harness/compose.phase3.yaml, tests/t3_knowledge/test_t3_integration.py
  Acceptance: Qdrant-backed retrieval runs in integration harness.; BGE-m3 embedding path is documented and tested.; Service-dependent skips are reduced or explicitly justified.
  Next: Run Phase 3 harness and capture integration results.
- `STWI-SYM-014` [P1] Validate recorded-camera or RTSP calibration and aggregate extraction path (Data/Vision, DataVisionAgent)
  Evidence: scripts/data_prep/capture_rtsp_frames.py, src/stwi/t1_pipeline, tests/t1_pipeline
  Acceptance: Calibration ROI/homography evidence is recorded for approved demo input.; ByteTrack or equivalent track quality is measured.; Five-minute aggregate output preserves the project data contract.
  Next: Run the recorded-camera calibration path on approved non-published demo evidence.
- `STWI-SYM-015` [P2] Improve detector AP toward current MVP promotion threshold (Data/Vision, DataVisionAgent)
  Evidence: data/derived/private/vision_evals/motoann_best_val_minarea003/roi_ap50_summary.json, scripts/training/train_vision_model.py, tests/vision
  Acceptance: Validation/test evaluation is rerun after label/model improvements.; Motorcycle and transport classes meet the accepted MVP evidence threshold or are explicitly scoped down.; Promotion decision is consistent with STWI-SYM-001.
  Next: Analyze low-precision classes and select retraining or class-scope adjustment.
- `STWI-SYM-018` / TRA-14 [P2] Specify observability minimum for trace, logs, and metrics (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: project_contract.json, docs/04_AI_Agent_Orchestrator_CF_VLA.md, docs/05_Implementation_Plan.md
  Acceptance: Required trace_id, job timing, model/data/policy version, status transition, and safety reason fields are listed.; Metric names are specified for job counts, job latency, safety loop outcomes, retrieval latency, and surrogate latency.; Prometheus, OpenTelemetry, or other observability services remain optional future deployment choices until explicitly approved.
  Next: Write the observability minimum as a docs/testable contract proposal before adding tooling.
- `STWI-SYM-019` / TRA-15 [P1] Define project-native model registry evidence format (ML/Simulation, MLSimulationAgent)
  Evidence: project_contract.json, docs/02_ML_and_Simulation_Specification.md, docs/guides/vision_local_training_runbook.md, src/stwi/tooling/vision_training/promotion.py
  Acceptance: Evidence schema covers model version, dataset version, checksum, metrics, calibration, benchmark profile, thresholds, and promotion decision.; The format works for vision, baseline forecast, and surrogate artifacts without requiring MLflow.; Existing promotion and validation paths either produce or validate the required fields.
  Next: Specify the project-native evidence format and map current provisional artifacts to it.
- `STWI-SYM-020` / TRA-16 [P1] Document fail-closed resilience policy for dependency failures (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: project_contract.json, docs/04_AI_Agent_Orchestrator_CF_VLA.md, docs/project_management/symphony/roadmap_intelligence_2026-07-03.md, tests/t4_orchestrator
  Acceptance: Retries, timeout, circuit-breaker-style behavior, and dependency failure classes map to `needs_review`, `failed`, or `expired`.; No runtime path returns an executable action after tool, RAG, TimescaleDB, Qdrant, Celery, Redis, or model failure.; The rejected fail-open wording is replaced with an explicit fail-closed policy and focused tests are identified.
  Next: Write the policy and identify the smallest tests needed before any runtime hardening issue.

### In Progress

- `STWI-SYM-012` [P1] Resolve dirty working tree into reviewable change groups (Orchestrator/API/Release, LeadCoordinator)
  Evidence: git status --short, python scripts/project_management/worktree_intake.py, docs/guides/repository_structure.md, src/stwi/tooling, tests/vision
  Acceptance: Unrelated generated manifests are kept separate from source changes.; Refactor files are reviewed as one coherent change set.; A read-only intake report groups dirty worktree changes before staging.; No user changes are reverted.
  Next: Review diff grouping before any staging or commit.

### Human Review

- `STWI-SYM-001` [P1] Reconcile official vision artifact with current promotion gate (Data/Vision, DataVisionAgent)
  Evidence: data/derived/private/vision_models/official/model_artifact.json, scripts/training/promote_vision_model.py, docs/vision_local_training_runbook.md
  Acceptance: Promotion gate threshold and official artifact metrics are consistent.; Decision is recorded without weakening privacy or aggregate-only constraints.; Detector status is documented as official, provisional, or rejected.
  Next: User/lead decides whether to lower gate, retrain, or mark artifact provisional.
- `STWI-SYM-010` [P2] Build operator dashboard or explicitly scope it out of demo (Orchestrator/API/Release, FrontendAgent)
  Evidence: docs/05_Implementation_Plan.md, slides/sections/07_01_multiagent.html, slides/sections/09_01_kpi.html
  Acceptance: Dashboard scope is approved by user.; If implemented, UI shows job status, citations, warnings, versions, trace_id, and approval state.; If deferred, docs and demo script clearly state the limitation.
  Next: User decides whether to build a minimal dashboard or keep API/slides demo.
- `STWI-SYM-013` / TRA-5 [P1] Complete vision artifact metadata for latency, thresholds, ROI policy, and license/source (Data/Vision, DataVisionAgent)
  Evidence: data/derived/private/vision_models/official/model_artifact.json, docs/guides/vision_local_training_runbook.md, docs/01_System_Architecture_Data_Pipeline.md
  Acceptance: Official or candidate artifact records latency and threshold evidence.; ROI policy and source/license review are present.; Privacy review remains aggregate-only and does not publish raw images/video.
  Next: Resolve review findings: promotion validator does not yet require latency, thresholds, ROI policy, or source/license metadata.
- `STWI-RTSP-003` / TRA-11 [P1] Run supervised live RTSP smoke test for edge_camera_1 (Data/Vision, DataVisionAgent with human supervision)
  Evidence: STWI_RTSP_URL local environment variable, data/quarantine/rtsp_frames, https://linear.app/traffic-agent-assistant/issue/TRA-11/run-supervised-live-rtsp-smoke-test-for-edge-camera-1
  Acceptance: Human operator confirms the RTSP endpoint is approved for STWI testing and sets it only in `STWI_RTSP_URL`.; Live capture is bounded to a small sample, stores sparse frames only in quarantine, and retains no raw video.; Manifest is reviewed to confirm no endpoint, credentials, image base64, or raw video reference is present.; Resulting evidence is deleted, kept in quarantine for privacy review, or converted into approved aggregate-only evidence by a follow-up issue.
  Next: Keep in Human Review; do not add `symphony-approved` because this requires live external service access and human supervision.

### Rework

- `STWI-SYM-016` / TRA-12 [P2] Reconcile readiness scoring and progress evidence (Orchestrator/API/Release, LeadCoordinator)
  Evidence: docs/project_management/symphony/board.json, docs/project_management/symphony/roadmap_intelligence_2026-07-03.md, docs/project_management/symphony/status_report.md
  Acceptance: Progress estimates are derived from board state, gate criteria, and verified checks instead of raw agent-report percentages.; Stale test counts are replaced or explicitly marked stale.; A single readiness summary is available for Symphony/Linear handoff.
  Next: Define one gate-backed readiness score and update the status report without changing contract invariants.

### Merging

- None

### Done

- `STWI-SYM-002` [P1] Close Phase 1 camera aggregate evidence gap (Data/Vision, DataVisionAgent)
  Evidence: docs/01_System_Architecture_Data_Pipeline.md, tests/t1_pipeline, data/derived/private/phase1_mock/gate_p1_report.json
  Acceptance: Aggregate-only outputs are validated for demo camera or recorded RTSP inputs.; No raw video, image base64, or private model artifact is published.; Phase 1 gate report records dataset/model/privacy versions.
  Next: Keep current mock gate evidence; split real camera calibration into a separate task.
  Checks: validate_phase1_gate.py data/derived/private/phase1_mock -> pass; unittest discover -s tests/t1_pipeline -> pass, 35 tests, 1 skipped
- `STWI-SYM-011` / TRA-8 [P1] Run full release QA after current refactor changes are settled (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: AGENTS.md, .agents/skills/stwi-release-qa/SKILL.md, git status --short
  Acceptance: Docs validator, contract tests, JS checks, slide static check, and git diff check pass.; Skipped tests and unverified service paths are listed.; No cache/build artifact is staged.
  Next: Keep QA evidence attached to Linear and rerun release QA after the remaining staged batch changes.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-RTSP-001` / TRA-9 [P1] Prepare RTSP source alias and capture guardrails for edge_camera_1 (Data/Vision, DataVisionAgent)
  Evidence: scripts/data_prep/capture_rtsp_frames.py, tests/t1_pipeline/test_capture_rtsp_frames.py, docs/guides/vision_local_training_runbook.md, https://linear.app/traffic-agent-assistant/issue/TRA-9/prepare-rtsp-source-alias-and-capture-guardrails-for-edge-camera-1
  Acceptance: `edge_camera_1` is accepted as a safe source id and unsafe source ids remain rejected.; Capture path continues reading the endpoint only from `STWI_RTSP_URL`.; Command output and manifests do not include the RTSP endpoint, credentials, image base64, or raw video references.; Focused tests cover missing env handling, safe source id, redaction, and fail-closed behavior without opening a live stream.
  Next: Keep done evidence on Linear; live capture remains gated by STWI-RTSP-003.
  Checks: python -m unittest tests.t1_pipeline.test_capture_rtsp_frames -> pass, 14 tests; git diff --cached --check -> pass

### Canceled

- None

### Duplicate

- None
