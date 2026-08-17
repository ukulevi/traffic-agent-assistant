# Network-impact evidence and showcase video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Add typed per-node network-impact evidence to the synthetic 20-node demo and produce a truthful MP4 showcasing location changes, neighboring impacts, route comparison and fail-closed review states.

**Architecture:** The orchestrator emits a complete validated `network_impact` grid from the same incident-aware forecasts used by the safety loop. The dashboard validates one shared view model for the Leaflet map and accessible table; route evidence remains independently typed and non-executable. A deterministic browser capture script records three scenarios with subtitles and provenance overlays.

**Tech Stack:** Python/Pydantic/FastAPI/SSE, vanilla ES modules, Leaflet CRS.Simple, Node test runner, Python unittest, ffmpeg/imageio-ffmpeg for MP4 capture.

## Global Constraints

- Preserve `X[B,12,N,16]`, `M[B,12,N,16]`, `A[N,N]`, `Y[B,6,N,2]` and stable 20-node order.
- `network_impact` is optional for backward compatibility but must fail closed when present and malformed.
- No raw video, automatic actuation, executable route, or claim of real-world optimality.
- `succeeded` remains advisory and requires operator approval; `needs_review`, failed and expired never promote a route.
- All metrics require matching topology/model/data provenance and finite values.

---

### Task 1: Extend the typed result contract

**Files:**
- Modify: `src/stwi/t4_orchestrator/contracts.py` (`WhatIfJobResult` and new frozen impact models)
- Test: `tests/t4_orchestrator/test_t4_contracts.py`

**Interfaces:** `NetworkImpactPoint(node_id: str, horizon_minutes: int, traffic_volume_5m: float, avg_speed_kmh: float, vc_ratio: float, uncertainty_score: float, ood_score: float, impact_role: Literal["incident", "adjacent", "network"])`; `NetworkImpactEvidence(topology_version: str, model_version: str, data_version: str, horizons_minutes: tuple[int, ...], incident_node_ids: tuple[str, ...], node_impacts: tuple[NetworkImpactPoint, ...])`; `WhatIfJobResult.network_impact: NetworkImpactEvidence | None`.

- [x] Add RED tests for a valid 20×6 grid and rejection of invalid role, unknown node, duplicate `(node,horizon)`, missing horizon and non-finite metric.
- [x] Run `python -m unittest tests.t4_orchestrator.test_t4_contracts` and confirm RED.
- [x] Implement Pydantic models with strict bounded/finite numeric validation and optional result field; do not alter existing status or action fields.
- [x] Re-run contract tests and `python -m unittest tests.contracts.test_project_contract`.
- [x] Commit `feat: add typed network impact evidence contract`.

### Task 2: Produce complete incident-aware impact evidence

**Files:**
- Modify: `src/stwi/t4_orchestrator/orchestrator.py`
- Create: `src/stwi/t4_orchestrator/network_impact.py`
- Test: `tests/t4_orchestrator/test_t4_network_impact.py`

**Interfaces:** `build_network_impact(results, topology, incident, horizons_minutes, model_version, data_version) -> NetworkImpactEvidence` and `validate_network_impact(evidence, topology, expected_horizons) -> None`.

- [x] Add RED tests asserting 20 nodes × 6 horizons, roles derived from trusted directed neighbors, and incident relocation from `node_05` to `node_14`.
- [x] Run the focused test and confirm the builder is absent or incomplete.
- [x] Build the grid from typed incident-aware forecast results and trusted topology; reject missing/duplicate/provenance-mismatched rows rather than filling values.
- [x] Attach evidence to all terminal result paths that have complete scenario forecasts; leave it `None` with an explicit review reason when evidence cannot be trusted.
- [x] Run focused safety, routing, demo profile and API serialization tests.
- [ ] Commit `feat: emit validated network impact evidence`.

### Task 3: Derive one safe impact view model

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/dashboard-state.js`, `src/stwi/t4_orchestrator/static/dashboard-map.js`
- Test: `tests/frontend/dashboard-map.test.mjs`, `tests/frontend/dashboard-state.test.mjs`

**Interfaces:** `deriveNetworkImpactViewModel({status, networkImpact, authorizedNodeIds, topology}) -> {status, topologyVersion, horizons, selectedHorizon, rows, incidentNodeIds, available}`.

- [x] Add RED tests for exact grid acceptance, malformed-grid unavailable state, status fail-closed behavior, and selected-horizon filtering.
- [x] Implement strict client validation against authorized node order and directed topology; never synthesize missing metrics.
- [x] Keep `available=false` for production context failure, invalid evidence, needs_review without evidence, failed and expired results.
- [x] Run all map/state/frontend tests.
- [ ] Commit `feat: validate network impact view model`.

### Task 4: Render map, table and accessibility evidence

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/index.html`, `dashboard-map.js`, `dashboard-view.js`, `dashboard.css`
- Test: `tests/frontend/dashboard-view.test.mjs`, `tests/frontend/dashboard-coordinator.test.mjs`, `tests/demo/test_dashboard_static.py`

- [x] Add RED tests for map/table parity, horizon selector, explicit incident/adjacent/network labels, keyboard focus and unavailable evidence.
- [x] Add a non-mutating impact panel, legend and horizon select; every metric includes units and uncertainty/OOD, and the table is the keyboard fallback.
- [x] Make map marker overlays and table rows consume only the shared view model; clear overlays on invalid/non-terminal states.
- [x] Run full frontend suite, static dashboard tests, JS syntax and docs validator.
- [ ] Commit `feat: show network impact evidence on dashboard`.

### Task 5: Update runbook and create deterministic capture script

**Files:**
- Modify: `docs/guides/mvp_dashboard_demo_walkthrough.md`
- Create: `scripts/demo/capture_network_impact_showcase.ps1`
- Test: `tests/demo/test_comprehensive_demo.py` and capture smoke checks

- [x] Add runbook steps for `node_05` refinement, `node_14` relocation, and third-node `needs_review`/missing-evidence verification, including exact labels to read aloud.
- [x] Implement capture script that starts the demo server, drives the three deterministic scenarios, records browser frames at 1280×720, adds subtitles/provenance/limitation captions, and writes `tmp/demo-network-impact-showcase.mp4`; stop the server in a finally block.
- [x] Add a smoke assertion that the output exists, is MP4, has duration 5–6 minutes target metadata (or a documented shorter CI capture mode), and contains no raw-video input.
- [x] Run docs validation and a local capture smoke run; inspect representative frames for legibility and state accuracy.
- [ ] Commit `docs: add network impact showcase runbook and capture`.

### Task 6: Release review and PR

**Files:** `git` history and generated ignored MP4 only; no contract artifact omissions.

- [x] Run full Python suite, full frontend suite, contract tests, docs validator, JS checks, `git diff --check` and `stwi-release-qa`.
- [x] Review the MP4 against the three required scenarios and confirm subtitles never say optimal, proven safe in the field, or automatic.
- [x] Run `git status --short` and ensure caches/logs/video are not staged.
- [ ] Push the feature branch, open a separate PR, monitor `fast-guards` and `build-pdf`, then merge with admin only after both pass.
