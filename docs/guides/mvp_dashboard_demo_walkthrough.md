# Hướng dẫn sử dụng và demo STWI Operator Dashboard

Tài liệu này hướng dẫn sử dụng dashboard bằng các test case synthetic, deterministic. STWI chỉ hỗ trợ ra quyết định: hệ thống không gửi lệnh đến đèn tín hiệu hoặc thiết bị hiện trường, không lưu video thô và mọi action trong demo đều không thể thực thi tự động.

## 1. Phạm vi và điều kiện chuẩn bị

Bạn cần Python 3.11+ và PowerShell. Từ thư mục gốc repository, cài runtime và kiểm tra phạm vi demo:

```powershell
pip install -e ".[orchestrator]"
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-mvp-demo-evidence.json
```

Khởi động dashboard chỉ trên loopback:

```powershell
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/demo/`. Không dùng file `index.html` trực tiếp vì chế độ `static_preview` không thể tạo job. Citation trong demo là bằng chứng provisional phục vụ kiểm thử, không phải xác nhận pháp lý production.

## 2. Nhận biết giao diện

![Tổng quan STWI Operator Dashboard](../assets/demo_walkthrough/01-dashboard-overview.png)

Kiểm tra các vùng chính trước khi chạy, theo thứ tự DOM và visual:

- Thanh đầu trang hiển thị `Demo synthetic`, trạng thái kết nối và danh tính operator/tenant.
- Node registry thanh bên với nút cho `node_00` → `node_19`; mỗi nút dùng `aria-pressed` để báo trạng thái chọn.
- **Input** — Khối **Tạo kịch bản What-If** chứa preset, node và `green_time_ratio`.
- **Job lifecycle** — Khối **Theo dõi job** hiển thị `queued`/`running`/terminal status, sự kiện và `trace_id`.
- **Result** — Khối **Kết quả 30 phút** hiển thị các số liệu có đơn vị trước khi chuyển sang evidence.
- **Route evidence** — Bảng và sơ đồ Leaflet tile-free dùng chung route ID, chỉ
  hiển thị route đã được validate cho đúng terminal status.
- **Safety/evidence** — Evidence rail hiển thị safety gate, uncertainty/OOD, citation, model/data version, `job_id` và `trace_id`.
- **Operator review** — Decision gate chỉ ghi audit. Bản ghi luôn phải cho thấy `applied_by_system=false`.

## 3. Test case cơ sở: `safe` → `succeeded`

### Bước 1 — Chọn dữ liệu đầu vào

**Mục tiêu:** tạo một job synthetic vượt qua các gate demo.

**Dữ liệu chọn:** preset `safe`, node `node_00`, `green_time_ratio=0.70`, jurisdiction `VN`.

![Biểu mẫu preset safe](../assets/demo_walkthrough/02-safe-preset-input.png)

**Thao tác:** chọn preset `safe`, xác nhận các giá trị tự điền, rồi bấm **Chạy mô phỏng**.

**Kết quả mong đợi:** job lần lượt chuyển `queued`/`running` và kết thúc ở `succeeded`.

**Điểm kiểm tra:** nhãn **Simulation only** phải hiển thị; thao tác không làm thay đổi đèn thật.

### Bước 2 — Đọc kết quả

![Kết quả succeeded và số liệu 30 phút](../assets/demo_walkthrough/03-succeeded-result.png)

**Kết quả mong đợi:** màn hình hiển thị `traffic_volume_5m`, `avg_speed_kmh`, V/C, timestamp, job/trace ID và ngữ cảnh dự báo 30 phút.

**Điểm kiểm tra:** đơn vị phải đi cùng số liệu. V/C `0.9` là policy cấu hình của MVP, không phải ngưỡng do pháp luật quy định.

### Bước 3 — Kiểm tra bằng chứng và action

![Evidence rail của kết quả succeeded](../assets/demo_walkthrough/04-succeeded-evidence.png)

**Thao tác:** cuộn tới safety/evidence rail và mở phần citation/action nếu đang thu gọn.

**Kết quả mong đợi:** evidence ở trạng thái demo provisional; model/data version và citation có cấu trúc được hiển thị. Chỉ job `succeeded` mới có `recommended_action`.

**Điểm kiểm tra:** action phải mang nhãn `NON-EXECUTABLE`/`executable: false`; operator vẫn phải quyết định.

