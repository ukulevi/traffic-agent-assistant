# Đánh giá tiến độ hoàn thiện STWI — 2026-08-23

## Tổng quan

- Dự án: SmartTraffic What-If (STWI), 13-week MVP, decision-support only, không tự động điều khiển thiết bị.
- Nhánh hiện tại: `main`, đồng bộ với `origin/main`. Có thay đổi chưa commit liên quan báo cáo thực tập (`report/chapters/ch00`, `ch12`, `internship_main*.tex`, `report_en/`, `scripts/report/`, `tests/report/`).
- Nguồn đánh giá: `project_contract.json` v1.0.0, `docs/00–05_*`, đánh giá trước `docs/ProgressAssessment_2026_07_15.md`, gate reports trong `data/derived/private/**`, source tree `src/stwi/**`, 4 CI workflows, git history (47 commit mới kể từ 2026-07-15).
- Kết quả kiểm tra thực tế ngày 2026-08-23:
  - `python scripts/validation/validate_docs.py` → PASS
  - `python -m unittest tests.contracts.test_project_contract` → PASS, 6 tests
  - `python -m pytest tests/ -q` → **581 passed, 6 skipped**, 247 subtests passed (≈21s)
- Ước tổng thể hoàn thiện MVP: **~78%** (tăng từ ~70% tại assessment 2026-07-15).

## Diễn biến chính kể từ assessment 2026-07-15

1. **TRA-50 Production baseline đã được triển khai** — giải quyết trực tiếp 2/3 critical gap trước đó:
   - `src/stwi/production.py`, `production_components.py`: composition fail-closed với `ProductionSettings.from_environ()`.
   - `RuntimeArtifactSet.load(baseline_manifest, surrogate_manifest)` → production startup yêu cầu promoted artifact manifest (không còn implicit fallback sang fake adapters trên đường production).
   - `RedisJobStore` + Celery broker/backend thay InMemoryJobStore trên đường production; thêm `production_preflight.py`, `production_migrate.py`, `production_health.py`, `production_worker.py`, images pinned theo digest.
2. **Demo/operator experience trưởng thành rõ rệt**: typed incident contract (TRA-59), bounded diversion candidates, validated route evidence, network impact evidence showcase, dashboard "truthful state" fix, citation collapse, mentor demo runbook.
3. **Vision pipeline có measured external evidence**: nhiều `external_benchmark_summary.json` (YOLOv8 trên VisDrone/gayatri/viet_highway samples) và bộ training data Roboflow v001 kèm smoke test gated bằng env.
4. **Công việc đang dở (untracked)**: báo cáo thực tập song ngữ Việt/Anh — cần hoàn tất và tách khỏi code runtime.

## Breakdown theo phase

| Phase | Hoàn thành | Trạng thái | Ghi chú |
|---|---|---|---|
| P0 Foundation | ~95% | near-complete | Contract v1.0.0, docs validation PASS, contract tests PASS, CI fast-guards + manual QA + Pages + build. |
| P1 Data pipeline | ~65% | partial | Mock gate P1 + tensor artifacts + RTSP guardrails; vision có measured external benchmark + training data thật; nhưng camera aggregate evidence cho luồng camera chức năng vẫn chưa thay thế mock. |
| P2 Forecast/Surrogate | ~80% | mostly done | Surrogate benchmark measured (v1 p99=9.99ms, v2 p99=55.49ms, 300 runs mỗi bản); artifact manifest giờ được bind vào production runtime; GCN-LSTM module vẫn mỏng (~2.4KB) — baseline evidence vẫn là điểm yếu nhất của phase này. |
| P3 Knowledge/RAG | ~60% | partial | Gate P3 pass (citation_precision=1.0, FP=0), corpus Luật 35+36/2024/QH15; **5 integration test skip cục bộ** do thiếu `qdrant-client`/`sentence-transformers`/TimescaleDB reachable — chưa chạy service-backed end-to-end. |
| P4 Orchestrator/API | ~75% | partial | API + safety loop + SSE + fail-closed verified; production composition với Redis/Celery + preflight + health + migration đã có code và contract test; chưa có measured E2E SLA trên contract profile. |
| Demo & reporting | ~85% | strong | Demo runbook, operator SOP, dashboard walkthrough, network impact showcase, internship report đang viết dở. |

## Rủi ro / Gaps

### 🔴 Critical
1. **Chưa có measured E2E SLA** — surrogate p99 đã đo, nhưng E2E P95 ≤ 30s / hard deadline P99 ≤ 180s trên profile 8 CPU/32GB/12–16GB VRAM chưa có bằng chứng đo thật. Đây là SLA ghi trong contract.
2. **Baseline GCN-LSTM evidence mỏng** — module ~2.4KB, chưa thấy binding report/training-run/scaler-version rõ ràng như phía surrogate; dễ bị nghi ngờ khi mentor/reviewer hỏi "baseline đo bằng gì".
3. **Service-backed integration chưa chạy trong môi trường hiện tại** — 5 skip ở `tests/t3_knowledge/test_t3_integration.py` do thiếu qdrant-client/sentence-transformers/TimescaleDB. Skip = `not_verified`, không phải pass.

