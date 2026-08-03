# STWI Bounded Scenario Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mở rộng demo synthetic bằng năm tình huống vận hành tái lập được, đồng thời chứng minh các tín hiệu môi trường hiện có được xử lý đúng contract và mọi trường hợp không an toàn đều fail closed.

**Architecture:** Giữ nguyên API, schema, tensor và safety loop; bổ sung năm node profile vào `DemoSurrogateForecaster` chỉ được auto-wire trong `STWI_RUNTIME_MODE=demo`. UI chỉ ánh xạ preset sang payload hiện hành, còn terminal state vẫn do orchestrator và safety gate quyết định; kiểm thử data chỉ xác nhận feature/mask/tính độc lập, không đưa environmental feature vào forecast output.

**Tech Stack:** Python 3.11, NumPy, Pydantic/FastAPI, `unittest`, HTML và JavaScript thuần.

## Global Constraints

- Giữ `X[B,12,N,16]`, `M[B,12,N,16]`, `A[N,N]` và `Y[B,6,N,2]` cùng thứ tự feature trong `project_contract.json`.
- Giữ nguyên `WhatIfJobRequest`, HTTP 202, SSE và các status `queued`, `running`, `succeeded`, `needs_review`, `failed`, `expired`.
- Không thêm `IncidentVector` vào request, không thêm API field, service, model, dependency hoặc tensor feature.
- Không thêm rainfall, water depth, visibility hoặc compound incident engine.
- Chỉ `succeeded` có `recommended_action`; các profile mới phải trả `needs_review`, `candidate_action.executable=false` và không automatic actuation.
- V/C 0.90 là policy cấu hình của MVP, không phải quy định pháp luật.
- Nội dung người dùng phải nói rõ dữ liệu synthetic; environmental anomaly là tín hiệu tương quan cần review, không phải nguyên nhân gây ùn tắc hay cảnh báo sức khỏe.
- Không thay đổi hành vi `node_00` đến `node_04`.
- Không sửa hoặc stage `docs/project_management/symphony/board.json`, `docs/project_management/symphony/status_report.md`, `.codex/` hoặc `docs/ProgressAssessment_2026_07_19.md`.
- Không commit, push hoặc tạo PR trong lúc thực thi kế hoạch nếu người dùng chưa yêu cầu rõ.

## File Map

- `src/stwi/t4_orchestrator/demo_adapters.py`: nguồn duy nhất của các giá trị forecast synthetic theo node.
- `tests/t4_orchestrator/test_t4_demo_profiles.py`: kiểm tra terminal status, reason, metrics và action boundary của profile.
- `src/stwi/t4_orchestrator/static/index.html`: nhóm lựa chọn preset, không thêm màn hình hay navigation.
- `src/stwi/t4_orchestrator/static/dashboard.js`: ánh xạ preset sang payload và diễn giải không-causal.
- `tests/demo/test_dashboard_static.py`: contract tĩnh của option, mapping, safety copy và DOM rendering.
- `tests/t1_pipeline/test_phase1_pipeline.py`: regression contract cho environmental feature, missing mask và tensor shape.
- `scripts/demo/run_mvp_smoke.py`: smoke nhanh gồm bốn case cũ và hai case đại diện mới.
- `tests/demo/test_mvp_smoke.py`: contract evidence cho sáu smoke case.
- `docs/guides/mvp_demo_runbook.md`: lời thoại và kết quả mong đợi cho người demo lần đầu.
- `docs/guides/mvp_operator_dashboard.md`: ý nghĩa hai nhóm preset và giới hạn diễn giải.

---

### Task 1: Demo profiles cho năm tình huống vận hành

**Files:**
- Modify: `tests/t4_orchestrator/test_t4_demo_profiles.py`
- Modify: `src/stwi/t4_orchestrator/demo_adapters.py`

**Interfaces:**
- Consumes: `WhatIfOrchestrator.run(job_id: str, request: WhatIfJobRequest)` và `DemoSurrogateForecaster.predict(...)` hiện có.
- Produces: `_PROFILE_OVERRIDES` cho `node_05` đến `node_09`; không tạo public API mới.

- [ ] **Step 1: Viết test fail-closed cho catalog mới**

Thêm vào `TestDemoProfiles`:

