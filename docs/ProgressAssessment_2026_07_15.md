# Đánh giá tiến độ hoàn thiện STWI — 2026-07-15

## Tổng quan
- Dự án: SmartTraffic What-If (STWI), 13-week MVP, decision-support only, no automatic actuation.
- Nhánh hiện tại: `codex/tra-30-fail-closed-auth-boundary`.
- Nguồn đánh giá: `project_contract.json`, `docs/00_05_*`, clean test run ngày 2026-07-15, gate reports trong `data/derived/private/**`, source tree `src/stwi/**`, CI workflow `.github/workflows/stwi-fast-ci.yml`.
- Ước tổng thể hoàn thiện: **~70%**

## Trạng thái kiểm tra hiện tại
- `python scripts/validation/validate_docs.py` → PASS
- `python -m unittest tests.contracts.test.project_contract` → PASS, 4 tests
- `python -m unittest tests.t2_forecast.test_phase2_provisional_gate tests.t2_forecast.test_surrogate_models tests.t2_forecast.test_surrogate_safety tests.t2_forecast.test_gcn_lstm tests.t2_forecast.test_phase2_baselines -q` → PASS, 28 tests

## Breakdown theo phase
| Phase | Hoàn thành | Trạng thái | Ghi chú |
|---|---|---|---|
| P0 Foundation | ~90% | partial | Contracts, docs, CI fast-guards, provisional vs production boundary có trong code/test; chưa production hardend deploy mode. |
| P1 Data pipeline | ~55% | partial | Mock gate P1 và tensor artifacts có sẵn; real camera aggregate evidence, camera artifact promotion, và measured privacy/quality chưa thay thế mock. |
| P2 Forecast/Surrogate | ~75% | partial | Có trained models, SUMO offline dataset, surrogate v1/v2 artifacts, measured surrogate benchmark reports và pass P2 tests; baseline artifact/production calibration cần rõ hơn. |
| P3 Knowledge/RAG | ~55% | partial | Corpus, gate P3, retriever/executor contracts có; nhưng `FakeRetriever`/`DuckDBFakeExecutor` vẫn tồn tại, T3 integration có 10 skips, SOP corpus chưa có. |
| P4 Orchestrator/API | ~65% | partial | API, safety loop, contracts, auth boundary code, smoke demo và measured evidence validator có; production runtime vẫn cần replace in-memory store/Celery/Redis, real tenant auth, measured E2E SLA trên contract hardware. |

## Chi tiết từng hạng mục

### P0 Foundation
- Có sẵn: `project_contract.json`, `docs/00_05_*`, contract tests, CI fast-guards.
- Tồn đọng: nhiều `provisional_mock_v1`, `synthetic_mock_phase4`, fake adapters tồn tại; production mode chưa bind artifact manifest/checksum.

### P1 Data pipeline
- Có sẵn: `data/derived/private/phase1_mock/**`, gate `gate_p1_report.json`, T1 tests, RTSP privacy/upload guardrails.
- Tồn đọng: evidence chủ yếu synthetic; camera aggregate measured evidence chưa có; vision official artifact vẫn đang ở hồ sơ prisam/legal chưa clear.

### P2 Forecast/Surrogate
- Có sẵn: `model.pt`/`ensemble.pt`, SUMO manifest, calibration, scenario coverage, benchmark reports:
  - `phase2_surrogate/v1/benchmark_report.json`: `p99_ms=9.99`, measured 300 runs
  - `phase2_surrogate/v2/benchmark_report.json`: `p99_ms=55.49`, measured 300 runs
  - Pass `validate_surrogate_benchmark_evidence.py`
  - Pass `tests.t2_forecast.test_phase2_provisional_gate`
- Tồn đọng: GCN-LSTM file chỉ 2.5KB, giống stub; baseline training artifact/report binding cần rõ hơn. OOD/uncertainty threshold chưa có measured validation trên bản split thật.

### P3 Knowledge/RAG
- Có sẵn: corpus manifest, gate P3, `QdrantRetriever`, `TimescaleQueryExecutor`, citation validator.
- Tồn đọng: `phase4_start_readiness_report` ghi T3 tests pass với 10 skips; `FakeRetriever` + `DuckDBFakeExecutor` vẫn có trong code; SOP corpus và real service path hardening chưa hoàn toàn.

