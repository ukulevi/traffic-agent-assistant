# STWI Mentor Demo Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển runbook hiện tại thành hướng dẫn demo mentor-facing 8–10 phút, đồng thời giữ phụ lục đủ 17 capability và sửa hướng dẫn UI không tồn tại.

**Architecture:** Giữ `mvp_demo_runbook.md` là nguồn canonical gồm luồng trình bày chính và phụ lục evidence. `mvp_dashboard_demo_walkthrough.md` chỉ mô tả thao tác dashboard thật; các probe không có preset UI được gắn nhãn harness-only. Một contract test đọc Markdown sẽ ngăn hai tài liệu lệch khỏi UI và catalog demo.

**Tech Stack:** Markdown, Python `unittest`, STWI offline smoke harness, PowerShell verification.

## Global Constraints

- Demo chính dài 8–10 phút và chỉ chạy live `safe`, `refinement`, `unsafe-vc`.
- Phụ lục phải bao quát đủ 17 capability đã được chấp nhận.
- Mọi node, incident, forecast và route trong demo là synthetic, aggregate-only.
- STWI là decision-support; không automatic actuation; action/route luôn non-executable và cần con người phê duyệt.
- Không mô tả V/C 0,9 là quy định pháp luật.
- Không tuyên bố accuracy, calibration, RTSP, SLA hoặc production readiness chưa được đo/xác nhận.
- Không sửa runtime, API, schema, report hoặc slides cho thay đổi tài liệu này.
- Không commit, push hoặc tạo branch trong quá trình thực hiện nếu người dùng chưa yêu cầu riêng.

---

### Task 1: Khóa contract tài liệu mentor-demo bằng test đỏ

**Files:**
- Modify: `tests/demo/test_comprehensive_demo.py`
- Test: `tests/demo/test_comprehensive_demo.py`

**Interfaces:**
- Consumes: `docs/guides/mvp_demo_runbook.md`, `docs/guides/mvp_dashboard_demo_walkthrough.md` dưới dạng UTF-8 text.
- Produces: regression test xác nhận timed script, bốn cue fields, phân loại live/harness và không hướng dẫn chọn preset OOD/uncertainty trên UI.

- [ ] **Step 1: Thêm helper đọc tài liệu và failing test**

Thêm vào `ComprehensiveOfflineDemoTest`:

```python
    def test_mentor_runbook_separates_live_demo_from_harness_evidence(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        runbook = (repository / "docs/guides/mvp_demo_runbook.md").read_text(
            encoding="utf-8"
        )
        walkthrough = (
            repository / "docs/guides/mvp_dashboard_demo_walkthrough.md"
        ).read_text(encoding="utf-8")

        for marker in (
            "Kịch bản demo chính 8–10 phút",
            "**Thao tác:**",
            "**Nói:**",
            "**Chỉ trên màn hình:**",
            "**Kết quả mong đợi:**",
            "Dashboard-live",
            "Evidence/harness-only",
            "Câu hỏi mentor thường gặp",
            "Phương án dự phòng",
        ):
            self.assertIn(marker, runbook)

        for capability in (
            "normal_baseline",
            "route_recommendation",
            "route_needs_review",
            "ood",
            "high_uncertainty",
            "dependency_failure",
            "deadline_exceeded",
            "invalid_scenario",
            "tenant_scope_denied",
            "sse_reconnect",
            "static_preview",
        ):
            self.assertIn(f"`{capability}`", runbook)

        self.assertIn("không có preset `ood`", walkthrough)
        self.assertIn("không có preset `uncertainty`", walkthrough)
        self.assertNotIn("Chọn `ood` và chạy", walkthrough)
        self.assertNotIn("Chọn `uncertainty` và chạy", walkthrough)
```

- [ ] **Step 2: Chạy test và xác nhận RED đúng lý do**

Run:

```powershell
python -m unittest tests.demo.test_comprehensive_demo.ComprehensiveOfflineDemoTest.test_mentor_runbook_separates_live_demo_from_harness_evidence -v
```