### Bước 4 — Ghi quyết định audit-only

![Hộp thoại ghi quyết định operator](../assets/demo_walkthrough/05-decision-dialog.png)

**Thao tác:** bấm **Ghi nhận quyết định**, chọn một lựa chọn được policy cho phép, nhập lý do đã xem evidence rồi gửi.

![Bản ghi quyết định không được hệ thống áp dụng](../assets/demo_walkthrough/06-decision-recorded.png)

**Kết quả mong đợi:** dashboard tải lại bản ghi quyết định từ job và hiển thị decision, operator, lý do cùng `applied_by_system=false`.

**Điểm kiểm tra:** đây là audit trail bất biến, không phải nút điều khiển hiện trường.

## 4. Test case `refinement` — hai candidate và route evidence

Chọn một node hợp lệ bất kỳ, sau đó chọn preset `refinement`, giữ
`green_time_ratio=0.70` và chạy. Preset chỉ chọn `signal_change`; incident luôn
áp dụng tại node đang được operator chọn.
Counterfactual Safety Loop phải hiển thị hai vòng: vòng đầu V/C vượt policy
`0.90`; vòng sau đánh giá candidate mới với ratio `0.85` và pass. Kết quả cuối
là `succeeded`, nhưng action vẫn `NON-EXECUTABLE` và cần operator phê duyệt.

Trong **Hành lang điều hướng**, đối chiếu route ID trên bảng và bản đồ. Mỗi route
phải có rank, node sequence, max V/C, tốc độ, delay proxy, uncertainty, OOD và
model/data/topology version. Nét liền biểu thị recommendation đã qua gate; route
vẫn có `requires_operator_approval=true` và `applied_by_system=false`.

Refinement chỉ áp dụng cho failure V/C cô lập. OOD, uncertainty cao, thiếu
citation, invalid input hoặc dependency failure phải dừng ngay thay vì thử đổi
action.

## 5. Test case fail-closed

Chạy lần lượt từng preset. Sau mỗi lần, chờ trạng thái terminal rồi đối chiếu bảng sau:

| Preset | Node | Trạng thái mong đợi | Quan sát bắt buộc |
|---|---|---|---|
| `unsafe-vc` | `node_01` | `needs_review` | V/C vượt policy `0.9`; không được approve. |
| `ood` | `node_02` | `needs_review` | OOD fail-closed; chỉ có `candidate_action`. |
| `uncertainty` | `node_03` | `needs_review` | Uncertainty cao; cần operator review. |
| `missing-evidence` | `node_04` | `needs_review` | Thiếu citation hợp lệ; không có recommendation. |
| `extreme` | `node_00` | `needs_review` | `green_time_ratio=0.00` bị safety gate giữ lại. |

### V/C không an toàn

![Preset unsafe-vc bị giữ lại để review](../assets/demo_walkthrough/07-unsafe-vc-review.png)

Chọn `unsafe-vc` và chạy. Kết quả phải nêu V/C `0.96` vượt policy `0.90`, chuyển `needs_review` và chỉ hiển thị `candidate_action · NON-EXECUTABLE`.

### Ngoài phân phối (OOD)

![Preset OOD bị giữ lại để review](../assets/demo_walkthrough/08-ood-review.png)

Chọn `ood` và chạy. Lý do review phải nhận diện `out_of_distribution`; không được xuất `recommended_action` hay đường phê duyệt.

### Độ bất định cao

![Preset uncertainty bị giữ lại để review](../assets/demo_walkthrough/09-uncertainty-review.png)

Chọn `uncertainty` và chạy. Dashboard phải giải thích uncertainty cao, giữ trạng thái `needs_review` và yêu cầu con người đánh giá.

### Thiếu bằng chứng hợp lệ

![Preset thiếu evidence bị giữ lại để review](../assets/demo_walkthrough/10-missing-evidence-review.png)

Chọn `missing-evidence` và chạy. Jurisdiction synthetic không có căn cứ trong corpus được phép phải fail closed; không được coi citation demo là xác nhận pháp lý production.

Với `extreme`, chọn preset và xác nhận tỷ lệ xanh bằng `0.00`. UI phải giữ job ở `needs_review`. Test case này dùng chung mẫu kiểm tra safety với bốn trường hợp trên nên không cần ảnh riêng.

