# Hướng dẫn demo MVP SmartTraffic What-If

Tài liệu này hướng dẫn trình diễn STWI theo phạm vi đã phê duyệt:
**simulation-first, offline, aggregate-only**. Mục tiêu là minh hoạ luồng hỗ
trợ ra quyết định What-If, không phải chứng minh hệ thống đã sẵn sàng vận hành
production hoặc điều khiển thiết bị giao thông.

## 1. Hiểu demo trong một phút

Hãy xem STWI như một **bàn thử phương án giao thông**: trước khi một người đưa
ra quyết định, họ có thể hỏi hệ thống “nếu thay đổi điều này thì điều gì có thể
xảy ra?”. Hệ thống phân tích tình huống, tự kiểm tra mức an toàn của kết quả và
trình bày bằng chứng để con người quyết định cuối cùng.

Luồng demo là:

```text
Người demo nhập tình huống
        ↓
STWI tạo một job phân tích
        ↓
STWI dự báo và mô phỏng tác động
        ↓
STWI tự kiểm tra an toàn / độ tin cậy
        ↓
Người vận hành xem kết quả và ghi quyết định
```

Ví dụ, bạn có thể hỏi: “Tại `node_00`, nếu giả định thời gian đèn xanh là 70%
thì tình hình trong 30 phút tới có thể thay đổi như thế nào?” Đây chỉ là một
câu hỏi mô phỏng. Việc nhập 70% **không thay đổi đèn thật**.

Ba điều người xem cần hiểu ngay từ đầu:

1. Dữ liệu trong demo là dữ liệu giao thông tổng hợp/mô phỏng theo từng 5 phút;
   không có camera trực tiếp, RTSP hay cảm biến hiện trường.
2. Kết quả là bằng chứng hỗ trợ quyết định, không phải mệnh lệnh điều khiển.
3. Nút **Phê duyệt** hoặc **Từ chối** chỉ ghi nhận ý kiến của operator vào audit
   trail; hệ thống không gửi lệnh đến đèn tín hiệu hoặc thiết bị ngoài thực tế.

### Những gì xuất hiện trên màn hình

| Khu vực UI | Cách hiểu đơn giản |
|---|---|
| **Tạo kịch bản What-If** | Nơi bạn đặt câu hỏi giả định cho hệ thống. |
| **Theo dõi job** | “Số thứ tự” của câu hỏi: đã nhận, đang phân tích hay đã xong. |
| **Đánh giá an toàn** | Hệ thống có đủ tự tin để đưa ra gợi ý hay phải dừng để con người xem thêm. |
| **Action payload** | Nội dung gợi ý dưới dạng dữ liệu kỹ thuật; luôn có `executable: false` trong demo. |
| **Quyết định operator** | Nơi con người lưu quyết định cuối cùng để phục vụ audit. |

### Diễn giải hai kết quả có thể gặp

- `succeeded`: kiểm tra đã pass. Hệ thống có thể hiển thị một
  `recommended_action`, nhưng operator vẫn phải xem xét và phê duyệt.
- `needs_review`: hệ thống không đủ cơ sở an toàn hoặc đủ tin cậy để khuyến nghị.
  Khi đó chỉ có `candidate_action` để tham khảo; không có hành động nào được
  thực thi.

## 2. Thông điệp cần chốt trước khi demo

Nói rõ ba điểm này ngay từ đầu:

1. STWI dự báo baseline 30 phút và ước lượng tác động của một kịch bản bằng
   GCN-LSTM cùng surrogate ensemble từ các kịch bản SUMO offline.
2. Dữ liệu demo là chuỗi 5 phút tổng hợp mô phỏng. Không có video thô, RTSP
   trực tiếp, hay cảm biến hiện trường trong lượt demo này.
3. STWI chỉ hỗ trợ quyết định. Mọi action đều `executable=false`; ngay cả kết
   quả `succeeded` vẫn cần operator phê duyệt và quyết định chỉ được ghi audit.

Không mô tả demo là pilot, độ chính xác ngoài thực địa, benchmark SLA production,
hay khả năng điều khiển đèn tín hiệu.

