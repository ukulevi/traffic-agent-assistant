# STWI Dashboard Demo User Guide Design

## 1. Mục tiêu

Tạo một tài liệu hướng dẫn sử dụng dashboard STWI bằng tiếng Việt, có ảnh chụp
thực tế và dùng các test case deterministic làm luồng demo. Tài liệu giúp người
dùng tự khởi động demo, thao tác dashboard, đọc kết quả và nhận biết các nhánh
fail-closed mà không cần đọc mã nguồn hoặc JSON trước.

Tài liệu không chứa lời thoại thuyết trình và không mô tả dashboard như một hệ
thống tự động ra quyết định hay điều khiển hiện trường.

## 2. Đầu ra

- Tài liệu chính: `docs/guides/mvp_dashboard_demo_walkthrough.md`.
- Ảnh PNG: `docs/assets/demo_walkthrough/`.
- `docs/guides/mvp_demo_runbook.md` liên kết đến walkthrough mới.
- Không thay đổi `project_contract.json`, API schema, runtime dependency hoặc
  logic nghiệp vụ dashboard chỉ để phục vụ tài liệu.

## 3. Đối tượng sử dụng

- Người lần đầu chạy STWI MVP trên máy local.
- Operator hoặc giảng viên cần kiểm tra luồng What-If bằng dữ liệu synthetic.
- QA cần đối chiếu trạng thái, evidence, action gate và demo compatibility.

Người dùng cần biết cách chạy lệnh PowerShell cơ bản nhưng không cần hiểu kiến
trúc GCN–LSTM, surrogate hoặc LangGraph để hoàn thành walkthrough.

## 4. Cấu trúc tài liệu

1. Phạm vi và giới hạn an toàn của demo.
2. Điều kiện chuẩn bị và lệnh khởi động FastAPI ở `STWI_RUNTIME_MODE=demo`.
3. Mở `/demo/` và nhận biết runtime, connection và canonical job status.
4. Tổng quan các vùng giao diện theo thứ tự operator sử dụng.
5. Chạy test case `safe` và kiểm tra `succeeded`.
6. Đọc metrics, evidence, citation, model/data version và `trace_id`.
7. Mở dialog và ghi nhận quyết định audit-only.
8. Chạy các test case fail-closed: `unsafe-vc`, `ood`, `uncertainty`,
   `missing-evidence` và `extreme`.
9. Chạy nhóm tình huống synthetic: `accident`, `flood`, `lane-closure`,
   `demand-surge` và `environmental-anomaly`.
10. Sử dụng bàn phím: `/`, `C`, `Enter`, `Esc` và copy thủ công khi clipboard
    bị browser chặn.
11. Bảng xử lý lỗi thường gặp và checklist kết thúc demo.

## 5. Mẫu nội dung cho mỗi test case

Mỗi test case dùng cùng một cấu trúc:

1. **Mục tiêu:** nhánh nghiệp vụ hoặc safety gate cần quan sát.
2. **Dữ liệu chọn:** preset, node, `green_time_ratio` và jurisdiction nếu liên
   quan.
3. **Thao tác:** các control cần chọn và nút cần kích hoạt.
4. **Ảnh:** trạng thái trước khi chạy hoặc kết quả terminal có liên quan.
5. **Kết quả mong đợi:** canonical status, metrics/evidence chính và action gate.
6. **Điểm kiểm tra:** điều không được xuất hiện, đặc biệt automatic actuation,
   executable action hoặc `recommended_action` trong `needs_review`.

Các test case có cùng kiểu kết quả có thể dùng chung một ảnh tổng quan và ảnh
chi tiết safety/evidence để tránh lặp tài liệu không cần thiết.

## 6. Danh mục ảnh dự kiến

| Tệp | Nội dung |
|---|---|
| `01-dashboard-overview.png` | Dashboard demo sau khi tải, chưa có job. |
| `02-safe-preset-input.png` | Form với preset `safe` và node synthetic. |
| `03-succeeded-result.png` | Kết quả terminal `succeeded` và metrics. |
| `04-succeeded-evidence.png` | Evidence, citation, version và trace ID. |
| `05-decision-dialog.png` | Dialog audit-only với lựa chọn được policy cho phép. |
| `06-decision-recorded.png` | Decision record với `applied_by_system=false`. |
| `07-unsafe-vc-review.png` | `needs_review` do V/C vượt policy. |
| `08-ood-review.png` | `needs_review` do OOD. |
| `09-uncertainty-review.png` | `needs_review` do uncertainty cao. |
| `10-missing-evidence-review.png` | `needs_review` do citation/evidence thiếu. |
| `11-incident-presets.png` | Nhóm preset tình huống synthetic trong selector. |
| `12-clipboard-fallback.png` | Thông báo khi browser chặn clipboard. |

Ảnh chỉ chứa dữ liệu synthetic/aggregate. Không chụp secret, endpoint riêng,
raw video, base64 image, dữ liệu cá nhân hoặc nội dung ngoài phạm vi dashboard.

## 7. Quy tắc ảnh và trình bày

- Chụp qua HTTP local từ chính FastAPI demo, không dùng `file://` làm bằng chứng
  runtime.
- Ưu tiên viewport desktop dễ đọc; thêm ảnh mobile chỉ khi thao tác khác desktop.
- Cắt ảnh theo panel hoặc trạng thái cần giải thích, nhưng giữ đủ runtime/status
  để người đọc hiểu ngữ cảnh.
- Alt text mô tả trạng thái nghiệp vụ, không chỉ ghi “ảnh minh họa”.
- Mỗi ảnh phải được tham chiếu bằng đường dẫn tương đối từ tài liệu Markdown.
- Không thêm hình trang trí hoặc ảnh tạo sinh.

## 8. Safety và contract

- Sáu status canonical giữ nguyên: `queued`, `running`, `succeeded`,
  `needs_review`, `failed`, `expired`.
- Chỉ `succeeded` có `recommended_action`; `needs_review` chỉ có
  `candidate_action` không executable.
- Mọi action trong demo vẫn có `automatic_actuation=false` và cần operator phê
  duyệt.
- V/C `0.9` được ghi là policy MVP, không phải quy định pháp luật.
- Citation demo được ghi rõ là provisional, không phải xác nhận pháp lý
  production.
- Tài liệu không tuyên bố toàn hệ thống production-ready.

## 9. Kiểm tra và tiêu chí hoàn thành

- Tất cả ảnh tồn tại, mở được và đúng với test case được mô tả.
- Các link ảnh và link từ runbook không bị hỏng.
- Lệnh khởi động được lấy từ runbook canonical hiện hành.
- Nội dung Vietnamese-first, thuật ngữ API/status giữ nguyên khi cần chính xác.
- `python scripts/validation/validate_docs.py` pass.
- `git diff --check` pass.
- Dashboard/frontend regression liên quan vẫn pass vì ảnh được chụp từ runtime
  hiện hành; tài liệu không sửa logic để ép kết quả khớp ảnh.

## 10. Ngoài phạm vi

- Không tạo lời thoại hoặc kịch bản thuyết trình.
- Không tạo video, GIF hoặc slide deck.
- Không triển khai production backend, auth provider, Redis/Celery deployment
  hoặc `/api/v1/ui-context` trong thay đổi tài liệu này.
- Không commit, push hoặc tạo PR nếu người dùng chưa yêu cầu thao tác Git cụ thể.