Expected: FAIL vì runbook chưa có timed cue fields/phân loại mới và walkthrough còn câu “Chọn `ood` và chạy”.

- [ ] **Step 3: Kiểm tra diff chỉ có test dự kiến**

Run:

```powershell
git diff -- tests/demo/test_comprehensive_demo.py
```

Expected: chỉ có một regression test mới; không thay đổi assertion runtime hiện hữu.

---

### Task 2: Viết lại runbook canonical theo luồng mentor 8–10 phút

**Files:**
- Modify: `docs/guides/mvp_demo_runbook.md`
- Test: `tests/demo/test_comprehensive_demo.py`

**Interfaces:**
- Consumes: preset thật từ `src/stwi/t4_orchestrator/static/index.html`, catalog từ `stwi.demo.scenarios`, evidence schema version `1.0`.
- Produces: runbook canonical gồm setup, preflight, timed live script, evidence appendix, Q&A và recovery.

- [ ] **Step 1: Giữ và làm rõ setup reproducible**

Runbook phải chứa nguyên các lệnh:

```powershell
python --version
pip install -e ".[orchestrator]"
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

Ghi rõ chỉ tiếp tục khi `profile=offline`, `verdict=pass`, `capability_count=17`; mở `http://127.0.0.1:8000/demo/`; `/` và favicon 404 không phải lỗi demo.

- [ ] **Step 2: Thêm checklist preflight 10 phút trước buổi trình bày**

Checklist phải kiểm tra: terminal smoke pass; runtime badge `Demo synthetic`; input-first order; 20 node và topology tile-free; ba preset live; route table/map đồng bộ; decision ghi `applied_by_system=false`; evidence file mở được; cửa sổ terminal không lộ secret/path riêng.

- [ ] **Step 3: Viết timed script với bốn cue fields cho từng đoạn**

Tạo mục `Kịch bản demo chính 8–10 phút` với năm đoạn:

1. `0:00–1:00` — mục đích/phạm vi.
2. `1:00–3:00` — `safe → succeeded`.
3. `3:00–6:00` — `refinement → succeeded` tại node khác.
4. `6:00–8:00` — `unsafe-vc → needs_review`.
5. `8:00–10:00` — evidence 17 capability và kết luận.

Mỗi đoạn chứa đúng các nhãn `**Thao tác:**`, `**Nói:**`, `**Chỉ trên màn hình:**`, `**Kết quả mong đợi:**`. Lời thoại giải thích plain-language trước, rồi mới dùng các thuật ngữ V/C, OOD, uncertainty và provenance.

- [ ] **Step 4: Viết ma trận 17 capability có cột nơi chứng minh**

Phân loại rõ:

- `Dashboard-live`: `normal_baseline`, `safe_rejection`, `route_recommendation`, các incident/preset UI phù hợp.
- `Evidence/harness-only`: `route_needs_review`, `ood`, `high_uncertainty`, `dependency_failure`, `deadline_exceeded`, `invalid_scenario`, `tenant_scope_denied`, `sse_reconnect`, `static_preview`.

Giải thích `status: pass` là hành vi quan sát khớp kỳ vọng, không đồng nghĩa terminal status `succeeded`.

- [ ] **Step 5: Thêm phương án dự phòng và câu hỏi mentor**

Phần `Phương án dự phòng` phải nêu:

- server lỗi: dùng ảnh walkthrough và evidence đã tạo sau một smoke pass gần nhất;
- job live lệch kỳ vọng: không sửa lời giải thích để biến thành pass, chuyển sang evidence và ghi nhận lỗi;
- mất mạng: demo vẫn chạy loopback, Leaflet không dùng tile ngoài;
- smoke fail hoặc evidence không đủ 17: dừng tuyên bố acceptance.

Phần `Câu hỏi mentor thường gặp` trả lời ngắn cho: synthetic, GCN–LSTM so với surrogate, V/C 0,9, route/action, citation, OOD/uncertainty và các gate còn thiếu để pilot.