### P4 Orchestrator/API
- Có sẵn: FastAPI endpoints, job contracts, fail-closed semantics, safety loop, SSE smoke, auth boundary tests.
- Tồn đọng: `InMemoryJobStore` vẫn provisional; default adapters vẫn fake/test; chưa có Celery/Redis persistence thực, real principal resolver, measured E2E SLA và release runbook.

## Rust / lỗi tiềm ẩn chính

### 🔴 Critical
1. **Fake adapters vẫn tồn tại như default/test fixture**
   - Vị trí: `src/stwi/t4_orchestrator/fake_adapters.py`, `src/stwi/t3_knowledge/fake_retriever.py`, `src/stwi/t4_orchestrator/job_store.py`
   - Hậu quả: deploy có thể chạy hợp đồng nhưng vẫn dùng in-memory/mock nếu không set `STWI_RUNTIME_MODE=production` và bind promoted artifact manifest.
   - Hành động: production startup yêu cầu promoted artifact manifest + checksum; fail-closed nếu thiếu.

2. **Baseline artifact/evidence binding chưa rõ**
   - Vị trí: `src/stwi/t2_forecast/gcn_lstm.py`, phối hợp `data/derived/private/phase2_forecast/**`
   - Hậu quả: dễ base claim trên surrogate mà không có baseline measured evidence.
   - Hành động: liên kết baseline report, training artifact version, scaler/adjacency version trong phase handoff.

3. **T3 still has integration skips**
   - Vị trí: `data/derived/private/phase4_orchestrator/phase4_start_readiness_report.json` ghi T3 tests 65 run + 10 skip.
   - Hậu quả: Qdrant/BGE/real executor path có thể có blindspot.
   - Hành động: chạy service-backed integration, bỏ skip hoặc chuyển thành `not_verified` có owner/ETA.

### 🟡 Medium
4. **Auth/RBAC chưa production enforcement**
   - Tests có, nhưng production resolver và tenant enforcement chưa có measured evidence.

5. **Celery/Redis persistence chưa thay thế in-memory**
   - Contract yêu cầu async job + SSE; hiện chỉ có provisional path.

6. **E2E measured SLA chưa có**
   - Benchmark surrogate đã có measured p99; nhưng E2E P95/P99 trên contract profile chưa đo.

## Kế hoạch thực hiện và sửa chữa đề xuất

### 10–14 ngày tới
- 🔧 Tạo artifact manifest/checksum binding cho production runtime; loại bỏ khả năng implicit fallback sang fake adapters.
- 🔧 Base GCN-LSTM artifact/report/scaler version được bind rõ vào Phase2/Phase4 handoff.
- 🔧 Chạy T3 service-backed integration; bỏ/ghi rõ 10 skips.
- 🔧 Xác định vision official/provisional và privacy promotion criteria.
- 🔧 Xác minh camera aggregate evidence plan; demo operator có dữ liệu đo thực.

### 20–40 ngày tới
- 🏗 Thay InMemoryJobStore bằng Redis/Celery persistence theo contract.
- 🏗 Thay fake adapters bằng real Qdrant/Timescale/GCN-LSTM/surrogate adapters với promoted artifacts.
- 🏗 Implement production auth/tenant enforcement và audit hardening.
- 🏗 Đo E2E SLA trên 8 CPU/32GB/12-16GB VRAM; ghi warmup, payload, p50/p95/p99, failures.
- 🏗 Final release QA và measured evidence trước khi khai báo production-ready.

## Kết luận
- Tiến độ hiện tại thuộc nhóm **~70%**: contracts, model artifacts, measured surrogate benchmark path, fail-closed semantics, API scaffolding và nhiều contract tests đều đã có.
- Rủi ro chuyển từ "thiếu artifact" sang **âm ỉ nhầm measured/simulated placeholder, fake default adapter, và thiếu production binding**, đặc biệt ở baseline evidence, T3 integration, auth, persistence và E2E SLA.
- Ưu tiên sửa theo thứ tự: measured benchmark ownership → artifact binding → service integration → auth → production runtime → measured E2E SLA.
