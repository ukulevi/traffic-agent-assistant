# Trusted Production UI Context Design

**Ticket:** `TRA-58`
**Decision:** Approved by Human Review on 2026-08-03
**Scope:** Canonical authenticated read-only API for dashboard bootstrap

## 1. Goal

Add `GET /api/v1/ui-context` as the canonical production bootstrap endpoint for the STWI operator dashboard. The endpoint exposes only the server-resolved identity, authorization scope, allowed network nodes and bounded UI capabilities needed to render the dashboard. It does not create jobs, execute actions, reveal credentials or weaken the human-approval boundary.

## 2. Selected approach

The selected approach is a typed endpoint backed by two independent server-side seams:

1. Existing `PrincipalResolver` provides trusted `tenant_id`, `operator_id` and roles.
2. A new non-provisional `UiContextProvider` provides allowlisted `node_ids` and capabilities for that resolved principal.

The API combines these values into a validated `UiContextResponse`. Production startup must receive both a trusted principal resolver and a trusted UI context provider. Development and demo do not register the endpoint, so the existing dashboard behavior remains exact: `404 /api/v1/ui-context` followed by validation of the provisional STWI OpenAPI document.

This approach is preferred over deriving node scope from demo constants or accepting context hints from the browser because those alternatives would create a production authorization bypass. It is also preferred over removing the endpoint because the production dashboard needs an authenticated way to discover operator scope before creating a job.

## 3. Canonical API contract

### 3.1 Endpoint

```text
GET /api/v1/ui-context
```

The endpoint is read-only and accepts no query parameters or request body. It must return `Cache-Control: no-store`.

### 3.2 Successful response

```json
{
  "mode": "production",
  "tenant_id": "tenant-a",
  "operator_id": "operator-17",
  "roles": ["operator"],
  "node_ids": ["node_00", "node_01"],
  "capabilities": {
    "record_decision": true
  }
}
```

`UiContextResponse` has these rules:

- `mode` is the literal `production`.
- `tenant_id` and `operator_id` are non-empty values from `PrincipalResolver`.
- `roles` contains unique values from `PrincipalRole`; it is never empty.
- `node_ids` contains 1–20 unique non-empty node identifiers in stable network order.
- `capabilities` is a typed object. The initial contract contains only `record_decision: bool`; unknown capability fields are rejected.
- The response never contains credentials, tokens, raw video references, executable actions or automatic-actuation fields.

### 3.3 Failure behavior

| Condition | HTTP | Stable behavior |
|---|---:|---|
| Missing or invalid trusted principal | 401 | Existing `AUTH_PRINCIPAL_REQUIRED` body with `trace_id`. |
| Principal has no supported dashboard role | 403 | `AUTH_ROLE_DENIED`; no context payload. |
| Context provider missing in production composition | startup failure | Application does not start. |
| Provider fails or returns invalid/empty scope | 503 | `UI_CONTEXT_UNAVAILABLE` with `trace_id`; no demo fallback. |
| Demo/development runtime | 404 | Existing provisional OpenAPI fallback remains available to the dashboard. |

The dashboard treats every non-404 error, malformed 200 response or network failure as `static_preview`. Only an exact 404 may attempt the demo fallback.

## 4. Server-side interfaces

Add an immutable typed scope and provider protocol:

```python
@dataclass(frozen=True)
class UiContextScope:
    node_ids: tuple[str, ...]
    record_decision: bool


class UiContextProvider(Protocol):
    def resolve(self, *, principal: ServerPrincipal) -> UiContextScope:
        ...
```

Production composition rejects providers marked `is_provisional_provider = True`. A deterministic static provider may exist only for tests. Demo composition does not inject a provider and therefore does not register the endpoint.

`UiContextScope` validates non-empty unique node IDs, a maximum of 20 nodes, stable input order and a strict boolean capability. It does not accept tenant/operator hints because the principal is already resolved at the auth boundary.

## 5. Frontend normalization

The wire contract remains API-style `snake_case`. `dashboard-mode.js` validates every field and converts the successful response into the existing internal shape:

```javascript
{
  mode: "production",
  tenantId,
  operatorId,
  roles,
  nodeIds,
  capabilities: { recordDecision }
}
```

Production validation rejects duplicate/empty node IDs, unsupported roles, unknown capability keys and non-boolean capability values. Demo continues to expose `demoPresets` only in the local internal context; it is not part of the production wire contract.

## 6. Contract and artifact synchronization

The implementation must update these sources together:

- `project_contract.json`: add `ui_context` under `api`.
- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`: document bootstrap, response and failure rules.
- `docs/design/auth_rbac_tenant_boundary.md`: bind the endpoint to `PrincipalResolver` and server-side scope.
- `report/chapters/appendix_api.tex`: add the endpoint and compact response example.
- `report/chapters/ch07_agent.tex`: document authenticated dashboard bootstrap.
- Dashboard/operator guide: explain production context versus demo fallback.

No tensor, SLA, status, technology, legal corpus, action or automatic-actuation contract changes are allowed.

## 7. Test strategy

Implementation follows TDD in this order:

1. Contract test fails until `project_contract.json` declares the endpoint.
2. Pydantic/dataclass tests fail for duplicate, empty, over-limit or unknown scope fields.
3. API tests fail until a trusted production context returns 200 with `no-store`.
4. Auth tests fail until missing principal, unsupported role, provider failure and provisional provider paths fail closed.
5. Demo API test proves `/api/v1/ui-context` remains 404.
6. Frontend tests fail until snake_case capabilities are normalized and malformed/unknown context stays `static_preview`.
7. Documentation, JavaScript, full Python and release QA run after all focused tests pass.

## 8. Non-goals

- Selecting or adding an external identity provider.
- Adding a node-registry service or new dependency.
- Returning permissions for field actuation.
- Trusting tenant, operator, roles, nodes or capabilities supplied by the client.
- Making demo fallback available after production auth/provider failures.
- Changing existing What-If job request/response fields.

## 9. Self-review

- No placeholders or deferred requirements remain.
- The endpoint is read-only and fail-closed.
- Demo and production behavior are unambiguous.
- Provider ownership is separated from authentication ownership.
- All contract and derived artifacts are identified.
- Scope remains one testable API feature with no new external service.
