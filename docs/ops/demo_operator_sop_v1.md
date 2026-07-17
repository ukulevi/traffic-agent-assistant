# SOP demo: Operator SmartTraffic What-If

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `stwi-demo-operator-sop-v1` |
| Phiên bản | 1.0 |
| Trạng thái | Draft — chưa được phê duyệt để index hoặc vận hành thật |
| Owner | Chờ project owner chỉ định rõ |
| Phạm vi | Demo MVP offline, decision-support only |

## 1. Mục đích và giới hạn

Quy trình này giúp operator trình diễn luồng What-If một cách có kiểm soát.
STWI chỉ trình bày bằng chứng và phương án để con người cân nhắc. Nó không gửi
lệnh điều khiển đèn, camera hay bất kỳ thiết bị hiện trường nào.

Nếu dữ liệu mang nhãn `public_proxy_demo_only`, operator phải hiển thị rõ đó là
traffic data proxy công khai, không đại diện cho mạng tại Việt Nam và không
phải bằng chứng calibration cho một can thiệp thực địa. Không được thay nhãn
mock hoặc public-proxy thành dữ liệu cảm biến thực.

## 2. Điều kiện trước khi demo

1. Xác nhận dataset/model version, timestamp và `trace_id` hiển thị được.
2. Xác nhận không có raw video/frame trong payload, log hoặc màn hình demo.
3. Xác nhận citation có document number, provision, URL, effective date và
   content hash; thiếu citation hợp lệ thì dừng ở `needs_review`.
4. Xác nhận status job chỉ thuộc `queued`, `running`, `succeeded`,
   `needs_review`, `failed` hoặc `expired`.
5. Xác nhận mọi output chỉ là khuyến nghị cho operator; không có endpoint hay
   nút bấm nào thực thi actuation.

## 3. Thực hiện demo

1. Tạo một `SimulationQuery` hợp lệ cho node và horizon trong scope demo.
2. Theo dõi job qua API/SSE; ghi nhận `trace_id`, status và thời điểm.
3. Khi `succeeded`, đối chiếu baseline, V/C, uncertainty/OOD, nguồn dữ liệu,
   model version và citations trước khi đọc `recommended_action`.
4. Khi `needs_review`, chỉ đọc `candidate_action`; không chuyển nó thành lệnh
   thực thi. Nêu rõ lý do fail-closed và chuyển cho operator/reviewer phù hợp.
5. Khi `failed` hoặc `expired`, giữ thông báo lỗi an toàn và `trace_id`; không
   tự retry vô hạn hoặc thay dữ liệu đầu vào không có provenance.

## 4. Kết thúc và audit

Operator ghi nhận quyết định của con người, dataset/model version, `trace_id`,
citation đã xem và giới hạn demo. Kết quả chỉ được dùng minh hoạ khả năng hỗ
trợ quyết định; không dùng để xác nhận điều hành hiện trường hay tuân thủ pháp
lý.

## 5. Điều kiện phê duyệt và index

Trước khi tài liệu này có thể trở thành corpus candidate, project owner phải
điền owner, approver, ngày phê duyệt, scope cuối cùng và content hash trong
`docs/ops/internal_sop_registry.json`, sau đó chạy validator. Việc validator
pass chỉ cho phép bắt đầu một quy trình corpus/index riêng; nó không tự index
vào Qdrant.