## 6. Nhóm tình huống giao thông synthetic

![Biểu mẫu nhóm preset tình huống giao thông](../assets/demo_walkthrough/11-incident-presets.png)

Các preset dưới đây kiểm tra khả năng trình bày nghiệp vụ, không chứng minh quan
hệ nhân quả hoặc độ chính xác ngoài thực địa. Trước mỗi lần chạy, operator chọn
một node bất kỳ trong registry; preset không thay đổi node và không tồn tại ánh
xạ cố định giữa loại incident với node.

| Preset | Kết quả demo mong đợi |
|---|---|
| `accident` | `needs_review`, V/C synthetic vượt policy |
| `flood` | `needs_review`, tốc độ synthetic thấp; không mô phỏng mực nước |
| `lane-closure` | `needs_review`, capacity giả định giảm theo tỷ lệ đóng làn |
| `demand-surge` | `needs_review`, lưu lượng synthetic tăng |
| `signal-change` | typed incident được đánh giá tại node đang chọn; route chỉ xuất hiện khi đủ evidence |

Thao tác cho mỗi hàng: chọn node, chọn preset, bấm **Chạy mô phỏng**, chờ terminal
status và đối chiếu action đúng semantics. Không đọc các giá trị deterministic
như số đo thực địa.

Không diễn giải các preset này như dữ liệu tai nạn thật, phép đo mực nước hoặc
khả năng điều khiển hiện trường.

Nhánh `route_needs_review` được kiểm tra bởi smoke harness với generator demo cố
ý không trả candidate. Dashboard mặc định không có control phá dependency này;
không dựng route giả. Hãy dùng evidence để chỉ `route_count=0`,
`route_status=needs_review` và lý do `no_passing_route`.

## 7. Bàn phím, thứ tự focus và sao chép trace ID

- Dùng skip link **Bỏ qua đến cấu hình** hoặc **Bỏ qua đến kết quả** để nhảy trực tiếp đến input/result.
- Nhấn `/` khi không ở trong ô nhập để đưa focus tới ô tìm node.
- Nhấn `C` khi không ở trong ô nhập để sao chép trace ID của job hiện tại.
- Dùng `Tab` theo thứ tự vùng: node rail → input → lifecycle → result → evidence → decision.
- Dùng `Enter` để kích hoạt nút/control native đang focus; node rail dùng button + `aria-pressed`, không dùng listbox.
- Dùng `Esc` để đóng decision dialog; focus phải quay lại control đã mở dialog.

![Phản hồi sau thao tác sao chép trace ID](../assets/demo_walkthrough/12-clipboard-fallback.png)

Ảnh trên minh họa trường hợp browser cho phép clipboard và UI báo **Đã sao chép trace ID**. Nếu browser từ chối quyền, dashboard phải hiển thị hướng dẫn chọn trace ID và sao chép thủ công; lỗi quyền clipboard không được làm hỏng job hay tạo console error chưa xử lý.

## 8. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Hiển thị `Static preview` hoặc không tạo được job | Dừng việc mở file HTML trực tiếp; dùng URL `http://127.0.0.1:8000/demo/`. |
| `Connection refused` | Kiểm tra cửa sổ Uvicorn còn chạy và đúng cổng `8000`; không đổi sang host public. |
| Job kết thúc `needs_review` | Đọc review reason, safety/OOD/uncertainty và citation. Đây có thể là kết quả đúng của test fail-closed. |
| Clipboard bị chặn | Chọn trace ID và sao chép thủ công; không cần cấp thêm quyền để tiếp tục demo. |
| Job `failed` hoặc `expired` | Ghi lại `job_id`, `trace_id`, error code/timestamp; không tự chuyển thành `succeeded` hoặc bỏ qua gate. |
| Evidence không rõ hoặc thiếu citation | Không phê duyệt; giữ `needs_review` và chuyển reviewer phù hợp. |

## 9. Kết thúc phiên

1. Xác nhận action vẫn `NON-EXECUTABLE` và mọi quyết định đã ghi `applied_by_system=false`.
2. Ghi lại job/trace ID cần phục vụ audit; không lưu payload vượt nhu cầu.
3. Dừng Uvicorn bằng `Ctrl+C`.
4. Xóa evidence tạm nếu không cần review và xác nhận không có raw video, credential hoặc endpoint riêng được lưu/phát hành.