## 3. Chuẩn bị trước buổi demo

Yêu cầu: Python 3.11+ và môi trường có thể cài package của repository. Không
cần Docker, GPU, RTSP URL, khóa API hoặc dịch vụ bên ngoài.

Từ thư mục gốc repository, cài dependency demo và kiểm tra phạm vi:

```powershell
pip install -e ".[orchestrator]"
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --output C:\tmp\stwi-mvp-demo-evidence.json
```

Kết quả mong đợi của smoke harness là bốn luồng terminal:

| Luồng | Trạng thái | Điểm cần nhấn mạnh |
|---|---|---|
| `safe_approval` | `succeeded` | Có `recommended_action`, nhưng `executable=false`; operator vẫn là người phê duyệt. |
| `unsafe_vc_rejection` | `needs_review` | V/C vượt policy; chỉ có `candidate_action`. |
| `ood_rejection` | `needs_review` | Tình huống ngoài phân phối bị fail-closed. |
| `uncertainty_rejection` | `needs_review` | Độ bất định cao nên không có recommendation. |

Tệp evidence tại `C:\tmp\stwi-mvp-demo-evidence.json` chỉ chứa dữ liệu tổng
hợp mô phỏng. Không đưa tệp này lên Git hoặc đính kèm raw/private artifact vào
tài liệu công khai.

Nếu một trong hai lệnh thất bại, không tiếp tục tuyên bố demo đã được xác minh;
hãy dùng thông báo lỗi để xử lý môi trường trước.

## 4. Khởi động giao diện operator

Giữ `STWI_RUNTIME_MODE` ở `development` hoặc `demo`; **không** đặt
`production` cho buổi demo offline vì production cố ý từ chối adapter/store
provisional.