```python
    def test_operational_profiles_fail_closed_for_expected_reason(self) -> None:
        expected_reasons = {
            "node_05": "vc_ratio",
            "node_06": "vc_ratio",
            "node_07": "vc_ratio",
            "node_08": "vc_ratio",
            "node_09": "out_of_distribution",
        }
        for node_id, reason in expected_reasons.items():
            with self.subTest(node_id=node_id):
                result = self.orchestrator.run(node_id, request(node_id, 0.7))
                self.assertEqual(result.status, JobStatus.NEEDS_REVIEW)
                self.assertIn(reason, result.needs_review_reason)
                self.assertIsNone(result.recommended_action)
                self.assertIsNotNone(result.candidate_action)
                self.assertFalse(result.candidate_action["executable"])

    def test_flood_profile_has_lowest_incident_speed(self) -> None:
        speeds = {}
        for node_id in ("node_05", "node_06", "node_07", "node_08"):
            result = self.orchestrator.run(node_id, request(node_id, 0.7))
            speeds[node_id] = result.scenario_summary["avg_speed"]

        self.assertEqual(min(speeds, key=speeds.get), "node_06")
```

- [ ] **Step 2: Chạy test và xác nhận RED đúng nguyên nhân**

Run:

```powershell
python -m unittest tests.t4_orchestrator.test_t4_demo_profiles.TestDemoProfiles.test_operational_profiles_fail_closed_for_expected_reason tests.t4_orchestrator.test_t4_demo_profiles.TestDemoProfiles.test_flood_profile_has_lowest_incident_speed
```

Expected: FAIL vì `node_05` đến `node_09` hiện rơi vào safe default và trả `succeeded`.

- [ ] **Step 3: Thêm đúng năm profile synthetic tối thiểu**

Mở rộng `_PROFILE_OVERRIDES` trong `DemoSurrogateForecaster` bằng đúng các entry sau:

```python
        "node_05": SurrogateScenario(
            vc_ratio=0.94,
            uncertainty_score=0.18,
            ood_score=0.15,
            predicted_volume=138.0,
            predicted_speed=22.0,
        ),
        "node_06": SurrogateScenario(
            vc_ratio=0.98,
            uncertainty_score=0.25,
            ood_score=0.30,
            predicted_volume=72.0,
            predicted_speed=12.0,
        ),
        "node_07": SurrogateScenario(
            vc_ratio=0.92,
            uncertainty_score=0.15,
            ood_score=0.10,
            predicted_volume=118.0,
            predicted_speed=27.0,
        ),
        "node_08": SurrogateScenario(
            vc_ratio=0.97,
            uncertainty_score=0.20,
            ood_score=0.15,
            predicted_volume=175.0,
            predicted_speed=21.0,
        ),
        "node_09": SurrogateScenario(
            vc_ratio=0.78,
            uncertainty_score=0.82,
            ood_score=0.60,
            predicted_volume=105.0,
            predicted_speed=36.0,
        ),
```

Không thêm keyword classifier vào `_scenario_for`; thứ tự extreme-ratio trước profile override phải được giữ nguyên.

- [ ] **Step 4: Chạy toàn bộ profile test và xác nhận GREEN, kể cả regression cũ**

Run:

```powershell
python -m unittest tests.t4_orchestrator.test_t4_demo_profiles -v
```

Expected: PASS; `node_00` ratio-sensitive vẫn `succeeded`, extreme vẫn fail closed, `node_01`–`node_03` vẫn giữ reason cũ.

---

### Task 2: Preset UI gọn và diễn giải không-causal

**Files:**
- Modify: `tests/demo/test_dashboard_static.py`
- Modify: `src/stwi/t4_orchestrator/static/index.html`
- Modify: `src/stwi/t4_orchestrator/static/dashboard.js`

**Interfaces:**
- Consumes: `DEMO_PRESETS`, `applyPreset()` và form payload hiện có.
- Produces: keys `accident`, `flood`, `lane-closure`, `demand-surge`, `environmental-anomaly`, mỗi key ánh xạ tới một node trong Task 1.

- [ ] **Step 1: Viết static tests cho option, node mapping và safety copy**

Thêm vào `TestDashboardStatic`:

```python
    def test_dashboard_exposes_bounded_operational_presets(self) -> None:
        expected_profiles = {
            "accident": "node_05",
            "flood": "node_06",
            "lane-closure": "node_07",
            "demand-surge": "node_08",
            "environmental-anomaly": "node_09",
        }
        self.assertIn('<optgroup label="Safety cơ bản">', self.html)
        self.assertIn('<optgroup label="Tình huống vận hành">', self.html)
        for profile, node_id in expected_profiles.items():
            self.assertIn(f'value="{profile}"', self.html)
            profile_block = re.search(
                rf'"{re.escape(profile)}"\s*:\s*\{{(?P<body>.*?)\n\s*\}},',
                self.js,
                re.DOTALL,
            )
            self.assertIsNotNone(profile_block)
            self.assertIn(node_id, profile_block.group("body"))
            self.assertIn("synthetic", profile_block.group("body"))

    def test_environmental_preset_avoids_causal_claims(self) -> None:
        self.assertIn("tín hiệu tương quan", self.js)
        self.assertIn("không kết luận nguyên nhân", self.js)
        self.assertNotIn("ô nhiễm gây ùn tắc", self.js.lower())
```

