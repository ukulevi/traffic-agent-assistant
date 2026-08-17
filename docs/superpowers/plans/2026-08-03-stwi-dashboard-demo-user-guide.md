# STWI Dashboard Demo User Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tạo walkthrough Vietnamese-first có ảnh chụp thật, hướng dẫn người dùng chạy và kiểm tra dashboard STWI bằng các test case deterministic của demo.

**Architecture:** Walkthrough là tài liệu Markdown độc lập, dùng PNG chụp từ FastAPI demo chạy qua HTTP local. Mỗi test case có input, thao tác, kết quả mong đợi và safety assertions; runbook canonical chỉ bổ sung link sang walkthrough để tránh nhân bản quy trình vận hành.

**Tech Stack:** Markdown, PNG, FastAPI/Uvicorn, dashboard HTML/CSS/native ES modules, Codex in-app browser screenshot API, Python validation scripts.

## Global Constraints

- Không có lời thoại hoặc kịch bản thuyết trình.
- Ảnh chỉ chứa dữ liệu synthetic/aggregate; không chứa secret, endpoint riêng, raw video, base64 image hoặc dữ liệu cá nhân.
- Chỉ dùng sáu status canonical: `queued`, `running`, `succeeded`, `needs_review`, `failed`, `expired`.
- Chỉ `succeeded` có `recommended_action`; `needs_review` chỉ có `candidate_action` không executable.
- Mọi action vẫn có `automatic_actuation=false` và cần operator phê duyệt.
- V/C `0.9` được mô tả là policy MVP, không phải quy định pháp luật.
- Citation demo là provisional evidence, không phải xác nhận pháp lý production.
- Không sửa `project_contract.json`, API schema hoặc logic dashboard để ép ảnh khớp tài liệu.
- Không thêm dependency hoặc framework screenshot mới.
- Không stage, commit, push hoặc tạo PR nếu người dùng chưa yêu cầu thao tác Git cụ thể.

---

## File map

| File | Responsibility |
|---|---|
| `docs/guides/mvp_dashboard_demo_walkthrough.md` | Hướng dẫn sử dụng từng bước và test-case matrix. |
| `docs/assets/demo_walkthrough/*.png` | Ảnh chụp dashboard từ runtime HTTP local. |
| `docs/guides/mvp_demo_runbook.md` | Nguồn lệnh khởi động canonical và link sang walkthrough. |
| `docs/superpowers/specs/2026-08-03-stwi-dashboard-demo-user-guide-design.md` | Đặc tả đã duyệt; không sửa trừ khi phát hiện mâu thuẫn. |

---

### Task 1: Chuẩn bị runtime và ma trận ảnh

**Files:**
- Read: `docs/guides/mvp_demo_runbook.md`
- Read: `src/stwi/t4_orchestrator/static/dashboard.js`
- Read: `src/stwi/t4_orchestrator/demo_adapters.py`
- Create directory: `docs/assets/demo_walkthrough/`

**Interfaces:**
- Consumes: lệnh chạy demo canonical và `DEMO_PRESETS` hiện hành.
- Produces: runtime `http://127.0.0.1:8000/demo/` và danh sách test case/ảnh xác nhận từ UI.

- [ ] **Step 1: Xác nhận preset canonical**

Run:

```powershell
rg -n 'safe|unsafe-vc|ood|uncertainty|missing-evidence|extreme|accident|flood|lane-closure|demand-surge|environmental-anomaly' src/stwi/t4_orchestrator/static/dashboard.js src/stwi/t4_orchestrator/demo_adapters.py
```

Expected: đủ 11 preset, không có preset ngoài registry hoặc semantics điều khiển hiện trường.

- [ ] **Step 2: Tạo thư mục ảnh**

Use `apply_patch` to add `docs/assets/demo_walkthrough/.gitkeep` temporarily if the directory does not exist. Remove `.gitkeep` with `apply_patch` after PNG files are present.

- [ ] **Step 3: Khởi động demo bằng Python runtime đã có orchestrator extra**

Run from repository root:

```powershell
$env:STWI_RUNTIME_MODE = "demo"
& 'C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

If port 8000 is occupied by the current STWI process, reuse it after verifying `/openapi.json`; otherwise use the next free loopback port and record that port only as QA infrastructure, not in the guide.

- [ ] **Step 4: Verify runtime identity before screenshots**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json | Select-Object StatusCode
```

Expected: HTTP 200; dashboard header resolves to `Demo synthetic` and does not use static preview.

- [ ] **Step 5: Record the screenshot matrix**

Use these exact output filenames:

```text
01-dashboard-overview.png
02-safe-preset-input.png
03-succeeded-result.png
04-succeeded-evidence.png
05-decision-dialog.png
06-decision-recorded.png
07-unsafe-vc-review.png
08-ood-review.png
09-uncertainty-review.png
10-missing-evidence-review.png
11-incident-presets.png
12-clipboard-fallback.png
```

Expected: filenames match the approved spec exactly.

---

### Task 2: Chụp overview và luồng `safe → succeeded`

**Files:**
- Create: `docs/assets/demo_walkthrough/01-dashboard-overview.png`
- Create: `docs/assets/demo_walkthrough/02-safe-preset-input.png`
- Create: `docs/assets/demo_walkthrough/03-succeeded-result.png`
- Create: `docs/assets/demo_walkthrough/04-succeeded-evidence.png`

**Interfaces:**
- Consumes: dashboard demo HTTP và preset `safe`.
- Produces: ảnh tổng quan, input, result và evidence dùng trong các phần đầu walkthrough.

- [ ] **Step 1: Mở dashboard bằng browser tại URL loopback đã xác nhận**

Claim or create one browser tab, navigate to `/demo/`, and take a fresh DOM snapshot. Confirm one unique `Chạy mô phỏng` button, 20 node options, preset `safe` selected, and `Copy` disabled before a job exists.

- [ ] **Step 2: Chụp overview desktop**

Set viewport to `1440×1000`. Capture the full visible dashboard as `01-dashboard-overview.png`. The image must show runtime mode, connection, result-first workspace, node registry and evidence rail without raw data.

- [ ] **Step 3: Chụp input preset `safe`**

Scroll or clip to the What-If form. Capture `02-safe-preset-input.png` with preset `safe`, `node_00`, `green_time_ratio=0.70`, tenant read-only and the `Simulation only` label visible.

- [ ] **Step 4: Chạy preset bằng control thật**

Confirm the unique `Chạy mô phỏng` locator resolves to count `1`, click it, then wait for canonical status `succeeded`. Do not call the API directly for screenshot state.

- [ ] **Step 5: Chụp result terminal**

Capture `03-succeeded-result.png` around the result and lifecycle panels. It must show `succeeded`, 30-minute result context, `traffic_volume_5m`, `avg_speed_kmh`, V/C and job/trace identifiers.

- [ ] **Step 6: Chụp evidence rail**

Capture `04-succeeded-evidence.png` around safety/evidence. It must show `demo_provisional_valid`, citation details, model/data version and `recommended_action · NON-EXECUTABLE`.

- [ ] **Step 7: Inspect browser logs**

Read console errors/warnings. Expected: no unhandled JavaScript error before clipboard testing.

---

### Task 3: Chụp decision audit-only và clipboard fallback

**Files:**
- Create: `docs/assets/demo_walkthrough/05-decision-dialog.png`
- Create: `docs/assets/demo_walkthrough/06-decision-recorded.png`
- Create: `docs/assets/demo_walkthrough/12-clipboard-fallback.png`

**Interfaces:**
- Consumes: terminal `succeeded` job from Task 2.
- Produces: decision and keyboard/copy evidence used by the walkthrough.

- [ ] **Step 1: Mở decision dialog bằng bàn phím**

Focus the unique `Ghi nhận quyết định` button and press `Enter`. Verify the native `<dialog>` is open and focus is on the first decision permitted by policy.

- [ ] **Step 2: Chụp dialog**

Capture `05-decision-dialog.png`. The image must show immutable job/trace/operator context, decision choices, rationale field and no field implying field actuation.

- [ ] **Step 3: Ghi nhận một quyết định audit-only**

Choose `approved`, enter a concise rationale that states evidence was reviewed, and submit. Wait for GET reconciliation and the immutable decision record.

- [ ] **Step 4: Chụp decision record**

