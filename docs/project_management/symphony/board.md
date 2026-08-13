# STWI MVP Readiness Symphony

Last reviewed: 2026-08-13

## Readiness Handoff Summary

- Evidence base: project_contract.json
- Todo: 0 | In Progress: 0 | Human Review: 4 | Rework: 0 | Done: 48
- Requires human review for: contract changes, dashboard scope changes, legal/SOP source approval, vision promotion threshold changes, production credentials or external services
- Report command: python scripts/project_management/symphony_report.py
- Daily agent update: enabled
- Handoff note: readiness is derived from board/state, gate acceptance criteria, and verified checks; not raw agentReport percentages.

## Summary

| Status | Count |
|---|---:|
| Backlog | 2 |
| Todo | 0 |
| In Progress | 0 |
| Human Review | 4 |
| Rework | 0 |
| Merging | 0 |
| Done | 48 |
| Canceled | 1 |
| Duplicate | 1 |

## Lane Readiness Evidence

| Lane | Owner | Completion | Health | Readiness Evidence |
|---|---|---:|---|---|
| Data/Vision | DataVisionAgent | 85% | yellow | Simulation-first demo evidence is complete; recorded-camera/RTSP calibration remains an external, human-supervised production/pilot gate. |
| ML/Simulation | MLSimulationAgent | 85% | yellow | Simulation-first demo forecasting and surrogate evidence is complete; non-mock calibration and contract-profile SLA measurement remain production gates. |
| Knowledge/RAG | KnowledgeRagAgent | 100% | green | Approved SOP registry and real Qdrant/BGE-m3 service-path validation are complete for the offline demo scope. |
| Orchestrator/API/Release | OrchestratorReleaseAgent | 90% | yellow | Offline MVP API, dashboard, persistence, safety, and auth boundaries are complete; deployment baseline and final production QA remain gated by external deployment decisions and production evidence. |

## Tasks

### Backlog

- `STWI-SYM-004` / TRA-36 [P1] Rerun surrogate calibration and OOD thresholds on non-mock validation data (ML/Simulation, MLSimulationAgent)
  Evidence: data/derived/private/phase2_surrogate/provisional_gate_p2_report.json, tests/t2_forecast/test_surrogate_safety.py
  Acceptance: Calibration report uses held-out validation data.; OOD/high uncertainty returns `needs_review`.; Retrieved cases are never blended into online input.
  Next: Prepare validation split and rerun provisional gate with standard evidence.
- `STWI-SYM-042` / TRA-51 [P1] Run final production release-readiness QA (Orchestrator/API/Release, ReleaseQaAgent / LeadCoordinator)
  Evidence: .agents/skills/stwi-release-qa/SKILL.md, docs/project_management/symphony/status_report.md
  Acceptance: All test, service, security, SLA, browser, artifact, recovery, and rollback evidence is attached.; Production mode rejects provisional or invalid dependencies/artifacts.; No open P1 blocker, unexplained service skip, privacy breach, invalid citation, actuation, or executable needs_review remains.; The result is a Human Review go/no-go recommendation without automatic release/deployment.
  Next: Keep in Backlog until every dependency is reviewable.

### Todo

- None

### In Progress

- None

### Human Review

- `STWI-SYM-005` / TRA-6 [P1] Prove surrogate P99 under the contract benchmark profile (ML/Simulation, MLSimulationAgent)
  Evidence: project_contract.json, data/derived/private/phase2_surrogate/v3/benchmark_report.json, docs/guides/surrogate_benchmark_evidence.md
  Acceptance: Benchmark machine profile matches 8 CPU, 32 GB RAM, 12-16 GB GPU VRAM.; Surrogate P99 is below 500 ms.; Raw benchmark result is retained as private artifact.; E2E P95 target is recorded as required future evidence; no claim is made without measurement.
  Next: Keep TRA-6 in Human Review until the benchmark runs on the 8 CPU / 32 GB RAM / NVIDIA GPU 12-16 GB contract profile; this workstation's 4 GB GPU cannot satisfy the gate.
- `STWI-SYM-014` / TRA-37 [P1] Validate recorded-camera or RTSP calibration and aggregate extraction path (Data/Vision, DataVisionAgent)
  Evidence: scripts/data_prep/capture_rtsp_frames.py, src/stwi/t1_pipeline, tests/t1_pipeline
  Acceptance: Calibration ROI/homography evidence is recorded for approved demo input.; ByteTrack or equivalent track quality is measured.; Five-minute aggregate output preserves the project data contract.
  Next: Run the recorded-camera calibration path on approved non-published demo evidence.