- [ ] **Step 2: Chạy test và xác nhận RED**

Run:

```powershell
python -m unittest tests.demo.test_dashboard_static.TestDashboardStatic.test_dashboard_exposes_bounded_operational_presets tests.demo.test_dashboard_static.TestDashboardStatic.test_environmental_preset_avoids_causal_claims
```

Expected: FAIL vì năm option và preset mapping chưa tồn tại.

- [ ] **Step 3: Nhóm selector mà không thêm chiều cao đáng kể**

Trong `index.html`, đặt sáu option hiện có vào `<optgroup label="Safety cơ bản">`, đặt năm option mới vào `<optgroup label="Tình huống vận hành">`, và giữ option tùy chỉnh sau hai nhóm:

```html
<optgroup label="Tình huống vận hành">
  <option value="accident">Tai nạn · nghẽn do giảm năng lực</option>
  <option value="flood">Ngập lụt · tốc độ rất thấp</option>
  <option value="lane-closure">Đóng làn · V/C vượt policy</option>
  <option value="demand-surge">Nhu cầu tăng · lưu lượng cao</option>
  <option value="environmental-anomaly">Tín hiệu môi trường bất thường · OOD</option>
</optgroup>
<option value="custom">Tùy chỉnh thủ công</option>
```

- [ ] **Step 4: Thêm mapping payload và expectation rõ giới hạn**

Thêm các object sau vào `DEMO_PRESETS` trong `dashboard.js`:

```javascript
  "accident": {
    nodeId: "node_05", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá quyền và nghĩa vụ người sử dụng đường trong tình huống tai nạn synthetic tại node_05.",
    expectation: "Kỳ vọng synthetic: giảm năng lực hiệu dụng làm V/C vượt policy 0.90; job cần operator review.",
  },
  "flood": {
    nodeId: "node_06", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá quyền và nghĩa vụ người sử dụng đường trong tình huống ngập lụt synthetic tại node_06.",
    expectation: "Kỳ vọng synthetic: tốc độ thấp nhất nhóm incident và V/C vượt policy; hệ thống không mô phỏng mực nước.",
  },
  "lane-closure": {
    nodeId: "node_07", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá quyền và nghĩa vụ người sử dụng đường khi đóng làn synthetic tại node_07.",
    expectation: "Kỳ vọng synthetic: năng lực giảm tương đương đóng một phần làn và job chuyển needs_review.",
  },
  "demand-surge": {
    nodeId: "node_08", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá quyền và nghĩa vụ người sử dụng đường khi nhu cầu tăng synthetic tại node_08.",
    expectation: "Kỳ vọng synthetic: lưu lượng cao và V/C vượt policy 0.90; không phải dự báo production.",
  },
  "environmental-anomaly": {
    nodeId: "node_09", ratio: 0.70, jurisdiction: "VN",
    query: "Đánh giá tín hiệu môi trường synthetic bất thường cần đối chiếu tại node_09.",
    expectation: "Kỳ vọng synthetic: tín hiệu tương quan nằm ngoài phân phối nên cần review; không kết luận nguyên nhân ô nhiễm–ùn tắc.",
  },
```

- [ ] **Step 5: Chạy static tests và JavaScript syntax check**

Run:

```powershell
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
node --check src/stwi/t4_orchestrator/static/dashboard.js
```

Expected: PASS, không có `innerHTML`, approval cho status khác `succeeded` vẫn bị khóa.

---

### Task 3: Environmental data contract regression

**Files:**
- Modify: `tests/t1_pipeline/test_phase1_pipeline.py`

**Interfaces:**
- Consumes: `feature_names()`, `apply_quality_and_impute(...)`, `build_tensor_windows(...)` và adjacency fixture hiện có.
- Produces: test-only evidence; không sửa production pipeline.

- [ ] **Step 1: Thêm regression test cho feature order và tính độc lập**

Thêm một test dùng 18 timestep, 20 node và vector hợp lệ sau:

