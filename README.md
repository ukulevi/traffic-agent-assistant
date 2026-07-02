# SmartTraffic What-If (STWI)

STWI là MVP 13 tuần hỗ trợ người vận hành đánh giá kịch bản giao thông What-if bằng dự báo GCN–LSTM, surrogate ensemble, truy xuất pháp lý có citation và Counterfactual Safety Loop fail-closed.

## Nguồn sự thật

1. [`project_contract.json`](./project_contract.json): hằng số, shape, SLA, API và version máy đọc được.
2. [`docs/00_STWI_Summary_and_Guidelines.md`](./docs/00_STWI_Summary_and_Guidelines.md): kiến trúc và quy chuẩn.
3. STWI-DOC-01–05 trong [`docs/`](./docs/): đặc tả từng tầng và kế hoạch triển khai.

`report/chapters/`, `report/main.tex` và `slides/sections/` là artifact trình bày được đồng bộ từ nguồn trên. Tài liệu trong `docs/archive/` chỉ dùng tham khảo lịch sử.

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

PDF được build từ `report/main.tex`; slides GitHub Pages được nạp từ `slides/sections/` qua `slides/js/presentation.js`.

## Local vision detector

Tier 1 uses a local open-source detector artifact as the primary detector path.
A Roboflow dataset export is treated as offline validation/calibration data and
fallback fine-tuning data, not as an online runtime dependency. Store the
downloaded YOLO/Ultralytics dataset under:

```text
data/derived/private/vision_training/roboflow_v001
```

The directory must contain the Roboflow YOLO layout `train/images`,
`train/labels`, `valid/images`, `valid/labels`, `test/images`, `test/labels`.
Keep downloaded archives and raw exports under `data/external/roboflow/`; both
locations are ignored by git. Before training, generate an STWI-compatible
`dataset_manifest.json` with image/label records, hashes,
source/license/privacy notes, then validate:

```powershell
pip install -e .[vision]
python scripts/prepare_roboflow_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 --dataset-version roboflow_v001 --privacy-status needs_review --reviewer pending
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001 --allow-pending-review
python scripts/build_stwi_vehicle_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short
python scripts/augment_vehicle_dataset_with_motorcycle.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --annotated-source motorcycle.yolov8
python scripts/evaluate_vision_roi_ap.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --model yolo11s.pt --model-family yolo --output data/derived/private/vision_diagnostics/pretrained_yolo11s_val_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --model yolo11s.pt --epochs 6 --imgsz 416 --batch 16 --device 0 --name stwi_yolo11s_roboflow_v001_vehicles_fallback --model-version stwi_yolo11s_roboflow_v001_vehicles_fallback
```

Only promote a detector after validation/test metrics, latency, source license,
class mapping, thresholds, and privacy review are recorded. The official MVP
loader reads
`data/derived/private/vision_models/official/model_artifact.json`, which is
created by `scripts/promote_vision_model.py` only after the gate passes.
Detector output remains evidence for five-minute aggregates such as
`traffic_volume_5m`, `avg_speed_kmh`, and `heavy_vehicle_ratio`; it never creates
traffic-control actions.

See [`docs/vision_local_training_runbook.md`](./docs/vision_local_training_runbook.md)
for the local detector selection and calibration checklist.

## Optional Roboflow workflow inference

Tier 1 can call the Roboflow workflow `STWI Traffic Unified Phase 2 v1 Logic`
through `stwi.t1_pipeline.roboflow_workflow` only when hosted detection is
explicitly needed. The workflow source of truth is:

- Workspace: `lymphaticvesselsegmentation`
- Workflow id: `stwi-traffic-unified-phase-2-v1-logic`
- Input: `image`
- Declared output: loaded from the workflow definition, currently `predictions`

Set `ROBOFLOW_API_KEY` in the environment; never commit it. Install the vision
extra before live calls:

```powershell
pip install -e .[vision]
```

Example:

```python
from stwi.t1_pipeline.roboflow_workflow import (
    RoboflowImageInput,
    run_stwi_traffic_workflow,
)

result = run_stwi_traffic_workflow(
    RoboflowImageInput.https_url("https://example.com/frame.jpg"),
)
predictions = result.first()["predictions"]
```

Only use workflow detections as camera evidence for five-minute aggregates such
as `traffic_volume_5m` and `heavy_vehicle_ratio`. Do not log raw image payloads
or base64 visualization outputs.

## AI agent

Quy tắc làm việc bền vững nằm trong [AGENTS.md](./AGENTS.md). Các workflow Codex project-local nằm trong [.agents/skills](./.agents/skills): triển khai, review và release QA.
