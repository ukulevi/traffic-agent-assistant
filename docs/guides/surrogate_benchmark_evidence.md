# STWI — Surrogate Benchmark Evidence Runbook

**Ticket:** `TRA-6` / `STWI-SYM-005`
**Status:** Draft
**Scope:** Documentation only. Preserve existing private benchmark artifacts; do not move, rename, or publish raw weights, datasets, or benchmark outputs outside approved private paths.

## 1. Purpose

Record how surrogate latency is measured, how the benchmark report is interpreted,
and what remains unmeasured. This runbook exists to support QA evidence for
`surrogate_p99_ms < 500` without inventing new hardware claims.

## 2. Contract targets

From `project_contract.json`:

- `surrogate_p99_ms`: 500 ms
- `e2e_p95_ms`: 30000 ms
- `hard_deadline_p99_ms`: 180000 ms
- benchmark profile: 8 CPU cores, 32 GB RAM, 12-16 GB GPU VRAM

## 3. Existing local benchmark artifact

Use the current private artifact as primary evidence:

- `data/derived/private/phase2_surrogate/v3/benchmark_report.json`

Current recorded values on this machine:

- `p50_ms`: approx 3.12 ms
- `p95_ms`: approx 10.54 ms
- `p99_ms`: approx 14.12 ms
- `status`: pass against 500 ms target

## 4. Measurement constraints

- Do not read private weights, raw datasets, or outputs beyond required metadata.
- Do not rename, copy, or publish private benchmark artifacts into public docs/slides.
- If a rerun is done, preserve previous report and stamp new report with run timestamp.

## 5. E2E status

Measured surrogate-only P99 is present. End-to-end P95 and hard deadline P99 are not yet measured in this runbook. Do not claim E2E SLA without additional evidence.

## 6. QA checklist

- [ ] `data/derived/private/phase2_surrogate/v3/benchmark_report.json` exists and is unmodified from approved run
- [ ] Recorded `p99_ms < 500`
- [ ] E2E evidence is absent or explicitly labeled pending
