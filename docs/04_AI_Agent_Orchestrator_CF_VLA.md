# 🚦 STWI — Tài liệu Đặc tả Kỹ thuật (Phần 4)

## LangGraph Orchestrator & Counterfactual Safety Loop

| Thuộc tính | Giá trị |
|---|---|
| **Dự án** | SmartTraffic What-If (STWI) |
| **Mã tài liệu** | STWI-DOC-04 |
| **Phiên bản** | 1.4 |
| **Ngày tạo** | 15/06/2026 |
| **Cập nhật lần cuối** | 21/06/2026 |
| **Trạng thái** | 📝 Đang soạn thảo (Draft) |
| **Phân loại** | Tài liệu nội bộ — Đặc tả kỹ thuật |

> [!NOTE]
> Cơ chế của STWI là **Counterfactual Safety Loop (CSL), lấy cảm hứng từ CF-VLA**. CF-VLA gốc là mô hình Vision–Language–Action end-to-end dùng ngữ cảnh thị giác để điều chỉnh quỹ đạo; STWI chỉ áp dụng ý tưởng tự phản biện vào workflow dữ liệu–mô phỏng–pháp lý: [arXiv:2512.24426](https://arxiv.org/abs/2512.24426).

## 1. Workflow điều phối

LangGraph được dùng như state machine có node chuyên trách; “agent” không được tự ý thay đổi policy hoặc gọi tool ngoài allowlist.

```mermaid
flowchart TB
    START["Job queued"] --> PARSE["Parse + validate scenario"]
    PARSE --> BASE["Baseline forecast"]
    BASE --> SIM["Scenario surrogate"]
    SIM --> OOD{"OOD / uncertainty cao?"}
    OOD -->|"Có"| REVIEW["needs_review"]
    OOD -->|"Không"| LEGAL["Retrieve law/SOP + citations"]
    LEGAL --> GROUND{"Đủ citation hợp lệ?"}
    GROUND -->|"Không"| REVIEW
    GROUND -->|"Có"| PROPOSE["Generate candidate"]
    PROPOSE --> CSL["Counterfactual Safety Loop"]
    CSL --> SAFE{"Policy pass?"}
    SAFE -->|"Có"| SUCCESS["succeeded"]
    SAFE -->|"Không, còn lượt"| CORRECT["Correct candidate"] --> CSL
    SAFE -->|"Không hội tụ"| REVIEW
    SUCCESS --> HUMAN["Operator approval"]
    REVIEW --> HUMAN
```

| Node | Trách nhiệm | Không được làm |
|---|---|---|
| Parser | Chuẩn hóa scenario và `IncidentVector` | Suy đoán node không tồn tại |
| Simulation | Gọi baseline/surrogate có version | Tự bỏ qua OOD gate |
| Knowledge | QuerySpec + Qdrant + citation validator | Chạy SQL thô hoặc dùng văn bản hết hiệu lực |
| Evaluator | Sinh candidate từ metrics/evidence | Biến evidence yếu thành khẳng định |
| Safety | Chạy tối đa 3 counterfactual iterations | Trả action thực thi khi chưa pass |
| Reporter | Đóng gói result và audit | Xóa warning/provenance |

## 2. Counterfactual Safety Loop

### 2.1. Policy

Ngưỡng V/C mặc định `0.9` là cấu hình MVP, không phải luật. Safety policy có version và kiểm tra tối thiểu:

- max V/C của node bị ảnh hưởng và node lân cận;
- network delay và spillback proxy;
- uncertainty/OOD;
- citation validity;
- constraints người vận hành;
- dữ liệu thiếu/degraded.

### 2.2. Fail-closed

| Điều kiện | Trạng thái |
|---|---|
| Tất cả check pass và có citation | `succeeded` + `recommended_action` |
| Không hội tụ sau 3 vòng | `needs_review` + `candidate_action` |
| OOD/uncertainty cao | `needs_review`; không gọi candidate là recommendation |
| Thiếu citation còn hiệu lực | `needs_review` hoặc `failed` tùy loại lỗi |
| Tool/runtime lỗi không phục hồi | `failed` |
| Vượt 180 giây | `expired` |

MVP không có actuator. Ngay cả `succeeded` vẫn cần operator phê duyệt và quyết định được ghi vào audit log.

### 2.3. Resilience Policy for Dependency Failures

Để đảm bảo an toàn hệ thống, STWI áp dụng chính sách **fail-closed tuyệt đối** (từ chối mọi cơ chế fail-open hoặc fallback phỏng đoán) đối với lỗi từ các hệ thống phụ thuộc (TimescaleDB, Qdrant, Celery, Redis, model inference, LLM call, tool execution).

- **Retry, Timeout và Circuit-breaker**: Các lỗi mạng hoặc lỗi dịch vụ tạm thời được phép retry có giới hạn (exponential backoff) nhưng bị ràng buộc bởi hard deadline P99 (180 giây). Nếu vượt quá deadline hoặc gặp lỗi hệ thống nghiêm trọng (connection refused, auth failure, schema mismatch), dependency client không được retry vô hạn mà phải ngắt mạch (circuit-break) ngay lập tức.
- **Fail-closed bắt buộc**:
  - Mọi sự cố phụ thuộc (timeout, sập dịch vụ, lỗi truy vấn) đều bắt buộc map về trạng thái `needs_review`, `failed`, hoặc `expired`.
  - Tuyệt đối không có bất kỳ đường chạy (runtime path) nào được trả về một `recommended_action` có khả năng thực thi (executable action) sau khi tool, RAG, TimescaleDB, Qdrant, Celery, Redis, hoặc model dự báo gặp sự cố. Bất kỳ ngôn từ hay ý định nào về việc "bỏ qua bước nếu lỗi" hay "dùng giá trị dự phòng để tiếp tục" đều bị loại bỏ.
- **Các kịch bản kiểm thử trọng tâm (focused tests)** cần được phát triển để xác nhận hành vi này trước mọi hoạt động hardening trên môi trường production:
  - `test_timescaledb_timeout_yields_expired`
  - `test_qdrant_unreachable_yields_failed`
  - `test_surrogate_model_crash_yields_failed`
  - `test_celery_redis_outage_fails_closed`

## 3. API bất đồng bộ

### 3.1. Tạo job

`POST /api/v1/what-if-jobs` → HTTP 202

```json
{
  "tenant_id": "test-tenant",
  "scenario_time": "2026-06-21T08:00:00+07:00",
  "candidate_action": {
    "node_id": "node-A",
    "green_time_ratio": 0.7
  },
  "node_ids": ["node-A", "node-B"],
  "scenario_query": "Tai nạn tại node A; đánh giá phương án phân luồng sang B",
  "horizons_minutes": [5, 10, 15, 30],
  "jurisdiction": "VN",
  "vc_threshold": 0.9
}
```

```json
{
  "job_id": "wf_01J...",
  "status": "queued",
  "status_url": "/api/v1/what-if-jobs/wf_01J...",
  "events_url": "/api/v1/what-if-jobs/wf_01J.../events",
  "trace_id": "tr_01J...",
  "created_at": "2026-06-21T08:00:01+07:00"
}
```

### 3.2. Theo dõi job

- `GET /api/v1/what-if-jobs/{job_id}`: snapshot trạng thái và result.
- `GET /api/v1/what-if-jobs/{job_id}/events`: SSE với `stage`, `iteration`, `progress`, `message`, `timestamp`.
- Status enum: `queued`, `running`, `succeeded`, `needs_review`, `failed`, `expired`.

### 3.3. Kết quả succeeded

```json
{
  "job_id": "wf_01J...",
  "status": "succeeded",
  "tenant_id": "test-tenant",
  "scenario_time": "2026-06-21T08:00:00+07:00",
  "recommended_action": {
    "node_id": "node-A",
    "green_time_ratio": 0.7,
    "action_kind": "recommended_action",
    "executable": false,
    "requires_operator_approval": true,
    "automatic_actuation": false
  },
  "candidate_action": null,
  "citations": [
    {
      "document_id": "sop-incident-14",
      "title": "SOP xử lý tai nạn nút giao",
      "document_number": "SOP-14",
      "provision": "Mục 3.2",
      "source_url": "https://internal.example/sop-14",
      "effective_from": "2026-01-01",
      "effective_to": null,
      "content_hash": "sha256:..."
    }
  ],
  "needs_review_reason": null,
  "baseline_summary": {
    "node_count": 20,
    "horizon_count": 4,
    "avg_volume": 120.5,
    "avg_speed": 45.2,
    "warning": ""
  },
  "scenario_summary": {
    "node_count": 20,
    "max_vc_ratio": 0.86,
    "max_uncertainty": 0.12,
    "max_ood_score": 0.05,
    "avg_volume": 118.4,
    "avg_speed": 47.1,
    "warning": ""
  },
  "safety_iterations": 2,
  "safety_checks": [
    {
      "passed": false,
      "iteration": 1,
      "vc_ratio_ok": false,
      "citations_ok": true,
      "uncertainty_ok": true,
      "ood_ok": true,
      "fail_reason": "V/C ratio 0.95 exceeds threshold 0.90"
    },
    {
      "passed": true,
      "iteration": 2,
      "vc_ratio_ok": true,
      "citations_ok": true,
      "uncertainty_ok": true,
      "ood_ok": true,
      "fail_reason": null
    }
  ],
  "audit_record": {
    "trace_id": "tr_01J...",
    "job_id": "wf_01J...",
    "tenant_id": "test-tenant",
    "scenario_time": "2026-06-21T08:00:00+07:00",
    "model_version": "provisional_mock_v1",
    "corpus_parser_version": "1.0.0",
    "status": "succeeded",
    "status_reason": "succeeded",
    "safety_iterations": 2
  },
  "model_version": "provisional_mock_v1",
  "data_version": "synthetic_mock_phase4"
}
```

### 3.4. Kết quả needs_review

```json
{
  "job_id": "wf_01J...",
  "status": "needs_review",
  "tenant_id": "test-tenant",
  "scenario_time": "2026-06-21T08:00:00+07:00",
  "recommended_action": null,
  "candidate_action": {
    "node_id": "node-A",
    "green_time_ratio": 0.7,
    "action_kind": "candidate_action",
    "executable": false,
    "requires_operator_approval": true,
    "automatic_actuation": false
  },
  "citations": [],
  "needs_review_reason": "SAFETY_NOT_CONVERGED: Không đạt policy sau 3 vòng; max V/C còn 0.93",
  "baseline_summary": {
    "node_count": 20,
    "horizon_count": 4,
    "avg_volume": 120.5,
    "avg_speed": 45.2,
    "warning": ""
  },
  "scenario_summary": {
    "node_count": 20,
    "max_vc_ratio": 0.93,
    "max_uncertainty": 0.15,
    "max_ood_score": 0.08,
    "avg_volume": 125.1,
    "avg_speed": 40.5,
    "warning": ""
  },
  "safety_iterations": 3,
  "safety_checks": [
    {
      "passed": false,
      "iteration": 1,
      "vc_ratio_ok": false,
      "citations_ok": true,
      "uncertainty_ok": true,
      "ood_ok": true,
      "fail_reason": "V/C ratio 0.95 exceeds threshold 0.90"
    },
    {
      "passed": false,
      "iteration": 2,
      "vc_ratio_ok": false,
      "citations_ok": true,
      "uncertainty_ok": true,
      "ood_ok": true,
      "fail_reason": "V/C ratio 0.94 exceeds threshold 0.90"
    },
    {
      "passed": false,
      "iteration": 3,
      "vc_ratio_ok": false,
      "citations_ok": true,
      "uncertainty_ok": true,
      "ood_ok": true,
      "fail_reason": "V/C ratio 0.93 exceeds threshold 0.90"
    }
  ],
  "audit_record": {
    "trace_id": "tr_01J...",
    "job_id": "wf_01J...",
    "tenant_id": "test-tenant",
    "scenario_time": "2026-06-21T08:00:00+07:00",
    "model_version": "provisional_mock_v1",
    "corpus_parser_version": "1.0.0",
    "status": "needs_review",
    "status_reason": "SAFETY_NOT_CONVERGED",
    "safety_iterations": 3
  },
  "model_version": "provisional_mock_v1",
  "data_version": "synthetic_mock_phase4"
}
```

### 3.5. Error model

```json
{
  "job_id": "wf_01J...",
  "status": "failed",
  "error": {
    "code": "SIMULATION_UNAVAILABLE",
    "message": "Surrogate worker không khả dụng",
    "retryable": true
  },
  "trace_id": "tr_01J..."
}
```

Error codes tối thiểu: `INVALID_SCENARIO`, `UNKNOWN_NODE`, `SIMULATION_UNAVAILABLE`, `KNOWLEDGE_UNAVAILABLE`, `QUERY_INVALID`, `POLICY_ERROR`, `INTERNAL_ERROR`.

## 4. Runtime và observability
- FastAPI tiếp nhận request; Celery chạy job; Redis làm broker/progress store.
- Ở provisional API (trước khi thay Celery/Redis), `STWI_JOB_CONCURRENCY=auto` tự chọn số job được chạy đồng thời bằng một nửa số CPU phát hiện được (ít nhất 1, tối đa 4). Job vượt mức giữ `queued`; người vận hành có thể đặt số nguyên dương sau khi benchmark. Cơ chế này không thay đổi deadline 180 giây hay safety gate.
- Khi `STWI_RUNTIME_MODE=production`, API từ chối cả fake adapter, kể cả `T3KnowledgeTier` bọc fake adapter, và `InMemoryJobStore` được inject tường minh; chỉ adapter/store production thực mới được phép nhận job. Guard này không tự khởi động hay truy cập dịch vụ bên ngoài.
- Mỗi transition LangGraph phát SSE event và ánh xạ sang minimum trace/log/metric trong `docs/guides/observability_minimum.md`.
- Retry chỉ áp dụng tool idempotent, có backoff và giới hạn.
- Hard deadline 180 giây được truyền xuống mọi tool.
- Lưu scenario hash, input/model/policy/corpus version, citations, iterations và operator decision.
- E2E target P95 ≤ 30 giây; P99/hard deadline ≤ 180 giây.
- Prometheus, OpenTelemetry, hoặc managed monitoring stack là future deployment choice; không chọn backend trong TRA-14.

## 5. Acceptance gates

1. API examples parse được và đúng status/field contract.
2. `recommended_action` không xuất hiện ở bất kỳ status nào ngoài `succeeded`.
3. `needs_review` luôn có `candidate_action.executable=false`.
4. OOD, thiếu citation, policy fail và timeout đều được test.
5. SSE reconnect không chạy lặp job.
6. Operator approval và audit log được kiểm thử.
7. Không có code path điều khiển thiết bị hiện trường.

## Phụ lục: Lịch sử phiên bản

| Phiên bản | Ngày | Tác giả | Mô tả |
|---|---|---|---|
| 1.0 | 15/06/2026 | Nhóm STWI | Soạn thảo ban đầu |
| 1.1 | 15/06/2026 | Nhóm STWI | Chuẩn hóa diagram |
| 1.2 | 20/06/2026 | Nhóm STWI | LangGraph và partial/error response |
| 1.3 | 20/06/2026 | Nhóm STWI | Đồng bộ version |
| 1.4 | 21/06/2026 | Nhóm STWI | Định vị CF-VLA-inspired đúng phạm vi, fail-closed, async jobs + SSE, structured citations và human approval |
