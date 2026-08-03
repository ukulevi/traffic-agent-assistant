# TRA-50 Production Deployment Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed, reproducible Docker Compose production baseline for STWI on one controlled host while preserving the independent offline demo.

**Architecture:** A new `infra/production` package owns the hardened Compose topology, immutable application image, configuration template, and non-destructive operations CLI. A pure-Python validator and contract tests reject public data-service ports, floating images, provisional runtime wiring, weak health checks, embedded credentials, and missing recovery evidence before Docker is needed. Production startup remains gated when promoted model adapters/artifacts or trusted identity/UI providers are unavailable; this ticket does not fabricate those dependencies.

**Tech Stack:** Docker Compose, Python 3.11, FastAPI, Celery, Redis, TimescaleDB, Qdrant, unittest, existing STWI validation scripts.

## Global Constraints

- Keep the approved stack: TimescaleDB, Qdrant, BGE-m3, LangGraph, Celery, Redis, FastAPI, and SSE.
- Keep `STWI_RUNTIME_MODE=production`; production must reject demo, fake, provisional, in-memory, or body-derived identity paths.
- Keep `POST /api/v1/what-if-jobs` at HTTP 202 and preserve the six canonical job statuses.
- Keep `recommended_action` limited to `succeeded`; `needs_review` exposes only non-executable `candidate_action`.
- Keep human approval required and `automatic_actuation=false`.
- Do not expose Redis, TimescaleDB, or Qdrant host ports.
- Do not commit credentials, raw video, private artifacts, backup output, or deployment-specific retention values.
- Do not claim measured SLA, production release readiness, or closure of TRA-6, TRA-11, TRA-36, TRA-37, TRA-48, or TRA-51.
- Do not add Kubernetes, Terraform, an identity provider, a secrets manager, a TLS proxy, a telemetry backend, or another runtime framework.

---

## File Structure

- `infra/production/compose.yaml`: private-network production topology and health/dependency rules.
- `infra/production/Dockerfile`: pinned Python base, locked project install, non-root runtime user, API/worker-compatible image.
- `infra/production/requirements.lock`: exact resolved Python packages for the candidate image; the promoted production image is still selected by digest.
- `infra/production/.env.example`: required variable names and Human Review placeholders without usable credentials.
- `infra/production/README.md`: preflight, startup, readiness, migration, recovery, backup/restore, rollback, and external gates.
- `infra/production/ops.py`: safe command builder/executor for validation and operator-approved operational procedures.
- `scripts/validation/validate_production_deployment.py`: deterministic static validation API and CLI.
- `tests/contracts/test_production_deployment.py`: negative and positive contract fixtures for infrastructure validation.
- `tests/operations/test_production_ops.py`: tests that operational commands are bounded and non-destructive by default.
- `docs/05_Implementation_Plan.md`: canonical deployment direction and remaining Human Review gates.
- `docs/project_management/symphony/board.json`: TRA-50 evidence/status update after verification, only if it can be updated without overwriting unrelated changes.

### Task 1: Production Baseline Static Contract

**Files:**
- Create: `tests/contracts/test_production_deployment.py`
- Create: `scripts/validation/validate_production_deployment.py`

**Interfaces:**
- Produces: `validate_production_deployment(root: pathlib.Path) -> list[str]`
- Produces: `main() -> int`, returning `0` only when the baseline satisfies every static guard.
- Consumes later: Task 2 files under `infra/production` and Task 3 runbook/operations evidence.

- [ ] **Step 1: Write failing validator tests**

Create table-driven temporary fixtures that assert exact errors for:

```python
from scripts.validation.validate_production_deployment import (
    validate_production_deployment,
)

errors = validate_production_deployment(fixture_root)
self.assertIn("compose: redis must not publish host ports", errors)
self.assertIn("compose: STWI_RUNTIME_MODE must be production", errors)
self.assertIn("dockerfile: application runtime must use a non-root USER", errors)
self.assertIn("compose: API healthcheck must not use /docs", errors)
self.assertIn("environment: credential variables must not have defaults", errors)
```

