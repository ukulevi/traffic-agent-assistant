# STWI — Production Adapter Replacement Runbook

**Ticket:** `TRA-7` / `STWI-SYM-009`
**Status:** Implemented boundary; deployment remains separately gated
**Scope:** Documentation and targeted runtime hardening only. No new framework, no secrets in repo, no live service startup outside approved harness.

## 1. Goal

Replace provisional fake adapters in production runtime so that
`STWI_RUNTIME_MODE=production` rejects incomplete wiring and fails closed when
real services are missing. This runbook documents the exact adapter boundary,
required environment variables, and verification commands.

## 2. Adapter Boundary

| Tier | Production adapter | Notes |
|---|---|---|
| Baseline forecast | explicit `BaselineForecaster` | required in production |
| Surrogate forecast | explicit `ScenarioForecaster` | required in production |
| Legal evidence / RAG | explicit `LegalEvidenceProvider` | required in production |
| Job persistence | `RedisJobStore` | required; no in-memory production fallback |
| Job execution | `CeleryJobDispatcher` | task id equals job id; duplicate workers are lock-guarded |
| Identity | explicit trusted `PrincipalResolver` | body-derived/static resolvers rejected |

In `development`, `test`, and `demo`, provisional adapters remain allowed for local experimentation. In `production`, `WhatIfOrchestrator` requires all three adapters to be injected explicitly and rejects adapters marked provisional even when a caller passes them directly, including a `T3KnowledgeTier` that wraps a fake adapter. The API also rejects `InMemoryJobStore` and a missing/provisional dispatcher before it accepts a job. Production composition requires validated baseline and surrogate artifact manifests. Demo composition remains isolated and is labeled `provisional_demo_composition` in audit output.

Corpus manifest writes use UTF-8 explicitly so Vietnamese legal metadata does not depend on the Windows active code page.

## 3. Required Environment

| Variable | Purpose | Rule |
|---|---|---|
| `STWI_RUNTIME_MODE=production` | Enable production guard | Do not commit value to repo |
| `STWI_TSDB_DSN` | TimescaleDB connection string | Required for real simulation queries; never log full DSN with password |
| `STWI_QDRANT_URL` | Qdrant service URL | Required; no embedded localhost fallback in production adapter |
| `STWI_QDRANT_API_KEY` | Optional Qdrant credential | Inject from approved secret configuration only |
| `STWI_REDIS_URL` | Celery broker and persistent job/event store | Required; never embed credentials |
| baseline artifact manifest path | Promoted GCN–LSTM evidence | Must pass checksum, calibration, expiry and promotion validation |
| surrogate artifact manifest path | Promoted surrogate evidence | Supplies model/data versions and calibrated OOD/uncertainty thresholds |
| `ROBOFLOW_API_KEY` | Optional hosted workflow inference | Required only when Roboflow path is used; read from env, never logged |

## 4. Fail-Closed Behavior

The runtime must fail closed when:

- Any required adapter is missing in production.
- TimescaleDB/Qdrant/Roboflow is unreachable or times out.
- Model/data version is missing or mismatched.
- Artifact checksum, calibration, promotion status, or expiry is invalid.
- Redis persistence or Celery dispatch is unavailable.
- OOD, high uncertainty, or missing legal evidence is detected.

No runtime path returns an executable action after service, RAG, database, or model failure.

## 5. Verification Commands

```bash
python -m unittest tests.t4_orchestrator.test_t4_safety -v
python -m unittest tests.t4_orchestrator.test_t4_auth_boundary -v
python -m unittest tests.t4_orchestrator.test_t4_redis_celery -v
python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries -v
python -c "from stwi.config.runtime import is_production_mode; print(is_production_mode({'STWI_RUNTIME_MODE': 'production'}))"
STWI_RUNTIME_MODE=production python -c "from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator; WhatIfOrchestrator()"
```

The last command must fail closed because no adapters were injected.

```bash
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

## 6. Acceptance Criteria

- `STWI_RUNTIME_MODE=production` rejects auto-wired fake adapters.
- Real adapters have documented required environment variables.
- Redis events persist across API-store recreation and SSE resumes by monotonic event ID.
- Terminal states are immutable and duplicate Celery delivery cannot execute a terminal job twice.
- Audit output records exact promoted artifact and manifest checksums.
- Production startup fails closed when services are missing.
- No new dependency or external service is added beyond the approved stack.