### 🟡 Medium
4. **Camera aggregate measured evidence cho P1** — vision side mạnh lên nhưng luồng camera chức năng (20 stream) vẫn chưa có bằng chứng aggregate đo thật.
5. **Auth/tenant enforcement production** — có code path và contract test, chưa có measured evidence/runbook xác minh với principal thật.
6. **Worktree lẫn lộn code và tài liệu thực tập** — các file report thực tập chưa commit trộn cùng thay đổi `.github/workflows/build.yml`; nguy cơ commit nhầm hoặc mất khi đổi nhánh.

### ✅ Strengths
- Hợp đồng bất biến được enforce bằng test thật (581 passed) chứ không chỉ văn bản.
- Production path fail-closed: thiếu env/artifact manifest là từ chối khởi động, không fallback âm thầm.
- Demo story mạch lạc và trung thực (truthful-state fix, citation collapse, network impact evidence).
- Quản trị công việc bằng ticket TRA-* + plan/spec trong `docs/superpowers/` rất kỷ luật.

## Roadmap đề xuất

### Giai đoạn A — 10–14 ngày tới (đóng critical gaps, hướng tới demo chốt)
1. 🔧 Đo E2E SLA trên contract profile: script benchmark E2E (POST job → poll/SSE → kết quả), ghi p50/p95/p99 + failures vào `data/derived/private/**/e2e_benchmark_report.json` + validator tương tự surrogate.
2. 🔧 Bind baseline GCN-LSTM evidence: training report, scaler/adjacency version, checkpoint hash vào manifest mà `RuntimeArtifactSet.load` đọc; thêm contract test bắt buộc sự tồn tại của baseline evidence.
3. 🔧 Chạy T3 service-backed integration trong môi trường có Qdrant + TimescaleDB (docker compose trong `infra/`): mục tiêu giảm số skip về 0 hoặc chuyển thành `not_verified` có owner/ETA trong readiness report.
4. 📄 Hoàn tất và commit bộ báo cáo thực tập ra nhánh riêng (ví dụ `ticket/report-internship-vi-en`), tách khỏi code runtime; chạy `python scripts/validation/validate_docs.py` + XeLaTeX build trước khi merge.

### Giai đoạn B — 3–5 tuần tới (production-ready claims)
5. 🏗 Camera aggregate measured evidence: chạy ít nhất 1 luồng camera ghi sẵn qua T1 pipeline, promote artifact, thay mock gate P1 evidence.
6. 🏗 Xác minh production auth/tenant enforcement với principal thật; bổ sung section vào `production_adapter_replacement_runbook.md`.
7. 🏗 Release QA tổng (`$stwi-release-qa`): chạy lại toàn bộ validators, benchmark đúng profile, kiểm tra slides/PDF đồng bộ, sau đó mới khai báo production-ready.
8. 💡 Mở rộng (tuỳ chọn, sau khi A+B xong): multi-node incident (contract hiện giới hạn 1 node), so sánh surrogate vs SUMO online nhỏ, hoặc export báo cáo tác động PDF cho operator.

## Cập nhật thực thi Giai đoạn A+B — 2026-08-26

| Hạng mục | Kết quả | PR |
|---|---|---|
| A1 E2E benchmark (app-layer) | ✅ p50=29.4ms / p95=35.2ms / p99=38.5ms, 300/300 — provisional | #60 |
| A2 Baseline evidence binding | ✅ SHA-256 manifest + 6 tests fail-closed | #60 |
| A3 T3 service integration | ✅ Qdrant+TimescaleDB thật: 9/9 pass, 0 skip | #60 |
| A4 Báo cáo thực tập | ✅ Chuyển ra ngoài repo đúng hygiene boundary (PR #58) | — |
| B5 Camera aggregate measured | ✅ 2 videos, 67 detections, sanity pass; **detector provisional (mAP50 0.69 < gate 0.85)** | #61 |
| B6 Auth/tenant enforcement | ✅ EnvBoundPrincipalResolver non-provisional; 202/403/404 measured pass; readiness probe | #62 |

### Blocker còn lại — production E2E SLA (TRA-69)

Không thể đo production SLA hợp lệ trên máy hiện tại:

1. **Hardware**: GTX 1050 Ti 4GB, torch không thấy CUDA — contract yêu cầu GPU 12–16GB VRAM.
2. **Artifacts**: surrogate v3 và GCN-LSTM mock_v2 đều `production_ready=false`; `RuntimeArtifactSet.load` sẽ từ chối đúng theo thiết kế fail-closed.

Điều kiện mở khoá: hardware đạt profile (hoặc quyết định rõ ràng về profile thay thế) + baseline/surrogate train lại và promote thật.

## Kết luận

- Tiến độ MVP hiện tại **~82%** (cập nhật từ ~78%): toàn bộ critical gaps về measured evidence đã được đóng hoặc ghi nhận blocker có định nghĩa mở khoá rõ ràng.
- Trọng tâm rủi ro còn lại tập trung vào **artifact promotion gate** (detector mAP50, surrogate/baseline production_ready) và **hardware benchmark profile**.
- Việc khai báo production-ready chỉ nên thực hiện sau khi TRA-69 mở khoá và release QA tổng hoàn tất.
