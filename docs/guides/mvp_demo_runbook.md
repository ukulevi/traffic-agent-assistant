# Runbook demo offline SmartTraffic What-If

Runbook này là kịch bản mentor-facing cho demo STWI trong 8–10 phút. Mọi node,
topology, incident, forecast và route trong profile này đều là **synthetic** và
**aggregate-only**. STWI chỉ hỗ trợ ra quyết định: không lưu video thô, không
gửi lệnh tới đèn tín hiệu hoặc thiết bị hiện trường, và không thay thế quyết
định của operator hay reviewer pháp lý.

## 1. Setup tái lập được

Yêu cầu Windows, PowerShell và Python 3.11+. Từ thư mục gốc repository, chạy
nguyên các lệnh sau:

Nếu `python` không có trên `PATH`, hãy kích hoạt virtual environment của dự án
hoặc thay mỗi lệnh `python` bằng `py -3.11`.

```powershell
python --version
pip install -e ".[orchestrator]"
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
$env:STWI_RUNTIME_MODE = "demo"
python -m uvicorn stwi.app:app --host 127.0.0.1 --port 8000
```

Chỉ tiếp tục khi **CLI summary** của smoke có `profile: "offline"`,
`verdict: "pass"` và `capability_count: 17`. Khi mở JSON evidence, kiểm tra
top-level `capabilities` có 17 entries; `capability_count` chỉ có ở CLI summary,
không phải field của JSON. Đây là xác nhận profile mô phỏng tái lập được, không
phải tuyên bố sẵn sàng production hay độ chính xác hiện trường. Evidence chỉ
ghi aggregate cần audit như incident/node, phiên bản topology/model/data/policy,
route status, safety reason, citation presence, trace và quyết định operator;
không ghi mô tả tự do, ảnh/base64, video thô, credential hay secret.

