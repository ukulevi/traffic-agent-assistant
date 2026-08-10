# Runbook demo offline SmartTraffic What-If

Tài liệu này dùng để setup và trình bày toàn bộ 13 kịch bản demo offline của
STWI. Demo sử dụng dữ liệu synthetic, chỉ hỗ trợ ra quyết định và không tự động
điều khiển thiết bị.

## 1. Chuẩn bị môi trường

### 1.1. Yêu cầu

- Windows và PowerShell.
- Python 3.11 trở lên.
- Chạy lệnh từ thư mục gốc của repository.
- Trình duyệt truy cập được địa chỉ loopback `127.0.0.1`.

Kiểm tra Python:

```powershell
python --version
```

Cài project và dependency cho API/dashboard:

```powershell
pip install -e ".[orchestrator]"
```

### 1.2. Chạy kiểm tra offline

```powershell
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
```

Kết quả mong đợi:

```json
{"profile":"offline","verdict":"pass","capability_count":13}
```

Không bắt đầu demo nếu `verdict` khác `pass` hoặc `capability_count` khác `13`.

### 1.3. Khởi động dashboard

```powershell
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

Giữ cửa sổ PowerShell này đang chạy và mở:

```text
http://127.0.0.1:8000/demo/
```

Đường dẫn `/` trả HTTP 404 vì dashboard được mount tại `/demo/`. Lỗi
`/favicon.ico` 404 không ảnh hưởng đến demo.

## 2. Kiểm tra trước khi demo

Xác nhận các mục sau:

- Header hiển thị `Demo synthetic` và `Simulation only`.
- Form tạo kịch bản có các preset `safe`, `refinement`, `unsafe-vc`, `ood`,
  `uncertainty` và `missing-evidence`.
- Nút **Chạy mô phỏng** hoạt động.
- File `C:\tmp\stwi-offline-evidence.json` tồn tại.
- File evidence có `schema_version: "1.0"`, `verdict: "pass"` và đủ 13 phần tử
  trong `capabilities`.
- Không mở trực tiếp file `index.html` khi trình bày các luồng tạo job.

## 3. Ma trận 13 kịch bản

| # | Capability | Cách chạy | Kết quả mong đợi |
|---:|---|---|---|
| 1 | `safe_approval` | Dashboard: preset `safe`, chạy job và chọn approve | `succeeded`, có `recommended_action`, quyết định `approved` |
| 2 | `safe_rejection` | Dashboard: tạo job `safe` mới và chọn reject | `succeeded`, quyết định `rejected` |
| 3 | `refinement_success` | Dashboard: preset `refinement` | `succeeded` sau hai candidate khác nhau |
| 4 | `unsafe_vc` | Dashboard: preset `unsafe-vc` | `needs_review`, chỉ có `candidate_action` |
| 5 | `ood` | Dashboard: preset `ood` | `needs_review`, không refinement |
| 6 | `high_uncertainty` | Dashboard: preset `uncertainty` | `needs_review`, không refinement |
| 7 | `missing_citation` | Dashboard: preset `missing-evidence` | `needs_review`, không có recommendation |
| 8 | `dependency_failure` | File evidence offline | `failed`, không có action |
| 9 | `deadline_exceeded` | File evidence offline | `expired`, không có action |
| 10 | `invalid_scenario` | File evidence offline | HTTP `422`, không tạo job |
| 11 | `tenant_scope_denied` | File evidence offline | HTTP `403`, không tạo job |
| 12 | `sse_reconnect` | File evidence offline | Resume từ event trước, không lặp terminal event |
| 13 | `static_preview` | Mở trực tiếp file HTML tĩnh | Preview không cho tạo job |

## 4. Hướng dẫn chạy từng kịch bản

### 4.1. `safe_approval`

1. Chọn preset `safe`.
2. Xác nhận node là `node_00` và `green_time_ratio` là `0.70`.
3. Bấm **Chạy mô phỏng**.
4. Chờ lifecycle chuyển `queued` → `running` → `succeeded`.
5. Kiểm tra kết quả có đơn vị, citation, model/data version, `job_id` và
   `trace_id`.
6. Kiểm tra `recommended_action` có nhãn `NON-EXECUTABLE`.
7. Bấm **Ghi nhận quyết định**, chọn approve, nhập lý do và xác nhận.
8. Kiểm tra quyết định là `approved` và `applied_by_system=false`.

### 4.2. `safe_rejection`

1. Chọn lại preset `safe` và tạo một job mới.
2. Chờ job kết thúc ở `succeeded`.
3. Bấm **Ghi nhận quyết định**, chọn reject và nhập lý do.
4. Kiểm tra quyết định là `rejected` và `applied_by_system=false`.

Phải tạo job mới vì quyết định của một job đã ghi thì không được thay đổi.

### 4.3. `refinement_success`

1. Chọn preset `refinement`.
2. Xác nhận node là `node_10` và ratio ban đầu là `0.70`.
3. Chạy mô phỏng và mở phần Counterfactual Safety Loop.
4. Kiểm tra vòng 1 đánh giá ratio `0.70` và không đạt gate V/C.
5. Kiểm tra vòng 2 đánh giá candidate mới với ratio `0.85` và đạt gate.
6. Xác nhận trạng thái cuối là `succeeded`; action vẫn `NON-EXECUTABLE`.

### 4.4. `unsafe_vc`

1. Chọn preset `unsafe-vc`; node phải là `node_01`.
2. Chạy mô phỏng.
3. Kiểm tra trạng thái cuối là `needs_review` do V/C vượt policy `0.90`.
4. Kiểm tra chỉ có `candidate_action`, không có `recommended_action` và không
   thể approve.

### 4.5. `ood`

1. Chọn preset `ood`; node phải là `node_02`.
2. Chạy mô phỏng.
3. Kiểm tra trạng thái cuối là `needs_review` với lý do
   `out_of_distribution`.
4. Kiểm tra safety loop dừng ngay, không thử candidate khác và không có
   `recommended_action`.

### 4.6. `high_uncertainty`

1. Chọn preset `uncertainty`; node phải là `node_03`.
2. Chạy mô phỏng.
3. Kiểm tra trạng thái cuối là `needs_review` do uncertainty cao.
4. Kiểm tra không refinement, không recommendation và không thể approve.

### 4.7. `missing_citation`

1. Chọn preset `missing-evidence`; node phải là `node_04`.
2. Chạy mô phỏng.
3. Kiểm tra trạng thái cuối là `needs_review` do thiếu citation hợp lệ.
4. Kiểm tra không refinement và không có `recommended_action`.

### 4.8. Xem năm kịch bản boundary trong evidence

Không cố ý làm hỏng dashboard để tạo lỗi dependency, timeout, validation,
authorization hoặc SSE. Mở file:

```powershell
notepad C:\tmp\stwi-offline-evidence.json
```

Tìm lần lượt từng giá trị `name` và đối chiếu:

| Capability | Trường cần kiểm tra |
|---|---|
| `dependency_failure` | `status: "pass"`, `observed: "failed"`, `terminal_status: "failed"`, không có action |
| `deadline_exceeded` | `status: "pass"`, `observed: "expired"`, `terminal_status: "expired"`, không có action |
| `invalid_scenario` | `status: "pass"`, `expected: "422"`, `observed: "422"`, `terminal_event_count: 0` |
| `tenant_scope_denied` | `status: "pass"`, `expected: "403"`, `observed: "403"`, `terminal_event_count: 0` |
| `sse_reconnect` | `status: "pass"`, `observed: "terminal_event_resumed"`, `terminal_event_count: 1` |

`status: "pass"` trong manifest nghĩa là kịch bản tạo đúng kết quả mong đợi;
ví dụ `dependency_failure` pass khi job kết thúc đúng ở `failed` và không làm lộ
action.

### 4.9. `static_preview`

1. Mở file sau trực tiếp bằng trình duyệt trong một tab riêng:

   ```text
   src/stwi/t4_orchestrator/static/index.html
   ```

2. Kiểm tra giao diện hiển thị `Static preview`.
3. Kiểm tra không thể tạo job hoặc gửi quyết định.
4. Đóng tab preview và quay lại `http://127.0.0.1:8000/demo/`.

