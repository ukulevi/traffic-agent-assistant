# STWI solid hybrid command-center dashboard design

**Ngày:** 2026-07-20

**Trạng thái:** Hướng thiết kế, kiến trúc và đặc tả viết đã được người dùng duyệt

**Phạm vi triển khai:** Dashboard tại `src/stwi/t4_orchestrator/static/`
**Nguồn sự thật:** `project_contract.json`

## 1. Quyết định thiết kế

Dashboard dùng phong cách **Solid Hybrid Command Center**, tham khảo ngôn ngữ tối giản, tương phản cao và modular incident hierarchy của Smart Streets. Thiết kế không dùng glass, blur, translucent card hoặc acrylic surface.

Logic frontend được tách thành các module nhỏ có state machine rõ ràng thay vì tiếp tục mở rộng một file JavaScript duy nhất. Cùng một dashboard phải hỗ trợ ba bối cảnh:

1. **Production:** identity và capability đến từ server; không hiển thị demo preset; mọi safety, evidence và audit gate fail closed.
2. **Demo:** giữ các preset synthetic hiện hành, mạng `mock-network-20-v1`, tenant/operator demo và toàn bộ nhánh safety tái lập được.
3. **Static preview:** chỉ xem giao diện; submit và decision bị vô hiệu hóa, có giải thích cách mở từ FastAPI runtime.

Mục tiêu là **production-grade dashboard behavior**. Đặc tả không tuyên bố toàn hệ thống production-ready khi backend, deployment hoặc operational evidence chưa đạt gate riêng.

## 2. Mục tiêu

- Operator tìm được kết luận, uncertainty/OOD, evidence và hành động tiếp theo trong vài giây.
- Transport error không làm sai canonical job status.
- Approval chỉ khả dụng khi status, action, evidence, identity và quyền đều hợp lệ.
- Reload, SSE reconnect và polling fallback không làm mất job đang theo dõi.
- Demo hiện tại vẫn chạy được mà không cần production identity provider hoặc dịch vụ mới.
- UI Vietnamese-first, responsive, keyboard-accessible và không tạo cảm giác hệ thống tự điều khiển giao thông.

## 3. Ngoài phạm vi

- Không thay đổi tensor, model, SLA, safety loop hoặc sáu status canonical.
- Không thêm automatic actuation, raw-video player, camera playback, traffic reroute hoặc signal control.
- Không thêm frontend framework hay dependency mới trong thiết kế này.
- Không lựa chọn IdP, telemetry vendor, secrets manager hoặc deployment platform.
- Không sửa slide, report hoặc visual system ngoài dashboard.

## 4. Visual direction không glass

### 4.1 Lớp giao diện

- Dark shell/navigation dùng màu đặc `#072B38`.
- Canvas `#EFF4F6`, primary surface `#FFFFFF`, subtle surface `#F5F8FA`.
- Border `#C9D7DF`, text `#14232C`, muted text `#52636D`.
- Primary giữ STWI `#006699`; hover/active `#004D73`.
- Data `#B45309`, ML `#1D4ED8`, Knowledge/RAG `#15803D`, Safety `#7E22CE`.
- Success, review, failure và expiry dùng semantic token riêng, luôn kèm icon và text.
- Radius 10–12 px; shadow nhẹ chỉ để phân lớp.

Không dùng `backdrop-filter`, translucent fill, glass border, acrylic blur, glow hoặc gradient trên data surface. Alpha chỉ dùng cho shadow và focus halo.

### 4.2 Typography và accessibility baseline

- `Be Vietnam Pro` cho nội dung tiếng Việt.
- `Azeret Mono` cho ID, timestamp, version và giá trị kỹ thuật.
- Body tối thiểu 14 px; metadata tối thiểu 12 px.
- Target tương tác tối thiểu 44×44 px.
- Text thường đạt WCAG AA; status không truyền đạt chỉ bằng màu.

### 4.3 Thành phần tham khảo và phần bị loại

Mượn từ Smart Streets: high contrast, compact rail, timeline, node context, modular incident hierarchy và khoảng trắng có chủ đích.

Không sao chép: camera feed, playback, fault/no-fault judgment, real-time surveillance claim, auto-resolve, dispatch, reroute, signal control, palette đỏ-nâu chủ đạo, chữ cực nhỏ hoặc motion cinematic.

## 5. Information architecture

### 5.1 Desktop từ 1024 px

1. **Header:** STWI, runtime mode, selected node, data freshness, connection state và canonical job status.
2. **Left rail 220–240 px:** search/filter đúng 20 node; không tạo node ngoài registry.
3. **Main workspace tối thiểu 560 px:** plain-language conclusion, horizon 30 phút, assumptions, hai forecast output, V/C và lifecycle.
4. **Evidence rail 280–320 px:** uncertainty/OOD, citation validation, provenance, model/data/capacity/policy version và `trace_id`.
5. **Decision gate:** sau evidence, dùng CTA **Ghi nhận quyết định** mở dialog audit.

