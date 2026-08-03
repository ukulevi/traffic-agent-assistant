# TRA-50 Production Deployment Baseline Design

**Ticket:** `TRA-50` / `STWI-SYM-041`  
**Decision:** Hardened Docker Compose on one controlled host  
**Status:** Approved design, implementation pending written-spec review

## 1. Outcome and Boundary

TRA-50 will add a reproducible production deployment baseline for the approved
STWI stack on one operator-controlled host. The baseline is deployable evidence,
not authorization to deploy, and it does not claim measured production SLA,
field calibration, or release readiness.

The existing deterministic offline demo remains independent. Production never
falls back to demo, fake, provisional, in-memory, or body-derived identity
components. STWI remains decision support only and cannot actuate field devices.

## 2. Selected Architecture

The production topology uses Docker Compose with private service networks:

- `stwi-api`: FastAPI/SSE ingress, composed with production runtime guards.
- `stwi-worker`: Celery worker using the same immutable application image.
- `redis`: queue and durable job/progress/event state; no host port.
- `timescaledb`: time-series store with separate migration/admin and runtime
  read-only roles; no host port.
- `qdrant`: vector store for the approved BGE-m3 retrieval path; no host port.

Only the API port may bind to the host, and its bind address is configurable so
the controlled host can place a separately approved TLS reverse proxy in front.
This ticket does not add a proxy, identity provider, secrets manager,
observability backend, Kubernetes, or managed service.

All services use pinned image references, non-root execution where supported,
read-only filesystems where compatible, dropped Linux capabilities, bounded
resource/process settings, health checks, and explicit dependency ordering.
Persistent data uses named volumes; source code and private datasets are not
mounted into production containers.

## 3. Configuration and Secrets

The repository contains only a variable-name template. Required credentials are
injected by the controlled host through an ignored environment file or an
equivalent host-managed mechanism. Compose must fail interpolation when a
required secret is absent; no development default is allowed for credentials.

`STWI_RUNTIME_MODE=production` is fixed in the production service definition.
Production requires the existing real Redis/Celery job path, trusted principal
resolver, trusted UI-context provider, production T3 adapters, and promoted
artifact provenance. Missing, provisional, expired, uncalibrated, or
checksum-invalid dependencies fail startup or readiness.

The template documents secret rotation ownership but does not contain example
secret values that could be mistaken for usable credentials.

## 4. Health, Readiness, and Failure Semantics

Liveness proves that a process is responsive. Readiness is stricter and proves
that the production composition can reach required dependencies and that its
runtime boundary is valid. OpenAPI `/docs` is not health evidence.

The API and worker must remain unavailable when Redis, TimescaleDB, Qdrant,
trusted auth/UI context, or promoted production artifacts are unavailable.
Dependency failures never produce `recommended_action`; existing job terminal
states remain immutable. Health output exposes stable component codes and a
`trace_id` where applicable, never raw exception text, credentials, endpoints,
SQL literals, prompts, images, or private payloads.

Compose restart policies support process recovery without converting failed or
expired jobs into success. Startup order is bounded by health checks rather than
unbounded sleeps.

## 5. Operations Evidence

Implementation will provide executable, conservative operator commands for:

1. configuration preflight and Compose validation;
2. database migration under a short-lived privileged role;
3. startup and readiness verification;
4. backup of TimescaleDB, Qdrant, and required Redis persistence;
5. restore into a non-production verification namespace;
6. restart-recovery smoke checks;
7. rollback to the prior pinned application image after migration compatibility
   review;
8. shutdown without deleting named volumes.

Backup artifacts remain private and are never committed. Restore and rollback
are explicit operator actions. Destructive volume removal is excluded from the
normal runbook.

Retention, rate limits, monitoring export, backup schedule, encryption keys,
host hardening, TLS, DNS, and on-call ownership are deployment-specific Human
Review gates. The baseline must list these gates and must not invent values.

## 6. Files and Responsibilities

- `infra/production/compose.yaml`: hardened production topology only.
- `infra/production/Dockerfile`: pinned, non-root application image shared by
  API and worker.
- `infra/production/.env.example`: names and validation notes only; no secrets.
- `infra/production/README.md`: bounded operator runbook and Human Review gates.
- `infra/production/scripts/`: focused preflight, backup/restore, recovery, and
  rollback helpers that default to non-destructive behavior.
- `scripts/validation/validate_production_deployment.py`: static contract and
  security validation without requiring external services.
- `tests/contracts/test_production_deployment.py`: regression tests for the
  validator and required fail-closed properties.
- `docs/05_Implementation_Plan.md`: canonical deployment-baseline direction.
- Symphony tracker artifacts: status/evidence synchronization after verified
  implementation, without overwriting unrelated tracker edits.

The provisional files under `infra/harness/` remain demo/integration harnesses
and are not silently rebranded as production.

## 7. Validation Strategy

Development validation must be deterministic and avoid real credentials:

- tests first assert missing secrets, public data-service ports, floating image
  tags, root application execution, demo/runtime fallbacks, and docs-only health
  checks are rejected;
- the validator checks Compose structure and runbook evidence without parsing or
  printing secret values;
- `docker compose config` is run with ephemeral dummy values only when Docker is
  available, and absence of Docker is reported rather than treated as evidence;
- focused runtime tests prove production composition remains fail closed;
- standard docs, contract, JavaScript, and diff checks remain mandatory.

No test may weaken SLA thresholds or label local/simulated measurements as
contract-profile evidence. TRA-6 and TRA-48 remain Human Review gates.

## 8. Acceptance Criteria

TRA-50 may move to `In Review` only when:

- the production Compose definition contains only the approved stack and has no
  public Redis, TimescaleDB, or Qdrant port;
- application processes are non-root and use reproducibly pinned image inputs;
- required credentials have no development defaults and do not appear in logs,
  generated evidence, or version control;
- health/readiness checks verify real boundaries rather than `/docs`;
- production rejects every demo, fake, provisional, in-memory, missing trusted
  identity/UI context, or invalid promoted-artifact path;
- migration, backup/restore, restart recovery, and rollback procedures have
  executable validation or an explicit Human Review gate;
- the offline demo remains usable and its provisional status stays visible;
- all required project checks pass and remaining external production gates are
  recorded without a production-ready claim.

## 9. Explicit Non-Goals

- No deployment to a real host, cloud, cluster, or managed service.
- No Kubernetes, Terraform, new CI deployment, or new runtime framework.
- No identity-provider, TLS proxy, secrets-manager, or telemetry-backend choice.
- No raw-video storage, automatic actuation, or executable `candidate_action`.
- No claim that TRA-50 closes hardware, camera, calibration, SLA, or final
  release-readiness tickets.
