# Thiết kế runbook demo STWI cho mentor

## Mục tiêu

Điều chỉnh tài liệu demo thành một hướng dẫn Vietnamese-first mà người thực hiện
dự án cá nhân có thể tự dùng để trình bày STWI trong 8–10 phút. Luồng chính phải
giúp mentor hiểu vấn đề, mục đích, ba hành vi cốt lõi và ranh giới an toàn; ma trận
evidence phía sau vẫn bao quát đủ 17 capability đã được chấp nhận.

Runbook không được biến kết quả synthetic thành tuyên bố về độ chính xác thực địa,
không mô tả action/route là executable và không thay đổi contract, runtime hoặc UI.

## Người dùng và tiêu chí thành công

Người dùng chính là tác giả dự án, không có chuyên môn giao thông sâu, đang demo
trực tiếp cho mentor kỹ thuật hoặc học thuật. Sau phiên demo, mentor phải hiểu được:

1. STWI giải quyết bài toán What-If nào và đầu vào/đầu ra là gì.
2. Dashboard theo dõi job bất đồng bộ, forecast, evidence và operator decision ra sao.
3. Counterfactual Safety Loop và route evidence hoạt động trên mạng synthetic 20 nút.
4. Vì sao `needs_review`, `failed` hoặc `expired` là kết quả an toàn hợp lệ.
5. Dự án đã demo-ready trong phạm vi offline synthetic nhưng chưa production-ready.

## Cấu trúc tài liệu

`docs/guides/mvp_demo_runbook.md` tiếp tục là nguồn hướng dẫn canonical và được
chia thành hai tầng:

- **Luồng trình bày chính 8–10 phút:** ba lần chạy dashboard, có mốc thời gian,
  thao tác, lời thoại gợi ý, điểm cần chỉ trên màn hình và kết quả mong đợi.
- **Phụ lục toàn diện:** ma trận đủ 17 capability, setup/recovery, câu hỏi mentor,
  giới hạn và cách đọc evidence.

`docs/guides/mvp_dashboard_demo_walkthrough.md` giữ vai trò hướng dẫn thao tác chi
tiết có ảnh. Nội dung phải phân biệt rõ preset có trên dashboard và probe chỉ tồn
tại trong smoke harness; không hướng dẫn người dùng chọn control không tồn tại.

## Luồng demo chính

| Thời gian | Nội dung | Bằng chứng chính |
|---|---|---|
| 0:00–1:00 | Mục đích và phạm vi | Synthetic, aggregate-only, decision-support |
| 1:00–3:00 | `safe` | `queued → running → succeeded`, forecast, citation, trace và audit-only decision |
| 3:00–6:00 | `refinement` tại node khác | Hai vòng safety, tối đa ba route, version/provenance và operator approval |
| 6:00–8:00 | `unsafe-vc` | `needs_review`, candidate non-executable, nút approve không khả dụng |
| 8:00–9:00 | Evidence 17 capability | OOD, uncertainty, dependency, deadline, 422, 403, SSE và static preview |
| 9:00–10:00 | Kết luận | Giá trị MVP, giới hạn và điều kiện để tiến tới pilot |

Mỗi đoạn có bốn trường cố định: **Thao tác**, **Nói**, **Chỉ trên màn hình**, và
**Kết quả mong đợi**. Lời thoại dùng ngôn ngữ dễ hiểu, sau đó mới gắn thuật ngữ
chính xác như V/C, OOD, uncertainty hoặc provenance.

## Phân loại tình huống

Các tình huống được gắn nhãn theo nơi có thể chứng minh:

- **Dashboard-live:** `safe`, `refinement`, `unsafe-vc`, `missing-evidence`,
  `extreme` và năm incident operational.
- **Evidence/harness-only:** `ood`, `high_uncertainty`, `dependency_failure`,
  `deadline_exceeded`, `invalid_scenario`, `tenant_scope_denied`, `sse_reconnect`,
  `static_preview` và `route_needs_review` khi không có candidate.

Runbook không dựng route giả hoặc tuyên bố một probe harness-only có control trên
dashboard. `status: pass` của evidence được giải thích là hệ thống tạo đúng hành vi
mong đợi, kể cả khi terminal status là `needs_review`, `failed` hoặc `expired`.

## Setup, preflight và phương án dự phòng

Runbook cung cấp:

- lệnh cài dependency, validate simulation scope, chạy smoke và khởi động Uvicorn;
- URL chính xác `/demo/`, giải thích `/` và favicon 404;
- checklist 10 phút trước buổi demo: port, runtime mode, evidence 17 capability,
  kích thước trình duyệt, node/map, console và quyết định operator;
- điểm dừng rõ ràng nếu smoke không pass;
- phương án dự phòng dùng evidence đã tạo và ảnh walkthrough khi live server lỗi,
  nhưng không đổi một lỗi thành kết quả thành công;
- hướng dẫn kết thúc, dừng server và xử lý evidence aggregate-only.

## Câu hỏi mentor và giới hạn tuyên bố

Phần hỏi–đáp bao quát tối thiểu: vì sao dùng synthetic; GCN–LSTM khác surrogate;
V/C 0,9 có phải luật không; route có được tự áp dụng không; citation demo có phải
thẩm định pháp lý không; tại sao OOD/uncertainty dừng; dự án còn thiếu gì để pilot.

Câu trả lời phải giữ nguyên các ranh giới: không raw video, không automatic
actuation, không accuracy/SLA production claim khi chưa có dữ liệu và benchmark
đúng profile, route/action luôn cần con người phê duyệt.

## Đồng bộ và kiểm tra

Phạm vi chỉnh sửa dự kiến:

- `docs/guides/mvp_demo_runbook.md`;
- `docs/guides/mvp_dashboard_demo_walkthrough.md`;
- test tài liệu phù hợp trong `tests/demo/test_comprehensive_demo.py`.

Không cần sửa report, slides, API, schema hoặc runtime nếu nội dung chỉ làm rõ cách
trình bày hành vi đã có. Kiểm tra tối thiểu gồm docs validator, project contract,
targeted demo documentation test, JavaScript syntax checks và `git diff --check`.