Hero quảng bá, KPI giới thiệu và glossary dài không nằm trong first decision-relevant viewport. Nội dung demo được chuyển thành disclosure hoặc help panel.

### 5.2 Tablet 768–1023 px

- Node rail thu gọn thành drawer.
- Result ở đầu, evidence ngay sau result.
- Lifecycle, scenario composer và history đặt sau decision section.
- Metric hai cột chỉ khi label và unit không bị cắt.

### 5.3 Mobile 360–767 px

Thứ tự bắt buộc:

`result → uncertainty/OOD → evidence → citations/audit → decision → scenario/history`

- 360 px dùng metric một cột.
- 390 px có thể dùng hai cột sau visual verification.
- Long ID wrap hoặc có nút copy.
- Không sticky CTA trước evidence.
- Drawer/dialog có focus trap và trả focus đúng vị trí.

## 6. Kiến trúc frontend module hóa

Không thêm build step hoặc framework. Dùng native ES modules:

### 6.1 `dashboard.js`

Entry point và coordinator. Bootstrap mode, nối event handler, tạo dependency và điều phối state → render. Không chứa business-rule chi tiết.

### 6.2 `dashboard-state.js`

Pure reducer, transition guards và selectors:

- canonical job state;
- transport state;
- decision state;
- response validation result;
- selectors như `canApprove`, `canReject`, `canRequestChanges`, `shouldShowRecommendation`.

Module không truy cập DOM hoặc network để có thể unit test trực tiếp.

### 6.3 `dashboard-api.js`

Bao bọc `fetch`, timeout, `AbortController`, safe error parsing, exact HTTP status validation, SSE lifecycle, retry/backoff và polling fallback. Không render UI.

### 6.4 `dashboard-view.js`

Render state bằng `textContent`, `replaceChildren` và DOM APIs. Quản lý focus, live region, dialog/drawer và copy ID. Không quyết định eligibility.

### 6.5 `dashboard-mode.js`

Chuẩn hóa runtime context cho production, demo và static preview. Module này giữ compatibility với demo hiện hành và cô lập mọi fallback provisional.

## 7. Ba miền trạng thái độc lập

### 7.1 Creation phase và authoritative job state

Local creation phase là `idle → submitting → accepted | creation_unknown | error`. Các giá trị này chỉ là UI phase, không phải job status.

Sau khi POST được xác nhận, authoritative job state là:

`queued → running → succeeded | needs_review | failed | expired`

- Chỉ validated API payload được phép đặt sáu status canonical.
- Không cho transition lùi từ terminal về running/queued.
- Unknown status trở thành presentation condition `invalid_response`, không trở thành job status mới.

### 7.2 Transport state

`checking → online → streaming → reconnecting → polling_fallback → offline | protocol_error`

- Transport state không ghi đè job state.
- Mất kết nối giữ `job_id`, last-known status và timestamp.
- UI hiển thị “Mất kết nối — trạng thái job chưa xác định”, không hiển thị `failed`.

### 7.3 Decision state

`unavailable → eligible → confirming → submitting → reconciling → recorded | error`

Mọi operation giữ immutable context `{jobId, traceId, operationEpoch}`. Callback cũ bị bỏ qua nếu không khớp active context.

## 8. Runtime mode và demo compatibility

### 8.1 Bootstrap order

1. Thử lấy trusted runtime context do server cung cấp.
2. Nếu context xác nhận production, bắt buộc có tenant/operator/roles/capabilities hợp lệ.
3. Nếu endpoint/context chưa tồn tại nhưng `/openapi.json` xác nhận provisional STWI runtime, dùng `demo_compat`.
4. Nếu không tìm thấy runtime, dùng static preview và disable submit/decision.

Production không được fallback im lặng sang demo. Chỉ runtime provisional rõ ràng mới được dùng `demo_compat`.

### 8.2 Mode matrix

| Capability | Production | Demo | Static preview |
|---|---|---|---|
| Scenario submit | Theo role | Có | Không |
| Demo presets | Ẩn | Hiện | Có thể xem, không chạy |
| Tenant/operator | Read-only từ principal | Nhãn demo/provisional | Không có |
| Node registry | Versioned server context | `node_00`–`node_19` | Mock labels chỉ để preview |
| Decision | Theo role và gate | Audit-only như hiện tại | Không |
| Synthetic warning | Khi dữ liệu synthetic | Luôn hiện | Luôn hiện |

### 8.3 Không regress demo

