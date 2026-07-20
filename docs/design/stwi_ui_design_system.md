# STWI MVP UI design system

> TRA-56 design handoff. This is derived guidance; [`project_contract.json`](../../project_contract.json) remains authoritative.

## Purpose and guardrails

The dashboard helps an operator understand a 30-minute **estimate**, its limits, evidence and citations before recording a human decision. It never sends a field command, changes a signal phase, stores or plays raw video, or treats a recommendation as automatically approved.

Use exactly 20 registered nodes. Keep the contract names `X[B,12,N,16]`, `M[B,12,N,16]`, `A[N,N]`, and `Y[B,6,N,2]` only as explanatory topology metadata, not as user tasks.

## Visual language

Load `stwi_ui_tokens.css`. Use `Be Vietnam Pro` for Vietnamese interface text and `Azeret Mono` for IDs, values, timestamps, versions and trace IDs. `#006699` is the primary action and navigation colour. Orange, blue, green and purple identify Data, ML, Knowledge/RAG and Safety respectively; they do not by themselves encode success or failure. Every status and OOD indicator has an icon and text label.

Cards have a modest radius and clear border; use shadow only to separate layers. Respect a 44×44px minimum pointer target, visible focus, semantic landmarks and a logical Tab order. Do not use glass effects, high-motion decoration or a dashboard that needs users to hunt for the conclusion.

## Reading order and responsive layout

At 1280px, keep the first decision-relevant viewport in this order:

1. Header: STWI, node picker/search, freshness, status text + icon.
2. Left 240px: the registered 20-node selector; filters can narrow it but cannot create a node.
3. Centre (minimum 560px): plain-language conclusion, 30-minute horizon and assumptions; then the two forecast outputs and evidence entry point.
4. Right 300px: uncertainty/OOD explanation, citation completeness and provenance/audit entry point.
5. Action gate: after evidence. The CTA is **Ghi nhận quyết định**, never a field command.

At 360px and 390px use one column with no horizontal scrolling: result first, uncertainty/OOD, evidence disclosure, citations/audit disclosure, then decision support. The 20-node selector opens as a drawer. Long IDs must wrap or offer copy. At 390px, a two-column metric pair is allowed only when labels and units remain readable.

## Plain-language labels

| Contract field | UI label | Required explanation |
|---|---|---|
| `traffic_volume_5m` | Lưu lượng giao thông | Số xe dự kiến đi qua trong mỗi 5 phút (`xe/5 phút`). |
| `avg_speed_kmh` | Tốc độ trung bình | Tốc độ dự kiến của dòng xe (`km/h`). |
| `capacity_version` | Phiên bản năng lực thông hành | Phiên bản dữ liệu dùng để tính tỷ lệ tải/năng lực. |
| V/C | Tỷ lệ tải/năng lực | `0.9` là policy MVP có thể cấu hình, không phải quy định pháp luật. |
| uncertainty | Độ không chắc chắn | Khoảng ước tính và lý do kết quả có thể thay đổi. |
| OOD | Cảnh báo dữ liệu khác thường | Nêu mức, nguyên nhân và khi nào cần operator xem xét. |

## Exact state and action matrix

| State | Vietnamese display | Result/action rule |
|---|---|---|
| `queued` | Đang xếp hàng | Chưa có kết quả; chỉ có thể hủy nếu API cho phép. |
| `running` | Đang phân tích | Hiển thị tiến độ và lần cập nhật gần nhất; không có action proposal. |
| `succeeded` | Hoàn tất | Hiển thị `recommended_action` chỉ khi citation bắt buộc đầy đủ; đó là đề xuất quyết định, không phải lệnh. |
| `needs_review` | Cần người vận hành xem xét | Chỉ hiển thị `candidate_action`, gắn nhãn “Ứng viên — không thể thực thi”. |
| `failed` | Thất bại an toàn | Nêu lỗi an toàn; chỉ hiện retry khi API cho phép. |
| `expired` | Hết hạn | Hiển thị thời điểm hết hạn và yêu cầu chạy lại. |

No other state is valid. `queued`, `running`, `failed`, and `expired` never show an action proposal. Missing source, timestamp, trace ID, model version, data version or legal validity where applicable suppresses `recommended_action` and leads to review/insufficient-evidence treatment. The required legal corpus is Luật 35/2024/QH15 and Luật 36/2024/QH15, both effective from 2025-01-01.

`empty` is a presentation condition, not a seventh job status: use it when no node/job is selected or no permitted data can be shown. It explains the next safe step (choose one of the 20 registered nodes or create a valid query) and contains no forecast, citation claim or action proposal.

## Prototype and interaction contract

The prototype demonstrates a static evidence render/detection summary only; it must have no video player or transport controls. `/` focuses node search, `Enter` opens the focused registered node, `Esc` closes a drawer/dialog, and `C` copies the trace ID. “Ghi nhận quyết định” opens an accessible confirmation dialog to record operator, timestamp, rationale and trace ID. It does not call a control endpoint.

### Handoff acceptance

- TRA-57 maps only the six states above and rejects/flags unknown status or node IDs.
- TRA-57 preserves units, capacity version, policy wording, citations and non-actuation action gating.
- TRA-55 tests 360/390/430/768/1024 layouts, keyboard navigation, focus trap/return, status/OOD text and WCAG AA contrast.
- Any future visual change must preserve the result → uncertainty/OOD → evidence → citations/audit reading order.