```python
    def test_environmental_features_preserve_contract_and_missing_mask(self) -> None:
        self.assertEqual(
            feature_names()[3:11],
            (
                "co_ppm",
                "co2_ppm",
                "nox_ppb",
                "pm25_ugm3",
                "pm10_ugm3",
                "temperature_c",
                "humidity_pct",
                "wind_speed_ms",
            ),
        )
        baseline = np.array(
            [50, 40, 0.1, 1, 450, 30, 20, 35, 30, 70, 3, 0, 1, 0, 1, 0.5],
            dtype=np.float32,
        )
        values = np.tile(baseline, (18, 20, 1))
        observed = np.ones_like(values, dtype=bool)
        values[0, 0, 0] = 10.0
        values[0, 0, 6] = 500.0
        values[1, 0, 3:11] = np.nan
        observed[1, 0, 3:11] = False

        quality = apply_quality_and_impute(values, observed, self.network.adjacency)
        dataset = build_tensor_windows(
            quality.values,
            quality.observed_mask,
            self.network.adjacency,
        )

        self.assertEqual(quality.values[0, 0, 0], 10.0)
        self.assertEqual(quality.values[0, 0, 6], 500.0)
        self.assertFalse(quality.observed_mask[1, 0, 3:11].any())
        self.assertTrue(np.isfinite(quality.values).all())
        self.assertEqual(dataset.X.shape, (1, 12, 20, 16))
        self.assertEqual(dataset.M.shape, (1, 12, 20, 16))
        self.assertEqual(dataset.Y.shape, (1, 6, 20, 2))
```

Nếu fixture dùng tên adjacency khác, chỉ thay `self.network.adjacency` bằng thuộc tính fixture đã có; không tạo helper production mới.

- [ ] **Step 2: Chạy test characterization**

Run:

```powershell
python -m unittest tests.t1_pipeline.test_phase1_pipeline -v
```

Expected: PASS ngay nếu pipeline đang giữ đúng contract. Đây là characterization test cho hành vi hiện hành, không phải chu kỳ RED giả tạo; nếu fail, dừng và sửa đúng boundary được lỗi chỉ ra thay vì nới sanity bounds.

---

### Task 4: Smoke evidence cho hai case đại diện

**Files:**
- Modify: `tests/demo/test_mvp_smoke.py`
- Modify: `scripts/demo/run_mvp_smoke.py`

**Interfaces:**
- Consumes: `_run_case(name, scenario, expected_status, decision)` và `SurrogateScenario` hiện có.
- Produces: evidence sáu case, thêm `accident_rejection` và `environmental_anomaly_rejection`.

- [ ] **Step 1: Mở rộng smoke contract test trước**

Thay assertion số case bằng:

```python
        self.assertEqual(len(evidence["cases"]), 6)
        self.assertEqual(
            [case["case"] for case in evidence["cases"]],
            [
                "safe_approval",
                "unsafe_vc_rejection",
                "ood_rejection",
                "uncertainty_rejection",
                "accident_rejection",
                "environmental_anomaly_rejection",
            ],
        )
```

Giữ nguyên assertions rằng chỉ case đầu `succeeded`, năm case còn lại `needs_review`, không applied-by-system và không automatic actuation.

- [ ] **Step 2: Chạy test và xác nhận RED**

Run:

```powershell
python -m unittest tests.demo.test_mvp_smoke.TestMvpSmoke.test_smoke_writes_safe_aggregate_evidence
```

Expected: FAIL vì harness hiện chỉ tạo bốn case.

- [ ] **Step 3: Thêm hai `SurrogateScenario` đại diện vào smoke**

Import `SurrogateScenario` cùng các factory hiện có và nối vào cuối `cases`:

```python
            _run_case(
                "accident_rejection",
                SurrogateScenario(
                    vc_ratio=0.94,
                    uncertainty_score=0.18,
                    ood_score=0.15,
                    predicted_volume=138.0,
                    predicted_speed=22.0,
                ),
                "needs_review",
                "rejected",
            ),
            _run_case(
                "environmental_anomaly_rejection",
                SurrogateScenario(
                    vc_ratio=0.78,
                    uncertainty_score=0.82,
                    ood_score=0.60,
                    predicted_volume=105.0,
                    predicted_speed=36.0,
                ),
                "needs_review",
                "rejected",
            ),
```

Các literal này chỉ là smoke representatives; profile behavior đầy đủ vẫn được khóa bởi Task 1.

- [ ] **Step 4: Chạy smoke test và harness thực**

Run:

```powershell
python -m unittest tests.demo.test_mvp_smoke -v
python scripts/demo/run_mvp_smoke.py --output data/derived/private/demo/mvp_smoke_evidence.json
```

Expected: PASS và CLI in JSON có `"case_count": 6`; evidence chỉ chứa aggregate result, không raw video.

---

### Task 5: Đồng bộ hướng dẫn demo và giới hạn sử dụng