- Giữ toàn bộ preset safety và operational hiện hành.
- Giữ mapping synthetic node và wording không-causal.
- Giữ POST 202, GET status và SSE events hiện hành.
- Demo không cần production SSO, external telemetry hoặc server context endpoint mới.
- Static preview vẫn giải thích rõ vì sao không thể submit.

## 9. Job lifecycle và transport

### 9.1 Create

- Validate và snapshot form trước khi gửi.
- Ngăn double-click trong tab bằng state `creating`.
- Require HTTP 202 và validate `job_id`, `queued`, tenant, resolved operator và runtime mode.
- Persist accepted active job trong `sessionStorage`; không lưu scenario query hoặc payload nhạy cảm.
- Response create không rõ kết quả trở thành `creation_unknown`; UI không tự retry POST.

Exactly-once create cần server-enforced idempotency key. UI có thể sinh/persist key nhưng không được tuyên bố chống trùng hoàn toàn nếu backend chưa enforce.

### 9.2 Observe

- SSE là kênh progress chính.
- Track và deduplicate monotonic event ID.
- Cho phép native/bounded reconnect và resume `Last-Event-ID`.
- GET là kênh reconciliation và polling fallback.
- Polling backoff 1 s → 2 s → tối đa 5 s, có jitter và giảm tần suất khi tab hidden.
- Mỗi request có timeout/abort; local timeout không tạo `expired`.

### 9.3 Terminal reconcile

Sau terminal event, GET authoritative envelope và validate:

- job ID, tenant và timestamps;
- envelope/result status consistency;
- trace ID và audit record;
- model/data/capacity/policy/calibration provenance;
- action field đúng status;
- `executable=false`, `automatic_actuation=false` và human approval requirement;
- evidence/citation outcome.

Mismatch trở thành `protocol_error` hoặc `evidence_insufficient` và suppress approval.

### 9.4 Refresh/resume

Khi reload, UI đọc active job ID từ `sessionStorage`, gọi GET, sau đó resume SSE nếu job chưa terminal. Access vẫn do server tenant/role boundary quyết định.

## 10. Evidence và approval gate

UI không tự tuyên bố citation “hợp lệ” chỉ vì trường tồn tại. Nó phân biệt:

- `pending`: chưa có terminal result;
- `valid`: server xác nhận structured citation/effective-date checks;
- `insufficient`: thiếu nguồn, provision, effective date hoặc provenance;
- `invalid`: server xác nhận nguồn hết hiệu lực/không hợp lệ;
- `unknown`: backend hiện tại chưa cung cấp typed outcome.

Trong `unknown`, UI hiển thị citation để operator xem nhưng không gọi là đã hợp lệ. Production approval cần typed validation outcome từ backend. Demo compatibility dùng một `demoEvidenceGate` tách biệt, giữ bounded fail-closed checks hiện hành và luôn gắn nhãn provisional; kết quả này không được trình bày như production legal validation.

`canApprove` chỉ true khi tất cả điều kiện đúng:

- role là operator/admin;
- canonical status là `succeeded`;
- terminal payload đã reconcile;
- `recommended_action` hợp lệ và non-executable;
- evidence gate đạt mức được runtime mode cho phép;
- chưa có decision record;
- transport không ở `protocol_error`.

## 11. Decision matrix và confirmation dialog

| Job state | Cho phép |
|---|---|
| `queued`, `running` | Không có decision |
| `succeeded` + gate đầy đủ | Approve, reject, request changes |
| `succeeded` + evidence/protocol thiếu | Không submit decision; yêu cầu reload/đối chiếu |
| `needs_review` | Reject hoặc request changes; không approve |
| `failed`, `expired` | Ghi nhận không sử dụng kết quả hoặc tạo job mới; không có proposal |
| Decision đã ghi | Chỉ xem immutable audit record |

CTA ngoài panel là **Ghi nhận quyết định**. Dialog hiển thị job ID, trace ID, operator, terminal status, action kind và evidence state.

- Rationale bắt buộc với reject/request changes.
- Approve yêu cầu explicit confirmation rằng đây là audit-only và không gửi lệnh hiện trường.
- Sau POST decision, GET lại job để xác nhận record persisted và `applied_by_system=false`.
- 409/conflict hiển thị decision hiện có, không tự ghi đè.

## 12. Error taxonomy và observability

UI ưu tiên stable server error `code`, safe `message` và `trace_id`; không hiển thị raw exception hoặc log scenario query/citation payload.

Presentation conditions ngoài job status:

- `unauthorized` / `forbidden`;
- `offline` / `reconnecting`;
- `creation_unknown`;
- `invalid_response` / `protocol_error`;
- `decision_conflict`;
- `static_preview`.

Telemetry hook chỉ ghi loại sự kiện, latency bucket, status code, job/trace ID đã được policy cho phép và runtime mode. Không ghi prompt đầy đủ, image/base64, secret hoặc tenant/operator hint chưa được phép.

