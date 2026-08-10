# STWI Comprehensive Hybrid Demo Design

**Status:** Approved for implementation on 2026-08-03
**Scope:** Deterministic offline demo plus an optional service-backed lab
**Contract:** `project_contract.json` remains unchanged

## 1. Goal

Provide one reproducible demo workflow that explains the complete STWI
decision-support path without claiming field calibration, production SLA, raw
camera processing, or automatic actuation. The offline profile is mandatory and
must run without Docker, network access, credentials, RTSP, or GPU. The services
profile is optional and may report `not_verified` when its approved dependencies
are unavailable.

## 2. Approach

Use a capability-aware runner rather than a documentation-only checklist or a
production-only Compose demo. The runner owns scenario selection, preflight,
evidence aggregation, and the final verdict. It calls existing public API and
contract boundaries instead of duplicating orchestrator logic.

Profiles:

- `offline`: deterministic synthetic aggregates and provisional adapters;
- `services`: real Redis/Celery/Qdrant/TimescaleDB boundaries after preflight;
- RTSP and contract-profile GPU benchmarks remain separate Human Review gates.

The services profile must never replace missing evidence with offline results.

## 3. Capability Flow

```text
Preflight
  -> data/tensor contract
  -> baseline forecast
  -> scenario surrogate
  -> legal/query evidence
  -> counterfactual safety/refinement
  -> HTTP 202 + GET + SSE
  -> operator decision
  -> evidence manifest
```

The dashboard is the presentation surface. The runner is the reproducible
acceptance surface. Both use the same scenario catalog and canonical status
semantics.

## 4. Offline Scenario Matrix

| Case | Expected result | Evidence demonstrated |
|---|---|---|
| `safe_approval` | `succeeded`, approved | recommendation remains non-executable |
| `safe_rejection` | `succeeded`, rejected | operator may reject a safe recommendation |
| `refinement_success` | `succeeded` after changed candidate | bounded re-simulation is real, not repeated logging |
| `unsafe_vc` | `needs_review` | V/C policy fail-closed |
| `ood` | `needs_review` | OOD cannot be refined away |
| `high_uncertainty` | `needs_review` | uncertainty cannot be refined away |
| `missing_citation` | `needs_review` | legal abstention |
| `dependency_failure` | `failed` | no action after dependency failure |
| `deadline_exceeded` | `expired` | deadline and immutable terminal state |
| `invalid_scenario` | typed HTTP validation error | reject before dispatch |
| `tenant_scope_denied` | typed auth error | tenant/RBAC isolation |
| `sse_reconnect` | no duplicate execution | monotonic event replay/idempotency |
| `static_preview` | mutation disabled | untrusted UI runtime fails closed |

Queued and running transitions are recorded as lifecycle evidence even though
they are not terminal cases.

## 5. Evidence Manifest

The top-level manifest contains:

- schema version, demo profile, start/end timestamps and overall verdict;
- contract/model/data/policy/corpus versions;
- capability results with `pass`, `fail`, or `not_verified`;
- case results with HTTP status, job status, event sequence and trace ID;
- baseline/scenario summaries, citations, safety iterations and action history;
- operator decision with `applied_by_system=false`;
- `raw_video_retained=false` and `automatic_actuation=false`;
- redacted failure codes and an explicit reason for every `not_verified` item.

The manifest must not contain DSNs, API keys, RTSP URLs, image payloads, raw
video references, private model paths, or full internal exceptions.

## 6. Services Profile

The optional profile preflights Docker and the approved service endpoints, then
collects independent evidence for:

- Qdrant/BGE-m3 retrieval and effective-date filtering;
- TimescaleDB read-only, parameterized, tenant-scoped queries;
- Redis job/event persistence;
- Celery idempotent dispatch;
- SSE reconnect after store/API recreation;
- dependency outage mapping to `failed` or `expired` without recommendations.

If a dependency or credential is absent, its capability is `not_verified` and
the overall services verdict cannot be `pass`. Offline evidence remains valid
for the demo profile but is not promoted to service-backed evidence.

## 7. Presentation Runbook

The runbook has two durations:

- 7-minute executive flow: scope disclaimer, safe case, refinement case,
  fail-closed case, operator decision, evidence summary;
- 15-minute technical flow: adds tensor contract, API/SSE, citations,
  uncertainty/OOD, failed/expired, tenant isolation and service preflight.

It includes presenter wording, expected UI state, recovery actions, a pre-demo
checklist, a post-demo cleanup checklist, and a question/answer section. It
must never describe the synthetic cases as field observations or accuracy
benchmarks.

## 8. Error Handling

- Offline mandatory capability failure makes the offline verdict `fail`.
- Optional unavailable dependency produces `not_verified`, never `pass`.
- Invalid or contradictory evidence makes the manifest invalid.
- Unknown job status, executable candidate, missing trace/version, duplicate
  terminal event, or automatic-actuation claim fails the run.
- Evidence writing is atomic so a partial file is not mistaken for a pass.

## 9. Verification

Tests cover scenario catalog validation, every terminal branch, evidence schema,
secret redaction, service preflight tri-state behavior, CLI exit codes and
dashboard/runbook consistency. Release QA also runs the full Python suite,
frontend Node tests, docs validation, JavaScript checks and `git diff --check`.

Live RTSP, legal-owner approval, restore drills and contract-profile GPU results