- [ ] **Step 6: Chạy targeted test và xác nhận chưa GREEN hoàn toàn nếu walkthrough chưa sửa**

Run:

```powershell
python -m unittest tests.demo.test_comprehensive_demo.ComprehensiveOfflineDemoTest.test_mentor_runbook_separates_live_demo_from_harness_evidence -v
```

Expected: runbook markers pass; test vẫn FAIL ở walkthrough nếu câu hướng dẫn preset giả chưa được sửa.

---

### Task 3: Đồng bộ walkthrough với control thật trên dashboard

**Files:**
- Modify: `docs/guides/mvp_dashboard_demo_walkthrough.md:104-140`
- Test: `tests/demo/test_comprehensive_demo.py`

**Interfaces:**
- Consumes: danh sách preset thật trong `src/stwi/t4_orchestrator/static/index.html` và evidence capability names.
- Produces: hướng dẫn UI chỉ dùng control tồn tại; OOD/uncertainty được đọc từ evidence harness.

- [ ] **Step 1: Sửa phần fail-closed thành hai nhóm**

Nhóm `Dashboard-live` giữ `unsafe-vc`, `missing-evidence`, `extreme`. Nhóm `Evidence/harness-only` nêu rõ dashboard không có preset `ood` và không có preset `uncertainty`; người demo mở `C:\tmp\stwi-offline-evidence.json` để chỉ capability `ood` và `high_uncertainty`.

- [ ] **Step 2: Loại bỏ thao tác UI không tồn tại**

Xóa hoặc viết lại chính xác hai câu:

```text
Chọn `ood` và chạy.
Chọn `uncertainty` và chạy.
```

Không thêm preset runtime mới và không dựng screenshot giả cho hai probe này.

- [ ] **Step 3: Chạy regression test và toàn bộ targeted demo test**

Run:

```powershell
python -m unittest tests.demo.test_comprehensive_demo.ComprehensiveOfflineDemoTest.test_mentor_runbook_separates_live_demo_from_harness_evidence -v
python -m unittest tests.demo.test_comprehensive_demo -v
```

Expected: PASS; toàn bộ test trong module giữ nguyên action, privacy và 17-capability semantics.

---

### Task 4: Release QA cho thay đổi tài liệu

**Files:**
- Verify: `docs/guides/mvp_demo_runbook.md`
- Verify: `docs/guides/mvp_dashboard_demo_walkthrough.md`
- Verify: `tests/demo/test_comprehensive_demo.py`
- Verify: `docs/superpowers/specs/2026-08-14-stwi-mentor-demo-runbook-design.md`
- Verify: `docs/superpowers/plans/2026-08-14-stwi-mentor-demo-runbook.md`

**Interfaces:**
- Consumes: thay đổi đã hoàn thành từ Task 1–3.
- Produces: bằng chứng validation không drift contract/artifact.

- [ ] **Step 1: Chạy docs và contract checks bắt buộc**

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
```

Expected: PASS.

- [ ] **Step 2: Chạy JavaScript syntax checks bắt buộc**

```powershell
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
```

Expected: PASS; không sửa slide.

- [ ] **Step 3: Chạy demo scope, smoke và targeted tests**

```powershell
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-mentor-runbook-evidence.json
python -m unittest tests.demo.test_comprehensive_demo -v
```

Expected: scope validator PASS; smoke `verdict=pass`, `capability_count=17`; targeted module PASS.

- [ ] **Step 4: Kiểm tra consistency và whitespace**

```powershell
rg -n "Chọn `ood` và chạy|Chọn `uncertainty` và chạy|13 capabilities" docs/guides docs/project_management/symphony/mvp_demo_acceptance.md
git diff --check
git status --short
```

Expected: `rg` không tìm thấy hướng dẫn preset giả hoặc số capability cũ; `git diff --check` PASS; status chỉ chứa năm file đúng scope.

- [ ] **Step 5: Báo cáo bàn giao, không commit**

Báo cáo Result, changed files, exact checks, contract/artifact impact và residual production gates. Không stage/commit/push khi chưa có yêu cầu riêng.