Backend collector, retention và alerting là dependency ngoài UI.

## 13. Accessibility và interaction

- Có skip link đến main result.
- Sau submit, focus chuyển đến lifecycle heading; terminal result chuyển focus có kiểm soát đến conclusion.
- Error đưa focus đến alert summary nhưng không làm mất dữ liệu form.
- Drawer/dialog có focus trap, `Esc`, focus return và accessible name.
- Status live region dùng mức thông báo phù hợp, không đọc lại toàn panel.
- Tôn trọng `prefers-reduced-motion`; không animation lặp.
- Node search, copy ID và decision flow dùng được hoàn toàn bằng bàn phím.

## 14. Thay đổi artifact dự kiến

- `src/stwi/t4_orchestrator/static/index.html`: IA result-first, drawer/dialog và semantic landmarks.
- `src/stwi/t4_orchestrator/static/dashboard.css`: solid token system, responsive layout và accessibility.
- `src/stwi/t4_orchestrator/static/dashboard.js`: coordinator/bootstrap.
- `src/stwi/t4_orchestrator/static/dashboard-state.js`: reducer/guards/selectors.
- `src/stwi/t4_orchestrator/static/dashboard-api.js`: transport/API client.
- `src/stwi/t4_orchestrator/static/dashboard-view.js`: safe DOM rendering.
- `src/stwi/t4_orchestrator/static/dashboard-mode.js`: production/demo/static adapter.
- Dashboard static/behavior tests: state matrix, response guards và mode compatibility.
- `docs/design/stwi_ui_design_system.md`: no-glass direction, IA và state separation.
- `docs/guides/mvp_operator_dashboard.md`: dual-mode operator workflow.

Không sửa `project_contract.json` trong UI implementation. API dependency nào cần contract change phải được tách thành quyết định riêng.

## 15. Acceptance matrix

### 15.1 Safety và contract

- Sáu canonical status là server-authoritative.
- Transport error không tạo canonical status.
- Chỉ `succeeded` có `recommended_action`; chỉ `needs_review` có `candidate_action`.
- Không action nào executable hoặc automatic.
- Missing/unknown evidence suppress approval trong production.

### 15.2 Reliability

- SSE reconnect/resume và partial timeline reconciliation được test.
- Polling fallback có backoff, abort và visibility handling.
- Stale response không cập nhật job mới.
- Reload resume job đúng tenant boundary.
- Ambiguous create không tự retry.

### 15.3 Mode compatibility

- Production không hiển thị demo preset hoặc editable identity.
- Demo giữ toàn bộ preset, synthetic warnings và deterministic branches.
- Static preview disable submit/decision.
- Production không fallback sang demo khi context không hợp lệ.

### 15.4 Browser và accessibility

- Test 360, 390, 430, 768, 1024 và 1280 px.
- Không horizontal overflow, text clipping hoặc overlap.
- Keyboard traversal, dialog/drawer focus, zoom 200% và reduced motion được kiểm tra.
- Chromium là gate tối thiểu; Firefox/WebKit là production evidence mong muốn nếu dependency được chấp thuận.

### 15.5 Performance

- Không poll 250 ms liên tục.
- Không render lại toàn dashboard cho một progress event.
- Không tải raw video hoặc asset không cần thiết.
- Console không có uncaught error trong các nhánh lifecycle.

## 16. Verification commands

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
python -m unittest tests.demo.test_dashboard_static tests.t4_orchestrator.test_dashboard_static -v
python -m unittest tests.t4_orchestrator.test_t4_api_http tests.t4_orchestrator.test_t4_auth_boundary -v
node --check src/stwi/t4_orchestrator/static/dashboard.js
node --check src/stwi/t4_orchestrator/static/dashboard-state.js
node --check src/stwi/t4_orchestrator/static/dashboard-api.js
node --check src/stwi/t4_orchestrator/static/dashboard-view.js
node --check src/stwi/t4_orchestrator/static/dashboard-mode.js
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Dashboard còn phải chạy qua HTTP local để kiểm tra demo happy path, tất cả fail-closed branches, static preview, SSE reconnect, offline recovery, keyboard/dialog focus và responsive layout.

## 17. Ranh giới production readiness

UI implementation có thể đạt production-grade behavior cho state management, safe rendering, reconnect, validation, accessibility và demo compatibility.

Các gate sau không thể được UI tự giải quyết:

- trusted session/principal/capability bootstrap;
- server-enforced idempotency;
- typed citation validity/effective-date outcome;
- authoritative network registry/freshness metadata;
- CSP/security headers và CSRF policy;
- telemetry collector, retention và alerting;
- Redis/Celery/TimescaleDB/Qdrant deployment evidence.

Dashboard chỉ được gọi production-ready end-to-end khi các dependency này có implementation và verification evidence riêng.
