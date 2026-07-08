# STWI — Production Adapter Replacement Runbook

**Ticket:** `TRA-7` / `STWI-SYM-009`
**Status:** Draft
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

In `development`, `test`, and `demo`, provisional adapters remain allowed for local experimentation. In `production`, `WhatIfOrchestrator` requires all three adapters to be injected explicitly.

## 3. Required Environment

| Variable | Purpose | Rule |
|---|---|---|
| `STWI_RUNTIME_MODE=production` | Enable production guard | Do not commit value to repo |
| `STWI_TSDB_DSN` | TimescaleDB connection string | Required for real simulation queries; never log full DSN with password |
| `QDRANT_URL` | Qdrant service URL | Default `http://localhost:6333` if local |
| `ROBOFLOW_API_KEY` | Optional hosted workflow inference | Required only when Roboflow path is used; read from env, never logged |

## 4. Fail-Closed Behavior

The runtime must fail closed when:

- Any required adapter is missing in production.
- TimescaleDB/Qdrant/Roboflow is unreachable or times out.
- Model/data version is missing or mismatched.
- OOD, high uncertainty, or missing legal evidence is detected.

No runtime path returns an executable action after service, RAG, database, or model failure.

## 5. Verification Commands

```bash
python -m unittest tests.t4_orchestrator.test_t4_safety -v
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
- Production startup fails closed when services are missing.
- No new dependency or external service is added beyond the approved stack.
