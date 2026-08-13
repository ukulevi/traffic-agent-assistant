# Runbook demo offline SmartTraffic What-If

Runbook này dùng để setup và showcase toàn bộ profile demo offline của STWI. Tất
cả node, topology, incident, forecast và route trong profile đều là dữ liệu
synthetic, aggregate-only. Hệ thống chỉ hỗ trợ ra quyết định, không gửi lệnh đến
đèn tín hiệu hoặc thiết bị hiện trường.

## 1. Setup

Yêu cầu Windows, PowerShell và Python 3.11+. Từ thư mục gốc repository:

```powershell
python --version
pip install -e ".[orchestrator]"
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
```

Kết quả smoke bắt buộc:

```json
{"profile":"offline","verdict":"pass","capability_count":17}
```

Không demo nếu `verdict` khác `pass` hoặc số capability khác `17`. Evidence chỉ
ghi loại incident/node, phiên bản topology/model/data/policy, số route, trạng
thái route, lý do safety, có/không citation, trace và quyết định operator. Nó
không ghi mô tả tự do, ảnh/base64, video thô, credential hoặc secret.

Khởi động dashboard trên loopback:

```powershell
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/demo/`. `/` trả 404 là đúng vì dashboard được mount
tại `/demo/`; lỗi favicon 404 không ảnh hưởng demo.

## 2. Kiểm tra trước khi trình bày

- Header có `Demo synthetic` và `Simulation only`.
- Khối input **Tạo kịch bản** nằm trước topology, theo dõi job và kết quả.
- Người trình bày chọn node và loại incident độc lập; preset không khóa incident
  vào một node cố định.
- Sơ đồ Leaflet tile-free hiển thị mạng lưới synthetic 4×5 gồm 20 node, không
  phải bản đồ địa lý thực và không gọi tile server bên ngoài.
- Route table và overlay dùng cùng route ID; recommendation là nét liền, candidate
  cần review là nét đứt và luôn `NON-EXECUTABLE`.
- Evidence file có `schema_version: "1.0"`, `verdict: "pass"` và 17 capability.

## 3. Ma trận 17 capability

| Nhóm | Capability | Kết quả cần đối chiếu |
|---|---|---|
| Baseline | `normal_baseline` | `succeeded`, recommendation không executable, operator có thể approve |
| Human review | `safe_rejection` | `succeeded`, operator reject, `applied_by_system=false` |
| Route pass | `route_recommendation` | `succeeded`, 3 route đã đánh giá và xếp hạng, đủ model/data/topology version |
| Incident | `accident_any_node` | `needs_review` do V/C policy |
| Incident | `flood_any_node` | `needs_review`, tốc độ synthetic thấp |
| Incident | `lane_closure_any_node` | `needs_review`, capacity giả định giảm |
| Incident | `demand_surge_any_node` | `needs_review`, demand giả định tăng |
| Route fail-closed | `route_needs_review` | `needs_review`, không bịa route khi generator không có candidate |
| Safety | `ood` | `needs_review`, không refinement |
| Safety | `high_uncertainty` | `needs_review`, không recommendation |
| Legal evidence | `missing_citation` | `needs_review`, citation không đủ |
| Dependency | `dependency_failure` | `failed`, không action |
| Deadline | `deadline_exceeded` | `expired`, không action |
| Validation | `invalid_scenario` | HTTP 422, không tạo job |
| Authorization | `tenant_scope_denied` | HTTP 403, không tạo job |
| Transport | `sse_reconnect` | resume sau event 1, chỉ một terminal event |
| Static mode | `static_preview` | không tạo job hoặc ghi quyết định |

Năm loại incident canonical là `accident`, `flood`, `lane_closure`,
`demand_surge` và `signal_change`. Harness chọn năm node khác nhau để chứng minh
incident không gắn cứng với node; trong dashboard người demo có thể chọn bất kỳ
node hợp lệ `node_00`–`node_19` trước khi chọn incident.

## 4. Kịch bản showcase trực tiếp

### 4.1. Baseline bình thường

1. Chọn một node bất kỳ và preset `safe`.
2. Xác nhận **Không có sự cố**, `green_time_ratio=0.70`, rồi chạy mô phỏng.
3. Theo dõi `queued → running → succeeded` và đọc kết quả 30 phút ở dưới input.
4. Kiểm tra đơn vị, citation provisional, model/data version, job/trace ID.
5. Mở operator review, ghi approve hoặc reject; xác nhận
   `automatic_actuation=false` và `applied_by_system=false`.

### 4.2. Incident và route recommendation

1. Chọn một node khác node vừa dùng, sau đó chọn preset `refinement` hoặc incident
   `signal_change`. Incident áp dụng tại node đang chọn, không phải node cố định.
