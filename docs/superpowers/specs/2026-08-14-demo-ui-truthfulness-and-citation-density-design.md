# STWI Demo UI Truthfulness and Citation Density Design

**Date:** 2026-08-14
**Scope:** Hai pull request độc lập cho dashboard `/demo/`; không đổi API contract,
không đổi visual system và không mở đường cho automatic actuation.

## 1. Bối cảnh

Lần chạy live trên `STWI_RUNTIME_MODE=demo` xác nhận các invariant an toàn chính
vẫn hoạt động: `succeeded` chỉ có `recommended_action`, `needs_review` không thể
được operator phê duyệt, mọi action đều `NON-EXECUTABLE` và quyết định audit có
`applied_by_system=false`.

Tuy nhiên, bốn trạng thái trình bày chưa phản ánh đúng runtime:

1. Preset `refinement` tuyên bố hai vòng nhưng demo composition chỉ chạy một vòng.
2. Tiêu đề Result và Safety vẫn giữ copy khởi tạo sau khi job terminal.
3. Callback SSE `reconnecting` đến muộn có thể ghi đè connection badge sau terminal.
4. UI có ô `capacity_version` nhưng job result không mang trường này, nên luôn hiện `—`.

Danh sách citation đầy đủ cũng đẩy vùng quyết định operator xuống quá xa. Vấn đề
này độc lập với state truthfulness và được triển khai trong PR riêng.

## 2. Quyết định phạm vi

### PR 1 — Demo state truthfulness

PR 1 sửa bốn lỗi runtime/UI và thêm regression tests. Không thay đổi
`project_contract.json`, `WhatIfJobResult`, status canonical hoặc decision policy.

### PR 2 — Citation density

PR 2 chỉ thay đổi cách trình bày citation: mặc định hiện tối đa ba mục, công bố
tổng số và cho phép mở rộng/thu gọn. Full payload và JSON audit vẫn được giữ.

Việc tách PR giúp mỗi thay đổi có acceptance criteria, rollback và review độc lập.

## 3. Thiết kế PR 1

### 3.1 Refinement demo đúng hai vòng

Demo composition sử dụng `RefinementDemoSurrogateForecaster`. Adapter này tiếp tục
delegate mọi trường hợp không phải typed `signal_change` về
`DemoSurrogateForecaster`, nên các preset `safe`, `unsafe-vc`, flood, lane closure
và demand surge không đổi hành vi.

Với typed `signal_change` tại node đã chọn và candidate ratio `0.70`:

1. vòng 1 trả V/C lớn hơn policy `0.90`;
2. safety loop tạo candidate `0.85` trong giới hạn tối đa ba vòng;
3. vòng 2 trả V/C nhỏ hơn policy và job kết thúc `succeeded`;
4. result ghi hai safety checks và action cuối vẫn non-executable.

Production composition không được import hoặc fallback sang demo adapter.

### 3.2 Result và Safety derive từ authoritative state

`createDashboardView.render()` là điểm duy nhất ánh xạ `state.job.status` sang
presentation state. Mỗi lần render phải cập nhật đồng thời:

- `result-title`;
- `job-status` và class status;
- Safety label, icon và class;
- reason, số vòng và danh sách checks.

Ánh xạ tối thiểu:

| Status | Result title | Safety label |
|---|---|---|
| chưa gửi | Chưa có kết quả mô phỏng | Chờ kết quả |
| `queued` | Kịch bản đang chờ xử lý | Đang chờ safety checks |
| `running` | Đang chạy mô phỏng | Đang đánh giá safety |
| `succeeded` | Kết quả mô phỏng đã sẵn sàng | Đã qua safety gate |
| `needs_review` | Kết quả cần operator xem xét | Cần xem xét |
| `failed` | Mô phỏng thất bại | Không có đề xuất khả dụng |
| `expired` | Kết quả đã hết hạn | Cần chạy lại |

Copy không được ngụ ý rằng `succeeded` đã được tự động áp dụng.

### 3.3 SSE terminal race

Khi nhận terminal envelope, coordinator đóng stream và chuyển transport phase về
`online` nếu transport không ở `protocol_error`, biểu thị API vẫn kết nối nhưng
không còn stream đang chạy. Callback transport đến sau đó phải bị bỏ qua nếu
authoritative job state đã terminal.

