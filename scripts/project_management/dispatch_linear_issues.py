"""Dispatch safe STWI Symphony work items to Linear.

The script reads LINEAR_API_KEY from the global Symphony env file outside this
repository and never prints the token. It creates a small set of low-risk,
Todo-state Linear issues that match WORKFLOW.md safety filters.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ENV_PATH = Path(r"C:\Users\PC\.codex\symphony\.env")
PROJECT_SLUG = "traffic-agent-assistant-811a1da43eac"
API_URL = "https://api.linear.app/graphql"

DRY_RUN = "--dry-run" in sys.argv
SEED_FILTER = next(
    (
        {
            seed.strip()
            for seed in arg.split("=", 1)[1].split(",")
            if seed.strip()
        }
        for arg in sys.argv[1:]
        if arg.startswith("--seeds=")
    ),
    None,
)

ISSUES = [
    {
        "seed": "STWI-SYM-001",
        "title": "Reconcile official vision artifact with current promotion gate",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:vision",
            "phase:1",
            "task:review",
            "needs-human-review",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "promotion evidence and decision record only; do not lower the "
            "mAP50 gate, publish private weights, or retain raw video"
        ),
        "criteria": [
            "Compare the current official artifact with the active promotion validator and mAP50 >= 0.85 gate.",
            "Record a Human Review decision to keep official, downgrade to provisional/rejected, or require retraining.",
            "Do not weaken privacy, aggregate-only processing, checksum, calibration, benchmark, or legal/source evidence requirements.",
            "Keep any retraining work in STWI-SYM-015 and camera-path validation in STWI-SYM-014.",
        ],
    },
    {
        "seed": "STWI-SYM-003",
        "title": "Replace Phase 2 mock observations with real aggregate dataset",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:ml",
            "lane:simulation",
            "phase:2",
            "task:review",
            "needs-human-review",
        ],
        "owner": "MLSimulationAgent",
        "scope": (
            "dataset selection, manifests, validators, and T2 evidence; no raw "
            "video, private-data publication, or contract shape change"
        ),
        "criteria": [
            "Use approved five-minute aggregate data with fixed 20-node order and no raw-video retention.",
            "Record chronological splits and scenario-family leakage checks.",
            "Fit scalers on the training split only and preserve ratio/cyclical features.",
            "Report forecast metrics by horizon, node, and missing-data bucket before STWI-SYM-004 starts.",
        ],
    },
    {
        "seed": "STWI-SYM-004",
        "title": "Rerun surrogate calibration and OOD thresholds on non-mock validation data",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:simulation",
            "phase:2",
            "task:validate",
        ],
        "owner": "MLSimulationAgent",
        "scope": (
            "surrogate calibration, OOD evidence, validators, and focused tests; "
            "no SLA, tensor, or safety-threshold weakening"
        ),
        "criteria": [
            "Start only after STWI-SYM-003 provides an approved non-mock chronological dataset.",
            "Calibrate uncertainty and OOD thresholds on held-out validation data with isolated scenario families.",
            "High uncertainty or OOD returns needs_review and never recommended_action.",
            "Retrieved cases remain evidence only and are never blended into online model input.",
        ],
    },
    {
        "seed": "STWI-SYM-006",
        "title": "Ingest approved SOP corpus and validate citation coverage",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:rag",
            "lane:legal",
            "phase:3",
            "task:review",
            "legal-review",
            "needs-human-review",
        ],
        "owner": "KnowledgeRagAgent",
        "scope": (
            "approved SOP source registry, ingestion, citation validation, and "
            "evaluation evidence only"
        ),
        "criteria": [
            "Start only after a human legal reviewer approves the SOP sources.",
            "Record source registry, effective date, content hash, jurisdiction, and supersession status.",
            "Unsupported claim rate is zero after validator/abstention and citation precision is measured.",
            "Do not replace or weaken the required Laws 35/2024/QH15 and 36/2024/QH15 corpus.",
        ],
    },
    {
        "seed": "STWI-SYM-007",
        "title": "Switch Phase 3 validation from fake retriever to Qdrant/BGE path",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:rag",
            "phase:3",
            "task:validate",
            "external-service",
        ],
        "owner": "KnowledgeRagAgent",
        "scope": (
            "T3 Qdrant/BGE-m3 and Timescale read-only integration harness, "
            "focused tests, and Gate P3 evidence"
        ),
        "criteria": [
            "Gate P3 cannot pass on FakeRetriever or literal unexecuted checks.",
            "Qdrant/BGE-m3 retrieval, effective-date filtering, structured citations, and read-only Timescale queries run in the integration harness.",
            "Service-dependent skips are removed or left as explicit Human Review blockers.",
            "Live service execution requires external-service-approved and must not expose credentials or private corpus content.",
        ],
    },
    {
        "seed": "STWI-SYM-008",
        "title": "Implement production job persistence with Celery and Redis",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:api",
            "phase:4",
            "task:refactor",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "Celery worker, Redis job/event persistence, SSE reconnect, and "
            "focused Tier-4 tests within the approved stack"
        ),
        "criteria": [
            "Start after the hard-deadline and terminal-state contract is implemented and reviewed.",
            "Jobs execute through Celery and progress/events persist in Redis across API restart.",
            "SSE reconnect is idempotent and never duplicates execution or overwrites a terminal state.",
            "Dependency, timeout, and persistence failures remain fail closed with no executable action.",
        ],
    },
    {
        "seed": "STWI-SYM-014",
        "title": "Validate recorded-camera or RTSP calibration and aggregate extraction path",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:data",
            "lane:vision",
            "phase:1",
            "task:validate",
            "needs-human-review",
            "external-service",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "human-approved recorded-camera or supervised RTSP calibration, "
            "tracking quality, and aggregate-only evidence"
        ),
        "criteria": [
            "Use only an approved source alias and keep endpoints/credentials outside repository, Linear, logs, and manifests.",
            "Record ROI/homography calibration and tracking quality for the approved demo input.",
            "Produce only five-minute aggregates that preserve the project data contract and stable node order.",
            "Retain no raw video; sparse quarantine frames require privacy review and bounded cleanup.",
        ],
    },
    {
        "seed": "STWI-SYM-015",
        "title": "Improve detector AP toward current MVP promotion threshold",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:vision",
            "phase:1",
            "task:validate",
            "needs-human-review",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "human-approved private training/evaluation workflow and promotion "
            "evidence; no unattended access to private weights or datasets"
        ),
        "criteria": [
            "Run only after STWI-SYM-001 selects retraining rather than downgrade/rejection.",
            "Rerun validation/test evaluation after label or model improvements with class-level evidence.",
            "Meet the accepted mAP50 gate or explicitly remain provisional; do not lower the gate silently.",
            "Keep privacy, source/license, calibration, benchmark, checksum, and aggregate-only evidence complete.",
        ],
    },
    {
        "seed": "STWI-SYM-030",
        "title": "Reconcile Linear and Symphony state before next dispatch",
        "state": "Done",
        "labels": ["stwi-agent", "lane:qa", "lane:release", "task:review"],
        "owner": "LeadCoordinator",
        "scope": "docs/project_management/symphony tracker artifacts only",
        "criteria": [
            "Read back all linked legacy Linear states and URLs before editing the mirror.",
            "Create missing legacy backlog issues without granting unsafe Symphony approval.",
            "Mark superseded placeholders duplicate and remove completed work from the dispatch packet.",
            "Select exactly one dependency-safe next issue for Symphony.",
        ],
        "checks": [
            "python scripts/project_management/symphony_report.py",
            "python scripts/project_management/hermes_runner_bridge.py --no-write",
            "python scripts/validation/validate_docs.py",
            "git diff --check",
        ],
        "expected_state": "Done after Linear readback and local mirror verification",
        "gap_check": "complete",
    },
    {
        "seed": "STWI-SYM-031",
        "title": "Repair full-suite, phase-gate, and CI evidence integrity",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:qa",
            "task:validate",
            "needs-human-review",
        ],
        "owner": "ReleaseQaAgent",
        "scope": "phase-gate validators, their tests, and STWI CI workflows only",
        "dependencies": ["STWI-SYM-030 / tracker reconciliation is Done"],
        "criteria": [
            "Phase 2 and Phase 3 gate CLIs run from repository root without import-path errors.",
            "The complete lightweight test suite has no failing test and measured evidence is not confused with simulated evidence.",
            "Gate P3 records measured pass/fail/not-verified results instead of literal unexecuted True values.",
            "CI runs the complete lightweight suite with an explicit optional-service skip policy.",
        ],
        "checks": [
            "python scripts/validation/validate_provisional_phase2_gate.py --help",
            "python scripts/validation/gate_p3_validator.py --help",
            "python -m unittest discover -s tests -v",
            "python scripts/validation/validate_ci_guardrails.py",
            "powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked for review after in-scope Hermes rework retained broad formatting churn",
    },
    {
        "seed": "STWI-SYM-032",
        "title": "Enforce hard deadline and immutable terminal job states",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:api",
            "phase:4",
            "task:refactor",
            "contract-risk",
            "reasoning:high",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": "Tier-4 orchestrator, API, job store, interfaces, tests, and DOC-04",
        "dependencies": ["STWI-SYM-031 is accepted"],
        "criteria": [
            "Blocking model/RAG/safety dependencies have bounded deadline or cancellation behavior.",
            "Allowed job transitions are explicit and terminal states cannot be overwritten by a late worker.",
            "SSE observes the job state without creating a conflicting timeout state.",
            "Timeout and dependency failures never return recommended_action.",
        ],
        "checks": [
            "python -m unittest tests.t4_orchestrator.test_t4_deadline_state_machine",
            "python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries",
            "python -m unittest tests.t4_orchestrator.test_t4_api_http",
            "python -m unittest tests.contracts.test_project_contract",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "inferred; implementation strategy requires high-reasoning review",
    },
    {
        "seed": "STWI-SYM-033",
        "title": "Type and validate scenario actions at the API boundary",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:api",
            "phase:4",
            "task:refactor",
            "needs-human-review",
            "contract-risk",
            "reasoning:high",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": "typed Tier-4 contracts, adapters, focused tests, and synchronized API artifacts",
        "criteria": [
            "Candidate action, nodes, horizons, scenario time, tenant context, and policy values are typed and boundary-validated.",
            "The accepted JSON shape remains wire-compatible unless a separate contract change is approved.",
            "Unknown nodes/fields and out-of-range values fail closed with no recommended_action.",
            "Demo behavior does not claim a fabricated causal relationship from synthetic data.",
        ],
        "checks": [
            "python -m unittest tests.t4_orchestrator.test_t4_request_validation",
            "python -m unittest tests.t4_orchestrator.test_t4_contracts",
            "python -m unittest tests.t4_orchestrator.test_t4_api_http",
            "python scripts/validation/validate_docs.py",
            "git diff --check",
        ],
        "expected_state": "Human Review before implementation approval",
        "gap_check": "inferred; typed action variants need explicit review",
    },
    {
        "seed": "STWI-SYM-034",
        "title": "Fix dashboard async lifecycle and demo terminal branches",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:frontend",
            "lane:api",
            "phase:4",
            "task:refactor",
        ],
        "owner": "FrontendAgent",
        "scope": "demo static UI, bounded API/demo adapters, demo tests, and runbooks",
        "dependencies": ["STWI-SYM-032", "approved STWI-SYM-033"],
        "criteria": [
            "The UI waits through queued/running via SSE reconnect or bounded polling fallback without null-result crashes.",
            "Approve/reject is enabled only for reviewable terminal results; failed/expired cannot be approved.",
            "Provisional evidence covers succeeded, safety/OOD review, missing citation, and failed/expired branches.",
            "Desktop/mobile/keyboard QA shows trace, versions, uncertainty/OOD, citations, and no automatic actuation.",
        ],
        "checks": [
            "python -m unittest tests.demo.test_mvp_smoke",
            "python -m unittest tests.t4_orchestrator.test_t4_api_http",
            "python scripts/demo/run_mvp_smoke.py",
            "node --check src/stwi/t4_orchestrator/static/dashboard.js",
            "git diff --check",
        ],
        "expected_state": "Human Review after browser QA",
        "gap_check": "blocked on dependencies",
    },
    {
        "seed": "STWI-SYM-035",
        "title": "Reconcile API documentation, report claims, and PDF layout",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:release",
            "lane:qa",
            "phase:4",
            "task:review",
            "needs-human-review",
        ],
        "owner": "ReleaseQaAgent",
        "scope": "DOC-04, demo guides, report/API appendix, affected slides, and release notes",
        "dependencies": ["STWI-SYM-033", "STWI-SYM-034"],
        "criteria": [
            "SLA, normalization, endpoints, examples, and statuses match the contract and implemented API.",
            "No production or measured-SLA claim appears without evidence; version/date/status wording requires Human Review.",
            "Header, endpoint, and appendix table overlaps are removed on affected PDF pages.",
            "Report, slides, and dashboard guide retain provisional, human-approval, and no-actuation wording.",
        ],
        "checks": [
            "python scripts/validation/validate_docs.py",
            "python -m unittest tests.contracts.test_project_contract",
            "python scripts/validation/validate_slides_static.py",
            "powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "inferred; cover status wording requires approval",
    },
    {
        "seed": "STWI-SYM-036",
        "title": "Run hardened offline MVP demo acceptance",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:qa",
            "lane:release",
            "phase:4",
            "task:qa",
            "needs-human-review",
        ],
        "owner": "ReleaseQaAgent and LeadCoordinator",
        "scope": "acceptance evidence and Symphony tracker artifacts only; no feature implementation",
        "dependencies": ["STWI-SYM-031 through STWI-SYM-035 accepted"],
        "criteria": [
            "Full lightweight tests and release verifier pass with every skip listed.",
            "Browser and CLI evidence cover success, safety/OOD review, missing citation, and failure/expiry.",
            "Every flow records no automatic actuation, valid action semantics, trace/version evidence, and no raw video or secrets.",
            "Acceptance lists all remaining real data/model/service/benchmark/auth/deployment gates.",
        ],
        "checks": [
            "python -m unittest discover -s tests -v",
            "python scripts/demo/run_mvp_smoke.py",
            "python scripts/validation/validate_slides_static.py",
            "powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked on dependencies",
    },
    {
        "seed": "STWI-SYM-037",
        "title": "Bind production runtime provenance and policy to promoted artifacts",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:ml",
            "lane:simulation",
            "lane:api",
            "phase:4",
            "task:refactor",
            "contract-risk",
            "reasoning:high",
        ],
        "owner": "MLSimulationAgent and OrchestratorReleaseAgent",
        "scope": "runtime composition, artifact loaders/registry, focused tests, and runbooks",
        "dependencies": ["STWI-SYM-003", "STWI-SYM-004", "STWI-SYM-007", "STWI-SYM-013"],
        "criteria": [
            "Production loads version, checksum, data version, calibration/OOD thresholds, and promotion status from validated artifacts.",
            "Missing, stale, checksum-mismatched, uncalibrated, or provisional artifacts fail closed.",
            "Provisional/demo composition remains isolated and visibly labeled.",
            "Audit records match the exact artifacts used for inference.",
        ],
        "checks": [
            "python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries",
            "python -m unittest tests.vision.test_vision_relabel_and_promotion",
            "python -m unittest tests.t2_forecast.test_surrogate_safety",
            "python -m unittest tests.contracts.test_project_contract",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked on promoted artifacts",
    },
    {
        "seed": "STWI-SYM-038",
        "title": "Harden T3 service boundary and redact internal errors",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:rag",
            "lane:legal",
            "lane:api",
            "phase:3",
            "task:refactor",
            "external-service",
            "legal-review",
        ],
        "owner": "KnowledgeRagAgent",
        "scope": "T3 facade, Qdrant retriever, Timescale executor/query builder, tests, harness, and DOC-03",
        "dependencies": ["STWI-SYM-007"],
        "criteria": [
            "Production requires environment/approved secret configuration and has no embedded dev credential fallback.",
            "Effective-date filtering and hybrid retrieval use pinned-client-supported APIs proven by integration tests.",
            "SQL stays typed, parameterized, allowlisted, tenant/job filtered, and read-only.",
            "Client failures expose stable error codes and trace_id rather than raw exception, DSN, SQL, or service text.",
        ],
        "checks": [
            "python -m unittest discover -s tests/t3_knowledge -v",
            "docker compose -f infra/harness/compose.phase3.yaml config --quiet",
            "python scripts/validation/gate_p3_validator.py",
            "python scripts/validation/validate_docs.py",
            "git diff --check",
        ],
        "expected_state": "Human Review after service-backed tests",
        "gap_check": "blocked on external-service approval",
    },
    {
        "seed": "STWI-SYM-039",
        "title": "Prove measured end-to-end SLA on the contract profile",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:qa",
            "lane:release",
            "lane:ml",
            "phase:4",
            "task:validate",
            "needs-human-review",
            "external-service",
        ],
        "owner": "ReleaseQaAgent and MLSimulationAgent",
        "scope": "benchmark harness/docs and private ignored benchmark output only",
        "dependencies": ["STWI-SYM-005", "STWI-SYM-008", "STWI-SYM-037", "STWI-SYM-038"],
        "criteria": [
            "Measure on 8 CPU cores, 32 GB RAM, and 12-16 GB GPU VRAM with recorded versions and representative load.",
            "Evidence is measured and records warmup/runs, payload, concurrency, p50/p95/p99, and failures.",
            "Surrogate P99 < 500 ms, E2E P95 <= 30 seconds, and hard deadline/P99 <= 180 seconds or report FAIL without threshold weakening.",
            "Keep raw results private and publish only reviewed aggregate claims.",
        ],
        "checks": [
            "python scripts/validation/validate_surrogate_benchmark_evidence.py",
            "python scripts/validation/validate_docs.py",
            "python -m unittest tests.contracts.test_project_contract",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked until contract-profile hardware is available",
    },
    {
        "seed": "STWI-SYM-040",
        "title": "Implement approved auth, RBAC, and tenant boundary",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:api",
            "phase:4",
            "task:refactor",
            "needs-human-review",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": "must be bounded from the approved TRA-13 design; no inferred provider or dependency",
        "dependencies": ["Human-approved TRA-13 / STWI-SYM-017 design"],
        "criteria": [
            "Request-body tenant/operator values cannot elevate privilege or cross tenant boundaries.",
            "Approved role boundaries apply to POST, GET, SSE, and operator-decision endpoints.",
            "Auth failures are auditable and redact secrets; anonymous/dev behavior is impossible in production.",
            "Negative tests cover tenant spoofing, wrong roles, SSE reconnect, and decision submission.",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked until implementation mechanism is explicitly approved",
    },
    {
        "seed": "STWI-SYM-041",
        "title": "Build the approved production deployment baseline",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:release",
            "lane:api",
            "phase:4",
            "task:refactor",
            "needs-human-review",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent and ReleaseQaAgent",
        "scope": "bounded after deployment-option approval; expected infra, runbooks, health/readiness, and deployment tests",
        "dependencies": ["STWI-SYM-008", "STWI-SYM-018", "approved STWI-SYM-021", "STWI-SYM-038", "STWI-SYM-040"],
        "criteria": [
            "Production starts with only approved stack components and no provisional/in-memory adapter or store.",
            "No dev secret, public database port, raw exception, or docs-only health check is production evidence.",
            "Processes use least privilege and reproducibly pinned dependencies/images without a new platform.",
            "Backup/restore, migration, restart recovery, monitoring, retention, rate limit, and rollback have executable evidence or Human Review gates.",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked on deployment and auth approvals",
    },
    {
        "seed": "STWI-SYM-042",
        "title": "Run final production release-readiness QA",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:qa",
            "lane:release",
            "task:qa",
            "needs-human-review",
        ],
        "owner": "ReleaseQaAgent and LeadCoordinator",
        "scope": "release evidence, approved runbooks, tracker mirror, and private ignored results only",
        "dependencies": ["all open P1 vision/data/ML/RAG/runtime/SLA/auth/deployment gates"],
        "criteria": [
            "Attach exact test, service, security, SLA, browser, PDF/slide, recovery, backup/restore, and rollback evidence.",
            "Production mode rejects every provisional, missing, uncalibrated, checksum-invalid, or expired artifact/dependency.",
            "No open P1 blocker, unexplained service skip, privacy breach, invalid citation, automatic actuation, or executable needs_review action remains.",
            "Return a Human Review go/no-go recommendation without merging, releasing, or deploying automatically.",
        ],
        "checks": [
            "python -m unittest discover -s tests -v",
            "python scripts/validation/validate_docs.py",
            "python scripts/validation/validate_slides_static.py",
            "powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1 -BuildPdf",
            "git diff --check",
        ],
        "expected_state": "Human Review",
        "gap_check": "blocked until every dependency is reviewable",
    },
    {
        "seed": "STWI-SYM-013",
        "title": (
            "Complete vision artifact metadata for latency, thresholds, "
            "ROI policy, and license/source"
        ),
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:vision",
            "phase:1",
            "task:validate",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "code/docs/tests only; do not read private weights, raw frames, "
            "or data/derived/private"
        ),
        "criteria": [
            "Detector metadata records latency, thresholds, ROI policy, class mapping, model/data version, and source/license notes.",
            "Promotion criteria remain consistent with scripts/training/promote_vision_model.py or the current promotion script location if renamed.",
            "No private weights, raw images, base64 images, or secret files are read or logged.",
            "Run focused validators/tests and report skipped private-artifact checks explicitly.",
        ],
    },
    {
        "seed": "STWI-SYM-005",
        "title": "Prove surrogate P99 under contract benchmark profile",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:simulation",
            "phase:2",
            "task:qa",
        ],
        "owner": "MLSimulationAgent",
        "scope": (
            "src/stwi/t2_forecast, scripts/validation, scripts/training, "
            "tests/t2_forecast, docs references"
        ),
        "criteria": [
            "Find or add a local/offline benchmark or report path for surrogate latency without requiring external services.",
            "Compare measured or recorded P99 against the contract target of surrogate P99 < 500 ms.",
            "If hardware benchmark cannot be run in the Symphony workspace, stop with Human Review and list exact missing evidence.",
            "Do not alter SLA thresholds or mark provisional results as production-ready.",
        ],
    },
    {
        "seed": "STWI-SYM-009",
        "title": "Replace provisional fake adapters in production runtime",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:api",
            "phase:4",
            "task:validate",
        ],
        "owner": "OrchestratorAgent",
        "scope": (
            "src/stwi/t4_orchestrator, src/stwi/config, "
            "tests/t4_orchestrator, DOC-04 references"
        ),
        "criteria": [
            "Inventory fake/provisional adapters reachable from production runtime paths.",
            "Replace only with fail-closed local implementations or add guards that prevent accidental production execution.",
            "Preserve statuses queued, running, succeeded, needs_review, failed, expired and recommended_action/candidate_action semantics.",
            "Run focused orchestrator/API tests and contract checks relevant to the touched files.",
        ],
    },
    {
        "seed": "STWI-SYM-011",
        "title": "Run full release QA after current refactor changes are settled",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:qa",
            "task:qa",
        ],
        "owner": "ReleaseQaAgent",
        "scope": (
            "validators/tests/docs/slides only; no staging, commit, push, "
            "PR, or release publication"
        ),
        "criteria": [
            "Run python scripts/validation/validate_docs.py and report pass/fail.",
            "Run python -m unittest tests.contracts.test_project_contract and report pass/fail.",
            "Run node --check slides/js/presentation.js and node --check slides/js/presentation-tools.js.",
            "Run git diff --check and confirm no cache/build artifact is staged.",
            "List skipped tests, unverified service paths, and any Human Review blockers.",
        ],
    },
    {
        "seed": "STWI-SYM-016",
        "title": "Reconcile readiness scoring and progress evidence",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:qa",
            "task:review",
        ],
        "owner": "LeadCoordinator",
        "scope": (
            "docs/project_management/symphony only; no contract, runtime, "
            "release, commit, or push actions"
        ),
        "criteria": [
            "Progress estimates are derived from board state, gate criteria, and verified checks instead of raw agent-report percentages.",
            "Stale test counts are replaced or explicitly marked stale.",
            "A single readiness summary is available for Symphony/Linear handoff.",
            "No project_contract.json invariants, API semantics, safety rules, or SLA thresholds are changed.",
        ],
    },
    {
        "seed": "STWI-SYM-017",
        "title": "Draft auth, RBAC, and tenant-boundary design",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:api",
            "phase:4",
            "task:review",
            "needs-human-review",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "docs/design proposal only; no dependency, IdP, API schema, "
            "credential, or runtime implementation"
        ),
        "criteria": [
            "Design derives operator identity and tenant context server-side instead of trusting request body fields.",
            "Role boundaries for operator, analyst, admin, and readonly are specified without choosing a new identity provider.",
            "No auth dependency, external IdP, or API schema change is implemented before Human Review approval.",
            "The proposal preserves decision-support-only behavior and human approval requirements.",
        ],
    },
    {
        "seed": "STWI-SYM-018",
        "title": "Specify observability minimum for trace, logs, and metrics",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:api",
            "phase:4",
            "task:review",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "docs and validation planning only; do not add Prometheus, "
            "OpenTelemetry, Grafana, or external services"
        ),
        "criteria": [
            "Required trace_id, job timing, model/data/policy version, status transition, and safety reason fields are listed.",
            "Metric names are specified for job counts, job latency, safety loop outcomes, retrieval latency, and surrogate latency.",
            "Prometheus, OpenTelemetry, or other observability services remain optional future deployment choices until explicitly approved.",
            "Any missing runtime fields are recorded as follow-up implementation issues rather than implemented in this issue.",
        ],
    },
    {
        "seed": "STWI-SYM-019",
        "title": "Define project-native model registry evidence format",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:ml",
            "phase:2",
            "task:review",
        ],
        "owner": "MLSimulationAgent",
        "scope": (
            "docs, schema proposal, and focused validators only; do not add "
            "MLflow or external model registry services"
        ),
        "criteria": [
            "Evidence schema covers model version, dataset version, checksum, metrics, calibration, benchmark profile, thresholds, and promotion decision.",
            "The format works for vision, baseline forecast, and surrogate artifacts without requiring MLflow.",
            "Existing promotion and validation paths either produce or validate the required fields.",
            "No current model claim is upgraded from provisional to production-ready without matching evidence.",
        ],
    },
    {
        "seed": "STWI-SYM-020",
        "title": "Document fail-closed resilience policy for dependency failures",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:api",
            "phase:4",
            "task:review",
            "contract-risk",
        ],
        "owner": "OrchestratorReleaseAgent",
        "scope": (
            "docs/tests planning first; runtime edits only if small and "
            "fail-closed, no pybreaker dependency or fail-open fallback"
        ),
        "criteria": [
            "Retries, timeout, circuit-breaker-style behavior, and dependency failure classes map to needs_review, failed, or expired.",
            "No runtime path returns an executable action after tool, RAG, TimescaleDB, Qdrant, Celery, Redis, or model failure.",
            "The rejected fail-open wording is replaced with an explicit fail-closed policy and focused tests are identified.",
            "recommended_action remains available only for succeeded jobs; needs_review exposes only non-executable candidate_action.",
        ],
    },
    {
        "seed": "STWI-SYM-021",
        "title": "Review production deployment options without changing the approved stack",
        "state": "Backlog",
        "labels": [
            "stwi-agent",
            "lane:release",
            "phase:4",
            "task:review",
            "needs-human-review",
            "contract-risk",
        ],
        "owner": "ReleaseQaAgent",
        "scope": (
            "options review only; do not add Kubernetes, secrets manager, "
            "tracing stack, model server, workflow, or CI deployment changes"
        ),
        "criteria": [
            "Docker Compose production, Kubernetes, and managed-service options are compared as deployment options only.",
            "No Kubernetes, secrets manager, tracing, or model-serving framework is added to active architecture.",
            "The recommendation lists cost, complexity, safety, rollback, and Human Review requirements for a later decision.",
            "The active MVP stack remains TimescaleDB, Qdrant, BGE-m3, LangGraph, Celery, Redis, FastAPI, and SSE.",
        ],
    },
    {
        "seed": "STWI-RTSP-001",
        "title": (
            "Prepare RTSP source alias and capture guardrails for edge_camera_1"
        ),
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:data",
            "phase:1",
            "task:validate",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "scripts/data_prep/capture_rtsp_frames.py, "
            "tests/t1_pipeline/test_capture_rtsp_frames.py, "
            "docs/guides/vision_local_training_runbook.md"
        ),
        "criteria": [
            "Accept edge_camera_1 as a safe source id while continuing to reject unsafe source ids.",
            "Keep the RTSP endpoint read only from STWI_RTSP_URL; do not put the endpoint in repo files, Linear, logs, or manifests.",
            "Ensure command output and manifests exclude endpoint values, credentials, image base64, and raw video references.",
            "Add or update focused tests for URL validation, missing env handling, safe source id, and fail-closed behavior without opening a live stream.",
        ],
    },
    {
        "seed": "STWI-RTSP-002",
        "title": "Document supervised RTSP-to-quarantine smoke test procedure",
        "state": "Todo",
        "labels": [
            "stwi-agent",
            "symphony-approved",
            "lane:vision",
            "phase:1",
            "task:review",
        ],
        "owner": "DataVisionAgent",
        "scope": (
            "docs/guides/vision_local_training_runbook.md, "
            "docs/01_System_Architecture_Data_Pipeline.md, README.md if needed"
        ),
        "criteria": [
            "Document how an operator sets STWI_RTSP_URL locally without writing the endpoint to repo, Linear, logs, or manifests.",
            "Document sparse-frame quarantine capture under data/quarantine/rtsp_frames with no raw video container retention.",
            "List privacy review, retention, cleanup, and aggregate-only next steps before any frame leaves quarantine.",
            "Include exact offline verification commands that can run after supervised capture.",
        ],
    },
    {
        "seed": "STWI-RTSP-003",
        "title": "Run supervised live RTSP smoke test for edge_camera_1",
        "state": "In Review",
        "labels": [
            "stwi-agent",
            "lane:data",
            "phase:1",
            "task:review",
            "needs-human-review",
            "external-service",
        ],
        "owner": "DataVisionAgent with human supervision",
        "scope": (
            "Human-supervised local run only; no unattended Symphony execution, "
            "no raw video retention, and no endpoint disclosure."
        ),
        "criteria": [
            "Human operator confirms the RTSP endpoint is approved for STWI testing and sets it only in STWI_RTSP_URL.",
            "Live capture is bounded to a small sample, stores sparse frames only in quarantine, and retains no raw video.",
            "Review the manifest to confirm no endpoint, credentials, image base64, or raw video reference is present.",
            "Delete evidence, keep it in quarantine for privacy review, or create a follow-up issue for approved aggregate-only conversion.",
        ],
    },
]


def read_key() -> str:
    if not ENV_PATH.exists():
        raise SystemExit(f"Missing env file: {ENV_PATH}")

    for raw_line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "LINEAR_API_KEY":
            return value.strip().strip('"').strip("'")

    raise SystemExit("LINEAR_API_KEY not found in Symphony env file")


TOKEN = read_key()


def gql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode(
        "utf-8"
    )
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": TOKEN},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Linear HTTP {error.code}: {body}") from error

    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]


def find_project() -> tuple[dict[str, Any], dict[str, Any]]:
    data = gql(
        """
        query ProjectBySlug($slug: String!) {
          projects(filter: { slugId: { eq: $slug } }, first: 1) {
            nodes {
              id
              name
              slugId
              teams(first: 5) {
                nodes {
                  id
                  key
                  name
                  states(first: 50) { nodes { id name type } }
                  labels(first: 250) { nodes { id name } }
                }
              }
            }
          }
        }
        """,
        {"slug": PROJECT_SLUG},
    )
    projects = data["projects"]["nodes"]
    if not projects:
        raise SystemExit(f"No Linear project found for slug {PROJECT_SLUG}")

    project = projects[0]
    teams = project.get("teams", {}).get("nodes", [])
    if not teams:
        raise SystemExit(f"Project {PROJECT_SLUG} has no teams")
    return project, teams[0]


def build_description(item: dict[str, Any]) -> str:
    lines = [
        f"Seed: {item['seed']}",
        "",
        f"Owner role: {item['owner']}",
        f"Allowed scope: {item['scope']}",
    ]
    dependencies = item.get("dependencies")
    if dependencies:
        lines.extend(["", "Dependencies:"])
        lines.extend(f"- {dependency}" for dependency in dependencies)
    forbidden = item.get("forbidden")
    if forbidden:
        lines.extend(["", "Forbidden changes:"])
        lines.extend(f"- {change}" for change in forbidden)
    lines.extend(["", "Acceptance criteria:"])
    lines.extend(f"- {criterion}" for criterion in item["criteria"])
    checks = item.get("checks")
    if checks:
        lines.extend(["", "Exact checks:"])
        lines.extend(f"- `{check}`" for check in checks)
    expected_state = item.get("expected_state")
    if expected_state:
        lines.extend(["", f"Expected final state: {expected_state}"])
    gap_check = item.get("gap_check")
    if gap_check:
        lines.extend([f"Gap check: {gap_check}"])
    lines.extend(
        [
            "",
            "Symphony safety filters:",
            "- Use the project-local STWI skills and read AGENTS.md, README.md, project_contract.json before edits.",
            "- Keep network disabled inside the Symphony agent run.",
            "- Do not read or write .env*, secrets, raw video, private datasets, private model weights, .git, .codex, or data/derived/private.",
            "- Do not stage, commit, push, create PRs, deploy, publish releases, or run destructive commands.",
            "- Stop for Human Review instead of weakening contract, tests, safety, legal citation, SLA, tensor, feature, or API semantics.",
        ]
    )
    return "\n".join(lines)


def issue_exists(
    team_id: str, project_id: str, seed: str, title: str
) -> str | None:
    data = gql(
        """
        query ExistingIssues($teamId: ID!, $projectId: ID!, $term: String!) {
          issues(
            first: 10,
            filter: {
              team: { id: { eq: $teamId } },
              project: { id: { eq: $projectId } },
              or: [
                { title: { containsIgnoreCase: $term } },
                { description: { containsIgnoreCase: $term } }
              ]
            }
          ) { nodes { id identifier title description url state { name } } }
        }
        """,
        {"teamId": team_id, "projectId": project_id, "term": seed},
    )
    expected_seed_line = f"Seed: {seed}".casefold()
    expected_title = title.casefold()
    for issue in data["issues"]["nodes"]:
        description_lines = {
            line.strip().casefold()
            for line in (issue.get("description") or "").splitlines()
        }
        if (
            issue["title"].casefold() == expected_title
            or expected_seed_line in description_lines
        ):
            return issue["url"]

    data = gql(
        """
        query ExistingByTitle($teamId: ID!, $projectId: ID!, $title: String!) {
          issues(
            first: 10,
            filter: {
              team: { id: { eq: $teamId } },
              project: { id: { eq: $projectId } },
              title: { eqIgnoreCase: $title }
            }
          ) { nodes { id identifier title url state { name } } }
        }
        """,
        {"teamId": team_id, "projectId": project_id, "title": title},
    )
    for issue in data["issues"]["nodes"]:
        return issue["url"]
    return None


def main() -> None:
    project, team = find_project()
    states = {state["name"].lower(): state for state in team["states"]["nodes"]}
    labels = {label["name"].lower(): label for label in team["labels"]["nodes"]}

    def ensure_label(name: str) -> str:
        found = labels.get(name.lower())
        if found:
            return found["id"]
        if DRY_RUN:
            return f"dry-label:{name}"

        created = gql(
            """
            mutation CreateLabel($input: IssueLabelCreateInput!) {
              issueLabelCreate(input: $input) {
                success
                issueLabel { id name }
              }
            }
            """,
            {"input": {"teamId": team["id"], "name": name}},
        )["issueLabelCreate"]
        if not created.get("success"):
            raise RuntimeError(f"Failed to create label {name}")
        label = created["issueLabel"]
        labels[label["name"].lower()] = label
        return label["id"]

    results = []
    for item in ISSUES:
        if SEED_FILTER is not None and item["seed"] not in SEED_FILTER:
            continue
        state = states.get(item["state"].lower())
        if not state:
            names = ", ".join(state["name"] for state in states.values())
            raise SystemExit(
                f"State {item['state']} not found in Linear team {team['key']}; "
                f"states: {names}"
            )

        existing_url = issue_exists(
            team["id"], project["id"], item["seed"], item["title"]
        )
        if existing_url:
            results.append(
                {"seed": item["seed"], "status": "existing", "url": existing_url}
            )
            continue

        label_ids = [ensure_label(label) for label in item["labels"]]
        if DRY_RUN:
            results.append({"seed": item["seed"], "status": "dry-run", "url": None})
            continue

        created = gql(
            """
            mutation CreateIssue($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                success
                issue {
                  id
                  identifier
                  title
                  url
                  state { name }
                  labels { nodes { name } }
                }
              }
            }
            """,
            {
                "input": {
                    "teamId": team["id"],
                    "projectId": project["id"],
                    "stateId": state["id"],
                    "title": item["title"],
                    "description": build_description(item),
                    "labelIds": label_ids,
                }
            },
        )["issueCreate"]
        if not created.get("success"):
            raise RuntimeError(f"Failed to create issue {item['seed']}")

        issue = created["issue"]
        results.append(
            {
                "seed": item["seed"],
                "status": "created",
                "identifier": issue["identifier"],
                "url": issue["url"],
            }
        )

    print(
        json.dumps(
            {
                "project": {
                    "id": project["id"],
                    "name": project["name"],
                    "slug": project["slugId"],
                },
                "team": {"id": team["id"], "key": team["key"], "name": team["name"]},
                "issues": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