Add a complete valid fixture that returns `[]`. The fixture must contain only dummy variable names, never secret-looking values.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.contracts.test_production_deployment -v
```

Expected: import failure because `validate_production_deployment.py` does not exist.

- [ ] **Step 3: Implement the minimal pure-Python validator**

Use `pathlib` and the Python standard library only. Parse the small Compose file conservatively as text; reject ambiguity rather than adding a YAML dependency. Check:

```python
REQUIRED_SERVICES = {"stwi-api", "stwi-worker", "redis", "timescaledb", "qdrant"}
FORBIDDEN_RUNTIME_MARKERS = {
    "STWI_RUNTIME_MODE: demo",
    "STWI_RUNTIME_MODE: development",
    "InMemoryJobStore",
    "ProvisionalBodyPrincipalResolver",
    "/docs",
}
REQUIRED_RUNBOOK_SECTIONS = {
    "Configuration preflight",
    "Migration",
    "Backup and restore verification",
    "Restart recovery",
    "Rollback",
    "Human Review gates",
}
```

Implement small focused functions for Compose, Dockerfile, environment template, operations CLI, and runbook validation. Error messages must be stable and must never include environment values.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m unittest tests.contracts.test_production_deployment -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the validator contract**

```powershell
git add scripts/validation/validate_production_deployment.py tests/contracts/test_production_deployment.py
git commit -m "test: define production deployment safety contract"
```

### Task 2: Hardened Compose Topology and Application Image

**Files:**
- Create: `infra/production/compose.yaml`
- Create: `infra/production/Dockerfile`
- Create: `infra/production/requirements.lock`
- Create: `infra/production/.env.example`
- Modify: `tests/contracts/test_production_deployment.py`

**Interfaces:**
- Compose services: `stwi-api`, `stwi-worker`, `redis`, `timescaledb`, `qdrant`.
- Required host configuration: `STWI_APP_IMAGE`, `STWI_API_BIND`, `STWI_API_PORT`, `STWI_REDIS_PASSWORD`, `STWI_TSDB_DB`, `STWI_TSDB_ADMIN_USER`, `STWI_TSDB_ADMIN_PASSWORD`, `STWI_TSDB_READER_USER`, `STWI_TSDB_READER_PASSWORD`, `STWI_QDRANT_API_KEY`, `STWI_BASELINE_MANIFEST`, and `STWI_SURROGATE_MANIFEST`.
- Produces: only the API publishes `${STWI_API_BIND:-127.0.0.1}:${STWI_API_PORT:-8000}:8000`; data services are reachable only on private Compose networks.

- [ ] **Step 1: Extend tests for actual topology requirements**

Assert the repository baseline requires:

```python
self.assertEqual(errors, [])
self.assertNotIn("ports:", redis_service_block)
self.assertIn("STWI_RUNTIME_MODE: production", api_service_block)
self.assertIn("read_only: true", api_service_block)
self.assertIn("cap_drop:", api_service_block)
self.assertIn("USER stwi", dockerfile_text)
self.assertNotRegex(compose_text, r"image:\s+[^\n]+:(latest|main|edge)\b")
```

Also assert the API/worker command does not reference `stwi.app:app`, because that module intentionally composes provisional defaults.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.contracts.test_production_deployment -v
```

Expected: missing `infra/production` files.

- [ ] **Step 3: Add the minimal production files**

Build both application services from one immutable image reference required as `${STWI_APP_IMAGE:?set promoted application image}`. Pin infrastructure images to exact approved version tags already compatible with the harness. Configure private `backend` and `data` networks, named volumes, `no-new-privileges`, dropped capabilities, bounded process limits, and service health checks.

The API/worker entry commands must target an explicit production composition entrypoint supplied by the promoted application image, not `stwi.app:app`. If the image lacks that entrypoint or promoted adapters, startup fails; Compose must not substitute a provisional module.

Resolve and record the multi-architecture manifest digest before writing the base image line:

```powershell
docker buildx imagetools inspect python:3.11.13-slim-bookworm
```

The repository Dockerfile builds a candidate image from
`python:3.11.13-slim-bookworm@sha256:<verified-index-digest>`. Generate
`requirements.lock` in a clean temporary virtual environment by installing the
existing `knowledge`, `forecast`, and `orchestrator` extras, then recording the
complete non-editable `pip freeze` result. The Dockerfile installs only from
that exact lock, copies required application code, creates `stwi` user/group,
and uses `USER stwi`. It does not embed credentials or private model files.

The environment template lists blank required values and points operators to host-managed injection. Credential interpolation in Compose uses `${NAME:?required}` with no fallback.

- [ ] **Step 4: Validate topology**

Run:

```powershell
python scripts/validation/validate_production_deployment.py
python -m unittest tests.contracts.test_production_deployment -v
```

If Docker is installed, additionally run with ephemeral process-only dummy variables:

```powershell
docker compose -f infra/production/compose.yaml config --quiet
```

Expected: static validator/tests pass; Compose config passes only when all required variables are supplied. Docker absence is recorded, not converted into a pass claim.

- [ ] **Step 5: Commit the topology**

```powershell
git add infra/production/compose.yaml infra/production/Dockerfile infra/production/requirements.lock infra/production/.env.example tests/contracts/test_production_deployment.py
git commit -m "feat: add hardened STWI production topology"
```

### Task 3: Non-Destructive Operations Evidence

**Files:**
- Create: `infra/production/ops.py`
- Create: `tests/operations/test_production_ops.py`
- Create: `infra/production/README.md`
- Modify: `scripts/validation/validate_production_deployment.py`

**Interfaces:**
- Produces: `build_command(action: str, *, project_name: str, backup_dir: pathlib.Path | None = None, restore_source: pathlib.Path | None = None, approved: bool = False) -> list[list[str]]`.
- Produces CLI actions: `preflight`, `start`, `readiness`, `backup`, `restore-verify`, `restart-recovery`, `rollback`, and `stop`.
- `restore-verify` and `rollback` require `--approved`; destructive volume deletion is not implemented.

