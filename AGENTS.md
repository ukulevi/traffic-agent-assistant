# AGENTS.md

## Phạm vi áp dụng

Tệp này áp dụng cho toàn bộ repository. Nếu một thư mục con có `AGENTS.md` riêng, hướng dẫn gần tệp đang sửa nhất được ưu tiên. Mọi AI agent phải đọc tệp này, `README.md` và `project_contract.json` trước khi thay đổi dự án.

## Project-local skills

Các workflow tái sử dụng nằm trong .agents/skills/:

- $stwi-implement: triển khai feature, bug fix, refactor hoặc thay đổi đặc tả và đồng bộ artifact liên quan.
- $stwi-review: review plan/code/docs theo contract, safety, privacy, pháp lý và tính khả thi.
- $stwi-release-qa: chạy verification trước bàn giao/release; dùng -BuildPdf khi report hoặc appendix thay đổi.

### 🔴 Cấu hình cứng (Hard Constraint)
**BẮT BUỘC SỬ DỤNG WORKFLOW FRAMEWORK:** Bất kỳ câu prompt hay yêu cầu nào được đưa ra, AI Agent **KHÔNG** được phép tự do thực hiện hành động trực tiếp mà không tuân thủ quy trình. Mọi thay đổi mã nguồn, thiết kế, kiểm thử hay biên dịch tài liệu **BẮT BUỘC phải được chạy tự động thông qua các skill có sẵn trong framework Superpowers** (hoặc thông qua hệ thống `.agents/skills/` cục bộ). Agent phải từ chối hoặc chuyển đổi yêu cầu thành triệu gọi skill tương ứng của Superpowers trước khi thực thi.

## 1. Mục tiêu dự án

SmartTraffic What-If (STWI) là MVP 13 tuần hỗ trợ người vận hành giao thông đánh giá kịch bản What-if. Hệ thống kết hợp:

- pipeline camera/cảm biến tạo dữ liệu giao thông đã aggregate;
- GCN–LSTM dự báo baseline 30 phút;
- surrogate ensemble học từ các kịch bản SUMO offline để ước lượng tác động sự cố;
- RAG pháp lý và `SimulationQuery` có kiểu;
- LangGraph, Celery, Redis và API job bất đồng bộ;
- Counterfactual Safety Loop fail-closed trước khi chuyển kết quả cho con người.

STWI chỉ hỗ trợ ra quyết định. MVP không tự điều khiển đèn tín hiệu, không gửi lệnh đến thiết bị hiện trường và không thay thế đánh giá của operator hoặc reviewer pháp lý.

## 2. Đối tượng người dùng

### Người dùng chính

- Operator tại trung tâm điều hành giao thông: tạo kịch bản, theo dõi tiến độ, xem tác động và quyết định có chấp thuận đề xuất hay không.
- Chuyên viên phân tích giao thông: kiểm tra baseline, V/C, độ trễ mạng và kết quả mô phỏng.
- Reviewer pháp lý/SOP: xác minh căn cứ, hiệu lực văn bản và điều/khoản được trích dẫn.

### Người dùng kỹ thuật

- Data/ML engineers xây pipeline, GCN–LSTM, SUMO dataset, surrogate và calibration.
- Backend/AI engineers xây typed query, RAG, workflow, job API và safety gate.
- Frontend, DevOps và QA engineers xây dashboard, CI, benchmark, audit và demo.

Mọi giao diện và tài liệu phải giúp người dùng hiểu rõ: trạng thái job, dữ liệu đầu vào, uncertainty/OOD, căn cứ pháp lý, lý do fail-closed và hành động nào vẫn cần con người phê duyệt.

## 3. Nguồn sự thật và thứ tự ưu tiên