Capture `06-decision-recorded.png` around the decision panel. It must show the recorded decision and `applied_by_system=false`.

- [ ] **Step 5: Chạy lại `safe` để có trace ID chưa ghi decision**

Create a fresh `safe` job if needed, focus outside editable controls, press `C`, and inspect `#copy-status`.

- [ ] **Step 6: Chụp clipboard fallback nếu browser từ chối quyền**

If clipboard is blocked, capture the visible operational message as `12-clipboard-fallback.png` and verify console logs contain no unhandled `NotAllowedError`. If clipboard succeeds, capture the success status under the same filename and document that behavior depends on browser permission.

---

### Task 4: Chụp các test case fail-closed

**Files:**
- Create: `docs/assets/demo_walkthrough/07-unsafe-vc-review.png`
- Create: `docs/assets/demo_walkthrough/08-ood-review.png`
- Create: `docs/assets/demo_walkthrough/09-uncertainty-review.png`
- Create: `docs/assets/demo_walkthrough/10-missing-evidence-review.png`

**Interfaces:**
- Consumes: preset selector and deterministic demo adapters.
- Produces: bốn ảnh phân biệt các lý do `needs_review`.

- [ ] **Step 1: Chạy `unsafe-vc`**

Select preset value `unsafe-vc`, run it, wait for `needs_review`, and capture `07-unsafe-vc-review.png`. Show V/C above policy and ensure no executable recommendation or approve path appears.

- [ ] **Step 2: Chạy `ood`**

Select preset value `ood`, run it, wait for `needs_review`, and capture `08-ood-review.png`. Show OOD/review reason and `candidate_action · NON-EXECUTABLE`.

- [ ] **Step 3: Chạy `uncertainty`**

Select preset value `uncertainty`, run it, wait for `needs_review`, and capture `09-uncertainty-review.png`. Show high-uncertainty reason and disabled approval semantics.

- [ ] **Step 4: Chạy `missing-evidence`**

Select preset value `missing-evidence`, run it, wait for `needs_review`, and capture `10-missing-evidence-review.png`. Show insufficient citation/evidence and no production-validity claim.

- [ ] **Step 5: Verify the omitted `extreme` screenshot is covered textually**

Run `extreme` once for verification. Record its expected `needs_review` behavior in the guide, but do not add a thirteenth screenshot unless its UI differs materially from the four captured fail-closed branches.

---

### Task 5: Chụp nhóm incident preset và viết walkthrough

**Files:**
- Create: `docs/assets/demo_walkthrough/11-incident-presets.png`
- Create: `docs/guides/mvp_dashboard_demo_walkthrough.md`

**Interfaces:**
- Consumes: 12 screenshot assets and all deterministic preset expectations.
- Produces: complete user guide.

- [ ] **Step 1: Chụp selector nhóm incident**

Open the native preset selector with the five operational cases visible where the browser permits a native-control screenshot. If native popup capture is unavailable, capture the form plus a nearby expanded explanatory table in the walkthrough rather than altering dashboard HTML. Save as `11-incident-presets.png`.

- [ ] **Step 2: Tạo heading và prerequisites**

Start `mvp_dashboard_demo_walkthrough.md` with:

```markdown
# Hướng dẫn sử dụng và demo STWI Operator Dashboard

Tài liệu này hướng dẫn chạy dashboard bằng dữ liệu synthetic deterministic.
STWI chỉ hỗ trợ ra quyết định, không gửi lệnh đến thiết bị hiện trường.
```

Include the exact PowerShell startup commands from `mvp_demo_runbook.md`, the URL `/demo/`, and a warning that only loopback should be used for the local demo.

- [ ] **Step 3: Viết phần nhận biết giao diện**

Embed `01-dashboard-overview.png` with descriptive alt text and explain runtime mode, connection state, canonical job status, node registry, result workspace, evidence rail and decision gate.

- [ ] **Step 4: Viết walkthrough `safe`**

Embed images `02` through `06`. For each step include `Mục tiêu`, `Dữ liệu chọn`, `Thao tác`, `Kết quả mong đợi` and `Điểm kiểm tra`; do not include presentation dialogue.

- [ ] **Step 5: Viết test-case matrix fail-closed**