**Files:**
- Modify: `docs/guides/mvp_demo_runbook.md`
- Modify: `docs/guides/mvp_operator_dashboard.md`

**Interfaces:**
- Consumes: profile names, nodes và terminal reasons từ Task 1–2.
- Produces: hướng dẫn Vietnamese-first có thể dùng trực tiếp khi trình diễn.

- [ ] **Step 1: Cập nhật runbook bằng catalog có thể đọc nhanh**

Thêm bảng gồm đúng các cột `Preset`, `Node`, `Điều hệ thống mô phỏng`, `Kết quả mong đợi`, với năm dòng:

```markdown
| Tai nạn | `node_05` | Giảm tốc và năng lực hiệu dụng (synthetic) | `needs_review` do V/C |
| Ngập lụt | `node_06` | Tốc độ rất thấp, năng lực giảm mạnh (synthetic) | `needs_review` do V/C |
| Đóng làn | `node_07` | Năng lực giảm tương đương đóng một phần làn | `needs_review` do V/C |
| Nhu cầu tăng | `node_08` | Lưu lượng synthetic tăng cao | `needs_review` do V/C |
| Tín hiệu môi trường bất thường | `node_09` | Tín hiệu tương quan ngoài phân phối | `needs_review` do OOD |
```

Ngay dưới bảng, ghi rõ hệ thống không mô phỏng lượng mưa/mực nước, không dự báo chất lượng không khí, không kết luận ô nhiễm gây ùn tắc và không gửi lệnh hiện trường.

- [ ] **Step 2: Cập nhật operator dashboard guide**

Mô tả `Safety cơ bản` dùng để chứng minh gate riêng lẻ; `Tình huống vận hành` dùng các abstraction bounded đã có. Nêu rằng free text không được parser thành incident parameters và terminal state không do UI tự suy ra.

- [ ] **Step 3: Chạy validators tài liệu**

Run:

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
```

Expected: PASS; không sửa `project_contract.json`, report, appendix hoặc slides vì không có contract/artifact trình bày nào thay đổi.

---

### Task 6: Release QA và kiểm tra demo trong browser

**Files:**
- Verify only: các file đã thay đổi trong Task 1–5.

**Interfaces:**
- Consumes: toàn bộ deliverable phía trên.
- Produces: evidence kiểm thử và danh sách giới hạn còn lại; không tạo source artifact mới.

- [ ] **Step 1: Chạy targeted suite**

Run:

```powershell
python -m unittest tests.t4_orchestrator.test_t4_demo_profiles tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static tests.t1_pipeline.test_phase1_pipeline tests.demo.test_mvp_smoke -v
```

Expected: PASS.

- [ ] **Step 2: Chạy mandatory repository checks**

Run:

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
node --check src/stwi/t4_orchestrator/static/dashboard.js
git diff --check
```

Expected: tất cả PASS và `git diff --check` không có output.

- [ ] **Step 3: Chạy release verifier theo skill local**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/stwi-release-qa/scripts/verify_project.ps1
```

Expected: PASS. Không dùng `-BuildPdf` vì report/appendix không thay đổi; nếu environment thiếu một runtime, ghi đúng command, error và phần chưa được xác nhận.

- [ ] **Step 4: Browser QA qua `/demo/`**

Với server demo hiện có tại `http://127.0.0.1:8000/demo/`, lần lượt chọn năm preset mới và xác nhận:

1. form tự điền đúng `node_05`–`node_09` và query tương ứng;
2. create job trả accepted rồi terminal `needs_review`;
3. incident profiles hiển thị V/C reason, environmental profile hiển thị OOD reason;
4. action là `NON-EXECUTABLE`, nút approve bị khóa, không có automatic actuation;
5. copy luôn ghi synthetic và environmental preset không có causal claim;
6. selector dùng được bằng bàn phím, không gây overflow ở viewport desktop và mobile.

- [ ] **Step 5: Rà soát Git scope trước bàn giao**

Run:

```powershell
git status --short
git diff -- src/stwi/t4_orchestrator/demo_adapters.py tests/t4_orchestrator/test_t4_demo_profiles.py src/stwi/t4_orchestrator/static/index.html src/stwi/t4_orchestrator/static/dashboard.js tests/demo/test_dashboard_static.py tests/t1_pipeline/test_phase1_pipeline.py scripts/demo/run_mvp_smoke.py tests/demo/test_mvp_smoke.py docs/guides/mvp_demo_runbook.md docs/guides/mvp_operator_dashboard.md
```

Expected: chỉ các thay đổi có chủ đích của kế hoạch; không stage hoặc chỉnh các file Symphony/assessment được liệt kê trong Global Constraints.