```powershell
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

Mở trình duyệt tại [http://127.0.0.1:8000/demo/](http://127.0.0.1:8000/demo/).
Chỉ dùng loopback khi demo trên một máy. Dừng server bằng `Ctrl+C` sau buổi demo.

## 5. Kịch bản trình diễn đề xuất (5–7 phút)

### Bước 1 — Đặt câu hỏi cho hệ thống

Trên trang `/demo/`, giữ giá trị mặc định hoặc nhập:

| Trường | Giá trị demo |
|---|---|
| Tenant | `demo-operator` |
| Node | `node_00` |
| Green time ratio | `0.70` |
| Mô tả | `Đánh giá quyền và nghĩa vụ người sử dụng đường tại node_00.` |

Chọn **Chạy mô phỏng**. Có thể nói theo cách dễ hiểu: “Hệ thống đã nhận câu
hỏi và tạo một job để xử lý ở nền.” Sau đó dashboard sẽ theo dõi tiến độ.
Nếu cần giải thích kỹ thuật, API trả `202 Accepted`, còn màn hình nhận tiến độ
qua GET và SSE.

### Bước 2 — Xem hệ thống đã xử lý gì

Trên màn hình, chỉ lần lượt chỉ ra:

1. Trạng thái trong phần **Theo dõi job**: hệ thống đã nhận, đã chạy và đã xong.
2. `trace_id`, `model_version` và `data_version`: nhãn giúp truy lại nguồn gốc
   kết quả khi cần kiểm tra/audit.
3. Các sự kiện lifecycle: các mốc tiến độ của job, thay vì coi đây là một nút
   bấm cho kết quả ngay lập tức.
4. **Đánh giá an toàn**: hệ thống đã pass kiểm tra, hoặc lý do tại sao nó yêu
   cầu con người xem thêm.
5. Action JSON: phải có `executable: false` và
   `requires_operator_approval: true`.

Nếu terminal là `succeeded`, gọi action là **recommended action**. Nếu là
`needs_review`, gọi nó là **candidate action**, không gọi là khuyến nghị.

### Bước 3 — Để con người quyết định

Với `succeeded`, chọn **Phê duyệt** hoặc **Từ chối** để minh hoạ audit trail.
Với `needs_review`, UI chỉ cho phép **Từ chối**; API cũng từ chối quyết định
`approved`. Đọc lại thông báo trên UI: quyết định được ghi nhận nhưng không có
hành động tự động.

Không nói rằng nút Phê duyệt thay đổi chu kỳ đèn, gửi lệnh xuống node, hoặc áp
dụng action vào hạ tầng thật.

### Bước 4 — Minh hoạ việc hệ thống biết dừng đúng lúc

Chọn **Bộ kiểm thử demo** trên giao diện để trình bày tuần tự các nhánh:

| Preset | Node/profile | Trạng thái mong đợi |
|---|---|---|
| Luồng bình thường | `node_00`, green time 70% | `succeeded` |
| V/C vượt policy | `node_01` | `needs_review` |
| Ngoài phân phối | `node_02` | `needs_review` |
| Độ bất định cao | `node_03` | `needs_review` |
| Thiếu căn cứ | `node_04`, jurisdiction không có corpus | `needs_review` |
| Green time cực trị | `node_00`, green time 0% | `needs_review` |

Các preset tạo dữ liệu synthetic xác định để minh họa nhánh điều khiển của
safety loop; chúng không phải bộ benchmark accuracy. Có thể đối chiếu thêm
evidence của smoke harness ở Mục 3:

```powershell
Get-Content C:\tmp\stwi-mvp-demo-evidence.json
```

Chỉ ra một case `*_rejection`: `recommended_action` vắng mặt,
`candidate_action` không executable, và `automatic_actuation=false`.

## 6. Checklist nói trong lúc trình bày

- [ ] Input là dữ liệu tổng hợp mỗi 5 phút; network logic vẫn theo contract 20 node.
- [ ] Baseline và scenario surrogate là hai vai trò riêng; không blend case truy xuất vào input online.
- [ ] Safety loop tối đa 3 vòng và fail-closed khi OOD, uncertainty cao, thiếu citation hoặc policy không hội tụ.
- [ ] Chỉ `succeeded` mới có `recommended_action`.
- [ ] `needs_review` chỉ có `candidate_action` và luôn cần người vận hành xem xét.
- [ ] Không lưu/phát hành raw video và không có automatic actuation.
- [ ] Đây là demo mô phỏng, không phải triển khai production.

## 7. Câu trả lời ngắn cho câu hỏi thường gặp

**Dữ liệu này có phải dữ liệu giao thông thật không?**  Không. Demo dùng dữ
liệu tổng hợp/mô phỏng đã version; RTSP và cảm biến thật là gate riêng.

**Hệ thống có tự thay đổi đèn tín hiệu không?**  Không. Tất cả action trả về
đều non-executable; operator chỉ ghi quyết định audit.

**Vì sao có `needs_review`?**  Đây là hành vi an toàn có chủ đích: khi policy,
uncertainty, OOD hoặc citation không đủ tin cậy, hệ thống không được đưa ra
khuyến nghị thực thi.

**Đã sẵn sàng production chưa?**  Chưa. Cần nguồn camera/aggregate được phê
duyệt, calibration non-mock, benchmark đúng cấu hình contract, và baseline
triển khai/khôi phục production trước khi có thể đánh giá release production.

## 8. Kết thúc và dọn dẹp

1. Dừng Uvicorn bằng `Ctrl+C`.
2. Chỉ giữ evidence mô phỏng tại thư mục private/tạm nếu cần review; không
   commit hoặc chia sẻ kèm credential, endpoint RTSP, raw video hay dataset
   private.
3. Ghi lại câu hỏi của người xem thành ticket riêng; không thay đổi contract,
ngưỡng SLA hoặc safety policy ngay trong lúc demo.

## Tham chiếu

- `project_contract.json` — phạm vi, API, safety và SLA bất biến.
- `docs/project_management/symphony/mvp_demo_acceptance.md` — evidence
  acceptance của MVP offline.
- `docs/04_AI_Agent_Orchestrator_CF_VLA.md` — lifecycle job, safety loop và
  semantics `succeeded`/`needs_review`.
