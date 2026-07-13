# STWI Production Deployment Options Review

**Ticket:** `TRA-17` / `STWI-SYM-021`  
**Status:** Design proposal for Human Review  
**Scope:** Deployment options only. This document does not add infrastructure,
dependencies, credentials, CI deployment, or runtime wiring.

## Decision Boundary

The active MVP stack remains TimescaleDB, Qdrant, BGE-m3, LangGraph, Celery,
Redis, FastAPI, and SSE. STWI remains decision support: deployment must not
enable automatic field-device actuation or reduce the existing fail-closed,
operator-approval, privacy, or citation safeguards.

## Options Compared

| Option | Cost and complexity | Safety and operations | Rollback | Human Review gate |
| --- | --- | --- | --- | --- |
| Hardened Docker Compose on one controlled host | Lowest initial cost and operational complexity; appropriate for a bounded pilot. | Pin images, separate read-only database roles, use host-managed secret injection, restrict network ingress, and retain audit logs. A single-host failure domain remains. | Versioned compose file and immutable images permit rollback to the prior approved release after database compatibility review. | Approve host ownership, backup/restore drill, network boundary, secret injection, and on-call responsibility. |
| Kubernetes deployment | Highest platform cost and operating complexity; useful only after a demonstrated multi-host availability or tenancy requirement. | Requires a separately approved policy for cluster access, secrets, ingress, workload isolation, telemetry, and incident response. It does not itself provide an authorization boundary. | Roll back a versioned workload only after migration compatibility and safety-gate checks. | Require an architecture decision record and security review before any cluster, chart, or CI deployment work. |
| Managed services plus a controlled application host | Moderate recurring cost and vendor dependency; can reduce database and queue operations work. | Evaluate data residency, tenant isolation, encryption, audit export, retention, service outage behavior, and vendor access. Managed services do not remove the need for STWI read-only roles or fail-closed dependency behavior. | Confirm export, restore, and provider-exit paths before adoption. | Require procurement, legal/privacy, security, and rollback approval for each provider. |

## Recommendation

For the next controlled deployment decision, assess **hardened Docker Compose
on a single approved host** first. It preserves the MVP stack and gives the
smallest reversible operational surface. This is a recommendation to evaluate,
not authorization to deploy.

Do not adopt Kubernetes or a managed service merely to appear production-like.
Either option needs a concrete scale, availability, compliance, or operations
requirement that Docker Compose cannot meet safely.

## Preconditions for Any Deployment Work

1. Approve server-side identity, RBAC, and tenant isolation from `TRA-13`.
2. Establish an approved SOP/legal corpus and citation refresh ownership.
3. Run the surrogate benchmark on the contract hardware profile (`TRA-6`).
4. Define backup/restore, key rotation, privacy retention, and incident
   response procedures.
5. Verify that all unsafe, OOD, uncertain, timeout, and missing-citation cases
   remain fail-closed in the selected environment.
6. Obtain Human Review approval before adding deployment manifests, CI jobs,
   Kubernetes resources, a secrets manager, tracing, or model-serving tools.

## Explicit Non-Changes

This proposal does not select an identity provider, secrets manager,
observability backend, model-serving framework, Kubernetes distribution, or
managed vendor. It makes no change to `project_contract.json`, API schemas,
SLA targets, data retention rules, or automatic-actuation policy.
