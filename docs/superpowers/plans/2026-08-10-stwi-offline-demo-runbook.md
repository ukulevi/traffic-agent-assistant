# STWI Offline Demo Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current broad demo document with one focused Vietnamese runbook containing setup and all 13 offline demo scenarios.

**Architecture:** Keep one operator-facing Markdown file as the runnable source. Use `src/stwi/demo/scenarios.py` as the canonical scenario list and distinguish dashboard-driven scenarios from CLI/evidence-only boundary scenarios.

**Tech Stack:** Markdown, PowerShell commands, FastAPI/Uvicorn dashboard, Python unittest and project documentation validator.

## Global Constraints

- Modify only the offline demo runbook and its dedicated design/plan artifacts.
- Preserve the 13 capability names and expected statuses from `src/stwi/demo/scenarios.py`.
- Use only `http://127.0.0.1:8000/demo/`; do not expose a public bind address.
- Do not include Docker, services profile, production readiness, RTSP, GPU, SLA, release or unrelated FAQ material.
- Do not claim automatic actuation, field observations or production evidence.
- Do not stage, commit or push.

---

### Task 1: Rewrite the offline demo runbook

**Files:**
- Modify: `docs/guides/mvp_demo_runbook.md`
- Reference: `src/stwi/demo/scenarios.py`
- Test: `tests/demo/test_demo_scenarios.py`

**Interfaces:**
- Consumes: ordered `offline_scenarios()` catalog with 13 immutable capability names.
- Produces: a standalone Vietnamese setup and presenter runbook.

- [x] **Step 1: Record the required document skeleton**

Use exactly these top-level sections:

```markdown
# Runbook demo offline SmartTraffic What-If
## 1. Chuẩn bị môi trường
## 2. Kiểm tra trước khi demo
## 3. Ma trận 13 kịch bản
## 4. Hướng dẫn chạy từng kịch bản
## 5. Trình tự demo đề xuất
## 6. Xử lý lỗi khi demo
## 7. Kết thúc
```

- [x] **Step 2: Write copy/paste setup commands**

Include installation, offline smoke, server startup and the exact dashboard URL:

```powershell
pip install -e ".[orchestrator]"
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

State that the expected smoke output is `profile=offline`, `verdict=pass`, and `capability_count=13`.

- [x] **Step 3: Add the canonical scenario matrix**

List each capability exactly once with its execution surface and expected result:

```text
safe_approval       dashboard safe preset + approve    succeeded
safe_rejection      dashboard safe preset + reject     succeeded
refinement_success  dashboard refinement preset        succeeded
unsafe_vc           dashboard unsafe-vc preset          needs_review
ood                 dashboard ood preset                needs_review
high_uncertainty    dashboard uncertainty preset        needs_review
missing_citation    dashboard missing-evidence preset   needs_review
dependency_failure  offline evidence                    failed
deadline_exceeded   offline evidence                    expired
invalid_scenario    offline evidence                    HTTP 422
tenant_scope_denied offline evidence                    HTTP 403
sse_reconnect       offline evidence                    HTTP 200/no duplicate terminal event
static_preview      open static HTML without runtime    non-mutating preview
```

- [x] **Step 4: Write actionable instructions for all scenarios**

For dashboard scenarios, specify preset, node, submit action, terminal status and action-field expectation. For evidence-only scenarios, tell the presenter to open `C:\tmp\stwi-offline-evidence.json`, locate the capability by `name`, and verify `status`, `observed`, `terminal_status` and action fields without deliberately breaking the live dashboard.

- [x] **Step 5: Remove out-of-scope material**

Delete the services profile, Docker/service probes, production/RTSP/GPU/SLA/release discussion, dual 7/15-minute scripts, extended FAQ and Human Review appendix. Retain only troubleshooting needed to open `/demo/`, identify static preview, handle connection refusal and stop Uvicorn.

- [x] **Step 6: Verify scenario coverage and documentation health**

Run:

```powershell
python -m unittest tests.demo.test_demo_scenarios
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Expected: all commands exit `0`; the runbook contains all 13 canonical names and contains no active setup for Docker or the services profile.
