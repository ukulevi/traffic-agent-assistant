# CHANGELOG — Đặc tả Kỹ thuật STWI

## [2026-06-21] — Chuẩn hóa MVP 13 tuần và toàn bộ artifact

- Thêm `project_contract.json` làm nguồn sự thật máy đọc được.
- Sửa input thành `X[B,12,N,16]`, missing mask `M[B,12,N,16]` và output `Y[B,6,N,2]`.
- Chuẩn hóa GCN–LSTM, SUMO scenario dataset, surrogate ensemble và uncertainty calibration.
- Đổi feature tín hiệu thành `green_time_ratio`; giới hạn demo 20 node và 1.000 aggregate producers tổng hợp.
- Chốt Qdrant, luật 35/2024/QH15 và 36/2024/QH15, typed SimulationQuery và structured citations.
- Định vị Counterfactual Safety Loop là cơ chế lấy cảm hứng từ CF-VLA; áp dụng fail-closed và human approval.
- Chuyển API sang async jobs + SSE với SLA P95 30 giây và hard deadline/P99 180 giây.
- Đồng bộ báo cáo LaTeX, slides, release notes và thêm validator CI.

Lịch sử chỉnh sửa tất cả các file đặc tả kỹ thuật.

---

## [2026-06-20] — Điều chỉnh toàn bộ docs theo review implementation plan

**Người thực hiện:** OWL Agent
**Phạm vi:** 6 file đặc tả kỹ thuật (DOC-00 đến DOC-05)

### Thay đổi chính

#### 1. Tech Stack cụ thể hóa
- **MQTT** là protocol chính cho IoT sensors (bỏ "hoặc REST polling")
- **Qdrant** cho Vector DB (bỏ "hoặc Milvus/Pinecone")
- **DuckDB** cho in-memory DB (bỏ "SQLite hoặc DuckDB")
- **LangGraph** cho Agent framework (bỏ "LangChain hoặc CrewAI")
- **TimescaleDB** cho time-series data (bỏ "InfluxDB hoặc PostgreSQL với TimescaleDB")
- **BGE-m3** cho embedding (giữ nguyên)
- **Text-to-SQL** (LLM + few-shot) thay vì XiYanSQL riêng

#### 2. Phase 0 mở rộng (DOC-05)
- **Task 0.4**: Data Contracts đầy đủ — tất cả schemas (InputTensor, IncidentVector, SimulationResult, LegalDocument, API request/response)
- **Task 0.6**: Mock Data Generators cho tất cả tầng (CCTV, Sensor, Graph, SOP, Corner Cases)
- **Task 0.7**: Fake Interfaces (ABC classes) để các phase phía sau không block
- Docker Compose thêm: TimescaleDB, MLflow, Qdrant

#### 3. Data Pipeline (DOC-01)
- **14 features chi tiết**: mỗi feature có type, range, encoding, mô tả
- **Cyclical encoding** cho time-of-day và day-of-week (sin/cos) — tránh artifact 23:59 gần 00:00
- **Data Validation Layer**: range check, NaN handling, camera offline detection
- **Mock Data Strategy** section mới

#### 4. ML & Simulation (DOC-02)
- **Baseline Models** (Sprint 2.2): Persistent Forecast, Historical Average — STGCN+LSTM phải tốt hơn 20% về RMSE
- **ADE → 3 sub-models ensemble** (Sprint 2.4): MLP, CNN-1D, Transformer nhẹ — đơn giản hơn ADE
- **Uncertainty estimation**: variance giữa 3 sub-models → flag `[⚠️ KHÔNG CHẮC CHẮN]`
- **Output shape rõ ràng**: `[B, 6, num_nodes]` — 6 bước × 5 phút = 30 phút tương lai
- **Corner Case Handling**: tích hợp vào Surrogate Model

#### 5. RAG (DOC-03)
- **XiYanSQL → Text-to-SQL** (LLM + few-shot): schema chỉ 1 bảng → không cần XiYanSQL riêng
- **Hybrid search**: BM25 + vector (không chỉ cosine similarity)
- **RealGen → Corner Case Retrieval**: tích hợp vào Surrogate Model (Tầng 2), Tầng 3 chỉ cung cấp database
- **Section mới**: Yêu cầu Dữ liệu Tri thức (owner, format, số lượng, fallback strategy)

#### 6. Agent & CF-VLA (DOC-04)
- **LangGraph** thay vì LangChain/CrewAI (hỗ trợ conditional edges và cycles)
- **Fallback Strategy**: sau 3 vòng lặp không hội tụ → xuất phương án tốt nhất + nhãn `[⚠️ CHƯA KIỂM CHỨNG]`
- **3 loại Response**: Success, Partial, Error (đầy đủ schema)
- **Error codes table**: TIMEOUT, INVALID_SCENARIO, SIMULATION_ERROR, KNOWLEDGE_ERROR, INTERNAL_ERROR
- **CF-VLA flow diagram** cập nhật với convergence check và fallback

#### 7. Implementation Plan (DOC-05)
- **Timeline**: 12 → 13 tuần
- **Integration Tests** tại mỗi giao điểm phase (Sprint 1.4, 2.5, 3.5)
- **Rủi ro mới**: R6 (dữ liệu pháp lý), R7 (Phase 1 delay)
- **Nguyên tắc vàng mới**: Mock data first, Integration tests tại mỗi giao điểm

### Files đã thay đổi

| File | Version | Thay đổi |
|------|---------|----------|
| `docs/00_STWI_Summary_and_Guidelines.md` | 1.1 → 1.2 | Tech stack cụ thể, mô tả tầng cập nhật |
| `docs/01_System_Architecture_Data_Pipeline.md` | 1.1 → 1.2 | 14 features chi tiết, cyclical encoding, validation, MQTT, mock data |
| `docs/02_ML_and_Simulation_Specification.md` | 1.1 → 1.2 | Baseline models, ADE → 3 sub-models, uncertainty, output shape |
| `docs/03_Knowledge_Base_and_RAG_Design.md` | 1.1 → 1.2 | XiYanSQL → Text-to-SQL, RealGen → Corner Case Retrieval, data requirements |
| `docs/04_AI_Agent_Orchestrator_CF_VLA.md` | 1.1 → 1.2 | LangGraph, fallback strategy, error/partial response, error codes |
| `docs/05_Implementation_Plan.md` | 1.0 → 1.1 | Phase 0 mở rộng, integration tests, timeline 13 tuần, rủi ro mới |

### Lý do thay đổi

1. **Giảm rủi ro**: Mock data + fake interfaces giúp các tầng phát triển độc lập
2. **Đơn giản hóa**: ADE → 3 sub-models, XiYanSQL → LLM few-shot — đạt 80% lợi ích với 20% effort
3. **Feasibility**: 12 tuần → 13 tuần, thêm integration tests để phát hiện bug sớm
4. **Production-ready**: Error handling, fallback strategy, validation layer
5. **Nhất quán**: Tất cả files tham chiếu đến cùng một tech stack
