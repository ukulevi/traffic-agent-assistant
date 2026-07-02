# 🗺️ KẾ HOẠCH TRIỂN KHAI DỰ ÁN STWI

| Thuộc tính | Giá trị |
|---|---|
| **Dự án** | SmartTraffic What-If (STWI) |
| **Mã tài liệu** | STWI-DOC-05 |
| **Phiên bản** | 1.3 |
| **Ngày tạo** | 19/06/2026 |
| **Cập nhật lần cuối** | 21/06/2026 |
| **Trạng thái** | 📝 Đang soạn thảo (Draft) |
| **Phân loại** | Tài liệu nội bộ — Kế hoạch triển khai MVP |

## 1. Mục tiêu và giả định

Trong 13 tuần, nhóm xây dựng MVP hỗ trợ operator đánh giá What-if trên mạng 20 node, có dự báo GCN–LSTM, surrogate từ SUMO, tri thức pháp lý có citation, workflow an toàn fail-closed và dashboard phê duyệt thủ công.

| Giả định | Giá trị |
|---|---|
| Nhân sự | 1 lead, 1 data, 2 ML, 2 AI/backend, 1 frontend, 1 DevOps; có reviewer pháp lý |
| Demo camera | Tối đa 20 video ghi sẵn/RTSP |
| Vision dataset | Roboflow export chỉ là dữ liệu offline; train YOLOv8 local trong `data/derived/private/vision_training/roboflow_v001` |
| Scale test | 1.000 producer aggregate tổng hợp |
| Hạ tầng benchmark | 8 CPU cores, 32 GB RAM, NVIDIA GPU 12–16 GB |
| Điều khiển hiện trường | Ngoài phạm vi; MVP chỉ đưa khuyến nghị |
| SLA | Surrogate P99 < 500 ms; E2E P95 ≤ 30 giây; hard deadline/P99 ≤ 180 giây |

## 2. Phase 0 — Foundation (Tuần 1)

| ID | Công việc | Deliverable |
|---|---|---|
| 0.1 | Monorepo, Python 3.11, lint/test và pre-commit | CI xanh |
| 0.2 | Docker Compose: TimescaleDB, Qdrant, Redis | Health checks |
| 0.3 | Pydantic contracts: tensor, mask, graph, IncidentVector, SimulationResult, Citation, SimulationQuery, Job API | Contract package |
| 0.4 | Fake interfaces và fixtures cho bốn tầng | Test độc lập |
| 0.5 | Mock network 20 node; camera/sensor/case/legal generators | Reproducible seed |
| 0.6 | Logging, trace_id, model/data/policy version fields | Trace mẫu |
| 0.7 | Privacy/security baseline: secret handling, RBAC skeleton, không lưu video thô | Checklist pass |

**Gate P0:** `project_contract.json`, contract tests, Docker health checks và fake E2E đều pass.

## 3. Phase 1 — Data pipeline (Tuần 2–4)

### Tuần 2: camera và sensor

| ID | Công việc |
|---|---|
| 1.1 | Calibration ROI/homography cho video demo; train/load YOLOv8 local từ dataset `roboflow_v001` + ByteTrack |
| 1.2 | Aggregate 5 phút: volume, speed, heavy-vehicle ratio |
| 1.3 | MQTT schema có version, unit, observed/received timestamp và quality flag |
| 1.4 | Dataset manifest, privacy review, local detector metrics; không phát hành video thô, image base64, signed URL hoặc weight private |

### Tuần 3–4: tensor và quality

| ID | Công việc |
|---|---|
| 1.5 | Node registry, sensor-node mapping, adjacency và capacity table có version |
| 1.6 | Tensor builder `X[B,12,N,16]`, mask `M[B,12,N,16]`, graph `A[N,N]` |
| 1.7 | Feature 16 là `green_time_ratio`; chỉ scale continuous feature bằng train-fitted scaler |
| 1.8 | Imputation + missing mask; dead-letter queue cho schema/unit sai |
| 1.9 | Load test 1.000 aggregate producers; không dùng 1.000 video stream |
| 1.10 | Contract integration T1→T2 |

**Gate P1:** tensor `[32,12,20,16]`, mask và adjacency đúng contract; dataset manifest, local detector artifact, quality/privacy tests pass.

## 4. Phase 2 — Forecast và surrogate (Tuần 3–9)

