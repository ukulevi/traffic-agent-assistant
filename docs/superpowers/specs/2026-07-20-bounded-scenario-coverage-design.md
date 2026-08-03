# Bounded Scenario Coverage Design

## 1. Mục tiêu

Mở rộng demo và automated tests để bao quát các tình huống giao thông, sự cố và
tín hiệu môi trường đã có trong contract hiện hành, nhưng không thêm service,
model, API field, tensor feature hoặc dependency mới.

Phạm vi này phục vụ demo synthetic và kiểm tra hành vi fail-closed. Nó không
chứng minh quan hệ nhân quả ngoài thực địa và không nâng hệ thống thành công cụ
dự báo khí tượng, thủy văn hoặc chất lượng không khí.

## 2. Ràng buộc bất biến

- Giữ `X[B,12,N,16]`, `M[B,12,N,16]`, `A[N,N]` và `Y[B,6,N,2]`.
- Giữ nguyên thứ tự 16 feature trong `project_contract.json`.
- Giữ nguyên `WhatIfJobRequest`, API job bất đồng bộ và status canonical.
- Không thêm `IncidentVector` vào request trong thay đổi này.
- Không thêm rainfall, water depth, visibility hoặc feature ngoài contract.
- Không lưu dữ liệu hình ảnh thô và không tạo automatic actuation.
- Chỉ `succeeded` có `recommended_action`; mọi profile không đủ an toàn phải
  trả `needs_review` với `candidate_action.executable=false`.

## 3. Phương án kiến trúc

Tiếp tục pattern demo hiện tại: một số node synthetic được dành làm profile tái
lập. UI chọn preset, gửi payload API hiện hành, còn
`DemoSurrogateForecaster` sinh aggregate forecast tương ứng với node. Logic chỉ
được auto-wire khi `STWI_RUNTIME_MODE=demo`; runtime khác không bị ảnh hưởng.

Không phân loại tình huống từ từ khóa trong `scenario_query`. Nội dung query chỉ
dùng để giải thích ngữ cảnh và truy xuất legal/SOP evidence như hiện tại. Điều
này tránh biến free text thành input mô phỏng không có type hoặc không thể kiểm
soát.

## 4. Catalog profile

Các node `node_00` đến `node_04` giữ nguyên ý nghĩa hiện tại. Năm node tiếp theo
được dùng cho coverage mới:

| Preset | Node | Abstraction hiện có | Kết quả dự kiến |
|---|---|---|---|
| Tai nạn | `node_05` | Giảm tốc, giảm năng lực hiệu dụng | `needs_review` do V/C |
| Ngập lụt | `node_06` | Đóng làn mạnh và tốc độ rất thấp | `needs_review` do V/C |
| Đóng làn | `node_07` | `lane_closure_ratio` tương đương 0.5 | `needs_review` do V/C |
| Nhu cầu tăng | `node_08` | `demand_multiplier` tăng | `needs_review` do V/C |
| Tín hiệu môi trường bất thường | `node_09` | Context từ feature khí thải/khí tượng hiện có | `needs_review` do OOD/uncertainty |

Preset môi trường phải ghi rõ đây là tín hiệu tương quan synthetic. UI không
được nói CO, CO2, NOx, PM2.5 hoặc PM10 gây ra ùn tắc. Các chỉ số môi trường
không được đưa vào output forecast vì output contract chỉ gồm
`traffic_volume_5m` và `avg_speed_kmh`.

`signal_change` tiếp tục được bao quát bởi preset green-time bình thường và
green-time cực trị, nên không cần thêm node riêng.

## 5. Data flow và UI

1. Người dùng chọn một preset có mô tả tiếng Việt và kỳ vọng terminal state.
2. UI đặt `node_id`, `green_time_ratio`, `scenario_query` và `jurisdiction`.
3. API validate payload bằng schema hiện hành và tạo job HTTP 202.
4. Demo surrogate trả volume, speed, V/C, OOD và uncertainty synthetic.
5. Safety gate quyết định terminal state; UI không tự suy ra hoặc ghi đè status.
6. UI hiển thị diễn giải thông thường, provenance, action không thực thi và lý
   do `needs_review`.