2. Chạy mô phỏng. Với profile `refinement`, vòng đầu đánh giá ratio `0.70`, vòng
   sau đánh giá ratio `0.85` và kết thúc `succeeded`.
3. Trong **Hành lang điều hướng**, đối chiếu tối đa ba route ở bảng và bản đồ:
   rank, node sequence, V/C, tốc độ, delay proxy, uncertainty, OOD và ba version.
4. Xác nhận route tránh node incident, có nhãn recommendation, nét liền và
   `requires_operator_approval=true`.

`route_needs_review` là probe tích hợp chạy trong smoke harness: generator demo
cố ý trả không có candidate để chứng minh fail-closed. Entrypoint dashboard mặc
định không có nút làm hỏng generator; không được dựng route giả trên màn hình để
minh họa nhánh này. Hãy mở evidence và đối chiếu `route_count: 0`,
`route_status: "needs_review"` cùng `safety_reason` bắt đầu bằng
`no_passing_route`.

### 4.3. Năm incident độc lập với node

Với mỗi lần chạy, tự chọn một node hợp lệ trước rồi chọn một loại incident. Không
dùng bảng ánh xạ event→node. Các giá trị là deterministic synthetic, không phải
đo đạc hiện trường:

| Incident | Điều cần quan sát |
|---|---|
| `accident` | V/C vượt policy và `needs_review` |
| `flood` | tốc độ synthetic giảm; không suy diễn mực nước |
| `lane_closure` | dùng `lane_closure_ratio`; không suy diễn số làn thực |
| `demand_surge` | dùng `demand_multiplier`; không phải dự báo production |
| `signal_change` | dùng typed `green_time_ratio_delta`; có thể tạo route evidence nếu các gate pass |

V/C 0,9 là policy cấu hình MVP, không phải quy định pháp luật. Mô tả tự do chỉ
phục vụ ngữ cảnh/citation và không chọn hành vi mô phỏng.

### 4.4. Fail-closed trên dashboard

- `unsafe-vc`: `needs_review`, chỉ `candidate_action`, không thể approve.
- `ood`: `needs_review` với lý do OOD, không refinement.
- `uncertainty`: `needs_review`, không recommendation.
- `missing-evidence`: `needs_review`, không coi citation demo là xác nhận pháp lý
  production.
- `extreme`: tỷ lệ xanh cực trị bị safety gate giữ lại.

### 4.5. Boundary và transport trong evidence

Mở `C:\tmp\stwi-offline-evidence.json` và đối chiếu:

- `dependency_failure`: observed `failed`, không action.
- `deadline_exceeded`: observed `expired`, không action.
- `invalid_scenario`: expected/observed `422`, không tạo job.
- `tenant_scope_denied`: expected/observed `403`, không tạo job.
- `sse_reconnect`: `terminal_event_count: 1` sau resume.
- `static_preview`: `non_mutating_static_preview`, `network_contacted: false`.

`status: "pass"` của capability nghĩa là hệ thống tạo đúng nhánh mong đợi, kể cả
khi job kết thúc ở `failed`, `expired` hoặc `needs_review`.

## 5. Trình tự showcase 8–10 phút

1. Giới thiệu phạm vi synthetic, aggregate-only và decision-support.
2. Chỉ khối input nằm trên; chọn node và incident độc lập.
3. Chạy baseline `safe`, đọc lifecycle, output, citation và trace.
4. Ghi một quyết định audit-only.
5. Chạy `signal_change/refinement`, đọc route trên bảng và bản đồ.
6. Chạy một incident fail-closed tại node khác.
7. Mở evidence để chỉ route `needs_review`, dependency, expiry, validation,
   authorization và SSE reconnect.
8. Kết luận: mọi action/route đều không executable và cần con người quyết định.

## 6. Xử lý lỗi và kết thúc

| Hiện tượng | Xử lý |
|---|---|
| `/` trả 404 | Mở đúng `/demo/`. |
| `Connection refused` | Kiểm tra Uvicorn và cổng 8000. |
| Dashboard hiện `Static preview` | Mở qua HTTP thay vì mở `index.html` trực tiếp. |
| Job `needs_review` | Đọc safety reason; không đổi thành `succeeded`. |
| Route trống | Đọc `route_status`/reason; không thêm route minh họa thủ công. |
| Smoke không đủ 17 capability | Dừng demo và đọc capability `status: "fail"`. |

Kết thúc bằng `Ctrl+C`. Chỉ giữ evidence nếu cần audit; không phát hành file có
credential, endpoint riêng, mô tả nhạy cảm, ảnh hoặc video thô.
