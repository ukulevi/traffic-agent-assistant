# Comprehensive Hybrid Demo Acceptance

**Scope:** Offline comprehensive profile plus optional real-service probes. This
document is not a production-readiness, SLA, RTSP, legal-review or model-accuracy
claim.

## Acceptance contract

The offline profile is accepted only when the versioned manifest contains all
17 capabilities from `stwi.demo.scenarios`, every mandatory capability is
`pass`, and the global safety/privacy invariants remain true:

- aggregate-only; no retained raw video or image payload;
- no automatic actuation and no system-applied operator decision;
- `recommended_action` only for `succeeded`;
- `candidate_action` only for `needs_review`;
- neither action for `failed` or `expired`;
- trace/model/data version and exactly one terminal event for every passing job;
- cross-tenant and invalid-input probes create no job;
- static preview is non-mutating.

## Reproducible commands

```powershell
python -m unittest discover -s tests/demo -v
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
node --test tests/frontend/*.test.mjs
node --check src/stwi/t4_orchestrator/static/dashboard.js
node --check src/stwi/t4_orchestrator/static/dashboard-view.js
```

The offline CLI returns exit code 0 only when the manifest verdict is `pass`.
The evidence file is intentionally outside the repository and contains only
synthetic aggregate metadata.

## Optional services profile

```powershell
python scripts/demo/run_mvp_smoke.py --profile services --output C:\tmp\stwi-services-evidence.json
```

Docker, Redis/Celery, Qdrant and TimescaleDB are probed independently without
mock replacement. An unavailable dependency is `not_verified`; a probe error is
`fail`. Both produce a non-zero, non-pass profile verdict. Secrets and raw
exceptions must not be printed.

## Browser acceptance

Serve `stwi.app:app` with `STWI_RUNTIME_MODE=demo` on loopback and inspect:

- safe approval and safe rejection;
- `refinement` shows two distinct candidate evaluations;
- `needs_review` never enables approval;
- failed/expired rendering exposes no action;
- SSE reconnect/polling fallback do not duplicate execution;
- keyboard focus, decision dialog, narrow viewport and console state;
- static preview cannot submit.

Browser acceptance: pass for the verified synthetic/offline scope on
2026-08-13. Desktop at 1280 px and mobile at 390 px preserve the input-first
workflow, keyboard focus order and route evidence without horizontal overflow.
The provisional live request fails closed to `needs_review`; the dashboard and
31-slide presentation report no console warning or error. Automated frontend
tests retain coverage for approval, rejection, failed/expired rendering, SSE
reconnect and static-preview mutation guards.

## PDF acceptance

PDF acceptance: pass on 2026-08-13. GitHub Actions built the 85-page report
with XeLaTeX for PR #51. Affected architecture, routing, evaluation and API
pages were rendered and visually inspected. The malformed
`green_time_ratio` command and overlapping API path were corrected before the
PR was merged as `e760ca396e9da70420e2b428562d2c57ba0b0940`.

## Human Review gates remaining

- live RTSP/camera privacy and calibration evidence;
- contract GPU profile and promoted model artifacts;
- non-mock calibration and surrogate/E2E benchmark;
- approved production identity, legal/SOP corpus and deployment environment;
- TLS/DNS, backup/restore drill, monitoring/on-call and go/no-go decision.

These gates remain explicit regardless of offline or service-profile results.
