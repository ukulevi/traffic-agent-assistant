# 🎯 STWI — Minimum Observability Proposal

| Thuộc tính | Giá trị |
|---|---|
| **Dự án** | SmartTraffic What-If (STWI) |
| **Mục tiêu** | Đề xuất trace/log/metric tối thiểu cho job execution |
| **Phạm vi** | Chỉ proposal docs; không chọn backend triển khai |
| **Trạng thái** | Draft |

> [!IMPORTANT]
> MVP chỉ hỗ trợ ra quyết định. Không tự điều khiển thiết bị hiện trường, không gửi lệnh actuation.

## 1. Yêu cầu trace fields

Mỗi job cần đủ fields để audit mà không nhân diện người dùng cá nhân hóa.

Required fields:
- `trace_id`: ident phản ánh request/job/iteration quan hệ
- `job_id`: ident job theo status enum và artifact timestamps
- `status`: một trong `queued`, `running`, `succeeded`, `needs_review`, `failed`, `expired`
- `status_transition`: epoch; lưu timestamp chuyển trạng thái cuối
- `created_at`, `started_at`, `ended_at`: epoch
- `model_version`, `data_version`, `policy_version`: giữ provenance
- `safety_loop_outcome`: kết quả vòng safety sau max 3 iterations
- `safety_reason_code`: ví dụ `VC_THRESHOLD`, `MISSING_CITATION`, `OOD`, `TIMEOUT`, `INTERNAL_ERROR`, `UNKNOWN_NODE`
- `citation_validation_outcome`: có/nhờ abstain/không hiệu lực khi relevant
- `operator_decision`: human approval state nếu áp dụng

## 2. Yêu cầu log redaction policy

Log có thể phát triển sau; nhung log bắt buộc tuân strict redaction.

Không log:
- secret, API key, token, password
- raw video, image base64, signed URL
- RTSP endpoint/credentials
- full prompt có dữ liệu nhạy cảm; chỉ lưu đủ PII/agg-only policy evidence
- raw SQL thô; thay bằng parameterized query shape không có literal values
- private data hoặc legal corpus payload dumps ngoài phần redacted
- model weights, checkpoint binary paths/public URLs khi private

## 3. Metric names tối thiểu

Dùng chung ở level aggregation; không giới hạn backend.

Counter:
- `stwi_jobs_total{status}`
- `stwi_jobs_timeout_fail_closed_total`
- `stwi_jobs_safety_loop_outcome_total{outcome}`
- `stwi_citation_validation_failures_total`
- `stwi_queue_age_violations_total`

Histogram:
- `stwi_job_latency_seconds{status}`
- `stwi_retrieval_latency_seconds`
- `stwi_surrogate_latency_seconds`

Gauge:
- `stwi_queue_age_seconds`

## 4. Retention/audit notes

- Giữ auditable trace_id, model/data/policy versions và operator decision trong vòng tối thiểu theo policy pháp lý nội bộ.
- Không export raw video hoặc private evidence ra log/metric/export pipeline.
- Chỉ phát hành bên ngoài data đã được aggregate-only approval.
- Các trạng thái `needs_review`, `failed`, `expired` phải ưu tiên hiển thị/highlight hơn nội dung trang trí.

## 5. Giới hạn triển khai

- Không chọn Prometheus, OpenTelemetry, managed monitoring hoặc thư viện telemetry mới lúc này.
- Nếu implementation gaps phát hiện, ghi thành follow-up issue thay vì implement trong TRA-14.

## 6. Tài liệu liên quan

- `docs/04_AI_Agent_Orchestrator_CF_VLA.md`
- `docs/05_Implementation_Plan.md`
