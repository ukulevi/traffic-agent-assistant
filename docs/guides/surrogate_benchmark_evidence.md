# STWI — Surrogate Benchmark Evidence Runbook

**Ticket:** `TRA-6` / `STWI-SYM-005`
**Status:** Draft
**Scope:** Documentation and assertions only. Preserve existing private benchmark artifacts; do not move, rename, or publish raw weights, datasets, or benchmark outputs outside approved private paths.

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

Surrogate-only P99 was measured offline on the local benchmark artifact above and
recorded as approximately 14.12 ms. That satisfies `surrogate_p99_ms < 500 ms`.

End-to-end P95 and hard-deadline P99 are not yet measured in this runbook. Do not
claim E2E SLA without additional evidence.

### 5.1 E2E measurement plan

The following plan is to support `e2e_p95_ms <= 30000` and
`hard_deadline_p99_ms <= 180000` in a later measurement pass. It is intentionally
kept offline and bounded.

- **Wrap the live job path with timing probes only:** add local event span names
  around inference, retrieval, safety-loop, and DB/queue access without changing
  business logic. Do not add new external services.
- **Fix one benchmark input:** reuse an approved offline scenario rather than
  synthetic noise so the E2E time reflects real conditional branching and queue
  latency.
- **Record process/system time separately:** machine time, wall time, and queue
  wait time when applicable, then derive E2E from wall time minus externally
  caused idle time.
- **Hold the deadline constant:** use the `project_contract.json` SLA target as
  the pass/fail boundary, not an arbitrary soft limit.
- **Report calibration explicitly:** state whether the run includes real queue
  latency, model cold-start, and cache-miss paths, or only warm-path surrogate
  inference.
- **Deliver a private artifact path:** store the raw E2E measurement under
  `data/derived/private/phase2_surrogate/` and never publish raw timings,
  machine identifiers, or environment metadata in public documents.

## 6. Archive procedure

- Keep the primary source in `data/derived/private/phase2_surrogate/v3/`.
- Do not commit raw benchmark JSON into the repository.
- If a rerun is needed, create a timestamped sibling directory such as
  `v3/run_<UTC timestamp>` and keep the original report untouched.
- When multiple runs exist, maintain a short local manifest with run timestamp,
  machine profile, and pass/fail status. The manifest may be referenced in QA
  notes but must not expose secrets, private weights, or raw data.
- All public documentation may cite only the scalar `p99_ms`, status, and the
  approved local artifact path.

## Benchmark profile compliance

Current artifact: `data/derived/private/phase2_surrogate/v3/benchmark_report.json`
- P99: `14.12 ms` < `500 ms` target
- Device: CPU-only, `cpu_threads=8`
- Memory: `32 GB RAM`
- GPU VRAM: `0 GB` (no GPU in current artifact)

Contract requirement: `cpu_cores=8`, `ram_gb=32`, `gpu_vram_gb_min=12`, `gpu_vram_gb_max=16`

### Finding
The current benchmark artifact **does not match the contract benchmark profile** for GPU VRAM. The P99 latency is well within the 500 ms threshold, but the measurement was taken on CPU, not on the specified GPU configuration.

### Compliance path
1. **Short-term evidence:** The CPU benchmark with `p99_ms=14.12` provides strong evidence that the surrogate is fast enough to meet the 500 ms target even without GPU acceleration.
2. **Full contract compliance:** Requires a benchmark rerun on the specified hardware profile (`8 CPU / 32 GB RAM / NVIDIA GPU 12–16 GB`) to generate a fully contract-compliant artifact.
3. **Required measured fields:** The report records `cpu_cores`, `ram_gb`, `device`, and the measured numeric `gpu_vram_gb`. Contract range fields are expectations, not substitutes for measured hardware evidence.
4. **Validator behavior:** `scripts/validation/validate_surrogate_benchmark_evidence.py` fails closed when the measured profile does not match the contract. This prevents false claims of compliance.

### Action
- [ ] Schedule GPU benchmark run on the specified hardware profile
- [ ] Update `benchmark_report.json` with `device` and measured `gpu_vram_gb`
- [ ] Re-run validator to confirm `benchmark_profile_match: true`
