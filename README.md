# SmartTraffic What-If (STWI)

STWI là MVP 13 tuần hỗ trợ người vận hành đánh giá kịch bản giao thông What-if bằng dự báo GCN–LSTM, surrogate ensemble, truy xuất pháp lý có citation và Counterfactual Safety Loop fail-closed.

## Nguồn sự thật

1. [`project_contract.json`](./project_contract.json): hằng số, shape, SLA, API và version máy đọc được.
2. [`docs/00_STWI_Summary_and_Guidelines.md`](./docs/00_STWI_Summary_and_Guidelines.md): kiến trúc và quy chuẩn.
3. STWI-DOC-01–05 trong [`docs/`](./docs/): đặc tả từng tầng và kế hoạch triển khai.

`chapters/`, `main.tex` và `sections/` là artifact trình bày được đồng bộ từ nguồn trên. Tài liệu trong `docs/archive/` chỉ dùng tham khảo lịch sử.

## Phạm vi MVP

- Mạng chức năng 20 node, tối đa 20 luồng camera ghi sẵn/RTSP.
- Kiểm thử tải bằng 1.000 producer aggregate tổng hợp.
- Không lưu video thô và không tự điều khiển thiết bị hiện trường.
- Surrogate P99 < 500 ms; E2E P95 ≤ 30 giây; hard deadline/P99 ≤ 180 giây.

## Kiểm tra

```powershell
python scripts/validate_docs.py
python -m unittest tests.test_project_contract
```

PDF được build từ `main.tex`; slides GitHub Pages được nạp từ `sections/` qua `js/presentation.js`.