- `STWI-RTSP-003` / TRA-11 [P1] Run supervised live RTSP smoke test for edge_camera_1 (Data/Vision, DataVisionAgent with human supervision)
  Evidence: STWI_RTSP_URL local environment variable, .env.local.example, data/quarantine/rtsp_frames, docs/guides/rtsp_smoke_test_runbook.md, https://linear.app/traffic-agent-assistant/issue/TRA-11/run-supervised-live-rtsp-smoke-test-for-edge-camera-1
  Acceptance: Human operator confirms the RTSP endpoint is approved for STWI testing and sets it only in `STWI_RTSP_URL`.; Local environment uses `.env.local.example` as the template; `.env.local` is not committed.; Live capture is bounded to a small sample, stores sparse frames only in quarantine, and retains no raw video.; Manifest is reviewed to confirm no endpoint, credentials, image base64, or raw video reference is present.; Resulting evidence is deleted, kept in quarantine for privacy review, or converted into approved aggregate-only evidence by a follow-up issue.
  Next: Keep in Human Review; do not add `symphony-approved` because this requires live external service access and human supervision.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-039` / TRA-48 [P1] Prove measured end-to-end SLA on the contract profile (ML/Simulation, ReleaseQaAgent / MLSimulationAgent)
  Evidence: project_contract.json, docs/guides/surrogate_benchmark_evidence.md
  Acceptance: Benchmark uses the 8 CPU / 32 GB RAM / 12-16 GB GPU profile.; Evidence is measured and records load, versions, percentiles, and failures.; Surrogate P99, E2E P95, and hard deadline meet contract or report FAIL.; Raw results remain private.
  Next: Wait for contract-profile hardware and all runtime dependencies.

### Rework

- None

### Merging

- None

### Done

- `STWI-SYM-001` / TRA-31 [P1] Reconcile official vision artifact with current promotion gate (Data/Vision, DataVisionAgent)
  Evidence: data/derived/private/vision_models/official/model_artifact.json, scripts/training/promote_vision_model.py, docs/vision_local_training_runbook.md
  Acceptance: Promotion gate threshold and official artifact metrics are consistent.; Decision is recorded without weakening privacy or aggregate-only constraints.; Detector status is documented as official, provisional, or rejected.
  Next: Detector evidence is closed for the simulation-first demo scope; retain the stricter live-camera promotion gate.
  Checks: Linear readback: TRA-31 is Done on 2026-07-19; no live-camera production claim is implied.
- `STWI-SYM-002` [P1] Close Phase 1 camera aggregate evidence gap (Data/Vision, DataVisionAgent)
  Evidence: docs/01_System_Architecture_Data_Pipeline.md, tests/t1_pipeline, data/derived/private/phase1_mock/gate_p1_report.json
  Acceptance: Aggregate-only outputs are validated for demo camera or recorded RTSP inputs.; No raw video, image base64, or private model artifact is published.; Phase 1 gate report records dataset/model/privacy versions.
  Next: Keep current mock gate evidence; split real camera calibration into a separate task.
  Checks: validate_phase1_gate.py data/derived/private/phase1_mock -> pass; unittest discover -s tests/t1_pipeline -> pass, 35 tests, 1 skipped
- `STWI-SYM-003` / TRA-32 [P1] Replace Phase 2 mock observations with real aggregate dataset (ML/Simulation, MLSimulationAgent)
  Evidence: data/derived/private/phase2_forecast/phase2_readiness_report.json, docs/02_ML_and_Simulation_Specification.md
  Acceptance: Chronological split is recorded.; Scaler is fit only on training split.; Forecast metrics are reported by horizon/node/missing bucket.
  Next: Closed for the approved simulation-first demo scope; retain non-mock aggregate data as a production/pilot gate.
  Checks: Linear readback: TRA-32 is Done on 2026-07-19; simulation-first scope remains explicit.
- `STWI-SYM-006` / TRA-33 [P1] Ingest approved SOP corpus and validate citation coverage (Knowledge/RAG, KnowledgeRagAgent)
  Evidence: docs/03_Knowledge_Base_and_RAG_Design.md, data/derived/private/phase3_knowledge/gate_p3_report.json
  Acceptance: SOP corpus has source registry, effective date, and content hash.; Unsupported claim rate is zero after validator/abstention.; Citation precision target is measured against the evaluation set.
  Next: Approved SOP corpus and citation validation are recorded; preserve source registry and effective-date checks.
  Checks: Linear readback: TRA-33 is Done on 2026-07-19.
- `STWI-SYM-007` / TRA-34 [P1] Switch Phase 3 validation from fake retriever to Qdrant/BGE path (Knowledge/RAG, KnowledgeRagAgent)
  Evidence: src/stwi/t3_knowledge, infra/harness/compose.phase3.yaml, tests/t3_knowledge/test_t3_integration.py
  Acceptance: Qdrant-backed retrieval runs in integration harness.; BGE-m3 embedding path is documented and tested.; Service-dependent skips are reduced or explicitly justified.
  Next: Real Phase 3 Qdrant/BGE-m3 integration harness is complete; retain the service-backed test evidence.
  Checks: Linear readback: TRA-34 is Done on 2026-07-19; Phase 3 integration passed 9/9 checks.
- `STWI-SYM-008` / TRA-35 [P1] Implement production job persistence with Celery and Redis (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/job_store.py, src/stwi/t4_orchestrator/api.py, infra/harness/compose.phase4.yaml
  Acceptance: Jobs are queued and executed by Celery worker.; Progress and events are persisted in Redis.; SSE reconnect does not duplicate execution.
  Next: Celery/Redis persistence slice is complete; production deployment remains a separate blocked gate.
  Checks: Linear readback: TRA-35 is Done on 2026-07-19.
- `STWI-SYM-009` / TRA-7 [P1] Replace provisional fake adapters in production runtime (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/config/runtime.py, src/stwi/t4_orchestrator/orchestrator.py, src/stwi/t3_knowledge/tier3_facade.py, docs/guides/production_adapter_replacement_runbook.md, https://github.com/ukulevi/traffic-agent-assistant/pull/8, 751bdd4, TRA-7
  Acceptance: `STWI_RUNTIME_MODE=production` rejects fake adapters.; Real adapters have documented required environment variables.; Production startup fails closed when services are missing.; No new dependency or external service is added beyond the approved stack.
  Next: Keep the PR #8 merge evidence; TRA-27 owns subsequent Symphony runtime changes.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-011` / TRA-8 [P1] Run full release QA after current refactor changes are settled (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: AGENTS.md, .agents/skills/stwi-release-qa/SKILL.md, git status --short
  Acceptance: Docs validator, contract tests, JS checks, slide static check, and git diff check pass.; Skipped tests and unverified service paths are listed.; No cache/build artifact is staged.
  Next: Keep QA evidence attached to Linear and rerun release QA after the remaining staged batch changes.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-012` [P1] Resolve dirty working tree into reviewable change groups (Orchestrator/API/Release, LeadCoordinator)
  Evidence: git status --short, python scripts/project_management/worktree_intake.py, docs/guides/repository_structure.md, src/stwi/tooling, tests/vision
  Acceptance: Unrelated generated manifests are kept separate from source changes.; Refactor files are reviewed as one coherent change set.; A read-only intake report groups dirty worktree changes before staging.; No user changes are reverted.
  Next: Keep the root workspace changes unstaged; handle tracker snapshots, authored documents and local-only tool output as separate future decisions.
  Checks: Read-only intake on 2026-08-13 found 12 changes on root branch codex/simulation-demo-release; no file was staged, stashed, deleted or rewritten.; Project-management group: four modified Symphony tracker/dispatch files; treat as one stale tracker snapshot and never mix it with current main automatically.; Authored-docs group: five untracked files split into progress assessment, incident-routing plan/spec and showcase-video plan/spec review units.; Local-only group: .codex/, .superpowers/ and tmp/ remain excluded from source commits pending explicit per-path review.; The dirty root contains no runtime/source-code change; user-owned changes remain intact.
- `STWI-SYM-013` / TRA-5 [P1] Complete vision artifact metadata for latency, thresholds, ROI policy, and license/source (Data/Vision, DataVisionAgent)
  Evidence: src/stwi/tooling/vision_training/promotion.py, docs/guides/model_registry_evidence.md, docs/guides/vision_local_training_runbook.md, docs/01_System_Architecture_Data_Pipeline.md
  Acceptance: Official or candidate artifact records latency and threshold evidence.; ROI policy and source/license review are present.; Privacy review remains aggregate-only and does not publish raw images/video.; Promotion validator requires calibration, benchmark, and legal/privacy metadata.
  Next: Keep TRA-5 closed for its bounded validator/docs scope; resolve the current private official-artifact mismatch through STWI-SYM-001 Human Review.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; python -m unittest tests.vision.test_vision_relabel_and_promotion -> pass; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-015` / TRA-38 [P2] Improve detector AP toward current MVP promotion threshold (Data/Vision, DataVisionAgent)
  Evidence: data/derived/private/vision_evals/motoann_best_val_minarea003/roi_ap50_summary.json, scripts/training/train_vision_model.py, tests/vision
  Acceptance: Validation/test evaluation is rerun after label/model improvements.; Motorcycle and transport classes meet the accepted MVP evidence threshold or are explicitly scoped down.; Promotion decision is consistent with STWI-SYM-001.
  Next: Detector scope is resolved for the simulation-first demo; do not promote it as live-camera production evidence.
  Checks: Linear readback: TRA-38 is Done on 2026-07-19.
- `STWI-SYM-016` / TRA-12 [P2] Reconcile readiness scoring and progress evidence (Orchestrator/API/Release, LeadCoordinator)
  Evidence: docs/project_management/symphony/board.json, docs/project_management/symphony/roadmap_intelligence_2026-07-03.md, docs/project_management/symphony/status_report.md
  Acceptance: Progress estimates are derived from board state, gate criteria, and verified checks instead of raw agent-report percentages.; Stale test counts are replaced or explicitly marked stale.; A single readiness summary is available for Symphony/Linear handoff.
  Next: Keep gate-backed readiness scoring and status report current.
  Checks: python scripts/project_management/symphony_report.py -> pass; docs/project_management/symphony/board.md -> regenerated; docs/project_management/symphony/status_report.md -> regenerated
- `STWI-SYM-017` / TRA-13 [P2] Draft auth, RBAC, and tenant-boundary design (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: project_contract.json, docs/04_AI_Agent_Orchestrator_CF_VLA.md, src/stwi/t4_orchestrator/contracts.py, src/stwi/t4_orchestrator/api.py, src/stwi/t4_orchestrator/orchestrator.py, src/stwi/t3_knowledge/query_builder.py, docs/design/auth_rbac_tenant_boundary.md
  Acceptance: Design derives operator identity and tenant context server-side instead of trusting request body fields.; Role boundaries for operator, analyst, admin, and readonly are specified without choosing a new identity provider.; No auth dependency, external IdP, credential storage, or runtime implementation is introduced in TRA-13.
  Next: Keep TRA-13 as completed design evidence; any runtime implementation remains a separate Human Review issue and must not infer an identity provider.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-018` / TRA-14 [P2] Specify observability minimum for trace, logs, and metrics (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: project_contract.json, docs/04_AI_Agent_Orchestrator_CF_VLA.md, docs/05_Implementation_Plan.md, docs/guides/observability_minimum.md
  Acceptance: Required trace_id, job timing, model/data/policy version, status transition, and safety reason fields are listed.; Metric names are specified for job counts, job latency, safety loop outcomes, retrieval latency, and surrogate latency.; Prometheus, OpenTelemetry, or other observability services remain optional future deployment choices until explicitly approved.
  Next: Write the observability minimum as a docs/testable contract proposal before adding tooling.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-019` / TRA-15 [P1] Define project-native model registry evidence format (ML/Simulation, MLSimulationAgent)
  Evidence: project_contract.json, docs/02_ML_and_Simulation_Specification.md, docs/guides/vision_local_training_runbook.md, src/stwi/tooling/vision_training/promotion.py
  Acceptance: Evidence schema covers model version, dataset version, checksum, metrics, calibration, benchmark profile, thresholds, and promotion decision.; The format works for vision, baseline forecast, and surrogate artifacts without requiring MLflow.; Existing promotion and validation paths either produce or validate the required fields.
  Next: Specify the project-native evidence format and map current provisional artifacts to it.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-020` / TRA-16 [P1] Document fail-closed resilience policy for dependency failures (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: project_contract.json, docs/04_AI_Agent_Orchestrator_CF_VLA.md, docs/project_management/symphony/roadmap_intelligence_2026-07-03.md, tests/t4_orchestrator
  Acceptance: Retries, timeout, circuit-breaker-style behavior, and dependency failure classes map to `needs_review`, `failed`, or `expired`.; No runtime path returns an executable action after tool, RAG, TimescaleDB, Qdrant, Celery, Redis, or model failure.; The rejected fail-open wording is replaced with an explicit fail-closed policy and focused tests are identified.
  Next: Write the policy and identify the smallest tests needed before any runtime hardening issue.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest discover -s tests/t4_orchestrator -> pass, 96 tests; git diff --check -> pass
- `STWI-SYM-021` / TRA-17 [P2] Review production deployment options without changing the approved stack (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: project_contract.json, infra/harness, docs/05_Implementation_Plan.md, docs/project_management/symphony/roadmap_intelligence_2026-07-03.md
  Acceptance: Docker Compose production, Kubernetes, and managed-service options are compared as deployment options only.; No Kubernetes, secrets manager, tracing, or model-serving framework is added to active architecture.; The recommendation lists cost, complexity, safety, rollback, and Human Review requirements for a later decision.
  Next: Keep TRA-17 as completed options-review evidence; production deployment implementation remains blocked pending an explicit Human Review selection.
  Checks: python scripts/validation/validate_docs.py -> pass on 2026-07-14; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests on 2026-07-14; node --check slides/js/presentation.js -> pass on 2026-07-14; node --check slides/js/presentation-tools.js -> pass on 2026-07-14; git diff --check -> pass on 2026-07-14
- `STWI-RTSP-001` / TRA-9 [P1] Prepare RTSP source alias and capture guardrails for edge_camera_1 (Data/Vision, DataVisionAgent)
  Evidence: scripts/data_prep/capture_rtsp_frames.py, tests/t1_pipeline/test_capture_rtsp_frames.py, docs/guides/vision_local_training_runbook.md, https://linear.app/traffic-agent-assistant/issue/TRA-9/prepare-rtsp-source-alias-and-capture-guardrails-for-edge-camera-1
  Acceptance: `edge_camera_1` is accepted as a safe source id and unsafe source ids remain rejected.; Capture path continues reading the endpoint only from `STWI_RTSP_URL`.; Command output and manifests do not include the RTSP endpoint, credentials, image base64, or raw video references.; Focused tests cover missing env handling, safe source id, redaction, and fail-closed behavior without opening a live stream.
  Next: Keep done evidence on Linear; live capture remains gated by STWI-RTSP-003.
  Checks: python -m unittest tests.t1_pipeline.test_capture_rtsp_frames -> pass, 14 tests; git diff --cached --check -> pass
- `STWI-RTSP-002` / TRA-10 [P1] Document supervised RTSP-to-quarantine smoke test procedure (Data/Vision, DataVisionAgent)
  Evidence: docs/guides/vision_local_training_runbook.md, docs/01_System_Architecture_Data_Pipeline.md, README.md, docs/guides/rtsp_smoke_test_runbook.md, scripts/data_prep/capture_rtsp_frames.py
  Acceptance: Runbook explains how an operator sets `STWI_RTSP_URL` locally without writing it to repo, Linear, logs, or manifests.; Procedure captures only sparse frames into `data/quarantine/rtsp_frames` and never stores a raw video container.; Procedure lists privacy review, retention, cleanup, and aggregate-only next steps before any frame leaves quarantine.; Procedure includes exact offline verification commands that can run after supervised capture.
  Next: Keep TRA-10 closed as runbook evidence; supervised live execution remains gated by TRA-11 / STWI-RTSP-003.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-023` / TRA-19 [P1] Backfill audit for PR #5 automation and CI stabilization (Orchestrator/API/Release, LeadCoordinator)
  Evidence: https://github.com/ukulevi/traffic-agent-assistant/pull/5, 4557064, TRA-19
  Acceptance: Merged PR #5 scope, checks, and residual benchmark blocker are recorded.; The ticket explicitly identifies its post-merge backfill status.; No private benchmark artifact is published.
  Next: Keep the audit record; future implementation must start from a Linear ticket before any code changes.
  Checks: GitHub fast-guards -> pass; GitHub build-pdf -> pass; PR #5 merged as 4557064
- `STWI-SYM-024` / TRA-20 [P1] Synchronize Symphony board snapshot after PR #5 tracker backfill (Orchestrator/API/Release, LeadCoordinator)
  Evidence: docs/project_management/symphony/board.json, docs/project_management/symphony/board.md, docs/project_management/symphony/status_report.md, https://github.com/ukulevi/traffic-agent-assistant/pull/6, e405a8c, TRA-6, TRA-19, TRA-20
  Acceptance: Board state matches the current Linear state for TRA-6, TRA-19, and TRA-20.; Generated Markdown reports are regenerated from board.json.; No private artifacts, secrets, or unrelated implementation files are changed.
  Next: Keep the merge evidence; TRA-21 owns post-merge tracker synchronization.
  Checks: GitHub fast-guards -> pass; GitHub build-pdf -> pass; PR #6 merged as e405a8c
- `STWI-SYM-025` / TRA-21 [P1] Synchronize Symphony tracker after PR #6 and prepare next dispatch (Orchestrator/API/Release, LeadCoordinator)
  Evidence: docs/project_management/symphony/board.json, docs/project_management/symphony/board.md, docs/project_management/symphony/status_report.md, docs/project_management/symphony/current_dispatch_packet.md, https://github.com/ukulevi/traffic-agent-assistant/pull/7, e9cfc6b, TRA-21
  Acceptance: TRA-20 is recorded as Done with PR #6 merge evidence e405a8c.; TRA-18 is recorded as Canceled because its tracker scope was superseded.; Generated Markdown reports are regenerated from board.json.; The dispatch packet names only TRA-7 and its bounded runtime safety scope.
  Next: Preserve the PR #7 merge evidence and keep the tracker snapshot current for the next bounded dispatch.
  Checks: python scripts/project_management/symphony_report.py -> pass; python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-026` / TRA-23 [P1] Make Tier-4 HTTP API tests mandatory for MVP demo CI (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: tests/t4_orchestrator/test_t4_api_http.py, .github/workflows/stwi-fast-ci.yml, .github/workflows/stwi-manual-qa.yml, project_contract.json
  Acceptance: Fast CI installs the existing orchestrator extra and runs tests.t4_orchestrator.test_t4_api_http.; The 36 HTTP tests run with no dependency-only skips.; No API/runtime/contract/dependency/deployment contract is weakened.
  Next: Keep TRA-23 closed; broader full-suite and phase-gate integrity follow-up is tracked separately in STWI-SYM-031.
  Checks: python scripts/validation/validate_ci_guardrails.py -> pass; python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; python -m unittest tests.t4_orchestrator.test_t4_api_http -> 36 tests; git diff --check -> pass
- `STWI-SYM-027` / TRA-24 [P1] Build minimal operator review dashboard for MVP demo (Orchestrator/API/Release, FrontendAgent)
  Evidence: src/stwi/t4_orchestrator/api.py, src/stwi/t4_orchestrator/static/index.html, src/stwi/t4_orchestrator/static/dashboard.css, src/stwi/t4_orchestrator/static/dashboard.js, docs/guides/mvp_operator_dashboard.md
  Acceptance: A same-origin /demo/ flow allows submit -> observe -> inspect -> approve/reject without raw video or secrets.; needs_review shows candidate_action only; never recommended_action.; Dashboard preserves fail-closed, aggregate-only, and human-approval semantics.
  Next: Keep TRA-24 closed for the minimal dashboard scope; asynchronous lifecycle hardening follows in STWI-SYM-034.
  Checks: python -m unittest tests.t4_orchestrator.test_t4_api_http -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check src/stwi/t4_orchestrator/static/dashboard.js -> pass; git diff --check -> pass
- `STWI-SYM-028` / TRA-25 [P1] Add deterministic offline MVP demo smoke harness and runbook (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: scripts/demo/run_mvp_smoke.py, tests/demo/test_mvp_smoke.py, docs/guides/mvp_demo_runbook.md, README.md
  Acceptance: Offline smoke proof covers POST 202 -> terminal result -> SSE -> approve/reject with applied_by_system=false.; Evidence JSON records statuses, trace IDs, provisional labels, and invariant checks.; No live service, raw video, secret, or production-readiness claim is introduced.
  Next: Keep TRA-25 closed for the deterministic offline smoke scope; expanded terminal-branch coverage follows in STWI-SYM-034 and STWI-SYM-036.
  Checks: python -m unittest tests.demo.test_mvp_smoke -> pass; python scripts/demo/run_mvp_smoke.py -> pass; python -m unittest tests.t4_orchestrator.test_t4_api_http -> 36 tests; python scripts/validation/validate_docs.py -> pass; git diff --check -> pass
- `STWI-SYM-029` / TRA-26 [P1] Run final integrated MVP demo acceptance (Orchestrator/API/Release, ReleaseQaAgent / LeadCoordinator)
  Evidence: docs/project_management/symphony/mvp_demo_acceptance.md, docs/project_management/symphony/board.json, docs/project_management/symphony/board.md, docs/project_management/symphony/status_report.md, docs/project_management/symphony/current_dispatch_packet.md, tests/t4_orchestrator, tests/demo
  Acceptance: TRA-23/24/25 are merged and the release verifier runs from updated main.; Tier-4 HTTP coverage, offline smoke evidence, and /demo/ browser QA are complete and reproducible.; Remaining live RTSP, production persistence, benchmark hardware, SOP corpus, and auth/RBAC gaps remain explicit and do not block acceptance.
  Next: Keep TRA-26 closed as the bounded offline Demo MVP acceptance baseline; post-audit hardening and re-acceptance follow in STWI-SYM-031 through STWI-SYM-036.
  Checks: python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass, 4 tests; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass
- `STWI-SYM-030` / TRA-39 [P1] Reconcile Linear and Symphony state before next dispatch (Orchestrator/API/Release, LeadCoordinator)
  Evidence: docs/project_management/symphony/board.json, docs/project_management/symphony/status_report.md, docs/project_management/symphony/current_dispatch_packet.md, docs/project_management/symphony/blocker_linear_ticket_drafts_2026-07-14.md
  Acceptance: Legacy Linear states and URLs are read back before mirror updates.; Missing legacy backlog issues are created without unsafe dispatch approval.; Superseded placeholders are marked duplicate and completed work is removed from dispatch.; Exactly one dependency-safe next issue is selected.
  Next: Dispatch only STWI-SYM-031 / TRA-40 after tracker verification.
  Checks: Linear readback TRA-5 through TRA-51 -> pass on 2026-07-14; dispatch_linear_issues.py dry-run for legacy and blocker seeds -> pass; new issue readback state/labels/URLs -> pass
- `STWI-SYM-031` / TRA-40 [P1] Repair full-suite, phase-gate, and CI evidence integrity (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: scripts/validation/validate_provisional_phase2_gate.py, scripts/validation/gate_p3_validator.py, tests/t2_forecast/test_phase2_provisional_gate.py, .github/workflows/stwi-fast-ci.yml
  Acceptance: Phase gate CLIs run from repository root without import errors.; The complete lightweight suite has no failing test and preserves measured-evidence semantics.; Gate P3 records executed pass/fail/not-verified evidence instead of literal True assertions.; CI runs the complete lightweight suite with explicit optional-service skips.
  Next: Accepted by the user on 2026-07-15; preserve the verified evidence and hand off the next dependency-safe ticket to TRA-41.
  Checks: Symphony log -> repeated task_complete with last_agent_message null and 1-second active-state continuation; Codex session turn_context -> model stepfun/step-3.7-flash-free; TRA-40 workspace -> Hermes produced an in-scope three-file diff; Symphony process -> stopped on 2026-07-14; Hermes native smoke -> HERMES_NATIVE_OK, provider nous, model stepfun/step-3.7-flash:free; Linear dispatch readback -> hermes-approved was used without codex-symphony-approved; Hermes final rework -> bridge exit 0, no scope violations, and diff reduced to 17 insertions / 7 deletions across three allowed files; Independent review: validate_provisional_phase2_gate.py --help -> pass; Independent review: gate_p3_validator.py --help -> FAIL ModuleNotFoundError: No module named tests; Independent review: tests.t2_forecast.test_phase2_provisional_gate -> pass, 2 tests; Independent review: validate_ci_guardrails.py and git diff --check -> pass; User approved a new two-validator Hermes repair cycle on 2026-07-15; Dispatch attempt was blocked before transmission by tenant data-export policy; no workaround attempted; User explicitly accepted outside-tenant processing risk and confirmed sharing authority/no prohibited data; Final Hermes repair uses repository root parents[2] in both validators; Codex independent CLI help checks -> pass for P2 and P3; Codex focused provisional-gate tests -> pass, 2 tests; Codex full lightweight suite with existing private/mock gate artifacts -> pass, 309 tests, 13 skipped; Codex CI guardrails, release verifier, and git diff --check -> pass; User final acceptance received; Linear TRA-40 moved to Done on 2026-07-15
- `STWI-SYM-032` / TRA-41 [P1] Enforce hard deadline and immutable terminal job states (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/orchestrator.py, src/stwi/t4_orchestrator/job_store.py, src/stwi/t4_orchestrator/api.py
  Acceptance: Blocking dependencies have bounded deadline/cancellation behavior.; Terminal job states are immutable and cannot be overwritten by a late worker.; SSE cannot create a conflicting timeout state.; Timeout/dependency failures never return recommended_action.
  Next: User accepted TRA-41 on 2026-07-15. Preserve the verified bounded deadline and immutable-terminal-state behavior; TRA-42 is the next dependency-safe review item.
  Checks: Codex configuration readback -> model gpt-5.6-terra, model_reasoning_effort medium; Hermes configuration readback -> Nous Step 3.7 Flash, agent.reasoning_effort xhigh; Hermes bridge enforces --allow-external-code-transfer for execution; --no-write remains local-only; Symphony run6 -> Codex app-server Terra Medium completed one turn with 61,832 tokens and no retry after coordinator stop; Codex review -> no workspace diff; worker reported codex-windows-sandbox-setup.exe Access is denied before mandatory reads; Independent review with PYTHONPATH pinned to the TRA-41 workspace source -> 57 targeted/contract tests pass; documentation validation and git diff --check pass; User final acceptance received; Linear TRA-41 moved to Done on 2026-07-15
- `STWI-SYM-033` / TRA-42 [P1] Type and validate scenario actions at the API boundary (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/contracts.py, src/stwi/t4_orchestrator/interfaces.py, docs/04_AI_Agent_Orchestrator_CF_VLA.md
  Acceptance: Scenario actions and request boundaries are typed and validated.; The wire shape remains compatible unless a contract change is separately approved.; Unknown/out-of-range input fails closed with no recommended_action.; Synthetic demo behavior does not claim fabricated causality.
  Next: Scenario action validation is complete; preserve fail-closed boundary behavior.
  Checks: TRA-42 scope narrowed to contracts.py and focused Tier-4 tests; no API route, status, SLA, or documentation contract change; Independent review with PYTHONPATH pinned to the TRA-42 workspace source -> test_t4_contracts pass (34 tests), test_t4_api_http pass (40 tests); validate_docs.py and git diff --check -> pass; Linear TRA-42 moved to In Review on 2026-07-15; waiting for user final approval; Linear readback: TRA-42 is Done on 2026-07-19
- `STWI-SYM-034` / TRA-43 [P1] Fix dashboard async lifecycle and demo terminal branches (Orchestrator/API/Release, FrontendAgent)
  Evidence: src/stwi/t4_orchestrator/static/dashboard.js, tests/demo, docs/guides/mvp_operator_dashboard.md
  Acceptance: UI handles queued/running, SSE reconnect, polling fallback, null result, and network errors.; Failed/expired results cannot be approved.; Demo evidence covers success, safety/OOD review, missing citation, and failure/expiry.; Desktop/mobile/keyboard QA preserves human approval and no actuation.
  Next: Dashboard async lifecycle and demo terminal branches are complete; preserve no-actuation controls.
  Checks: Linear readback: TRA-43 is Done on 2026-07-19.
- `STWI-SYM-035` / TRA-44 [P2] Reconcile API documentation, report claims, and PDF layout (Orchestrator/API/Release, ReleaseQaAgent)
  Evidence: report/main.tex, report/chapters/ch03_kien_truc.tex, report/chapters/ch07_agent.tex, report/chapters/appendix_api.tex
  Acceptance: SLA, normalization, endpoints, examples, and statuses match the contract and API.; No production or measured-SLA claim is made without evidence.; Affected PDF header, endpoint, and table overlaps are removed.; Version/date/status wording changes remain Human Review gated.
  Next: API/report reconciliation and PDF layout QA are complete; retain only evidence-backed SLA wording.
  Checks: Linear readback: TRA-44 is Done on 2026-07-19.
- `STWI-SYM-036` / TRA-45 [P1] Run hardened offline MVP demo acceptance (Orchestrator/API/Release, ReleaseQaAgent / LeadCoordinator)
  Evidence: docs/project_management/symphony/mvp_demo_acceptance.md, tests/demo, tests/t4_orchestrator
  Acceptance: Full lightweight tests and release verifier pass with all skips listed.; Browser and CLI evidence cover the required terminal branches.; Every flow proves no automatic actuation, valid action semantics, trace/version evidence, and no raw video/secrets.; Remaining pilot and production gates stay explicit.
  Next: Hardened offline MVP demo acceptance is complete; production gates remain explicit.
  Checks: Linear readback: TRA-45 is Done on 2026-07-19.
- `STWI-SYM-037` / TRA-46 [P1] Bind production runtime provenance and policy to promoted artifacts (ML/Simulation, MLSimulationAgent / OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/orchestrator.py, src/stwi/app.py, src/stwi/t1_pipeline/local_vision.py
  Acceptance: Production provenance and safety thresholds come from validated promoted artifacts.; Missing/stale/checksum-invalid/uncalibrated/provisional artifacts fail closed.; Demo composition remains isolated and visibly provisional.; Audit versions match the artifacts used for inference.
  Next: Production provenance validation is implemented; calibrated non-mock artifacts remain a deployment gate.
  Checks: Linear readback: TRA-46 is Done on 2026-07-19.
- `STWI-SYM-038` / TRA-47 [P1] Harden T3 service boundary and redact internal errors (Knowledge/RAG, KnowledgeRagAgent)
  Evidence: src/stwi/t3_knowledge/tier3_facade.py, src/stwi/t3_knowledge/qdrant_retriever.py, src/stwi/t3_knowledge/timescale_executor.py
  Acceptance: Production has no embedded dev credential fallback.; Effective-date and hybrid retrieval behavior is service-tested against the pinned client.; SQL remains typed, parameterized, allowlisted, tenant/job filtered, and read-only.; Client errors expose stable codes and trace_id, not raw internals.
  Next: T3 service boundary hardening is complete; retain service-backed test evidence.
  Checks: Linear readback: TRA-47 is Done on 2026-07-19.
- `STWI-SYM-040` / TRA-49 [P1] Implement approved auth, RBAC, and tenant boundary (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: docs/design/auth_rbac_tenant_boundary.md, src/stwi/t4_orchestrator/auth.py
  Acceptance: Tenant/operator request fields cannot elevate privilege or cross tenants.; Approved role boundaries cover POST, GET, SSE, and operator decisions.; Production cannot use anonymous/dev identity behavior.; Negative tenant/role/reconnect/decision tests pass.
  Next: Approved auth/RBAC and tenant boundary implementation is complete.
  Checks: Linear readback: TRA-49 is Done on 2026-07-19.
- `STWI-SYM-041` / TRA-50 [P1] Build the approved production deployment baseline (Orchestrator/API/Release, OrchestratorReleaseAgent / ReleaseQaAgent)
  Evidence: docs/design/production_deployment_options.md, infra/production, scripts/validation/validate_production_deployment.py, tests/contracts/test_production_deployment.py
  Acceptance: Production starts with approved stack components and no provisional/in-memory dependency.; No dev secret, public database port, raw error, or docs-only health check is accepted.; Runtime uses least privilege and reproducibly pinned dependencies/images.; Migration, backup/restore, recovery and rollback have bounded operator commands and explicit external Human Review gates.
  Next: Production topology baseline is merged; real deployment, monitoring, restore drill and SLA evidence remain TRA-51 Human Review gates.
  Checks: TRA-50 production baseline is present on main at f4a1a84.; Static production deployment contract and bounded operations tests pass on 2026-08-03.
- `STWI-SYM-043` [P1] Implement bounded Counterfactual Safety Loop refinement (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/safety_loop.py, tests/t4_orchestrator/test_t4_safety.py, docs/04_AI_Agent_Orchestrator_CF_VLA.md
  Acceptance: Each recorded iteration evaluates a distinct typed candidate.; Only an isolated V/C failure may be refined and at most three candidates are evaluated.; OOD, uncertainty, citation, validation and dependency failures stop immediately and fail closed.; Recommended/candidate action semantics and human approval remain unchanged.
  Next: Human-review the updated report after a XeLaTeX build becomes available.
  Checks: Full unittest discovery passes 414 tests with 6 intentional skips on 2026-08-10.; Offline comprehensive demo passes all 13 mandatory capabilities on 2026-08-10.; Documentation, contract, JavaScript syntax and git whitespace gates pass; PDF visual QA remains unavailable.
- `STWI-SYM-044` [P1] Implement fail-closed production composition entrypoints (Orchestrator/API/Release, OrchestratorReleaseAgent / ReleaseQaAgent)
  Evidence: src/stwi/production_components.py, src/stwi/production.py, src/stwi/production_worker.py, src/stwi/production_health.py, src/stwi/production_migrate.py
  Acceptance: Compose-referenced Python modules exist and reject missing/provisional components.; API/worker use Redis, Celery, RealT3 and promoted artifacts without fake fallback.; Preflight/readiness output is redacted and migration uses a separate approved admin-only process.; External adapters, artifacts, services and deployment remain explicit Human Review gates.
  Next: Keep promoted adapters, artifacts, services and deployment approval in their existing external Human Review gates.
  Checks: Full unittest discovery passes 414 tests with 6 intentional skips on 2026-08-10.; Production deployment validator passes on 2026-08-10.; Docker Compose operations profile config renders successfully with placeholder QA values on 2026-08-10.
- `STWI-SYM-045` [P1] Deliver comprehensive hybrid demo and presenter guidance (Orchestrator/API/Release, ReleaseQaAgent / LeadCoordinator)
  Evidence: src/stwi/demo, scripts/demo/run_mvp_smoke.py, docs/guides/mvp_demo_runbook.md, docs/project_management/symphony/mvp_demo_acceptance.md
  Acceptance: Offline profile covers all 17 catalog capabilities with a versioned atomic manifest.; Services profile preserves pass/fail/not_verified without mock substitution.; Dashboard and the 8-10 minute showcase cover success, refinement, fail-closed, audit and recovery.; Browser, frontend, docs, report and release QA evidence is recorded without production or SLA overclaim.
  Next: Keep the accepted demo synthetic-only; retain RTSP, contract-profile GPU/SLA and production deployment as separate Human Review gates.
  Checks: Offline profile passes all 17 mandatory capabilities and writes schema version 1.0 aggregate-only evidence on 2026-08-13.; Full Python suite passes 476 tests with 11 intentional skips; frontend interaction suite passes 81 tests on 2026-08-13.; Services profile honestly reports Docker fail plus Redis/Celery, Qdrant and TimescaleDB not_verified; no mock substitution.; Browser QA passes for the input-first dashboard at 1280 px and 390 px, the fail-closed provisional runtime, and the 31-slide presentation without console errors or horizontal overflow.; PR #51 fast-guards and build-pdf pass; the 85-page XeLaTeX artifact and affected pages were visually inspected before merge e760ca396e9da70420e2b428562d2c57ba0b0940.
- `STWI-SYM-046` / TRA-62 [P2] Reorder operator workflow and align accessibility order (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: docs/superpowers/specs/2026-08-10-stwi-incident-routing-map-design.md, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md, src/stwi/t4_orchestrator/static/index.html
  Acceptance: Input, lifecycle, result, evidence and operator review follow one canonical DOM, visual and tab order.; Desktop and mobile expose input as the first meaningful workspace region.; Focus progression, decision policy and non-executable semantics remain unchanged.
  Next: Merged on main; continue with the independent topology ticket STWI-SYM-049 / TRA-61.
  Checks: Hermes Rework 2 returned Human Review with 9 allowed files and no scope violation on 2026-08-10.; Independent Python dashboard tests pass: 20/20.; Independent frontend tests pass: 20/20; dashboard-view.js syntax passes.; validate_docs.py and project contract tests pass; git diff --check passes.; Browser QA passes at 1280x720 and 390x844 with canonical vertical workspace order, no horizontal overflow, and no console warning/error.; Linear readback: TRA-62 is Done on 2026-08-10.; PR #44 passed fast-guards and build-pdf, then admin squash-merged as da76e141e5ec6c87768b97902d56f0d3e631b535 on 2026-08-10; superseded draft PR #43 was closed.
- `STWI-SYM-047` / TRA-59 [P1] Add typed IncidentVector and contract validation (Orchestrator/API/Release, OrchestratorReleaseAgent / LeadCoordinator)
  Evidence: project_contract.json, docs/superpowers/specs/2026-08-10-stwi-incident-routing-map-design.md, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md
  Acceptance: IncidentVector is optional, typed, event-specific and scoped to exactly one allowlisted node for the MVP.; Free-text descriptions cannot select simulation behavior.; Existing API, status, tensor, action and fail-closed invariants remain unchanged.; Contract-risk changes receive Human Review before merge.
  Next: Merged through PR #47; retain the typed contract as the foundation for incident and routing work.
  Checks: Linear readback: TRA-59 is Done on 2026-08-13.; PR #47 is attached to TRA-59 and merged on main.
- `STWI-SYM-048` / TRA-60 [P2] Decouple demo incident profiles from node identity (ML/Simulation, MLSimulationAgent)
  Evidence: src/stwi/t4_orchestrator/demo_adapters.py, src/stwi/t4_orchestrator/static/dashboard.js, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md
  Acceptance: Every canonical incident can run at every allowlisted demo node.; Incident profile selection uses typed event fields, not node ID or free text.; The same immutable incident survives every safety refinement call.
  Next: Merged through PR #48; use the event/node cross-product as the canonical synthetic demo behavior.
  Checks: Linear readback: TRA-60 is Done on 2026-08-13.; PR #48 is attached to TRA-60 and merged on main.
- `STWI-SYM-049` / TRA-61 [P1] Define versioned synthetic 4x5 topology and routing graph (Data/Vision, DataVisionAgent / MLSimulationAgent)
  Evidence: src/stwi/t1_pipeline/mock_data.py, docs/superpowers/specs/2026-08-10-stwi-incident-routing-map-design.md, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md
  Acceptance: The synthetic grid has 20 stable nodes, unique coordinates and validated directed edges.; Routing graph and GCN adjacency remain separate versioned artifacts.; Authorized network context fails closed and makes no real-geography claim.
  Next: Merged through PR #45; retain the versioned synthetic topology as the authorized routing/map source.
  Checks: Linear readback: TRA-61 moved to In Progress with hermes-approved on 2026-08-10.; User approved ticket-specific external transfer of nine bounded source/test/docs files; no secrets, raw video, private data, model weights, .env files, logs or project_contract.json are included.; Linear readback: TRA-61 is Done on 2026-08-13; PR #45 is attached and merged on main.
- `STWI-SYM-050` / TRA-66 [P2] Add pinned offline-safe Leaflet network view (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/static, docs/superpowers/specs/2026-08-10-stwi-incident-routing-map-design.md, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md
  Acceptance: Leaflet 1.9.4 is vendored with its license and loads without external tiles, fonts or analytics.; L.CRS.Simple renders the visibly synthetic topology and stays synchronized with node selection.; An accessible table remains usable when the map is unavailable.
  Next: Merged through PR #46; keep the Leaflet network view local, tile-free and synthetic-only.
  Checks: Linear readback: TRA-66 is Done on 2026-08-13.; PR #46 is attached to TRA-66 and merged on main.
- `STWI-SYM-051` / TRA-65 [P1] Generate and evaluate bounded local diversion candidates (ML/Simulation, MLSimulationAgent / OrchestratorReleaseAgent)
  Evidence: docs/superpowers/specs/2026-08-10-stwi-incident-routing-map-design.md, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md, src/stwi/t4_orchestrator/safety_loop.py
  Acceptance: At most three deterministic directed simple paths avoid the incident node and use valid graph edges.; Every recommendation has typed evaluation evidence and matching model, data and topology versions.; Invalid, uncertain, OOD, unsafe or unevaluated paths fail closed and never become executable actions.; Safety behavior receives Human Review before merge.
  Next: Merged through PR #49; retain candidate-specific evidence and fail-closed route evaluation.
  Checks: Linear readback: TRA-65 is Done on 2026-08-13.; PR #49 is attached to TRA-65 and merged on main.
- `STWI-SYM-052` / TRA-63 [P2] Integrate route evidence into dashboard and operator review (Orchestrator/API/Release, OrchestratorReleaseAgent)
  Evidence: src/stwi/t4_orchestrator/static/dashboard-state.js, src/stwi/t4_orchestrator/static/dashboard-view.js, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md
  Acceptance: Map and fallback table render one validated route view-model with matching IDs and metrics.; Needs-review routes remain candidates and cannot be approved.; Failed and expired jobs expose no action or route overlay.; Responsive, keyboard, non-color and focus behavior pass frontend and browser checks.
  Next: Merged through PR #50; use the shared validated route view-model for map, table and operator review.
  Checks: Linear readback: TRA-63 is Done on 2026-08-13.; PR #50 is attached to TRA-63 and merged on main.
- `STWI-SYM-053` / TRA-64 [P2] Complete integrated QA and synchronize release artifacts (Orchestrator/API/Release, ReleaseQaAgent / LeadCoordinator)
  Evidence: scripts/demo/run_mvp_smoke.py, docs/guides/mvp_demo_runbook.md, docs/superpowers/plans/2026-08-10-stwi-incident-routing-map.md
  Acceptance: Comprehensive smoke covers baseline, five independent incidents, route success, needs-review and failure branches.; Runbook, report, slides and Symphony state describe the same synthetic workflow without production overclaim.; Full Python, frontend, docs, PDF and visual release QA evidence is recorded.; No local companion state, build output, secret or private evidence is staged.
  Next: Maintain the synthetic-only demo boundary; production service, latency and field-accuracy gates remain separate evidence work.
  Checks: Linear readback: TRA-64 is Done and all seven prerequisite tickets are Done on 2026-08-13.; Offline smoke passes all 17 capabilities; full Python 476 tests pass with 11 intentional skips and frontend 81 tests pass.; PR #51 fast-guards and build-pdf pass at head 237564a; the 85-page CI PDF and affected pages were visually inspected with no remaining overlap or malformed command.; Browser QA covers the input-first responsive dashboard, fail-closed runtime and four synchronized slides without console errors or horizontal overflow.

### Canceled

- `STWI-SYM-022` / TRA-18 [P2] Finalize Symphony automation evidence and release QA snapshot (Orchestrator/API/Release, ReleaseQaAgent / LeadCoordinator)
  Evidence: docs/project_management/symphony/board.json, docs/project_management/symphony/board.md, docs/project_management/symphony/status_report.md, docs/project_management/symphony/current_dispatch_packet.md, docs/project_management/symphony/hermes_orchestrator_handoff.md, docs/project_management/symphony/agent_routing.json, docs/project_management/symphony/hermes_worker_prompts.md, scripts/project_management/symphony_report.py, scripts/project_management/hermes_runner_bridge.py
  Acceptance: All modified/untracked workflow artifacts under `docs/project_management/symphony/**` are reviewed, grouped, and committed as a single coherent change set.; Generated `board.md`, `status_report.md`, and Hermes runner artifacts are regenerated and verified against current Linear state.; No secrets, `.env`, raw video, private weights, or private data are committed.; The ticket includes a final report with Result, Changed files, Checks, Contract/artifact impact, Risks/blockers, and Recommended next state.
  Next: Superseded by TRA-20 and TRA-21; do not dispatch a second tracker snapshot task.
  Checks: python scripts/project_management/symphony_report.py -> pass; python scripts/project_management/symphony_report.py --write-markdown docs/project_management/symphony/board.md -> pass; python scripts/project_management/symphony_report.py --write-markdown docs/project_management/symphony/status_report.md -> pass; python scripts/validation/validate_docs.py -> pass; python -m unittest tests.contracts.test_project_contract -> pass; node --check slides/js/presentation.js -> pass; node --check slides/js/presentation-tools.js -> pass; git diff --check -> pass

### Duplicate

- `STWI-SYM-010` [P2] Build operator dashboard or explicitly scope it out of demo (Orchestrator/API/Release, FrontendAgent)
  Evidence: docs/05_Implementation_Plan.md, slides/sections/07_01_multiagent.html, slides/sections/09_01_kpi.html
  Acceptance: Dashboard scope is approved by user.; If implemented, UI shows job status, citations, warnings, versions, trace_id, and approval state.; If deferred, docs and demo script clearly state the limitation.
  Next: Superseded by STWI-SYM-027 / TRA-24, which delivered the bounded minimal dashboard and is Done.
