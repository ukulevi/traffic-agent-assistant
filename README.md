# SmartTraffic What-If (STWI)

STWI lÃ  MVP 13 tuáº§n há»— trá»£ ngÆ°á»i váº­n hÃ nh Ä‘Ã¡nh giÃ¡ ká»‹ch báº£n giao thÃ´ng What-if báº±ng dá»± bÃ¡o GCNâ€“LSTM, surrogate ensemble, truy xuáº¥t phÃ¡p lÃ½ cÃ³ citation vÃ  Counterfactual Safety Loop fail-closed.

## Nguá»“n sá»± tháº­t

1. [`project_contract.json`](./project_contract.json): háº±ng sá»‘, shape, SLA, API vÃ  version mÃ¡y Ä‘á»c Ä‘Æ°á»£c.
2. [`docs/00_STWI_Summary_and_Guidelines.md`](./docs/00_STWI_Summary_and_Guidelines.md): kiáº¿n trÃºc vÃ  quy chuáº©n.
3. STWI-DOC-01â€“05 trong [`docs/`](./docs/): Ä‘áº·c táº£ tá»«ng táº§ng vÃ  káº¿ hoáº¡ch triá»ƒn khai.

`report/chapters/`, `report/main.tex` vÃ  `slides/sections/` lÃ  artifact trÃ¬nh bÃ y Ä‘Æ°á»£c Ä‘á»“ng bá»™ tá»« nguá»“n trÃªn. TÃ i liá»‡u trong `docs/archive/` chá»‰ dÃ¹ng tham kháº£o lá»‹ch sá»­.

## Pháº¡m vi MVP

- Máº¡ng chá»©c nÄƒng 20 node, tá»‘i Ä‘a 20 luá»“ng camera ghi sáºµn/RTSP.
- Kiá»ƒm thá»­ táº£i báº±ng 1.000 producer aggregate tá»•ng há»£p.
- KhÃ´ng lÆ°u video thÃ´ vÃ  khÃ´ng tá»± Ä‘iá»u khiá»ƒn thiáº¿t bá»‹ hiá»‡n trÆ°á»ng.
- Surrogate P99 < 500 ms; E2E P95 â‰¤ 30 giÃ¢y; hard deadline/P99 â‰¤ 180 giÃ¢y.

## Kiá»ƒm tra

```powershell
python scripts/validation/validate_docs.py
python -m unittest tests.contracts.test_project_contract
```

PDF Ä‘Æ°á»£c build tá»« `report/main.tex`; slides GitHub Pages Ä‘Æ°á»£c náº¡p tá»« `slides/sections/` qua `slides/js/presentation.js`.

## Repository structure

Reusable code lives under `src/stwi/`; command-line entrypoints under `scripts/`
should stay thin wrappers around importable modules. See
[`docs/guides/repository_structure.md`](./docs/guides/repository_structure.md)
for the current layout and vision-tooling ownership rules.

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
python scripts/data_prep/prepare_roboflow_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 --dataset-version roboflow_v001 --privacy-status needs_review --reviewer pending
python scripts/validation/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001 --allow-pending-review
python scripts/data_prep/build_stwi_vehicle_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short
python scripts/validation/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short
python scripts/data_prep/augment_vehicle_dataset_with_motorcycle.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --annotated-source motorcycle.yolov8
python scripts/validation/evaluate_vision_roi_ap.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --model yolo11s.pt --model-family yolo --output data/derived/private/vision_diagnostics/pretrained_yolo11s_val_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0
python scripts/training/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --model yolo11s.pt --epochs 6 --imgsz 416 --batch 16 --device 0 --name stwi_yolo11s_roboflow_v001_vehicles_fallback --model-version stwi_yolo11s_roboflow_v001_vehicles_fallback
```

Only promote a detector after validation/test metrics, latency, source license,
class mapping, thresholds, and privacy review are recorded. The official MVP
loader reads
`data/derived/private/vision_models/official/model_artifact.json`, which is
created by `scripts/training/promote_vision_model.py` only after the gate passes.
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

## Comprehensive Hybrid Demo

See [docs/guides/mvp_demo_runbook.md](./docs/guides/mvp_demo_runbook.md) for the 8-10 minute showcase sequence, the 17-capability matrix, recovery steps, and the aggregate-only evidence boundary.

The approved solo-project demo is simulation-first: versioned synthetic
five-minute time series feed the baseline model and offline Eclipse SUMO runs
feed the scenario surrogate. This mode never claims real sensor observations,
field calibration, production accuracy, or automatic actuation. Validate the
boundary with:

```powershell
python scripts/validation/validate_demo_simulation_scope.py
python scripts/demo/run_mvp_smoke.py --profile offline --output C:\tmp\stwi-offline-evidence.json
```

The optional `services` profile probes Docker, Redis/Celery, Qdrant and
TimescaleDB without mock fallback. Its verdict may be `pass`, `fail`, or
`incomplete` when a capability is `not_verified`; it is not a production
readiness declaration.

## AI agent

Quy táº¯c lÃ m viá»‡c bá»n vá»¯ng náº±m trong [AGENTS.md](./AGENTS.md). CÃ¡c workflow Codex project-local náº±m trong [.agents/skills](./.agents/skills): triá»ƒn khai, review vÃ  release QA.