Không tạo phase API/job mới. `protocol_error` đã quan sát trước terminal vẫn giữ
fail-closed; guard chỉ ngăn callback đóng stream tự tạo badge `reconnecting` giả.

### 3.4 Capacity provenance từ network context

Dashboard view giữ `capacity_version` từ network context đã được cấp cho map/table.
Khi render metrics, thứ tự nguồn là:

1. `scenario_summary.capacity_version` nếu runtime cung cấp;
2. `result.capacity_version` để tương thích payload cũ/test;
3. `network_context.capacity_version` đã xác thực;
4. `—` nếu topology/network context không khả dụng.

Không thêm trường vào `WhatIfJobResult`. Production vẫn fail-closed khi
`/network-context` lỗi và không được dùng synthetic fallback.

## 4. Thiết kế PR 2

`renderCitations()` vẫn tạo node bằng DOM text APIs. Với `N > 3`, UI hiển thị ba
citation đầu, dòng trạng thái `Đang hiển thị 3/N citation` và control
`Xem tất cả (N)`. Khi mở rộng, control đổi thành `Thu gọn`; focus không bị mất và
trạng thái mở rộng được truyền bằng `aria-expanded`.

Với `N <= 3`, không hiển thị control dư thừa. Khi job mới được render, citation
quay về trạng thái thu gọn để không mang UI state từ job trước. JSON audit và
action payload không thay đổi.

## 5. Error handling và safety

- Không thay đổi khả năng approve/reject/request changes.
- `needs_review` tiếp tục disable `approved`.
- `failed` và `expired` không có action khả dụng.
- Thiếu network context tiếp tục hiển thị provenance không khả dụng, không suy diễn.
- Citation malformed tiếp tục bị evidence policy xử lý; control mở rộng không làm
  citation trở nên hợp lệ.
- Không thêm raw video, external tiles, automatic actuation hoặc executable route.

## 6. Kiểm thử

PR 1 dùng TDD với regression tests sau:

1. demo `signal_change` từ `0.70` ghi đúng hai vòng và action cuối `0.85`;
2. non-signal preset giữ behavior hiện hành;
3. từng terminal status cập nhật Result/Safety copy và class;
4. `reconnecting` sau terminal không thay transport khỏi `online`;
5. `capacity_version` dùng trusted network context và để `—` khi context unavailable.

PR 2 dùng TDD với các test:

1. 0–3 citation không có expand control;
2. hơn ba citation mặc định chỉ hiện ba;
3. mở rộng/thu gọn cập nhật DOM và `aria-expanded`;
4. job mới reset trạng thái thu gọn;
5. nội dung citation tiếp tục được render bằng `textContent`.

Mỗi PR phải chạy frontend suite, demo/static tests, contract tests liên quan,
JavaScript syntax checks và `git diff --check`. Browser QA kiểm tra desktop,
mobile 390 px, keyboard focus, console và không tràn ngang.

## 7. Artifact synchronization

PR 1 cập nhật runbook/walkthrough chỉ khi copy hoặc số vòng trong artifact không
khớp hành vi sau sửa. PR 2 cập nhật walkthrough nếu ảnh hoặc hướng dẫn citation
đang mô tả danh sách luôn mở. Không đổi report/slides nếu không có claim bị ảnh hưởng.

## 8. Rollback

Hai PR có thể revert độc lập. Revert PR 2 chỉ khôi phục danh sách citation luôn mở.
Revert PR 1 khôi phục presentation/runtime cũ nhưng không làm thay đổi contract hay
dữ liệu persisted. Không force-push hoặc migration dữ liệu.

## 9. Acceptance criteria

- Preset `refinement` live khớp label/runbook hai vòng.
- Không còn terminal job với tiêu đề `Chưa có kết quả mô phỏng` hoặc Safety
  `Chờ kết quả`.
- Connection badge không chuyển `reconnecting` sau terminal.
- `capacity_version` hiển thị từ đúng network context của dashboard.
- Citation mặc định gọn nhưng vẫn truy cập đầy đủ và dùng được bằng bàn phím.
- Mọi action vẫn non-executable và human approval boundary không đổi.
