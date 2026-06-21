# STWI Documentation Index

| Thứ tự | Tài liệu | Vai trò |
|---|---|---|
| Contract | [`project_contract.json`](../project_contract.json) | Nguồn sự thật máy đọc được |
| DOC-00 | [Tổng hợp & Quy chuẩn](./00_STWI_Summary_and_Guidelines.md) | Kiến trúc và invariants |
| DOC-01 | [Data Pipeline](./01_System_Architecture_Data_Pipeline.md) | Tensor, feature, quality và privacy |
| DOC-02 | [ML & Simulation](./02_ML_and_Simulation_Specification.md) | GCN–LSTM, SUMO và surrogate |
| DOC-03 | [Knowledge & Query](./03_Knowledge_Base_and_RAG_Design.md) | Qdrant, pháp lý, QuerySpec và citations |
| DOC-04 | [Orchestrator & Safety](./04_AI_Agent_Orchestrator_CF_VLA.md) | Async API, SSE và Counterfactual Safety Loop |
| DOC-05 | [Implementation Plan](./05_Implementation_Plan.md) | Timeline và phase gates 13 tuần |

## Quy tắc thay đổi

- Cập nhật `project_contract.json` trước khi đổi shape, SLA, status hoặc công nghệ lõi.
- Cập nhật DOC tương ứng, changelog, báo cáo và slides trong cùng pull request.
- Chạy `python scripts/validate_docs.py` và contract tests trước khi merge.
- Nội dung trong [`archive/`](./archive/) không được dùng làm yêu cầu triển khai.
