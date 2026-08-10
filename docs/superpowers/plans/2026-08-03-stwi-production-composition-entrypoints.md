# STWI Production Composition Entrypoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement every Python entrypoint referenced by the TRA-50 Dockerfile and Compose baseline with fail-closed production composition.

**Architecture:** Centralize environment validation and trusted component loading in `production_components.py`. API, worker, preflight and health reuse this boundary; migration remains a separate admin-only CLI.

**Tech Stack:** Python 3.11, FastAPI, Celery, Redis, Qdrant, psycopg, existing STWI protocols and artifact registry.

## Global Constraints

- No provisional, fake, body-derived identity or in-memory fallback in production.
- Do not select a new IdP, model-serving framework or deployment stack.
- Never log credentials, DSNs, tokens, raw exception text or artifact contents.
- Production readiness remains a Human Review decision.
- Do not commit, stage, push or change branches.

---

### Task 1: Typed production settings and component factory

**Files:**
- Create: `src/stwi/production_components.py`
- Test: `tests/t4_orchestrator/test_production_components.py`

**Interfaces:**
- Produces: `ProductionSettings.from_environ(environ)`
- Produces: `ProductionComponents`
- Produces: `load_component_factory(import_path)`

- [ ] **Step 1: Write failing settings tests**

```python
def test_missing_component_factory_fails_closed(self):
    with self.assertRaisesRegex(ProductionConfigurationError, "COMPONENT_FACTORY_REQUIRED"):
        ProductionSettings.from_environ({"STWI_RUNTIME_MODE": "production"})
```

- [ ] **Step 2: Verify RED**

Run the new test module; expected import failure.

- [ ] **Step 3: Implement strict settings and import-path loading**

Require production mode, Redis URL, TimescaleDB reader DSN, Qdrant URL,
artifact manifests and `module:callable` factory. Return stable error codes.

- [ ] **Step 4: Verify GREEN**

Run the new test module.

### Task 2: Shared production composition factory

**Files:**
- Modify: `src/stwi/production_components.py`
- Test: `tests/t4_orchestrator/test_production_components.py`

**Interfaces:**
- Produces: `build_production_runtime(settings) -> ProductionRuntime`

- [ ] **Step 1: Add failing tests for provisional rejection**

```python
for field in ("baseline", "surrogate", "principal_resolver", "ui_context_provider"):
    component = replace(valid_components, **{field: ProvisionalComponent()})
    with self.assertRaisesRegex(ProductionConfigurationError, "PROVISIONAL_COMPONENT"):
        validate_components(component)
```

- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Compose validated artifacts, RealT3Adapter, Redis store, Celery app/dispatcher and orchestrator without fallback.**
- [ ] **Step 4: Verify GREEN and runtime-boundary regression tests.**

### Task 3: API and worker entrypoints

**Files:**
- Create: `src/stwi/production.py`
- Create: `src/stwi/production_worker.py`
- Test: `tests/t4_orchestrator/test_production_entrypoints.py`

**Interfaces:**
- Produces: `production.app`
- Produces: `production_worker.app`

- [ ] **Step 1: Write failing import/composition tests with a trusted test factory.**
- [ ] **Step 2: Verify RED because modules do not exist.**
- [ ] **Step 3: Implement API and worker modules using the shared runtime factory.**
- [ ] **Step 4: Verify GREEN, including stable Celery task name and no provisional marker.**

### Task 4: Preflight and readiness entrypoints

**Files:**
- Create: `src/stwi/production_preflight.py`
- Create: `src/stwi/production_health.py`
- Test: `tests/operations/test_production_entrypoints.py`

**Interfaces:**
- Produces: CLI `main(argv=None) -> int`
- Produces: redacted JSON verdict with component codes

- [ ] **Step 1: Add failing CLI tests for missing config, redaction and dependency failure.**
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement preflight plus injected Redis/Qdrant/Timescale probes.**
- [ ] **Step 4: Verify GREEN and assert secrets never occur in stdout/stderr.**

### Task 5: Migration entrypoint

**Files:**
- Create: `src/stwi/production_migrate.py`
- Test: `tests/operations/test_production_migrate.py`

**Interfaces:**
- Produces: `check` and `apply --approved` CLI actions

- [ ] **Step 1: Write failing tests proving apply requires approval/admin DSN and never uses reader DSN.**
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement version check and application of `infra/production/timescaledb-init/01_schema.sql`.**
- [ ] **Step 4: Verify GREEN with an injected connection factory; no live database in unit tests.**

### Task 6: Docker and documentation synchronization

**Files:**
- Modify: `infra/production/Dockerfile`
- Modify: `infra/production/README.md`
- Modify: `infra/production/.env.example`
- Modify: `docs/05_Implementation_Plan.md`
- Modify: `report/chapters/ch03_kien_truc.tex`
- Modify: `report/chapters/ch09_evaluation.tex`
- Modify: `scripts/validation/validate_production_deployment.py`
- Modify: `tests/contracts/test_production_deployment.py`

- [ ] **Step 1:** Add a failing validator test requiring all five module files.
- [ ] **Step 2:** Verify RED against the old validator fixture.
- [ ] **Step 3:** Extend validation/runbook/config without adding credentials.
- [ ] **Step 4:** Verify static validator and `docker compose config --quiet`.

### Task 7: Verify production composition

- [ ] Run all new focused tests and Tier-4 runtime/auth/Redis-Celery tests.
- [ ] Run production validator and CLI import smoke.
