# 🗄️ ARCHIVED — SMARTTRAFFIC WHAT-IF (STWI) INITIAL BLUEPRINT

> [!CAUTION]
> Tài liệu này chỉ lưu dấu ý tưởng ban đầu và không còn là nguồn sự thật. Kiến trúc hiện hành nằm trong `project_contract.json` và STWI-DOC-00–05. Các thuật ngữ, shape dữ liệu, timeline và cam kết quy mô bên dưới có thể đã lỗi thời.

* **Mô tả hệ thống:** Hệ thống hỗ trợ ra quyết định giao thông đô thị thông minh bằng cách tích hợp mô hình dự báo chuỗi thời gian không-thời gian, hệ thống truy xuất tri thức pháp lý (RAG) và tác tử thông minh (AI Agent) để xử lý các kịch bản giả định "What-if".
* **Trạng thái tài liệu:** Bản đặc tả kỹ thuật tổng thể (Tổng hợp 2026).
* **Mục tiêu cốt lõi:** Chuyển hóa các kịch bản ngôn ngữ tự nhiên từ người điều hành thành các số liệu mô phỏng chính xác và đề xuất phương án điều phối hợp pháp dưới 3 phút.

---

## 🏗️ PHẦN 1: KIẾN TRÚC HỆ THỐNG TOÀN DIỆN (SYSTEM ARCHITECTURE)

Hệ thống hoạt động dựa trên cơ chế Multi-modal Data Pipeline (Dòng dữ liệu đa nguồn) chuyển hóa thành hành động thông qua chu trình phối hợp khép kín giữa Số liệu và Ngôn ngữ.

### 1. Tầng Thu thập & Chuẩn hóa Dữ liệu (Data Pipeline)
* **Thị giác máy tính (CCTV Pipeline):** Xử lý luồng dữ liệu thời gian thực từ mạng lưới 1000 camera CCTV bằng mô hình YOLO (Object Detection) và ByteTrack (Multi-Object Tracking). Mỗi camera trích xuất dữ liệu định lượng theo chu kỳ 5 phút bao gồm: Lưu lượng xe (`traffic_volume`), vận tốc trung bình (`average_velocity`) và phân loại phương tiện (`vehicle_class`).
* **Cảm biến Môi trường & Khí tượng:** Thu thập liên tục nồng độ khí thải ($CO$, $CO_2$, $NO_x$, bụi mịn $PM_{2.5}, PM_{10}$) và các chỉ số thời tiết (nhiệt độ, độ ẩm, tốc độ gió). *Lưu ý kỹ thuật:* Tốc độ gió tỷ lệ nghịch với thời gian lưu giữ bụi mịn tại bề mặt giao lộ.
* **Chuẩn hóa dữ liệu:** Toàn bộ dữ liệu đa nguồn được xử lý qua bộ lọc MinMaxScaler về khoảng $(0, 1)$ và đóng gói thành một 3D Tensor có cấu trúc:
$$\text{Input Shape} = [\text{Batch Size}, \text{Time Steps}, \text{Features}]$$
    * `Batch Size`: Cấu hình mặc định là `32` hoặc `64` tùy thuộc hạ tầng GPU.
    * `Time Steps`: Lịch sử `12` bước thời gian gần nhất (tương đương 60 phút dữ liệu quá khứ).
    * `Features`: Ma trận `14` biến đặc trưng (Giao thông + Khí thải + Thời tiết).

### 2. Tầng Dự báo Số liệu & Giả lập (Numerical Simulation)
* **Mô hình cốt lõi (STGCN + LSTM):** Sử dụng kiến trúc lai Spatio-Temporal Graph Neural Network để phản ánh chính xác sự lan truyền giao thông. Mạng lưới đường phố được mô hình hóa thành đồ thị $G = (V, E)$. Lớp Graph Convolutional Network (GCN) trích xuất đặc trưng liên kết không gian (ví dụ: nghẽn nút giao này lan sang tuyến đường khác), trong khi các lớp Stacked LSTM (LSTM chồng tầng) chịu trách nhiệm học đặc trưng tích lũy thời gian của dòng xe.
* **Mô hình thay thế (Neural Surrogate Model):** Để giải quyết độ trễ lớn (Latency) khi chạy mô phỏng vi mô trực tiếp (như SUMO), hệ thống triển khai mô hình thay thế áp dụng thuật toán **ADE (Adversarial Diverse Deep Ensemble)**. Mô hình học sâu xấp xỉ này được huấn luyện đối kháng ngoại tuyến để dự báo chính xác các điểm biên cực trị (ùn tắc nặng hoặc giải tỏa dòng xe đột biến) với thời gian xử lý chưa tới 500ms.

### 3. Tầng Tri thức Đô thị (Retrieval-Augmented Generation - RAG)
* **Cơ sở dữ liệu Vector:** Lưu trữ toàn bộ Sổ tay quy trình vận hành sự cố (SOP) của Sở GTVT, Luật giao thông đường bộ, và các kịch bản ngập lụt/thiên tai lịch sử.
* **Schema-Level RAG với XiYanSQL:** Cho phép Agent sử dụng ngôn ngữ tự nhiên để truy vấn trực tiếp vào cơ sở dữ liệu có cấu trúc sau khi mô phỏng. Hệ thống tự động biên dịch câu hỏi tự nhiên thành câu lệnh SQL chính xác để truy xuất ma trận kết quả dự báo.
* **RealGen Component:** Sử dụng cơ chế RAG để truy xuất và tái tạo các kịch bản tương tác giao thông cận biên (Corner Cases) từ lịch sử để làm phong phú dữ liệu giả lập.

### 4. Tầng Tác tử Điều phối (AI Agent Orchestrator)
* **Bộ não điều khiển:** Phát triển trên nền tảng LangChain/CrewAI đóng vai trò "Trưởng phòng điều phối giao thông ảo".
* **Luồng suy luận tự phản biện (CF-VLA):** Khi nhận kịch bản "What-if", Agent tách nhiệm vụ thành luồng tính toán số liệu (gọi LSTM) và tra cứu pháp lý (gọi RAG). Trước khi hiển thị đề xuất lên Dashboard, Agent chạy một luồng lập luận phản thực tế giả lập tương lai (Self-Reflection) để kiểm tra xem hành động điều phối đó có gây ra hiện tượng "ù