Sau khi Uvicorn khởi động, mở [http://127.0.0.1:8000/demo/](http://127.0.0.1:8000/demo/).
`/` trả 404 và favicon 404 không phải lỗi demo: dashboard chỉ được mount tại
`/demo/`.

## 2. Preflight: 10 phút trước buổi trình bày

- [ ] CLI summary của terminal smoke vừa chạy có `profile=offline`,
  `verdict=pass` và `capability_count=17`; JSON
  `C:\tmp\stwi-offline-evidence.json` có mảng `capabilities` gồm 17 entries.
- [ ] Dashboard hiện badge runtime `Demo synthetic`; phần input xuất hiện trước
  topology, job lifecycle và kết quả.
- [ ] Registry có đúng mạng synthetic 20 node và topology Leaflet là tile-free,
  không đại diện địa lý thật, không dùng tile ngoài mạng.
- [ ] Chỉ định sẵn ba preset cho demo live: `safe`, `refinement`, `unsafe-vc`.
  Không trình bày các capability harness-only như một preset UI.
- [ ] Dashboard cũng có preset live fail-closed `missing-evidence`, `extreme` và
  các incident `accident`, `flood`, `lane-closure`, `demand-surge`,
  `signal-change`; chỉ chọn những preset này khi cần minh họa nhánh tương ứng.
- [ ] Với preset `refinement`, bảng route và overlay map dùng cùng route ID;
  route recommendation hiển thị nét liền và vẫn là non-executable.
- [ ] Operator decision chỉ tạo audit record có `applied_by_system=false`; không
  có thao tác nào áp dụng route/action cho hạ tầng.
- [ ] Cửa sổ terminal chỉ cho thấy lệnh cần thiết, không lộ secret, credential,
  endpoint nội bộ hoặc đường dẫn riêng tư không cần cho buổi demo.

## 3. Kịch bản demo chính 8–10 phút

### 0:00–1:00 — Mục đích và phạm vi

**Thao tác:** Mở dashboard tại `/demo/`; chỉ lần lượt badge `Demo synthetic`,
khối **Tạo kịch bản**, mạng 20 node và dòng disclosure của mạng.

**Nói:** “Đây là một công cụ để người vận hành so sánh các phương án trước khi
họ tự quyết định. Hôm nay mọi dữ liệu đều được tạo cho demo và đã tổng hợp, nên
ta không coi đây là quan sát giao thông thật hay lệnh điều khiển.” Sau phần
plain-language này, nói rõ topology là synthetic, aggregate-only và STWI là
decision-support.

**Chỉ trên màn hình:** Input-first order, badge `Simulation only`, sơ đồ 4×5
gồm 20 node, badge `Tile-free · Offline-safe` và disclosure không đại diện địa
lý thực.

**Kết quả mong đợi:** Mentor thấy đầu vào xuất hiện trước kết quả, hiểu phạm vi
offline synthetic và biết không có automatic actuation.

### 1:00–3:00 — `safe` → `succeeded`

**Thao tác:** Chọn `node_00`, preset `safe`, xác nhận không có sự cố và
`green_time_ratio=0.70`, rồi bấm **Chạy mô phỏng**. Theo dõi
`queued → running → succeeded`; mở forecast, evidence/citation và ghi một
operator decision audit-only (approve hoặc reject).

**Nói:** “Ở trường hợp bình thường, hệ thống dự báo 30 phút và đưa kết quả để
operator xem xét, chứ không tự thay đổi tín hiệu.” Sau đó chỉ V/C như tỷ lệ nhu
cầu trên năng lực, và giải thích forecast/evidence có đơn vị, `job_id`,
`trace_id`, model/data version. Citation ở đây là evidence có cấu trúc trong
demo, không phải xác nhận pháp lý production.

**Chỉ trên màn hình:** Job lifecycle, kết quả 30 phút có đơn vị, citation,
`model_version`, `data_version`, `trace_id`, `recommended_action` và audit
record `applied_by_system=false`.

**Kết quả mong đợi:** Job kết thúc `succeeded`; chỉ nhánh này có
`recommended_action`, nhưng action vẫn non-executable và cần operator approval.

### 3:00–6:00 — `refinement` → `succeeded` tại node khác

**Thao tác:** Chọn `node_10` (khác `node_00`), chọn `refinement`, giữ
`green_time_ratio=0.70`, chạy mô phỏng và mở **Hành lang điều hướng**. Đối
chiếu tối đa ba route giữa bảng và map bằng route ID.

**Nói:** “Khi phương án đầu tiên chưa đủ an toàn, hệ thống thử một điều chỉnh
trong giới hạn rồi mới trả kết quả cho người xem.” Sau đó gọi tên
Counterfactual Safety Loop: vòng đầu đánh giá ratio 0.70, vòng sau 0.85;
provenance là các version model/data/topology để biết kết quả đến từ đâu. V/C là
policy MVP cấu hình được, không phải quy định pháp luật.

**Chỉ trên màn hình:** Hai vòng safety, incident typed `signal_change`, route
rank/node sequence/V/C/speed/delay proxy/uncertainty/OOD, ba version provenance,
route tránh node incident, recommendation nét liền và nhãn operator review bắt
buộc.

**Kết quả mong đợi:** Job `succeeded`, có tối đa ba route đã xếp hạng và
`requires_operator_approval=true`; route là bằng chứng mô phỏng,
non-executable, không phải điều hướng được áp dụng tự động.

### 6:00–8:00 — `unsafe-vc` → `needs_review`

**Thao tác:** Chọn `node_01`, preset `unsafe-vc`, chạy mô phỏng. Khi job kết
thúc, mở safety state, review reason và action panel; không bấm hay mô tả như
có thể approve action.

**Nói:** “Đây là ví dụ hệ thống chủ động dừng khi phương án không an toàn, thay
vì cố tạo một câu trả lời đẹp.” Sau đó nêu V/C `0.96` vượt policy `0.90`, nên
job chuyển sang `needs_review`. Giải thích OOD là đầu vào khác miền dữ liệu và
uncertainty là mức không chắc chắn; cả hai cũng fail-closed nhưng được chứng
minh trong evidence harness, không có preset live tương ứng.

**Chỉ trên màn hình:** `needs_review`, safety reason, V/C vượt policy,
`candidate_action · NON-EXECUTABLE`, và trạng thái operator review thay vì route
recommendation.

**Kết quả mong đợi:** Không có `recommended_action`; chỉ có
`candidate_action` non-executable và operator không thể biến kết quả này thành
`succeeded` bằng thao tác UI.

### 8:00–10:00 — Evidence 17 capability và kết luận

**Thao tác:** Mở `C:\tmp\stwi-offline-evidence.json`, dùng ma trận bên dưới để
đối chiếu các capability không chạy live, rồi quay lại badge `Demo synthetic`
và operator decision audit-only trên dashboard.

**Nói:** “Ba tình huống live cho thấy luồng chính; evidence lưu lại cả những
nhánh cần từ chối hoặc lỗi để chứng minh hệ thống không che giấu chúng.” Sau đó
giải thích `status: "pass"` nghĩa là hành vi quan sát khớp kỳ vọng của capability,
không có nghĩa terminal status luôn là `succeeded`. Kết luận: STWI hữu ích cho
đánh giá what-if trong phạm vi demo; route/action luôn cần người phê duyệt.

**Chỉ trên màn hình:** `schema_version: "1.0"`, `verdict: "pass"`, mảng
`capabilities` gồm 17 entries, các nhánh `needs_review`, `failed`, `expired`,
422, 403, SSE reconnect và static preview. `capability_count: 17` là output của
CLI summary, không phải field cần tìm trong JSON.

**Kết quả mong đợi:** Mentor phân biệt được demo live với evidence/harness-only
và hiểu tất cả quyết định vẫn nằm ở con người.

## 4. Ma trận 17 capability và nơi chứng minh

`Dashboard-live` nghĩa là có thể quan sát qua control thật trên dashboard.
`Evidence/harness-only` nghĩa là smoke harness ghi nhận capability vào evidence;
không dựng route giả hoặc chỉ dẫn người trình bày chọn một preset không tồn tại.
`status: "pass"` của mỗi hàng chỉ cho biết hành vi quan sát khớp kỳ vọng, kể cả
khi terminal status là `needs_review`, `failed` hoặc `expired`; nó không đồng
nghĩa terminal status `succeeded`.

| Nơi chứng minh | Capability | Terminal/HTTP mong đợi | Cách đối chiếu |
|---|---|---|---|
| Dashboard-live | `normal_baseline` | `succeeded` | Preset `safe`; forecast 30 phút và `recommended_action` non-executable. |
| Dashboard-live | `safe_rejection` | `succeeded` | Từ `safe`, ghi operator reject; `applied_by_system=false`. |
| Dashboard-live | `route_recommendation` | `succeeded` | Preset `refinement`; tối đa 3 route, map/bảng cùng route ID và đủ provenance. |
| Dashboard-live | `accident_any_node` | `needs_review` | Preset `unsafe-vc` tại node đã chọn; V/C vượt policy. |
| Dashboard-live | `flood_any_node` | `needs_review` | Preset incident UI `flood`; tốc độ synthetic giảm, không diễn giải mực nước thật. |
| Dashboard-live | `lane_closure_any_node` | `needs_review` | Preset `lane-closure`; dùng `lane_closure_ratio`, không suy diễn số làn thực. |
| Dashboard-live | `demand_surge_any_node` | `needs_review` | Preset `demand-surge`; demand synthetic tăng, không phải dự báo production. |
| Evidence/harness-only | `route_needs_review` | `needs_review` | `route_count: 0`, `route_status: "needs_review"`, safety reason bắt đầu `no_passing_route`; không có nút làm hỏng generator. |
| Evidence/harness-only | `ood` | `needs_review` | OOD fail-closed, không refinement và không route recommendation; dashboard không có preset `ood`. |
| Evidence/harness-only | `high_uncertainty` | `needs_review` | Uncertainty cao, không recommendation; dashboard không có preset `uncertainty`. |
| Dashboard-live | `missing_citation` | `needs_review` | Preset `missing-evidence`; không coi citation demo là xác nhận pháp lý production. |
| Evidence/harness-only | `dependency_failure` | `failed` | Không action; evidence ghi nhánh dependency thất bại. |
| Evidence/harness-only | `deadline_exceeded` | `expired` | Không action; evidence ghi hard deadline hết hạn. |
| Evidence/harness-only | `invalid_scenario` | HTTP 422 | Input bị validate từ chối, không tạo job. |
| Evidence/harness-only | `tenant_scope_denied` | HTTP 403 | Tenant scope bị từ chối, không tạo job. |
| Evidence/harness-only | `sse_reconnect` | terminal event duy nhất | Resume sau event 1, `terminal_event_count: 1`. |
| Evidence/harness-only | `static_preview` | non-mutating | Không tạo job/quyết định và `network_contacted: false`. |

Năm event type canonical là `accident`, `flood`, `lane_closure`,
`demand_surge` và `signal_change`. Với từng incident dashboard-live, chọn node
hợp lệ trước rồi chọn incident; preset không được hiểu là ánh xạ cố định
event→node. Các giá trị chỉ deterministic synthetic. V/C `0.9` là policy cấu
hình của MVP, không phải quy định pháp luật.

## 5. Phương án dự phòng

| Tình huống | Cách xử lý trung thực |
|---|---|
| Server lỗi hoặc không mở được dashboard | Dùng ảnh trong walkthrough và evidence được tạo sau lần smoke pass gần nhất; nói rõ đây là phương án dự phòng, không phải live run. |
| Job live lệch kỳ vọng | Không sửa lời giải thích hay đổi trạng thái để biến thành pass. Chuyển sang evidence, ghi `job_id`/`trace_id`/lỗi và nêu đây là sai lệch cần điều tra. |
| Mất mạng | Tiếp tục trên loopback; Leaflet topology tile-free không cần tile ngoài. Không đổi host public để “cứu” demo. |
| Smoke fail hoặc evidence không đủ 17 | Dừng tuyên bố acceptance. Đọc capability `status: "fail"`, sửa nguyên nhân và chạy lại smoke trước buổi demo khác. |
| `/` hoặc favicon 404 | Mở đúng `/demo/`; đây không phải lỗi logic demo. |
| Route trống/`needs_review` | Đọc `route_status` và safety reason; không thêm route minh họa thủ công. |

Kết thúc server bằng `Ctrl+C`. Chỉ giữ evidence cho audit cần thiết và không phát
hành file có credential, endpoint riêng, ảnh hay video thô.

## 6. Câu hỏi mentor thường gặp

**Vì sao dùng dữ liệu synthetic?** Đây là demo offline tái lập được cho luồng
what-if và safety. Nó không tuyên bố là dữ liệu cảm biến thật, calibration hiện
trường hay độ chính xác production.

**GCN–LSTM khác surrogate thế nào?** GCN–LSTM dự báo baseline 30 phút khi không
can thiệp. Surrogate ensemble ước lượng tác động kịch bản, được học từ các run
SUMO offline; hai vai trò không được trộn thành một đầu vào online.

**V/C 0,9 có phải luật không?** Không. Đây là ngưỡng policy cấu hình cho MVP;
citation pháp lý và policy vận hành là hai loại evidence khác nhau.

**Route/action có được tự áp dụng không?** Không. Route/action là
non-executable, `applied_by_system=false`, và luôn cần operator approval.

**Citation trên màn hình có đủ để kết luận pháp lý không?** Không. Citation cần
cấu trúc và kiểm tra hiệu lực; thiếu căn cứ hợp lệ thì hệ thống phải fail-closed
và chuyển reviewer phù hợp.

**Vì sao OOD hoặc uncertainty cao lại dừng?** Khi đầu vào xa miền đã biết hoặc
độ không chắc chắn cao, an toàn hơn là trả `needs_review` thay vì đưa
recommendation. Hai nhánh này được chứng minh bằng harness evidence trong demo.

**Còn thiếu gì để pilot?** Cần dữ liệu được quản trị và aggregate hợp lệ,
calibration/benchmark đúng profile, vận hành citation và reviewer, kiểm thử
integration/observability, kiểm soát truy cập và phê duyệt governance. Không
được suy ra các gate đó đã pass chỉ từ demo offline.