1. `project_contract.json`: hợp đồng máy đọc được về scope, tensor, SLA, API, stack và safety.
2. `docs/00_STWI_Summary_and_Guidelines.md`: quy chuẩn kiến trúc tổng thể.
3. `docs/01_*.md` đến `docs/05_*.md`: đặc tả từng tầng và kế hoạch triển khai.
4. `report/chapters/`, `report/main.tex`, `slides/sections/`, release notes: artifact trình bày phải đồng bộ với các nguồn trên.
5. `docs/archive/`: lịch sử tham khảo, không phải nguồn sự thật.

Khi hai artifact mâu thuẫn, không tự chọn phương án thuận tiện. Giữ contract hiện hành, sửa artifact dẫn xuất và báo rõ mâu thuẫn. Nếu cần đổi contract, phải dừng và xin quyết định của người dùng.

## 4. Phong cách giao diện

### Nguyên tắc

- Vietnamese-first cho nội dung người dùng; giữ identifier, API field và thuật ngữ kỹ thuật bằng tiếng Anh khi cần chính xác.
- Giọng điệu vận hành: rõ ràng, bình tĩnh, có bằng chứng, không quảng cáo quá mức và không tạo cảm giác hệ thống tự động ra quyết định.
- Ưu tiên khả năng đọc nhanh: hierarchy rõ, khoảng trắng đủ, số liệu và trạng thái nổi bật, tránh dashboard quá dày.
- Các trạng thái `needs_review`, `failed`, `expired`, OOD, uncertainty cao và thiếu citation phải dễ nhận biết hơn nội dung trang trí.
- Luôn hiển thị đơn vị, timestamp, model/data version, `trace_id` và nguồn citation khi có liên quan.

### Visual language hiện tại

- Màu chủ đạo: xanh STWI `#006699`, cyan và nền sáng trung tính.
- Màu tầng: cam cho data, xanh dương cho ML, xanh lá cho knowledge/RAG, tím cho agent/safety.
- Dùng card bo góc vừa phải, shadow nhẹ, đường viền rõ; không lạm dụng gradient, animation hoặc hiệu ứng kính.
- Font giao diện ưu tiên `Be Vietnam Pro`; dữ liệu/code dùng monospace như `Azeret Mono`.
- Icon chỉ hỗ trợ nhận diện, không thay thế label.
- Bảo đảm contrast, focus state, keyboard navigation, responsive layout và không truyền đạt trạng thái chỉ bằng màu.

Không tự thiết kế lại toàn bộ visual system. Thay đổi lớn về palette, typography, navigation, layout slide/dashboard hoặc tone nội dung cần người dùng chấp thuận.

## 5. Hợp đồng bất biến

Không được tự ý thay đổi các giá trị sau:

- MVP: mạng chức năng 20 node, tối đa 20 luồng camera ghi sẵn/RTSP; 1.000 nguồn chỉ là producer aggregate tổng hợp.
- Không lưu/phát hành video thô.
- Input `X[B,12,N,16]`, missing mask `M[B,12,N,16]`, adjacency `A[N,N]`.
- Feature order và đơn vị trong `project_contract.json`; F16 là `green_time_ratio`.
- Baseline output `Y[B,6,N,2]` gồm `traffic_volume_5m` và `avg_speed_kmh`; V/C được tính từ capacity có version.
- GCN–LSTM là baseline; surrogate ensemble là mô hình kịch bản riêng, huấn luyện từ SUMO offline.
- Uncertainty phải calibration trên validation data; không blend case truy xuất trực tiếp vào input online.
- Stack đã chốt: TimescaleDB, Qdrant, BGE-m3, LangGraph, Celery, Redis, FastAPI và SSE. DuckDB chỉ dành cho offline/test.
- API: `POST /api/v1/what-if-jobs` trả HTTP 202; GET status và SSE events theo contract.
- Status: `queued`, `running`, `succeeded`, `needs_review`, `failed`, `expired`.
- Chỉ `succeeded` có `recommended_action`; `needs_review` chỉ có `candidate_action` không executable.
- Surrogate P99 < 500 ms; E2E P95 ≤ 30 giây; hard deadline/P99 ≤ 180 giây trên benchmark profile đã chốt.
- Counterfactual Safety Loop lấy cảm hứng từ CF-VLA, không phải mô hình VLA end-to-end; tối đa 3 vòng, fail-closed và luôn cần operator phê duyệt.
- V/C 0,9 là policy cấu hình của MVP, không được mô tả là quy định pháp luật.
- Citation phải có cấu trúc và kiểm tra hiệu lực; thiếu căn cứ hợp lệ phải từ chối đề xuất.
- Corpus tối thiểu gồm Luật 35/2024/QH15 và 36/2024/QH15, hiệu lực từ 01/01/2025.