Trong evidence, capability này phải có:

```json
{
  "name": "static_preview",
  "status": "pass",
  "observed": "non_mutating_static_preview"
}
```

## 5. Trình tự demo đề xuất

Chạy theo thứ tự sau để câu chuyện trình bày liền mạch:

1. Giới thiệu dashboard `Demo synthetic` và nguyên tắc không tự động điều khiển.
2. Chạy `safe_approval` để trình bày lifecycle, kết quả, citation và quyết định.
3. Chạy `safe_rejection` để chứng minh operator có thể bác bỏ recommendation.
4. Chạy `refinement_success` để trình bày hai candidate khác nhau.
5. Chạy `unsafe_vc`, `ood`, `high_uncertainty` và `missing_citation` để trình
   bày các nhánh `needs_review`.
6. Mở evidence và trình bày `dependency_failure`, `deadline_exceeded`,
   `invalid_scenario`, `tenant_scope_denied` và `sse_reconnect`.
7. Mở `static_preview`, xác nhận form không mutating rồi quay lại dashboard.
8. Kết luận rằng đủ 13 kịch bản đã được trình bày và mọi action đều cần quyết
   định của con người.

## 6. Xử lý lỗi khi demo

| Hiện tượng | Cách xử lý |
|---|---|
| Mở `/` thấy `404 Not Found` | Dùng đúng `http://127.0.0.1:8000/demo/`. |
| `/favicon.ico` trả 404 | Bỏ qua; lỗi này không ảnh hưởng dashboard. |
| `Connection refused` | Kiểm tra cửa sổ Uvicorn còn chạy và đang dùng cổng `8000`. |
| Thiếu `fastapi` hoặc `uvicorn` | Chạy lại `pip install -e ".[orchestrator]"`. |
| Dashboard hiển thị `Static preview` | Đóng file HTML trực tiếp và mở lại URL `/demo/`. |
| Job kết thúc `needs_review` | Đối chiếu preset; đây là kết quả đúng của các kịch bản fail-closed. |
| Smoke test không pass đủ 13 capability | Không tiếp tục demo; đọc capability có `status: "fail"` trong evidence. |

## 7. Kết thúc

1. Đóng tab `static_preview` nếu còn mở.
2. Giữ lại `C:\tmp\stwi-offline-evidence.json` nếu cần đối chiếu sau demo.
3. Nhấn `Ctrl+C` tại cửa sổ Uvicorn để dừng server.
