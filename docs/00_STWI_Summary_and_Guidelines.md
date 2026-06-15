# 🚦 STWI — TÀI LIỆU TỔNG HỢP & QUY CHUẨN DỰ ÁN

| Thuộc tính | Giá trị |
|---|---|
| **Dự án** | SmartTraffic What-If (STWI) |
| **Mã tài liệu** | STWI-DOC-00 |
| **Phiên bản** | 1.1 |
| **Ngày tạo** | 15/06/2026 |
| **Cập nhật lần cuối** | 15/06/2026 |
| **Trạng thái** | 📝 Đang soạn thảo (Draft) |
| **Phân loại** | Tài liệu nội bộ — Báo cáo tiến độ |

> [!NOTE]
> Đây là tài liệu "Kim chỉ nam" tóm tắt bức tranh toàn cảnh về kiến trúc, luồng xử lý và các quy chuẩn phát triển (Rules) bắt buộc tuân theo cho toàn bộ đội ngũ lập trình và vận hành dự án STWI.

---

## Mục lục

- [1. Tổng hợp Kiến trúc Hệ thống](#1-tổng-hợp-kiến-trúc-hệ-thống)
- [2. Quy trình Luồng Xử lý (Workflow Pipeline)](#2-quy-trình-luồng-xử-lý-workflow-pipeline)
- [3. Các Quy chuẩn Kỹ thuật Bắt buộc](#3-các-quy-chuẩn-kỹ-thuật-bắt-buộc)
- [4. Tài liệu Tham khảo](#4-tài-liệu-tham-khảo)
- [Phụ lục: Lịch sử Phiên bản](#phụ-lục-lịch-sử-phiên-bản)

---

## 1. Tổng hợp Kiến trúc Hệ thống

Hệ thống STWI được cấu trúc thành **4 phân tầng (Tiers)** tương tác chặt chẽ tạo thành một chu trình khép kín, chuyển hóa từ Dữ liệu thô (Raw Data) -> Dự báo số liệu (Prediction) -> Tri thức pháp lý (Legal Knowledge) -> Hành động điều phối (Action).

### Sơ đồ Kiến trúc Tổng quan

```mermaid
graph TB
    subgraph T1 [Tầng 1 - Thu Thập & Chuẩn Hóa Dữ Liệu]
        A1["📹 CCTV x 1000\nYOLO + ByteTrack"]
        A2["🌡️ Cảm biến Môi trường\nCO, NOx, PM2.5"]
        A3["☁️ Trạm Khí tượng\nNhiệt, Ẩm, Gió"]
        A4["⚙️ Data Normalization\nMinMaxScaler -> 3D Tensor"]
    end

    subgraph T2 [Tầng 2 - Dự Báo & Giả Lập]
        B1["🧠 STGCN + Stacked LSTM\nSpatial-Temporal Learning"]
        B2["⚡ Surrogate Model ADE\nInference < 500ms"]
    end

    subgraph T3 [Tầng 3 - Tri Thức Đô Thị]
        C1["📚 Vector Database\nSOP + Luật GTĐB"]
        C2["🔍 XiYanSQL\nText-to-SQL"]
        C3["🔄 RealGen\nCorner Case Retrieval"]
    end

    subgraph T4 [Tầng 4 - Tác Tử Điều Phối]
        D1["🤖 Orchestrator\nLangChain / CrewAI"]
        D2["🧪 Simulation Agent"]
        D3["⚖️ Legal Agent"]
        D4["📊 Evaluation Agent"]
        D5["🔁 CF-VLA\nCounterfactual Reflection"]
    end

    A1 --> A4
    A2 --> A4
    A3 --> A4
    A4 --> B1
    B1 --> B2
    B2 --> D2
    C1 --> C2
    C2 --> D3
    C3 --> D2
    D1 --> D2
    D1 --> D3
    D1 --> D4
    D4 --> D5
    D5 --> E["📺 Dashboard / Operator"]
    D5 --> D4

    style A4 fill:#1e3a5f,stroke:#4a9eff,color:#fff
    style B2 fill:#1e3a5f,stroke:#4a9eff,color:#fff
    style D5 fill:#5c2d00,stroke:#ff9500,color:#fff
    style E fill:#1a4d1a,stroke:#4ade80,color:#fff
```

### Mô tả từng Tầng

| Tầng | Tên gọi | Mô tả ngắn gọn | Tài liệu chi tiết |
|------|---------|-----------------|---------------------|
| **1** | Thu Thập & Chuẩn Hóa Dữ Liệu | Thu thập từ Camera CCTV (YOLO, ByteTrack) và Cảm biến. Chuẩn hóa thành `3D Tensor` chứa lịch sử 60 phút. | [📄 01_System_Architecture](./01_System_Architecture_Data_Pipeline.md) |
| **2** | Dự Báo & Giả Lập | Kiến trúc lai `STGCN + Stacked LSTM` cho đặc trưng Không gian-Thời gian. Surrogate Model `ADE` giả lập kịch bản với tốc độ < 500ms. | [📄 02_ML_and_Simulation](./02_ML_and_Simulation_Specification.md) |
| **3** | Tri Thức Đô Thị (RAG) | Vector Database lưu trữ SOP & Luật GTĐB. `XiYanSQL` chuyển text -> SQL truy vấn số liệu. `RealGen` tái tạo kịch bản biên. | [📄 03_Knowledge_Base_RAG](./03_Knowledge_Base_and_RAG_Design.md) |
| **4** | Tác Tử Điều Phối | Khung `Multi-Agent` với 3 tác tử con. Lõi suy luận `CF-VLA` tự phản biện trước khi hành động. | [📄 04_AI_Agent_CF-VLA](./04_AI_Agent_Orchestrator_CF_VLA.md) |

---

## 2. Quy trình Luồng Xử lý (Workflow Pipeline)

Quy trình End-to-End từ khi Người điều hành (Operator) nhập một kịch bản "What-if" cho đến khi xuất báo cáo hành động:

### Sơ đồ Luồng Xử lý

```mermaid
sequenceDiagram
    actor OP as 👤 Operator
    participant ORC as 🤖 Orchestrator
    participant SIM as 🧪 Simulation Agent
    participant T2 as ⚡ Tầng 2 (ADE)
    participant LEG as ⚖️ Legal Agent
    participant T3 as 📚 Tầng 3 (RAG)
    participant EVA as 📊 Evaluation Agent
    participant DB as 📺 Dashboard

    OP->>ORC: Kịch bản What-if
    Note over OP,ORC: "Nếu đóng ngã tư A do tai nạn,<br/>dòng xe chuyển sang đường B thì sao?"

    Note over ORC,T2: Bước 1-2: Phân rã & Mô phỏng
    ORC->>SIM: Giao nhiệm vụ mô phỏng
    ORC->>LEG: Giao nhiệm vụ tra cứu pháp lý
    SIM->>T2: Nạp Tensor 3D + Vector sự cố
    T2-->>SIM: Ma trận lưu lượng dự báo (< 500ms)

    Note over LEG,T3: Bước 3: Truy xuất Tri thức
    LEG->>T3: XiYanSQL -> Truy vấn In-memory DB
    T3-->>LEG: Số liệu + SOP liên quan

    Note over EVA,T2: Bước 4: Suy luận CF-VLA
    EVA->>EVA: Đề xuất phương án sơ bộ
    EVA->>T2: Counterfactual Reflection<br/>(Kiểm tra Cascade Congestion tại nút C)
    T2-->>EVA: V/C ratio nút C
    alt V/C <= 0.9 (An toàn)
        EVA->>DB: ✅ Xuất phương án lên Dashboard
    else V/C > 0.9 (Không an toàn)
        EVA->>EVA: 🔁 Hiệu chỉnh phương án
        EVA->>T2: Mô phỏng lại với phương án mới
    end

    DB-->>OP: Báo cáo + Đề xuất hành động
```

### Mô tả chi tiết từng Bước

| Bước | Tên gọi | Mô tả |
|------|---------|-------|
| **1** | Tiếp nhận & Phân rã | Operator nhập kịch bản. Orchestrator phân tích và giao việc cho Simulation Agent & Legal Agent. |
| **2** | Xử lý Số liệu | Simulation Agent kích hoạt Tầng 2. Nạp dữ liệu hiện tại (Tensor 3D) + Vector sự cố. Surrogate Model dự báo và đẩy kết quả vào In-memory DB. |
| **3** | Truy xuất Tri thức | Legal Agent dùng `XiYanSQL` truy vấn số liệu từ In-memory DB. Đồng thời search Vector DB lấy SOP quy định xử lý sự cố. |
| **4** | Suy luận CF-VLA | Evaluation Agent đề xuất phương án -> Kích hoạt phản biện Counterfactual -> Kiểm tra Cascade Congestion tại các nút lân cận. |
| **5** | Xuất Báo cáo | Nếu V/C <= 0.9: xuất phương án lên Dashboard. Nếu V/C > 0.9: vòng lặp quay lại Bước 4 để hiệu chỉnh. |

---

## 3. Các Quy chuẩn Kỹ thuật Bắt buộc

> [!CAUTION]
> Toàn bộ code và thiết kế hệ thống **PHẢI** tuân thủ nghiêm ngặt các quy chuẩn dưới đây. Vi phạm bất kỳ quy chuẩn nào đều yêu cầu review lại bởi Hội đồng Kiến trúc.

### 3.1. Quy chuẩn Độ trễ (Latency Limits)

| Chỉ số | Ngưỡng bắt buộc | Ghi chú |
|--------|------------------|---------|
| Tổng thời gian phản hồi End-to-End | **< 3 phút** | Từ khi nhận câu lệnh What-if -> Xuất báo cáo |
| Thời gian suy luận lõi AI (TTP) | **< 500ms** | Tầng 2 — Surrogate Model inference, đo tại P99 |

### 3.2. Quy chuẩn Dữ liệu (Data Integrity)

| Quy tắc | Chi tiết |
|---------|----------|
| Chuẩn hóa | Toàn bộ pipeline tiền xử lý phải qua `MinMaxScaler` đưa features về dải `(0, 1)` |
| Input Tensor Shape | Bắt buộc: `[Batch Size, 12, 14]` — 12 Time Steps x 14 Features |
| Thay đổi cấu trúc | Mọi thay đổi shape Tensor phải thông qua Hội đồng Kiến trúc phê duyệt |

### 3.3. Quy chuẩn An toàn Điều phối (CF-VLA Enforcements)

> [!WARNING]
> **KHÔNG BAO GIỜ** được bypass (bỏ qua) luồng tự phản biện Counterfactual. Đây là lớp an toàn cuối cùng trước khi đưa ra đề xuất cho Operator.

- Phương án đầu ra (Final Action) chỉ được chấp thuận nếu tỷ lệ **V/C (Volume / Capacity)** tại **tất cả** các nút lân cận sau khi phân luồng nhỏ hơn **`0.9`** (ngưỡng an toàn).
- Nếu vượt ngưỡng, hệ thống phải tự động kích hoạt vòng lặp hiệu chỉnh.

### 3.4. Quy chuẩn Tri thức (No-Hallucination Policy)

> [!IMPORTANT]
> Mọi đề xuất của Agent phải có căn cứ pháp lý. Tuyệt đối không chấp nhận "sáng tạo" thiếu kiểm chứng.

- Các đề xuất phân luồng/can thiệp giao thông **phải đi kèm Trích dẫn căn cứ pháp lý** (Legal Grounding) — Ví dụ: *Dựa trên khoản X Điều Y, hoặc theo SOP số Z*.
- Agent **không được phép** tự bịa (hallucinate) quyền hạn điều phối nếu chưa tham chiếu qua Tầng 3 (RAG).
- Mọi phương án "sáng tạo" ngoài SOP phải được dán nhãn: **`[⚠️ CẢNH BÁO — CHƯA KIỂM CHỨNG]`**

---

## 4. Tài liệu Tham khảo

| # | Tài liệu | Đường dẫn |
|---|----------|-----------|
| 1 | Kiến trúc Hệ thống & Data Pipeline | [01_System_Architecture_Data_Pipeline.md](./01_System_Architecture_Data_Pipeline.md) |
| 2 | Đặc tả Mô hình ML & Mô phỏng | [02_ML_and_Simulation_Specification.md](./02_ML_and_Simulation_Specification.md) |
| 3 | Thiết kế Cơ sở Tri thức & RAG | [03_Knowledge_Base_and_RAG_Design.md](./03_Knowledge_Base_and_RAG_Design.md) |
| 4 | Đặc tả Tác tử AI & CF-VLA | [04_AI_Agent_Orchestrator_CF_VLA.md](./04_AI_Agent_Orchestrator_CF_VLA.md) |
| 5 | Bản Idea Plan gốc (Blueprint) | [gemini-code-1781508694335.md](./gemini-code-1781508694335.md) |

---

## Phụ lục: Lịch sử Phiên bản

| Phiên bản | Ngày | Tác giả | Mô tả thay đổi |
|-----------|------|---------|-----------------|
| 1.0 | 15/06/2026 | Nhóm STWI | Soạn thảo ban đầu |
| 1.1 | 15/06/2026 | Nhóm STWI | Chuẩn hóa format doanh nghiệp, sửa lỗi Mermaid render, bỏ rect blocks trong sequence diagram |
