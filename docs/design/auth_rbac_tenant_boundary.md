# STWI — Auth, RBAC, and Tenant-Boundary Design

**Ticket:** `TRA-13` / `STWI-SYM-017`
**Status:** Approved and implemented by `TRA-30`; duplicate rollout scope is tracked by `TRA-49`.
**Scope:** Defines the approved boundary. `TRA-30` adds a resolver seam without
selecting an IdP, storing credentials, or adding a dependency.

> [!IMPORTANT]
> STWI is decision-support only. No automatic actuation is performed. Human operator approval is required before applying any recommended action.

## 1. Problem Statement

Current API paths derive `tenant_id` and `operator_id` from request body fields:

- `POST /api/v1/what-if-jobs` accepts a client-supplied `tenant_id`
- `POST /api/v1/what-if-jobs/{job_id}/operator-decision` accepts a client-supplied `operator_id`

This is acceptable for local/provisional testing, but it is not a production trust boundary. A caller can:

- submit a job under another tenant's id;
- record an operator decision under a fabricated identity;
- bypass tenant isolation in `simulation_results` queries because `query_builder.py` only filters by the supplied `tenant_id`.

TRA-13 defines the target design without prescribing a specific identity provider, secret manager, or new service dependency.

## 2. Design Goals

1. **Server-side identity:** tenant context and operator identity must originate from authenticated server-side claims, never from raw request body fields.
2. **Tenant isolation:** all data access must be scoped to the resolved tenant; missing or mismatched tenant must fail closed.
3. **Role boundaries:** operator, analyst, admin, and readonly roles have distinct capabilities without requiring a new IdP product.
4. **No new approved-stack dependency:** do not add external IdP, secrets manager, or auth service to active architecture in this ticket.
5. **Fail-closed:** any auth ambiguity results in `failed` or `needs_review`, never silent degradation.

## 3. Non-Goals

- Selecting or integrating a specific IdP (OAuth2, OIDC, SAML, mTLS, etc.).
- Storing passwords, tokens, or credentials in the repository.
- Changing `project_contract.json`, API status semantics, or safety loop behavior.
- Implementing runtime auth middleware; only specify the contract and boundary shapes.

## 4. Trust-Boundary Model

```text
Request
  │
  ▼
Auth Boundary
  │
  ├─ Resolve tenant identity from server-side claim
  │   (upstream gateway header, mTLS subject, or injected context)
  │
  ├─ Reject requests that do not provide verifiable tenant/operator claims
  │
  ▼
API Layer
  │
  ├─ Override any client-supplied tenant_id/operator_id with resolved claims
  ├─ Enforce role allowlists per endpoint
  │
  ▼
Orchestrator / Query Layer
  │
  ├─ Pass resolved tenant_id through job envelope and audit record
  ├─ Filter simulation_results by resolved tenant_id
  └─ Reject cross-tenant node access
```

Key invariant: **client-supplied tenant_id and operator_id are never treated as authoritative**.

## 5. Tenant Isolation Design

### 5.1. Resolution Rules

| Source | Allowed | Notes |
| --- | --- | --- |
| Authenticated upstream gateway header | Yes | Preferred for deployment behind reverse proxy/gateway |
| mTLS client certificate subject | Yes | Preferred for service-to-service |
| Request body field | No | Accepted only as backward-compatible hint; must be validated against resolved claim |
| Missing or mismatched claim | Fail closed | Return `failed` or reject request before job creation |

### 5.2. Job Envelope

`JobEnvelope` must carry a server-resolved `tenant_id` that is immutable after creation.

```text
JobEnvelope
  ├─ job_id
  ├─ tenant_id          ← server-resolved, immutable
  ├─ status
  ├─ created_at
  ├─ updated_at
  ├─ result
  └─ audit_record
        └─ tenant_id    ← must match envelope tenant_id
```

### 5.3. Query Builder Contract

`SQLQueryBuilder` must:

- always filter by the resolved `tenant_id` from the job envelope or query spec;
- never accept a default tenant when the resolved tenant is missing;
- reject queries that attempt to cross tenant boundaries via `node_ids` if the caller's role does not permit cross-tenant visibility.

Current fallback behavior in `query_builder.py`:

```python
if query.tenant_id:
    where_clauses.append("tenant_id = %s")
    params.append(query.tenant_id)
else:
    where_clauses.append("tenant_id = %s")
    params.append(self.default_tenant)
```

This fallback must be removed or replaced with a fail-closed path that rejects missing tenant context.

## 6. RBAC Design

