# Thiết kế runbook demo offline STWI

## Mục tiêu

Viết lại `docs/guides/mvp_demo_runbook.md` thành tài liệu thực hành duy nhất để
chuẩn bị và trình bày demo offline. Người đọc phải có thể setup dashboard, chạy
evidence và trình bày đủ 13 kịch bản mà không cần đọc tài liệu khác.

## Phạm vi

Runbook chỉ giữ:

1. yêu cầu môi trường và lệnh cài dependency;
2. lệnh kiểm tra demo offline;
3. lệnh khởi động Uvicorn và URL chính xác `/demo/`;
4. checklist trước khi demo;
5. hướng dẫn thao tác và kết quả mong đợi cho đủ 13 capability;
6. thứ tự trình bày hoàn chỉnh;
7. xử lý lỗi trực tiếp liên quan đến việc chạy demo và cách dừng server.

Loại bỏ profile services, Docker, production readiness, RTSP/GPU/SLA, release
gate, phụ lục Human Review và phần hỏi đáp không cần thiết cho thao tác demo.

## Cấu trúc

- **Setup:** cài `.[orchestrator]`, chạy smoke offline, khởi động dashboard.
- **Kiểm tra nhanh:** xác nhận evidence pass và dashboard ở chế độ demo.
- **Ma trận 13 kịch bản:** tên, cách chạy, trạng thái mong đợi, điểm cần kiểm tra.
- **Hướng dẫn chi tiết:** nhóm kịch bản chạy trực tiếp trên dashboard và nhóm
  được chứng minh bằng smoke/evidence vì UI không cung cấp control để cố ý gây
  lỗi authorization, dependency hoặc SSE reconnect.
- **Trình tự trình bày:** một luồng duy nhất, không duy trì hai phiên bản 7/15 phút.
- **Khắc phục lỗi:** chỉ gồm 404 do mở sai URL, connection refused, static preview,
  kết quả fail-closed đúng dự kiến và cách dừng Uvicorn.

## Ràng buộc

- Giữ nguyên 13 tên capability trong `src/stwi/demo/scenarios.py`.
- Không mô tả synthetic evidence là production hoặc dữ liệu hiện trường.
- Không thay đổi code, API, contract hoặc dashboard.
- Không hướng dẫn mở port public hay tự động áp dụng action.

## Tiêu chí chấp nhận

- Một người mới có thể copy/paste setup và mở đúng dashboard.
- Đủ 13 capability xuất hiện đúng một lần trong ma trận chính.
- Mỗi capability có cách chạy hoặc cách xem evidence cụ thể.
- Không còn nội dung services/production/RTSP/GPU/SLA/release không liên quan.