### Tuần 3–7: baseline forecast

| ID | Công việc |
|---|---|
| 2.1 | Persistence, historical average và seasonal-linear baselines |
| 2.2 | Time-based split, scaler trên train, geographic holdout tùy dữ liệu |
| 2.3 | GCN encoder theo timestep + LSTM temporal decoder |
| 2.4 | Output `Y[B,6,N,2]`: volume và speed; tính V/C từ capacity |
| 2.5 | Metrics theo horizon/node/missing bucket; MLflow artifact version |
| 2.6 | So sánh với baseline; target cải thiện RMSE 20%, không che kết quả nếu không đạt |

### Tuần 4–9: SUMO và surrogate

| ID | Công việc |
|---|---|
| 2.7 | Thiết kế scenario space: closure, demand, signal, duration, event type |
| 2.8 | Calibrate SUMO trên mạng 20 node; sinh dataset offline có seed/version |
| 2.9 | Split theo scenario family/time để tránh leakage |
| 2.10 | Huấn luyện MLP, CNN-1D và light Transformer; weighted ensemble |
| 2.11 | Calibrate uncertainty; cố định OOD/uncertainty threshold trước test |
| 2.12 | High uncertainty/OOD → retrieval evidence + `needs_review`; không blend row online |
| 2.13 | Benchmark P99 < 500 ms trên profile chuẩn |
| 2.14 | Contract integration T2→storage/query |

**Gate P2:** forecast report, SUMO coverage report, calibration report và benchmark report đều được lưu cùng model version.

## 5. Phase 3 — Knowledge và constrained query (Tuần 5–10)

### Tuần 5–7: corpus và Qdrant

| ID | Công việc |
|---|---|
| 3.1 | Source registry + Firecrawl snapshot gate cho luật, văn bản hướng dẫn và SOP ứng viên |
| 3.2 | Ingest Luật 35/2024/QH15, Luật 36/2024/QH15 và SOP đã duyệt |
| 3.3 | Chunk theo điều/khoản; metadata hiệu lực, superseded, source URL và content hash |
| 3.4 | Qdrant dense + sparse retrieval, effective-date filter và reranking |
| 3.5 | Bộ test ≥ 50 câu gồm unanswerable và văn bản hết hiệu lực |

### Tuần 7–9: query và citations

| ID | Công việc |
|---|---|
| 3.6 | LLM tạo Pydantic `SimulationQuery`, không tạo SQL tự do |
| 3.7 | Parameterized SQL builder, TimescaleDB read-only role, timeout/row/tenant limit |
| 3.8 | DuckDB chỉ dùng cho offline analysis và contract tests |
| 3.9 | Citation validator: source allowlist, hiệu lực, provision và content hash |
| 3.10 | Prompt-injection, SQL-injection và tenant-isolation tests |

### Tuần 10: tích hợp

| ID | Công việc |
|---|---|
| 3.11 | Integration T3→orchestrator bằng fake và real adapters |
| 3.12 | Citation precision ≥ 95%; unsupported claim bằng 0 sau validator/abstention |

**Gate P3:** query không có đường SQL thô; thiếu evidence phải trả structured failure/`needs_review`.

## 6. Phase 4 — Orchestrator, API và dashboard (Tuần 8–13)

### Tuần 8–10: workflow

| ID | Công việc |
|---|---|
| 4.1 | LangGraph state machine: parse → forecast → simulate → retrieve/query → evaluate → safety → report |
| 4.2 | Celery worker và Redis broker/progress |
| 4.3 | Counterfactual Safety Loop tối đa 3 vòng |
| 4.4 | Policy version; V/C 0.9 là default cấu hình, không phải luật |
| 4.5 | Fail closed với OOD, thiếu citation, không hội tụ hoặc tool failure |

### Tuần 10–12: API và UI

| ID | Công việc |
|---|---|
| 4.6 | `POST /api/v1/what-if-jobs` trả HTTP 202 + `job_id` |
| 4.7 | `GET /api/v1/what-if-jobs/{job_id}` và SSE `.../{job_id}/events` |
| 4.8 | Status: queued/running/succeeded/needs_review/failed/expired |
| 4.9 | Chỉ succeeded có `recommended_action`; needs_review có candidate không executable |
| 4.10 | Dashboard metrics, citations, warnings, model/policy version và approval |
| 4.11 | Audit operator decision; không có actuator/device API |