### 6.1. Roles

| Role | Create Job | Poll Own Job | Poll Any Job | Record Decision | Admin Config |
| --- | --- | --- | --- | --- | --- |
| `operator` | Yes | Yes | No | Yes (own tenant) | No |
| `analyst` | Yes | Yes | Yes (own tenant) | No | No |
| `admin` | Yes | Yes | Yes | Yes | Yes |
| `readonly` | No | Yes | Yes (own tenant) | No | No |

### 6.2. Allowlist Rules

- `POST /api/v1/what-if-jobs` requires `operator`, `analyst`, or `admin`.
- `GET /api/v1/what-if-jobs/{job_id}` requires any authenticated role; result visibility is filtered by tenant and role.
- `POST /api/v1/what-if-jobs/{job_id}/operator-decision` requires `operator` or `admin` within the same tenant.
- Admin endpoints (future) require `admin`.

### 6.3. Operator Decision Boundary

Operator decisions are audit-only and never trigger device actuation. The response must always include:

```json
{
  "automatic_actuation": false,
  "message": "Decision recorded for audit only; no field action was executed."
}
```

Role enforcement must prevent an `analyst` or `readonly` from recording operator decisions, even if they can view job status.

## 7. API Contract Changes

### 7.1. Request Shape

The following fields remain in the public API for documentation and backward compatibility, but are **not authoritative**:

- `tenant_id` in `WhatIfJobRequest`
- `operator_id` in `OperatorDecisionRequest`

Server behavior:

- ignore client-supplied values for authorization;
- compare client-supplied values against resolved claims and reject mismatches;
- never create a job or record a decision when resolved claims are missing.

### 7.2. Response Shape

Responses must include resolved identity metadata for audit:

```json
{
  "job_id": "wf_01J...",
  "tenant_id": "resolved-tenant",
  "operator_id": "resolved-operator",
  "status": "succeeded"
}
```

This allows downstream audit logs to store verifiable identity without trusting request body fields.

## 8. Failure Behavior

| Condition | Status | Response |
| --- | --- | --- |
| Missing tenant claim | `failed` | Reject job creation; do not queue |
| Tenant mismatch between claim and body | `failed` | Reject job creation |
| Operator without decision permission | `failed` or `403` | Reject operator-decision request |
| Cross-tenant query attempt | `failed` | Reject query; log audit event |
| Missing operator identity on decision | `needs_review` or `failed` | Record review flag; do not apply action |

## 9. Validation and Evidence

Acceptance criteria for TRA-13:

- Design derives operator identity and tenant context server-side instead of trusting request body fields.
- Role boundaries for operator, analyst, admin, and readonly are specified without choosing a new identity provider.
- No auth dependency, external IdP integration, credential storage, or runtime implementation is introduced.
- Query builder and job envelope contracts reflect immutable server-resolved tenant/operator identity.

Evidence to record in `board.json`:

- `docs/design/auth_rbac_tenant_boundary.md`
- Updated acceptance criteria and checks for `STWI-SYM-017` / `TRA-13`
- Regenerated `board.md` and `status_report.md`

## 10. Implementation Roadmap (Follow-On Tickets)

| Future Ticket | Scope |
| --- | --- |
| Auth middleware contract | Define request context injection contract for FastAPI without adding IdP |
| Operator identity mapping | Implement server-side mapping from gateway/mTLS claim to internal operator id |
| RBAC enforcement | Add role allowlist checks in API layer |
| Query builder hardening | Remove default-tenant fallback and enforce resolved tenant_id |
| Integration tests | Add focused tests for tenant mismatch, missing claim, and role denial |

## 10.1 Implemented Boundary Direction

`TRA-30` introduces a typed `PrincipalResolver` seam. Production composition
must inject a trusted server-side resolver; app startup fails without one.
Development, test, and demo may use an explicitly provisional resolver so
offline evidence remains reproducible. That resolver is never production
identity evidence and does not satisfy any future deployment authentication
requirement. Production composition rejects both body-derived and static
principal resolvers even when they are injected explicitly.
POST, GET, SSE reconnect, and operator-decision endpoints enforce tenant and
role checks. Denials return stable `AUTH_*` codes plus a `trace_id`; logs omit
tenant hints, operator hints, credentials, and raw resolver exception text.

## 11. References

- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- `src/stwi/t4_orchestrator/api.py`
- `src/stwi/t4_orchestrator/orchestrator.py`
- `src/stwi/t3_knowledge/query_builder.py`
- `docs/guides/observability_minimum.md`