Không đưa ADE, XiYanSQL, RealGen, FAISS, Weaviate, InfluxDB, LangChain hoặc CrewAI trở lại kiến trúc triển khai. Chúng chỉ được nhắc trong related work hoặc tài liệu lịch sử khi có ngữ cảnh rõ.

## 6. Quy tắc code

### Quy tắc chung

- Đọc code và contract liên quan trước khi sửa; ưu tiên thay đổi nhỏ nhất giải quyết đúng yêu cầu.
- Không sửa, format hoặc xóa phần không liên quan. Giữ nguyên thay đổi chưa commit của người dùng.
- Không hard-code lại các hằng số đã có trong `project_contract.json`; tạo một điểm cấu hình rõ ràng và validate tại boundary.
- Mọi input bên ngoài phải được validate; lỗi an toàn, pháp lý, OOD hoặc timeout phải fail closed.
- Không log secret, prompt đầy đủ chứa dữ liệu nhạy cảm, video thô hoặc payload vượt nhu cầu audit.
- Dùng query tham số hóa, allowlist và database role read-only cho truy vấn mô phỏng.
- Thêm test cho bug fix và contract mới; không làm yếu test chỉ để build xanh.
- Không thêm dependency, dịch vụ hoặc framework mới nếu chưa chứng minh nhu cầu và chưa được chấp thuận.

### Python

- Tuân theo PEP 8, dùng type hints cho API công khai và dữ liệu contract.
- Dùng `snake_case` cho biến/hàm, `PascalCase` cho class, hằng số `UPPER_SNAKE_CASE`.
- Ưu tiên `pathlib`, dataclass/Pydantic cho schema và exception có kiểu thay vì dictionary/string tùy ý.
- Tách logic thuần khỏi I/O để dễ unit test; không dùng bare `except`.

### JavaScript/HTML/CSS

- Dùng `const` mặc định, `let` khi cần gán lại; tránh tạo global mới.
- Không chèn dữ liệu không tin cậy bằng `innerHTML`; sanitize hoặc dùng DOM text APIs.
- Giữ section slide tự chứa, tên file phản ánh thuật ngữ canonical và cập nhật `slides/js/presentation.js` khi thêm/đổi tên.
- Tái sử dụng class/token CSS hiện có; tránh nhân bản inline style khi thành phần được dùng lặp lại.
- Mọi control tương tác phải có label truy cập được và dùng được bằng bàn phím.

### API và dữ liệu

- Schema API, `IncidentVector`, `SimulationResult`, `SimulationQuery` và job status phải có type/validation rõ.
- API thay đổi phải cập nhật đồng thời contract test, docs, appendices và slide liên quan.
- Giữ node order ổn định giữa X, M, A và Y; scaler chỉ fit trên training split theo thời gian.
- Split dữ liệu phải chronological/time-based và kiểm tra leakage giữa scenario families.

- Roboflow workflow integration must read `ROBOFLOW_API_KEY` from the environment, validate `https://`/base64 image input, avoid logging image base64, and use detector output only as camera aggregate evidence.

## 7. Quy tắc tài liệu và artifact