### Tuần 12–13: E2E và hardening

| ID | Tiêu chí pass |
|---|---|
| 4.12 | E2E P95 ≤ 30 giây; P99/hard deadline ≤ 180 giây |
| 4.13 | 10 job đồng thời không mất/replay sai job |
| 4.14 | OOD, policy fail, citation missing và timeout đều fail closed |
| 4.15 | SSE reconnect không nhân đôi execution |
| 4.16 | Security/privacy/audit checklist pass |
| 4.17 | PDF, slides và docs validator pass |

**Gate P4:** demo What-if hoàn chỉnh, có evidence, safety status và operator approval; không tự điều khiển thiết bị.

## 7. Timeline tổng hợp

| Tuần | Luồng chính |
|---|---|
| 1 | Contracts, CI, TimescaleDB, Qdrant, Redis |
| 2–4 | Camera/sensor pipeline, local YOLOv8 training, tensor 4D, privacy, 1.000 aggregate producers |
| 3–7 | Baselines và GCN–LSTM |
| 4–9 | SUMO scenario dataset, surrogate và calibration |
| 5–10 | Legal corpus, Qdrant, QuerySpec và citation validator |
| 8–12 | LangGraph, Celery, async API, SSE và dashboard |
| 12–13 | E2E, security, benchmark, PDF/slides và demo |

## 8. Definition of Done

- Code có unit/contract/integration tests và traceable version.
- Vision model artifact có dataset version, checksum, class map, metrics và privacy review trước khi dùng cho demo.
- Không dùng mock qua phase gate trừ test fixture được ghi rõ.
- Không tuyên bố KPI nếu thiếu benchmark profile và raw result.
- Mọi model claim có baseline; mọi legal claim có citation hợp lệ.
- Mọi failure an toàn đều fail closed và cần human review.
- Docs, report, slides và release notes không mâu thuẫn `project_contract.json`.

## 9. Risk register

| ID | Rủi ro | Mức | Trigger | Owner | Ứng phó |
|---|---|---|---|---|---|
| R1 | SUMO chưa đủ calibration/data | Cao | Error vượt gate P2 | ML lead | Thu hẹp scenario space, công bố giới hạn |
| R2 | P99 surrogate > 500 ms | Cao | Benchmark fail | ML lead | Profile → quantize → giảm ensemble |
| R3 | Legal corpus thiếu/hết hiệu lực | Cao | Citation test fail | Legal reviewer | Abstain, bổ sung nguồn chính thức |
| R4 | Retrieval bị prompt injection | Cao | Red-team test fail | AI lead | Isolate content, allowlist và validator |
| R5 | Query vượt quyền/SQL injection | Cao | Security test fail | Backend lead | Typed spec, parameter binding, read-only |
| R6 | Safety loop không hội tụ | Trung bình | Hết 3 vòng | AI lead | `needs_review`, không recommendation |
| R7 | Camera calibration kém | Trung bình | Speed QA fail | Data lead | Bỏ speed tại camera đó, recalibrate |
| R8 | Missing data cao | Trung bình | Missing ratio vượt policy | Data lead | Mask/impute/degraded mode |
| R9 | Timeline trễ | Cao | Gate trễ > 1 tuần | Project lead | Cắt optional UI/MLOps, không cắt safety |
| R10 | Scope 1.000 camera bị hiểu sai | Cao | Demo claim sai | Project lead | Ghi rõ synthetic aggregate load test |
| R11 | Dataset Roboflow không đủ quyền dùng hoặc lệch class map | Trung bình | Manifest thiếu license/privacy hoặc class không ánh xạ | Data lead | Không promote weights, bổ sung review/label hoặc thu hẹp detector claim |

## 10. Lịch sử phiên bản

| Phiên bản | Ngày | Tác giả | Mô tả |
|---|---|---|---|
| 1.0 | 19/06/2026 | Nhóm STWI | Soạn thảo ban đầu |
| 1.1 | 20/06/2026 | Nhóm STWI | Mock-first, integration gates và 13 tuần |
| 1.2 | 20/06/2026 | Nhóm STWI | 16 features và cyclical encoding |
| 1.3 | 21/06/2026 | Nhóm STWI | Chốt MVP 20 node, GCN–LSTM, SUMO dataset, legal/query safety, async jobs, fail-closed và acceptance gates |
