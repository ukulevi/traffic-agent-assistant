# STWI Demo Safety Coverage Design

## Mục tiêu

Biến `/demo/` thành một demo mô phỏng có thể tái lập nhiều nhánh kết quả mà
không tạo cảm giác dữ liệu mock là dự báo thực địa. Mọi input phải được kiểm tra
tại API boundary, mọi nhánh không đủ an toàn phải fail-closed, và chỉ job
`succeeded` mới được ghi quyết định `approved`.

## Thiết kế được chọn

1. `CandidateAction` trở thành schema có kiểu với `node_id` và
   `green_time_ratio`; request kiểm tra action node thuộc `node_ids` và loại bỏ
   chuỗi chỉ chứa khoảng trắng.
2. Trong `STWI_RUNTIME_MODE=demo`, API chỉ nhận node có trong
   `generate_mock_network().node_ids` (`node_00` đến `node_19`). Production và
   test adapters không bị ràng buộc bởi registry demo.
3. Một `DemoSurrogateForecaster` riêng tạo kết quả synthetic có quan hệ xác
   định với green-time ratio. Các node `node_01`, `node_02`, `node_03` lần lượt
   minh họa V/C cao, OOD và uncertainty cao; ratio cực trị tự fail-closed.
4. UI có preset rõ ràng cho happy path, V/C, OOD, uncertainty, thiếu evidence
   và giá trị cực trị. Preset chỉ điền các trường API hiện hữu, không thêm
   trường test-only vào API contract.
5. API từ chối `approved` đối với `needs_review`, `failed` và `expired`.
   `rejected` vẫn được ghi audit cho mọi terminal state.
6. UI gọi kết quả mock là “đạt kiểm tra trong profile mô phỏng”, luôn hiển thị
   model/data version và giữ action `executable=false`.

## Luồng dữ liệu

`preset UI -> typed WhatIfJobRequest -> demo node allowlist -> demo adapters ->
OOD/uncertainty/RAG/safety loop -> terminal result -> operator audit decision`.

Validation lỗi trả HTTP 422 trước khi tạo job. Runtime exception và deadline
vẫn theo hành vi `failed`/`expired` hiện hành.

## Phạm vi ngoài thiết kế

- Không kết nối RTSP, cảm biến hoặc thiết bị hiện trường.
- Không tuyên bố accuracy, calibration hay SLA production.
- Không đổi tensor, feature order, status API, stack hoặc policy V/C mặc định.
- Không thêm automatic actuation hay action executable.

## Tiêu chí chấp nhận

- `node-unknown` bị từ chối trong demo mode và không sinh job.
- Action node khác `node_ids` bị HTTP 422 ở mọi runtime.
- Ratio 0%/100% kết thúc `needs_review`, không có `recommended_action`.
- Preset safe có kết quả khác khi thay đổi green-time ratio trong miền hợp lệ.
- Có thể tái lập `succeeded`, V/C review, OOD, uncertainty và thiếu citation.
- API không chấp nhận `approved` cho bất kỳ status nào ngoài `succeeded`.
- UI không có console error và không render dữ liệu không tin cậy bằng
  `innerHTML`.