- Sửa nguồn sự thật trước, sau đó đồng bộ report LaTeX (`report/`), appendices, slides (`slides/`) và changelog trong cùng thay đổi.
- Không chỉnh tài liệu trong `docs/archive/` như đặc tả hiện hành.
- Khi đổi tên slide, cập nhật `slides/js/presentation.js` và xác nhận không có 404.
- Không khôi phục pipeline Markdown→LaTeX legacy nếu `main.tex` không dùng output của nó.
- CI không được tự commit log lỗi; chỉ upload artifact.
- GitHub Pages chỉ publish `slides/index.html`, CSS, JS và slides công khai, không phát hành tài liệu nội bộ.
- Không tăng version tài liệu, đổi ngày phát hành hoặc sửa nguồn pháp lý nếu chưa có yêu cầu rõ.

## 8. Kiểm thử bắt buộc

Chạy tối thiểu sau thay đổi contract, docs hoặc slides:

```powershell
python scripts/validate_docs.py
python -m unittest tests.test_project_contract
node --check slides/js/presentation.js
node --check slides/js/presentation-tools.js
git diff --check
```

Ngoài ra:

- Build `report/main.tex` bằng XeLaTeX khi sửa report/appendix và kiểm tra trực quan các trang bị ảnh hưởng.
- Chạy slideshow qua HTTP local khi sửa `slides/index.html`, CSS, JS hoặc `slides/sections/`; kiểm tra đủ slide, console error, điều hướng và overflow.
- Với code runtime, chạy unit/contract/integration test tương ứng và benchmark đúng profile nếu thay đổi đường inference.
- Nếu không thể chạy một kiểm tra, không nói rằng đã pass; báo rõ lý do và rủi ro còn lại.

## 9. Git và an toàn khi thao tác

- Không commit, amend, push, force-push, tạo PR hoặc đổi branch nếu người dùng chưa yêu cầu.
- Không dùng `git reset --hard`, xóa/move hàng loạt hoặc ghi đè thay đổi người dùng.
- Trước khi stage, kiểm tra `git status` và bảo đảm không có cache/build artifact như `__pycache__`, PDF hoặc log.
- Commit phải mô tả outcome, không mô tả chung chung kiểu "update files".
- Không force-push lên `main`.

## 10. Cách báo cáo sau mỗi lần sửa

Phản hồi cuối phải ngắn gọn nhưng tự đủ thông tin, theo thứ tự:

1. **Kết quả:** Nêu outcome đã đạt được, không chỉ liệt kê thao tác.
2. **Tệp đã thay đổi:** Liệt kê các tệp chính và mục đích của từng nhóm thay đổi.
3. **Kiểm tra:** Ghi chính xác lệnh/test đã chạy và trạng thái pass/fail.
4. **Ảnh hưởng contract/artifact:** Cho biết contract, docs, PDF, slides, API hoặc schema nào đã được đồng bộ.
5. **Rủi ro/giới hạn:** Nêu warning, assumption, phần chưa kiểm tra hoặc việc cần người dùng quyết định.
6. **Git:** Chỉ báo commit/branch/push khi thao tác thực sự đã thành công.

Không nói "hoàn tất", "build sạch" hoặc "đã đồng bộ toàn bộ" nếu chưa có bằng chứng kiểm tra tương ứng. Khi gặp blocker, mô tả lỗi cụ thể, phần đã thử và quyền/thông tin còn thiếu; không âm thầm đổi scope để né lỗi.

## 11. Checklist trước khi bàn giao

- [ ] Thay đổi phù hợp mục tiêu decision-support và không mở đường cho automatic actuation.
- [ ] Không vi phạm tensor, feature order, API, SLA, stack hoặc safety contract.
- [ ] Không đưa thuật ngữ/công nghệ legacy trở lại active architecture.
- [ ] Dữ liệu nhạy cảm, raw video, SQL và citation được xử lý đúng policy.
- [ ] Source-of-truth và artifact dẫn xuất đã đồng bộ.
- [ ] Test phù hợp đã chạy và kết quả được báo trung thực.
- [ ] `git diff --check` pass; không có cache/build artifact bị stage.
- [ ] Báo cáo cuối nêu rõ outcome, file, test và rủi ro còn lại.
