# STWI Production Composition Entrypoints Design

**Status:** Approved for implementation on 2026-08-03
**Scope:** Make the TRA-50 image entrypoints executable without provisional fallback
**Contract:** Approved stack only; deployment and external gates remain Human Review

## 1. Goal

Provide the Python modules referenced by the hardened production Dockerfile and
Compose baseline. The modules validate and compose approved runtime boundaries;
they do not claim the environment, artifacts, legal corpus, hardware or camera
gate has passed.

## 2. Trusted Component Factory

`STWI_PRODUCTION_COMPONENT_FACTORY` is a required import path to a callable that
returns typed production components:

- real `BaselineForecaster`;
- real `ScenarioForecaster`;
- trusted non-provisional `PrincipalResolver`;
- trusted non-provisional `UiContextProvider`.

STWI supplies Redis persistence, Celery dispatch, real T3 construction and
runtime-artifact validation. Missing factory, import failure, wrong type,
provisional component or incomplete component fails startup. There is no demo,
fake, static-principal or in-memory fallback.

The factory seam preserves the approved decision not to select an IdP or a new
model-serving framework inside this ticket.

## 3. Entrypoints

### `stwi.production_preflight`

Validate required environment variable names and formats, promoted artifact
manifests, component factory import and non-provisional markers. It redacts
values and exits non-zero on any missing boundary.

### `stwi.production`

Create the FastAPI application with `RuntimeMode.PRODUCTION`, `RedisJobStore`,
`CeleryJobDispatcher`, real T3, validated artifacts, trusted identity and UI
scope. Import/startup failure is intentional when configuration is incomplete.

### `stwi.production_worker`

Create the Celery application and register the stable idempotent job task. The
worker constructs the same validated orchestrator and Redis store as the API.

### `stwi.production_health`

Expose a CLI readiness check for Redis ping, Qdrant reachability, TimescaleDB
read-only query, artifact validity and component factory validity. Output
contains stable component codes only, never credentials or raw exceptions.

### `stwi.production_migrate`

Run the versioned TimescaleDB schema with an explicitly supplied admin DSN.
Migration is separate from API/worker startup, never uses the reader role and
never seeds demo data. It supports check/apply modes and fails on unknown schema
state. Destructive downgrade is out of scope.

## 4. Configuration

Required variables include Redis URL, TimescaleDB reader DSN, Qdrant URL/key,
baseline/surrogate manifest paths and the component-factory import path. The
migration command separately requires an admin DSN. Empty values, development
defaults, non-HTTPS external Qdrant endpoints, malformed import paths and
non-production runtime mode fail preflight.

## 5. Failure Semantics

- Startup configuration errors stop the process before accepting requests.
- Dependency readiness errors make the container unhealthy.
- Runtime dependency errors remain typed `failed`/`expired` paths and cannot
  return `recommended_action`.
- Health and preflight logs include stable error codes, not DSNs, tokens,
  passwords, internal exception strings or artifact contents.

## 6. Verification

TDD tests first assert that the currently missing modules and unsafe/incomplete
config fail. Implementation tests cover successful composition with explicitly
trusted test doubles, rejection of every provisional component, redaction,
shared API/worker factories, health verdicts, migration check/apply boundaries
and Docker command importability.

Static deployment validation and `docker compose config` remain necessary but
are not sufficient. A build-smoke imports every entrypoint in a configured test
image. Actual deployment, TLS/DNS, secret injection, service restore, promoted