- [ ] **Step 1: Write failing operations safety tests**

Test exact bounded command arrays without executing Docker:

```python
commands = build_command("stop", project_name="stwi-prod")
self.assertNotIn("-v", commands[0])

with self.assertRaisesRegex(ValueError, "explicit --approved"):
    build_command(
        "restore-verify",
        project_name="stwi-restore-check",
        restore_source=Path("backup"),
        approved=False,
    )

for command in build_command("backup", project_name="stwi-prod", backup_dir=target):
    self.assertNotIn("rm", command)
    self.assertNotIn("down -v", " ".join(command))
```

Verify project names and paths are validated and command output never contains environment values.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.operations.test_production_ops -v
```

Expected: import failure because `infra/production/ops.py` does not exist.

- [ ] **Step 3: Implement safe command construction and CLI**

Use `subprocess.run` with argument arrays, `check=True`, bounded timeouts, and no shell. Validate project names against `^[a-z][a-z0-9-]{2,40}$`; resolve backup/restore paths and reject paths outside an explicitly supplied operator directory. Print action names and exit results only, never environment contents.

`preflight` runs the static validator and `docker compose config --quiet`. `stop` uses `docker compose down` without `--volumes`. `backup`, `restore-verify`, and `rollback` construct explicit service commands documented by the runbook. `restore-verify` uses a distinct project name and never targets the active production volumes.

- [ ] **Step 4: Write the runbook with exact gates**

Document commands in Vietnamese-first operational language. Include all required sections and explicitly state:

- no deployment is authorized by this repository change;
- TLS/DNS, host firewall, retention, rotation, backup schedule, monitoring backend, and on-call owner require Human Review;
- backup output is private and ignored;
- rollback requires database migration compatibility review;
- production startup is expected to fail until the promoted image supplies real model adapters, trusted identity/UI providers, and valid manifests;
- the offline demo uses `infra/harness` and remains separate.

- [ ] **Step 5: Run operations and static tests**

Run:

```powershell
python -m unittest tests.operations.test_production_ops tests.contracts.test_production_deployment -v
python scripts/validation/validate_production_deployment.py
```

Expected: all tests and validator pass without Docker or credentials.

- [ ] **Step 6: Commit operations evidence**

```powershell
git add infra/production/ops.py infra/production/README.md tests/operations/test_production_ops.py scripts/validation/validate_production_deployment.py
git commit -m "feat: add bounded production operations evidence"
```

### Task 4: Canonical Documentation, Tracker, and Release QA

**Files:**
- Modify: `docs/05_Implementation_Plan.md`
- Modify if conflict-free: `docs/project_management/symphony/board.json`
- Regenerate if board changed: `docs/project_management/symphony/board.md`
- Regenerate if board changed: `docs/project_management/symphony/status_report.md`

**Interfaces:**
- Produces documentation that distinguishes deployable baseline, actual deployment approval, measured SLA evidence, and final release readiness.
- Produces TRA-50 evidence links while leaving status `Human Review`/Linear `In Review`, not `Done`.

- [ ] **Step 1: Add canonical deployment wording**

Update DOC-05 to name hardened single-host Docker Compose as the approved baseline and list the exact remaining gates. Preserve the approved stack, SLA numbers, demo scope, API semantics, and automatic-actuation prohibition.

- [ ] **Step 2: Add tracker evidence without overwriting user changes**

Compare the isolated worktree tracker with the original checkout's dirty tracker. If the TRA-50 entry can be updated without overlapping user edits, record the new files/tests and set local status to `Human Review`. Otherwise leave tracker files untouched and record the synchronization as a follow-up in the Linear comment.

- [ ] **Step 3: Run focused and mandatory checks**

Run:

```powershell
python scripts/validation/validate_production_deployment.py
python -m unittest tests.contracts.test_production_deployment tests.operations.test_production_ops -v
python -m unittest tests.t4_orchestrator.test_t4_runtime_boundaries tests.t4_orchestrator.test_t4_redis_celery tests.t4_orchestrator.test_t4_auth_boundary tests.t4_orchestrator.test_t4_ui_context -v
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Expected: all available checks pass; dependency-based skips and Docker unavailability are listed exactly.

- [ ] **Step 4: Run project release verification**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
```

No PDF build is required unless report or appendix files change.

- [ ] **Step 5: Review the final diff for contract drift**

Confirm the diff contains no new framework/dependency, public data-service port, credential value, provisional production fallback, automatic actuation, SLA weakening, or production-ready claim.

- [ ] **Step 6: Commit the synchronized documentation**

```powershell
git add docs/05_Implementation_Plan.md
git add docs/project_management/symphony/board.json docs/project_management/symphony/board.md docs/project_management/symphony/status_report.md
git commit -m "docs: record TRA-50 deployment baseline evidence"
```

Omit unchanged or intentionally deferred tracker files from `git add`.

- [ ] **Step 7: Update Linear for Human Review**

Attach exact test results and remaining external gates to TRA-50, then move it from `In Progress` to `In Review`. Do not mark it `Done`, deploy it, or close TRA-51.