Create a table with exact rows:

| Preset | Node | Expected status | Required observation |
|---|---|---|---|
| `unsafe-vc` | `node_01` | `needs_review` | V/C vượt policy `0.9`; không approve. |
| `ood` | `node_02` | `needs_review` | OOD fail-closed; chỉ candidate action. |
| `uncertainty` | `node_03` | `needs_review` | Uncertainty cao; cần operator review. |
| `missing-evidence` | `node_04` | `needs_review` | Thiếu citation hợp lệ; không recommendation. |
| `extreme` | `node_00` | `needs_review` | Green-time cực trị bị safety gate giữ lại. |

Embed images `07` through `10` next to their matching procedures.

- [ ] **Step 6: Viết incident test-case matrix**

Document `accident`, `flood`, `lane-closure`, `demand-surge` and `environmental-anomaly` as synthetic operational cases. State explicitly that they do not prove causality, flood depth, pollution causation or field-control behavior.

- [ ] **Step 7: Viết keyboard và clipboard section**

Document `/`, `C`, native `Enter`, `Esc`, focus return and manual trace selection. Embed `12-clipboard-fallback.png`.

- [ ] **Step 8: Viết troubleshooting và exit checklist**

Cover static preview, connection refused, clipboard denial, `needs_review`, missing evidence and expired/failed states. End with stopping the local Uvicorn process and confirming no raw video was retained.

---

### Task 6: Liên kết runbook và verify toàn bộ artifact

**Files:**
- Modify: `docs/guides/mvp_demo_runbook.md`
- Test: `docs/guides/mvp_dashboard_demo_walkthrough.md`
- Test: `docs/assets/demo_walkthrough/*.png`

**Interfaces:**
- Consumes: completed walkthrough and screenshot assets.
- Produces: discoverable, validated documentation handoff.

- [ ] **Step 1: Thêm link từ runbook**

Add a short paragraph after the runbook introduction:

```markdown
Để thao tác theo từng test case kèm ảnh chụp dashboard, xem
[Hướng dẫn sử dụng và demo STWI Operator Dashboard](../../guides/mvp_dashboard_demo_walkthrough.md).
```

- [ ] **Step 2: Verify every image path**

Run:

```powershell
$guide = Get-Content -Raw docs/guides/mvp_dashboard_demo_walkthrough.md
Get-ChildItem docs/assets/demo_walkthrough -Filter *.png | ForEach-Object {
  if ($guide -notmatch [regex]::Escape($_.Name)) { throw "Unreferenced image: $($_.Name)" }
}
```

Expected: exit 0 and exactly 12 referenced PNG files.

- [ ] **Step 3: Run documentation and contract checks**

```powershell
& 'C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/validation/validate_docs.py
& 'C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 4: Run focused dashboard regressions**

```powershell
node --test tests/frontend/*.test.mjs
& 'C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
```

Expected: all tests pass; report any existing deprecation warning without classifying it as failure.

- [ ] **Step 5: Inspect final scope**

```powershell
git status --short
git diff -- docs/guides/mvp_dashboard_demo_walkthrough.md docs/guides/mvp_demo_runbook.md docs/superpowers/specs/2026-08-03-stwi-dashboard-demo-user-guide-design.md docs/superpowers/plans/2026-08-03-stwi-dashboard-demo-user-guide.md
```

Expected: only intended guide/spec/plan references plus pre-existing user dashboard changes; no secret, log, raw video, PDF or browser cache artifact.

---

## Plan self-review checklist

- [x] Mọi section trong spec đã duyệt ánh xạ đến ít nhất một task.
- [x] Có đúng 12 ảnh và mỗi ảnh có mục đích/test case rõ.
- [x] `safe`, năm fail-closed preset và năm incident preset đều được hướng dẫn.
- [x] Decision, keyboard, clipboard fallback và demo compatibility đều có bước kiểm tra.
- [x] Không có lời thoại thuyết trình, dependency mới hoặc contract change.
- [x] Ảnh được chụp qua HTTP local và chỉ dùng dữ liệu synthetic/aggregate.
- [x] Git operations vẫn bị cấm nếu chưa có yêu cầu Git cụ thể.
