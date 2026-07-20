# STWI Demo Safety Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cung cấp demo STWI mô phỏng, fail-closed và tái lập được nhiều nhánh safety qua UI.

**Architecture:** Giữ nguyên API endpoints/status, bổ sung typed request validation và một adapter chỉ dành cho demo. UI preset chỉ sinh payload chuẩn hiện hữu; orchestrator và safety loop quyết định terminal state.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, unittest, HTML/CSS/JavaScript thuần.

## Global Constraints

- Decision-support only; `automatic_actuation=false` và human approval bắt buộc.
- API create job vẫn trả HTTP 202; status giữ nguyên contract.
- V/C mặc định 0.9 là configurable demo policy, không phải quy định pháp luật.
- Dữ liệu demo synthetic/aggregate-only; không raw video hoặc claim production.
- Không thêm dependency.

---

### Task 1: Typed request và demo node boundary

**Files:**
- Modify: `src/stwi/t4_orchestrator/contracts.py`
- Modify: `src/stwi/t4_orchestrator/api.py`
- Test: `tests/t4_orchestrator/test_t4_contracts.py`
- Test: `tests/t4_orchestrator/test_t4_api_http.py`

**Interfaces:**
- Produces: `CandidateAction`, `validate_demo_node_ids(request)`.

- [ ] Viết test reject action thiếu field, mismatch node, chuỗi trắng và demo node lạ.
- [ ] Chạy test để xác nhận RED do request hiện chấp nhận input trên.
- [ ] Thêm schema, cross-field validator và demo allowlist lấy từ mock network.
- [ ] Chạy lại test để xác nhận GREEN.

### Task 2: Demo surrogate có profile tái lập

**Files:**
- Create: `src/stwi/t4_orchestrator/demo_adapters.py`
- Modify: `src/stwi/t4_orchestrator/orchestrator.py`
- Test: `tests/t4_orchestrator/test_t4_demo_profiles.py`

**Interfaces:**
- Produces: `DemoSurrogateForecaster.predict(...)` và `demo_node_ids()`.

- [ ] Viết test cho safe, ratio-sensitive, extreme, V/C, OOD và uncertainty.
- [ ] Chạy test để xác nhận RED vì adapter chưa tồn tại.
- [ ] Cài adapter deterministic và chỉ auto-wire khi runtime mode là `demo`.
- [ ] Chạy test để xác nhận GREEN và không ảnh hưởng fake adapters hiện hữu.

### Task 3: Fail-closed operator approval

**Files:**
- Modify: `src/stwi/t4_orchestrator/api.py`
- Test: `tests/t4_orchestrator/test_t4_api_http.py`

**Interfaces:**
- Consumes: terminal `JobStatus` và `OperatorDecision`.

- [ ] Viết test `approved` bị 409 cho `needs_review`/`failed`/`expired`.
- [ ] Chạy test để xác nhận RED do API hiện nhận mọi terminal state.
- [ ] Chặn approval nếu status khác `succeeded`; vẫn cho phép rejection audit.
- [ ] Chạy test để xác nhận GREEN.

### Task 4: Preset UI và diễn giải mock

**Files:**
- Modify: `src/stwi/t4_orchestrator/static/index.html`
- Modify: `src/stwi/t4_orchestrator/static/dashboard.js`
- Modify: `src/stwi/t4_orchestrator/static/dashboard.css`
- Modify: `tests/demo/test_dashboard_static.py`

**Interfaces:**
- Produces: preset selector, node selector và payload API không đổi schema.

- [ ] Viết static regression tests cho preset, node registry, fail-closed copy và approval state.
- [ ] Chạy test để xác nhận RED.
- [ ] Thêm controls, preset mapping và copy Vietnamese-first bằng DOM text APIs.
- [ ] Chạy unit/static tests và `node --check` để xác nhận GREEN.

### Task 5: Tài liệu, smoke và browser QA

**Files:**
- Modify: `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- Modify: `docs/guides/mvp_demo_runbook.md`
- Modify: `docs/guides/mvp_operator_dashboard.md`
- Modify: `scripts/demo/run_mvp_smoke.py`
- Test: `tests/demo/test_mvp_smoke.py`

**Interfaces:**
- Produces: runbook và smoke evidence bao phủ các terminal profile.

- [ ] Đồng bộ node IDs, preset, action semantics và mock disclaimer.
- [ ] Chạy smoke, contract/API tests và release verifier.
- [ ] Khởi động `/demo/`, chạy từng preset, kiểm tra status/action/copy và console.
- [ ] Chạy `git diff --check`; báo rõ mọi giới hạn production còn lại.