Danh sách preset được nhóm thành "Safety cơ bản" và "Tình huống vận hành" để
không làm form dài thêm đáng kể. Không thêm màn hình hoặc navigation mới.

## 6. Automated coverage

### 6.1 Demo profile tests

- Mỗi node `node_05` đến `node_09` tạo đúng terminal status và reason family.
- Accident, flood, lane closure và demand surge có V/C vượt policy 0.9.
- Flood có tốc độ thấp nhất trong nhóm incident.
- Environmental anomaly bị OOD/uncertainty gate giữ lại.
- Không profile mới nào trả executable action hoặc automatic actuation.
- Các profile cũ `node_00` đến `node_04` không đổi hành vi.

### 6.2 Data-contract tests

- Feature registry vẫn chứa đúng CO, CO2, NOx, PM2.5, PM10, temperature,
  humidity và wind speed tại đúng index.
- Giá trị synthetic môi trường cao nhưng hữu hạn vẫn đi qua quality pipeline
  theo contract; missing value phải được đánh dấu trong `M`.
- Một sample có lưu lượng thấp và PM cao phải giữ hai giá trị độc lập; test
  không được mã hóa giả định "PM cao đồng nghĩa ùn tắc".
- Missing nhiều sensor môi trường không được làm thay đổi node order hoặc tensor
  shape.

### 6.3 UI/static tests

- Năm preset mới tồn tại, ánh xạ đúng node và có copy không-causal.
- Mọi preset incident/environment đều mô tả dữ liệu synthetic.
- Approval vẫn bị khóa cho `needs_review`.
- UI không dùng `innerHTML` để render dữ liệu không tin cậy.

## 7. Xử lý lỗi và safety

- Node ngoài allowlist vẫn bị HTTP 422.
- Extreme input, OOD, uncertainty, thiếu citation hoặc V/C vượt policy tiếp tục
  fail closed.
- Nếu dữ liệu môi trường bị thiếu, hệ thống biểu diễn bằng missing mask; không
  tự điền một giá trị có nghĩa nhân quả.
- Nếu tín hiệu giao thông và môi trường mâu thuẫn, demo chỉ trình bày như bằng
  chứng cần review, không tạo recommendation.

## 8. Tài liệu cần đồng bộ

- `docs/guides/mvp_demo_runbook.md`: thêm catalog preset và lời thoại demo.
- `docs/guides/mvp_operator_dashboard.md`: mô tả nhóm preset vận hành.
- `docs/02_ML_and_Simulation_Specification.md`: không đổi contract; chỉ cần sửa
  nếu phát hiện mô tả dẫn xuất hiện tại mâu thuẫn với implementation.
- Smoke evidence được mở rộng bằng một incident representative và một
  environmental-anomaly representative, thay vì chạy toàn bộ preset trong
  smoke nhanh.

## 9. Non-goals

- Không mô phỏng bão, lượng mưa hoặc mực nước vật lý.
- Không xây compound incident engine.
- Không dự báo chất lượng không khí hoặc cảnh báo sức khỏe.
- Không khẳng định nguyên nhân giữa ô nhiễm và ùn tắc.
- Không huấn luyện lại GCN-LSTM hoặc surrogate production.
- Không thay đổi project contract hoặc kiến trúc triển khai.

## 10. Acceptance criteria

- UI có năm preset vận hành mới và vẫn gọn trên desktop/mobile.
- Tất cả profile mới tái lập được và kết thúc fail-closed theo catalog.
- Tests chứng minh feature môi trường giữ đúng vị trí, missing mask và tính độc
  lập với traffic volume.
- Không có API/schema/tensor/dependency mới.
- Smoke, contract, safety, static UI và release verifier đều pass.
- Demo copy phân biệt rõ dữ liệu synthetic, tương quan và quan hệ nhân quả.
