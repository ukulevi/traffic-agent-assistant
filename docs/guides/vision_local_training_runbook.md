# STWI Local Vision Training Runbook

This runbook describes how to use downloaded/private image datasets for local
detector selection, calibration, and fallback fine-tuning while keeping STWI's
runtime architecture unchanged.

## Scope

- The dataset is offline perception validation/calibration data for Tier 1
  first, and fallback fine-tuning data only when pretrained models fail the
  gate.
- The primary runtime detector is a local open-source detector loaded from a
  private model artifact.
- Roboflow hosted workflow inference remains optional and must not be required
  for demo or deployment.
- Detector output is converted into five-minute aggregate evidence:
  `traffic_volume_5m`, `avg_speed_kmh`, and `heavy_vehicle_ratio`.
- The detector never creates `recommended_action`, never bypasses the safety
  loop, and never sends commands to field devices.

## Pretrained-First Pivot

Long local training runs have plateaued around `mAP50` 0.69 on the preserved
validation split, below the MVP promotion gate of 0.85. For the next iteration,
prefer open-source pretrained detectors and tune only configuration that can be
validated quickly: class mapping, prompts, confidence thresholds, ROI/min-area
policy, image size, and export/runtime format. Keep the local reviewed dataset
as the acceptance test; do not claim production readiness from COCO/public
benchmark metrics alone.

Researched sources on 2026-07-01:

| Candidate | Source | License | STWI fit | Recommended use |
|---|---|---|---|---|
| YOLO11 `yolo11s.pt`/`yolo11m.pt` | Ultralytics docs and Hugging Face model card | AGPL-3.0 or commercial | COCO includes `car`, `motorcycle`, `bus`, `truck`; strong speed/accuracy tradeoff | First benchmark if AGPL/commercial terms are acceptable |
| RT-DETR `PekingU/rtdetr_r50vd_coco_o365` | Hugging Face model card and RT-DETR paper | Apache-2.0 | COCO/Objects365 pretrained, strong AP50 and no NMS; heavier than YOLO on GTX 1050 Ti | Best permissive-license candidate for local evaluation |
| YOLO-World v2 | Ultralytics docs and YOLO-World paper | AGPL-3.0 or upstream license constraints | Open-vocabulary prompts can focus on STWI classes without retraining | Fast prompt-based ablation; useful if class naming/domain shift hurts COCO IDs |
| Grounding DINO tiny/base | Hugging Face model cards and paper | Apache-2.0 | Zero-shot prompts, strong label-assist behavior, slower runtime | Use for review/label-assist or fallback evidence, not default real-time path |

Reference URLs:

- YOLO11: `https://docs.ultralytics.com/models/yolo11/`,
  `https://huggingface.co/Ultralytics/YOLO11`
- RT-DETR: `https://huggingface.co/PekingU/rtdetr_r50vd_coco_o365`,
  `https://arxiv.org/abs/2304.08069`
- YOLO-World: `https://docs.ultralytics.com/models/yolo-world/`,
  `https://arxiv.org/abs/2401.17270`
- Grounding DINO: `https://huggingface.co/IDEA-Research/grounding-dino-base`,
  `https://huggingface.co/IDEA-Research/grounding-dino-tiny`

### Benchmark order

1. Evaluate `yolo11s.pt`, `yolo11m.pt`, and the existing `yolov8s.pt` as
   pretrained COCO baselines without fine-tuning. Use name-based mapping from
   detector output to STWI classes.
2. Evaluate RT-DETR R50 when the `transformers`/Ultralytics runtime path is
   available locally. Prefer this route if license simplicity matters more than
   lowest latency.
3. Evaluate YOLO-World with prompts `car`, `motorcycle`, `bus`, `truck`, then
   with vehicle-specific aliases only if validation errors show prompt drift.
4. Use Grounding DINO to generate review candidates for missed small objects
   and class confusions, not as the first live detector.

Use the existing AP evaluator for Ultralytics-compatible candidates:

```powershell
python scripts/evaluate_vision_roi_ap.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model yolo11s.pt --model-family yolo --output data/derived/private/vision_diagnostics/pretrained_yolo11s_val_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0
python scripts/evaluate_vision_roi_ap.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model yolov8s-worldv2.pt --model-family yolo_world --prompt-class car --prompt-class motorcycle --prompt-class bus --prompt-class truck --output data/derived/private/vision_diagnostics/pretrained_yoloworld_s_val_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0
```

If a pretrained candidate clears or approaches the gate, run the same evaluator
on `test`, record latency on representative hardware, then create a reviewed
model artifact with source model, license, checksum, class map, thresholds, ROI
policy, validation/test metrics, and privacy status. Only promote after the
same `mAP50 >= 0.85` gate and privacy review pass.

### Pretrained benchmark results

The first pretrained-only evaluation used the reviewed label-fix validation
split
`roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix`,
`imgsz=640`, `conf=0.05`, IoU 0.5, and name-based mapping to STWI classes. These
results are diagnostic AP50 values from `scripts/evaluate_vision_roi_ap.py`, not
Ultralytics training-run gate artifacts.

| Candidate | Scope | mAP50_roi | bus | car | motorcycle | truck | Seconds/image | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `yolo11m.pt` | full val, 2,668 images | 0.4192 | 0.3227 | 0.5663 | 0.2811 | 0.5066 | 0.0559 | Best pretrained-only fallback, not promotable |
| `yolo11x.pt` | sample val, 50 images | 0.3910 | 0.4444 | 0.5363 | 0.2500 | 0.3333 | 0.4770 CPU | Larger generic model; too slow on CPU and still far below gate |
| `yolov8m.pt` | full val, 2,668 images | 0.4069 | 0.3265 | 0.5818 | 0.2025 | 0.5170 | 0.0544 | Slightly behind YOLO11m |
| `yolov8s-worldv2.pt` prompts `car,motorcycle,bus,truck` | full val, 2,668 images | 0.2830 | 0.1803 | 0.4357 | 0.2017 | 0.3144 | 0.0322 | Fast prompt baseline, weak AP |
| `rtdetr-l.pt` | sample val, 200 images | 0.3389 | 0.3973 | 0.5693 | 0.2565 | 0.1326 | 0.1317 | Slower; do not full-run unless thresholds/variant change |

Conclusion: pretrained-only detectors reduce setup time but do not currently
replace the best fine-tuned YOLOv8s candidate (`mAP50` about 0.6902). For MVP,
use `yolo11m.pt` as the first external fallback/base candidate and keep
YOLO-World/Grounding DINO for label-assist and error review. Do not promote any
pretrained-only candidate until it clears the same validation/test gate.

### Domain-specific open-source search

Domain-specific weights from Hugging Face or GitHub can be evaluated, but they
must pass the same STWI acceptance gate as locally fine-tuned weights. Public
traffic/vehicle metrics are not enough: every candidate needs a local
validation run on the preserved STWI split, a clear source license, a usable
class map, and a runtime artifact path that does not require hosted inference.

Initial Hugging Face search terms on 2026-07-01 found these candidates for the
next network-enabled benchmark pass:

| Candidate | Observed source fit | License signal | Evaluation decision |
|---|---|---|---|
| `gayatrigovindasetty/vehicle-detection-yolov8` | Vehicle-focused YOLOv8n model; model card lists `Auto`, `Bus`, `Car`, `LCV`, `Motorcycle`, `Multiaxle`, `Tractor`, `Truck` and reports `mAP@0.5 > 85%` on its own dataset. The files tab contains `best.pt` (about 6.25 MB, SHA256 `482f0782bc283651ff8365612c01097b4ab4ff3974d103ab03fd3b4b166456ac`). | Model card reports MIT | Highest-priority domain candidate because it covers `bus`, `car`, `motorcycle`, and `truck`; benchmark locally before trusting the public metric |
| `vietnguyennn0705/highway-vehicle-detection` | Highway YOLOv8m model; card lists 8,219 highway images, Stage-2 truck/bus fine-tuning, and the same 8 vehicle classes | Model card reports MIT | Good domain wording, but must pass local STWI validation because highway/source camera geometry may still differ |
| `lukasiktar11/traffic_vehicle_detection` and `traffic_vehicle_detection2` | Traffic vehicle detector, ONNX-oriented | Model tags report AGPL-3.0 | Evaluate only if metadata embeds or documents class names; otherwise keep as reference |
| `mshamrai/yolov8s-visdrone` / `mshamrai/yolov8m-visdrone` | VisDrone vehicle classes include car, truck, bus, and `motor` | License/class map must be confirmed from model card | Evaluate with `motor:motorcycle`; do not map `van` to `truck` unless explicitly accepted |
| `dronefreak/visdrone-yolov8m` / `visdrone-yolov8x` | VisDrone model card lists `best.pt`, Apache-2.0, classes including `car`, `truck`, `bus`, and `motor`; reported VisDrone mAP@50 for YOLOv8m is 34.39 | Model card reports Apache-2.0 | Lower-priority runtime candidate because domain is aerial and reported AP is weak; useful as a permissive-license label-assist/ablation |

The evaluator supports class aliases so external class names can be compared
against the STWI class contract without modifying source labels:

```powershell
python scripts/evaluate_vision_roi_ap.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_external_models/<candidate>/weights.pt --model-family yolo --output data/derived/private/vision_diagnostics/<candidate>_val_sample200_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0 --max-images 200 --class-alias motor:motorcycle
```

Fetch each external weight with checksum verification, then register it before
benchmarking so license, class map, and promotion gate evidence are tracked:

```powershell
python scripts/fetch_external_vision_model.py --url https://huggingface.co/gayatrigovindasetty/vehicle-detection-yolov8/resolve/main/best.pt --output data/derived/private/vision_external_models/gayatrigovindasetty_vehicle_detection_yolov8/best.pt --expected-sha256 482f0782bc283651ff8365612c01097b4ab4ff3974d103ab03fd3b4b166456ac
python scripts/register_external_vision_model.py --model-id gayatrigovindasetty/vehicle-detection-yolov8 --source-url https://huggingface.co/gayatrigovindasetty/vehicle-detection-yolov8 --source-license mit --weights data/derived/private/vision_external_models/gayatrigovindasetty_vehicle_detection_yolov8/best.pt --model-family yolo --source-class Auto --source-class Bus --source-class Car --source-class LCV --source-class Motorcycle --source-class Multiaxle --source-class Tractor --source-class Truck --class-map Bus:bus --class-map Car:car --class-map Motorcycle:motorcycle --class-map Truck:truck --reviewer operator-reviewer --notes "HF model card reports MIT and mAP@0.5 > 85 on source dataset; requires local STWI validation before promotion."
python scripts/register_external_vision_model.py --model-id dronefreak/visdrone-yolov8m --source-url https://huggingface.co/dronefreak/visdrone-yolov8m --source-license apache-2.0 --weights data/derived/private/vision_external_models/dronefreak_visdrone_yolov8m/best.pt --model-family yolo --source-class pedestrian --source-class people --source-class bicycle --source-class car --source-class van --source-class truck --source-class tricycle --source-class awning-tricycle --source-class bus --source-class motor --class-map car:car --class-map truck:truck --class-map bus:bus --class-map motor:motorcycle --class-alias motor:motorcycle --reviewer operator-reviewer --notes "VisDrone Apache-2.0 candidate; aerial-domain ablation only unless local STWI validation beats the current candidate."
```

Then benchmark the registered manifest. Start with a 200-image validation sample
to avoid wasting GPU time on weak candidates. A sample result is never
promotable; it only decides whether to run the full gate:

```powershell
python scripts/benchmark_external_vision_model.py --manifest data/derived/private/vision_external_models/gayatrigovindasetty_vehicle-detection-yolov8/external_model_manifest.json --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --output data/derived/private/vision_diagnostics/external_gayatri_vehicle_yolov8_val_sample200_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0 --max-images 200 --baseline-map50 0.6902
```

Only if the sample beats the current best candidate should it get full
validation/test runs:

```powershell
python scripts/benchmark_external_vision_model.py --manifest data/derived/private/vision_external_models/gayatrigovindasetty_vehicle-detection-yolov8/external_model_manifest.json --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --output data/derived/private/vision_diagnostics/external_gayatri_vehicle_yolov8_val_full_conf005 --split val --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0 --baseline-map50 0.6902
python scripts/benchmark_external_vision_model.py --manifest data/derived/private/vision_external_models/gayatrigovindasetty_vehicle-detection-yolov8/external_model_manifest.json --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --output data/derived/private/vision_diagnostics/external_gayatri_vehicle_yolov8_test_full_conf005 --split test --conf 0.05 --iou-threshold 0.5 --imgsz 640 --device 0 --baseline-map50 0.6902
```

`benchmark_external_vision_model.py` writes
`external_benchmark_summary.json` with the external model metadata, local AP50,
latency, and verdict. It does not promote a model. Promotion still requires
the existing `scripts/promote_vision_model.py` path after metrics, source
license, class map, privacy review, thresholds, and human approval are complete.

The first verified external-weight samples did not clear the local gate:

| Candidate | Local scope | mAP50_roi | Seconds/image | Verdict |
|---|---:|---:|---:|---|
| `gayatrigovindasetty/vehicle-detection-yolov8` narrow STWI map | 200 validation images, CPU, `conf=0.05` | 0.0000 | 0.0464 | Reject; only 17 predictions and no true positives |
| `gayatrigovindasetty/vehicle-detection-yolov8` generous `auto/lcv/multiaxle/tractor` alias ablation | 200 validation images, CPU, `conf=0.001` | 0.0002 | 0.0479 | Reject; class aliasing and lower threshold do not fix domain mismatch |
| `vietnguyennn0705/highway-vehicle-detection` narrow STWI map | 200 validation images, CPU, `conf=0.05` | 0.0013 | 0.1846 | Reject; highway model card/domain wording does not transfer to STWI validation |
| `vietnguyennn0705/highway-vehicle-detection` generous alias ablation | 200 validation images, CPU, `conf=0.001` | 0.0022 | 0.1898 | Reject; low confidence and broad class aliases still miss local boxes |
| `dronefreak/visdrone-yolov8x` with `motor:motorcycle` | 50 validation images, CPU, `conf=0.05` | 0.0377 | 0.5142 | Reject as runtime candidate; useful only as label-assist/ablation |

Current decision: no tested pretrained or HF/GitHub external model is eligible
for MVP promotion. Keep `stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6` as
the best measured candidate and keep `yolo11m.pt` only as a generic
fallback/base candidate. The external search should now pause unless a model is
trained on fixed CCTV/roadside camera viewpoints with explicit `car`, `bus`,
`truck`, and motorcycle/motorbike classes plus downloadable weights and license
metadata. Generic highway, COCO repackages, larger COCO models, and aerial
VisDrone weights have not transferred to the preserved STWI validation split.

## Dataset Location

Place the exported YOLOv8/Ultralytics dataset at:

```text
data/derived/private/vision_training/roboflow_v001
```

Expected structure:

```text
dataset.yaml
train/images
train/labels
valid/images
valid/labels
test/images
test/labels
```

If Roboflow downloaded `data.yaml`, keep it in place and generate the STWI
manifest plus Ultralytics `dataset.yaml` with the prepare script:

```powershell
python scripts/prepare_roboflow_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 --dataset-version roboflow_v001 --privacy-status needs_review --reviewer pending --notes "Roboflow export prepared for local training; privacy review required before official promotion."
```

Keep downloaded zip files or untouched exports under:

```text
data/external/roboflow/
```

Both paths are ignored by git.

## Manifest Checklist

Before training, create or update `dataset_manifest.json` in the dataset root
with:

- dataset version, for example `roboflow_v001`;
- source workspace/project/version and export format;
- download timestamp and archive checksum;
- class list and class mapping to STWI vehicle classes;
- split counts and image counts;
- license/usage note;
- privacy review status;
- reviewer notes for any real camera frame or sensitive image source.

The current validator expects an STWI-compatible manifest with `classes` and a
`records` list. Each record must point to an image/label pair, include the split,
source type, object count, and image `sha256`. If a raw Roboflow export does not
include this manifest, create it before running validation; do not train directly
from an untracked export. The prepare script also converts any YOLO segmentation
polygon labels to normalized detection boxes and records the conversion count in
`dataset_manifest.json`.

## Validation And Training

Install the vision extra once:

```powershell
pip install -e .[vision]
```

Run dataset validation. During initial inspection, pending review is allowed:

```powershell
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001 --allow-pending-review
```

Before promoting weights, privacy review must be finalized and validation must
run without `--allow-pending-review`:

```powershell
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001
```

Build the MVP vehicle-only dataset so metrics and promotion gates focus on
`bus`, `car`, `motorcycle`, and `truck`:

```powershell
python scripts/build_stwi_vehicle_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short
```

If extra motorcycle-focused YOLO exports are available, add only sources whose
labels actually describe motorcycles/motorbikes. Helmet-only labels should not
be merged directly into the vehicle detector; use pseudo-labeling only as an
experiment and compare per-class metrics before accepting the result.

```powershell
python scripts/augment_vehicle_dataset_with_motorcycle.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --annotated-source motorcycle.yolov8
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann
```

Helmet-source datasets can still be useful for motorcycle/rider context and
future abnormal-evidence experiments, but they must be relabeled as motorcycle
boxes before they are used by the vehicle detector. Generate a small
high-confidence relabel candidate pack with preview images, review it, then add
only accepted labels as a motorcycle supplement:

```powershell
python scripts/relabel_helmet_dataset_for_motorcycle.py --source "MOTORCYCLE.yolov8 (1)" --output data/derived/private/vision_training/helmet_motorcycle_relabel_v001 --model data/derived/private/vision_runs/stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6/weights/best.pt --min-conf 0.55 --max-images 80 --device 0 --reviewer pending
```

The generated `review/review_queue.csv` and preview images are the review
surface. Until those rows are visually accepted, the relabel pack remains
`needs_review` and must not be promoted as official training evidence. Do not
expand the MVP detector classes to helmet or violation status without an
explicit contract change; such signals can be kept as separate Tier 1 evidence
for `needs_review`/OOD workflows.

After review, set accepted rows in `review/review_queue.csv` to
`review_status=accepted`, then materialize only those rows into a reviewed
supplement:

```powershell
python scripts/finalize_motorcycle_relabel_review.py --relabel-root data/derived/private/vision_training/helmet_motorcycle_relabel_v001 --output data/derived/private/vision_training/helmet_motorcycle_relabel_v001_reviewed --reviewer operator-reviewer --notes "Accepted high-confidence motorcycle relabel candidates after visual spot review."
```

Use the reviewed supplement as an `--annotated-source` only after this step.

Vietnam-style YOLO exports with the class set `bicycle`, `bus`, `car`,
`motorcycle`, and `truck` can be added as a multi-class vehicle supplement.
Keep `bicycle` ignored for the MVP detector and preserve the base validation
and test splits for comparable metrics. For quick motorcycle improvement, start
with a motorcycle-focused subset instead of adding every vehicle image:

```powershell
python scripts/prepare_roboflow_yolo_dataset.py vietnam.yolov8 --dataset-version vietnam_yolov8_v001 --privacy-status needs_review --reviewer pending --notes "Vietnam YOLO export prepared for STWI local training; visual/privacy review required before official promotion."
python scripts/augment_vehicle_dataset_with_yolo_sources.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_vietnam_motoonly --yolo-source vietnam.yolov8 --require-class motorcycle --max-records-per-source 320 --privacy-status needs_review --reviewer pending --notes "Vietnam YOLO motorcycle-focused supplement added train-only; visual/privacy review required before official promotion."
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_vietnam_motoonly --allow-pending-review
```

The first Vietnam experiment
`stwi_yolov8n_vehicles_motoann_vietnam_motoonly_cuda416_b32_e3` remained below
the previous candidate on base validation metrics (`mAP50` 0.6395 versus
0.6589). Keep it as an experiment until review and tuning improve the metric.

Use Vietnam as a hard-case review pool before another official retrain. The
review pack below runs the current best candidate on the Vietnam source, finds
ground-truth `motorcycle` boxes missed at IoU 0.5, and writes preview images
plus `review_queue.csv`. Add only visually accepted rows into a future reviewed
supplement; do not promote a model trained from pending-review Vietnam rows.

```powershell
python scripts/build_vision_error_review_pack.py --source vietnam.yolov8 --output data/derived/private/vision_reviews/vietnam_motorcycle_error_review_v001 --model data/derived/private/vision_runs/stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6/weights/best.pt --target-class motorcycle --split train --split val --split test --max-images 80 --conf 0.25 --iou-threshold 0.5 --imgsz 416 --device 0 --reviewer pending --notes "Vietnam YOLO motorcycle hard-case review before any official retrain."
```

The first review pack scanned 206 Vietnam images and selected 80 motorcycle
hard-case previews. This indicates the source is useful for active learning,
but it should stay outside the official model gate until human review and a
new validation run beat the current candidate.

The first pending-review hard-case fine-tune
`stwi_yolov8n_motoann_vietnam_hardcase80_cuda416_b32_e6` reached `mAP50`
0.6479, below the current 0.6589 candidate. Treat the 80-row Vietnam pack as a
review queue, not as a direct training shortcut.

When new motorcycle-only YOLO exports are dropped at the repository root,
deduplicate them by image hash before augmentation. The first audit found
`notonlyMotorcycle.yolov8` and `onlyMotorcycle.yolov8` were exact duplicates of
the existing `motorcycle.yolov8` export: 998/998 image hashes overlapped, so
both were skipped. `yolor motorcycle.yolov8` was unique against the current
base dataset and added 1,819 train-only images with 2,869 motorcycle boxes:

```powershell
python scripts/augment_vehicle_dataset_with_yolo_sources.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_yolor_moto_aug --yolo-source "yolor motorcycle.yolov8" --source-split train --require-class motorcycle --privacy-status needs_review --reviewer pending --notes "YOLOR motorcycle YOLO source added train-only after exact-hash dedupe; duplicate only/notonly motorcycle exports skipped."
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_yolor_moto_aug --allow-pending-review
```

The dataset `roboflow_v001_stwi_vehicles_motoann_yolor_moto_aug` preserves the
base validation/test splits and contains 10,508 train images, 2,668 validation
images, 1,298 test images, and 4,152 motorcycle boxes. The follow-up fine-tune
`stwi_yolov8n_motoann_yolor_moto_aug_cuda416_b32_e5` reached `mAP50` 0.6524
and `mAP50-95` 0.4243, below the current 0.6589 candidate. Keep this source as
a pending-review experiment; it should be visually/domain filtered before
another official training attempt.

For YOLOR, prefer hard-case mining over bulk ingestion. The first YOLOR
false-negative review pack scanned 464 train images and selected 160
motorcycle hard-case previews:

```powershell
python scripts/build_vision_error_review_pack.py --source "yolor motorcycle.yolov8" --output data/derived/private/vision_reviews/yolor_motorcycle_error_review_v001 --model data/derived/private/vision_runs/stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6/weights/best.pt --target-class motorcycle --split train --max-images 160 --conf 0.25 --iou-threshold 0.5 --imgsz 416 --device 0 --reviewer pending --notes "YOLOR motorcycle hard-case false-negative review before filtered retrain."
```

The combined experiment
`roboflow_v001_stwi_vehicles_motoann_mean_transport_yolor_hardcase160` reached
`mAP50` 0.6585 and `mAP50-95` 0.4309. This was better than bulk YOLOR but still
below the mean-transportation-only run, so keep YOLOR as a review pool until
the preview rows are visually accepted and domain-filtered.

`Mean of transportation.yolov8` is more useful as a train-only supplement
because it contains `bus`, `car`, `motorbike`, `person`, and `truck`, has no
exact image-hash overlap with the current base dataset or YOLOR source, and
adds many small vehicle boxes. `person` is ignored and `motorbike` is remapped
to STWI `motorcycle`:

```powershell
python scripts/augment_vehicle_dataset_with_yolo_sources.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_aug --yolo-source "Mean of transportation.yolov8" --privacy-status needs_review --reviewer pending --notes "Mean of transportation YOLO source added train-only; person ignored; visual/privacy review required before official promotion."
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_aug --allow-pending-review
```

The first mean-transportation-only fine-tune
`stwi_yolov8n_motoann_mean_transport_cuda416_b32_e6` reached `mAP50` 0.6671
and `mAP50-95` 0.4370, which beats the previous 0.6589 candidate but remains
below the production gate and is not promotable until visual/privacy review is
completed.

With the available root datasets saturated, the best training-only path is to
increase detector capacity carefully rather than keep adding noisy images. The
YOLOv8n polish run
`stwi_yolov8n_motoann_mean_transport_polish_cuda416_b32_e10` improved the
mean-transportation candidate to `mAP50` 0.6729 and `mAP50-95` 0.4390, mostly
by improving motorcycle AP50 from 0.4162 to about 0.4670. However, the curve
started to flatten after the later epochs, so further same-model polishing is
not the primary route to the `mAP50 >= 0.85` gate.

Keep image size at 416 for the current data. Evaluation of the stronger
YOLOv8s candidate at larger inference sizes reduced the gate metric:

| Eval image size | mAP50 | mAP50-95 | Note |
|---:|---:|---:|---|
| 416 | 0.6904 | 0.4457 | Best current gate metric |
| 512 | 0.6765 | 0.4369 | Motorcycle AP50 dropped sharply |
| 640 | 0.6513 | 0.4023 | Not suitable for the current MVP gate |

Minority oversampling also needs restraint. The
`roboflow_v001_stwi_vehicles_motoann_mean_transport_moto_r2_bus_r2` dataset
boosted motorcycle and bus train records, but the follow-up run reached only
`mAP50` 0.6669 and `mAP50-95` 0.4371. Treat this as evidence that class
imbalance is not the only blocker; noisy labels, small boxes, and domain
mismatch are now more important than raw class counts.

The best current pending-review candidate is the YOLOv8s capacity run trained
from the previous YOLOv8s checkpoint on the mean-transportation supplement:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_aug --model data/derived/private/vision_runs/stwi_yolov8s_motoann_cuda416_b16_e10/weights/best.pt --epochs 6 --imgsz 416 --batch 16 --device 0 --workers 0 --amp --output data/derived/private/vision_runs --name stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6 --model-version stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6 --allow-pending-review --optimizer AdamW --lr0 0.00018 --lrf 0.08 --cos-lr --mosaic 0.25 --close-mosaic 2
```

It reached `mAP50` 0.6902 and `mAP50-95` 0.4453, with per-class AP50 about
`bus=0.6830`, `car=0.7216`, `motorcycle=0.5015`, and `truck=0.8557`. A lower-LR
YOLOv8s polish run improved `mAP50-95` to 0.4498 but slightly reduced `mAP50`
to 0.6897, so keep
`stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6` as the best gate-metric
candidate for now. It is still not an official MVP model because it is below
the `mAP50 >= 0.85` gate and the source dataset remains
`privacy_status=needs_review`.

For human label QA, prepare a compact review batch instead of opening every
dataset folder. The batch copies only preview images and keeps pointers back to
the original `review_queue.csv` rows:

```powershell
python scripts/prepare_vision_review_batch.py --output data/derived/private/vision_reviews/mvp_round1_motorcycle_review_batch --pack data/derived/private/vision_reviews/base_val_motorcycle_error_review_v001 --pack data/derived/private/vision_reviews/vietnam_motorcycle_error_review_v001 --pack data/derived/private/vision_reviews/yolor_motorcycle_error_review_v001 --status pending --limit-per-pack 80 --title "STWI MVP round 1 motorcycle review"
```

Open `data/derived/private/vision_reviews/mvp_round1_motorcycle_review_batch/index.html`
for visual review, then edit
`data/derived/private/vision_reviews/mvp_round1_motorcycle_review_batch/review_batch.csv`.
Use only these statuses:

- `accepted`: label is usable for train-only supplement;
- `rejected`: image/label is wrong, noisy, duplicate, non-domain, or not useful;
- `needs_fix`: label needs manual correction before it can be used;
- `pending`: not reviewed yet.

After reviewing the batch CSV, apply the decisions back to the source packs:

```powershell
python scripts/apply_vision_review_batch.py --batch data/derived/private/vision_reviews/mvp_round1_motorcycle_review_batch/review_batch.csv
```

Then materialize accepted rows from each source review pack with
`scripts/augment_vehicle_dataset_with_review_pack.py`. Keep validation/test
preserved and add accepted review rows to train only.

The first round-1 review produced 47 `accepted`, 147 `needs_fix`, and 5
`rejected` rows. Accepted external hard cases were materialized into:

```text
data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor
```

This dataset keeps the preserved base validation/test splits and adds only
human-accepted Vietnam/YOLOR rows to train. Its split counts are 10,368 train,
2,668 validation, and 1,298 test images; object counts are `car=85840`,
`bus=2891`, `truck=21389`, and `motorcycle=4112`.

Rows marked `needs_fix` remain excluded from training and are queued for manual
label correction at:

```text
data/derived/private/vision_reviews/mvp_round1_motorcycle_label_fix_queue/index.html
```

Do not promote or train from `needs_fix` rows until the missing/wrong boxes are
corrected and the review status is changed to `accepted`.

For train-split `needs_fix` rows, generate a computer-vision assisted label-fix
candidate pack instead of editing the original source labels directly:

```powershell
python scripts/build_vision_label_fix_candidates.py --batch data/derived/private/vision_reviews/mvp_round1_motorcycle_label_fix_queue/review_batch.csv --output data/derived/private/vision_training/mvp_round1_motorcycle_label_fix_candidates --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/weights/best.pt --imgsz 416 --conf 0.35 --device 0 --reviewer codex-cv-pass --notes "Computer-vision assisted label-fix candidates for train split needs_fix rows; valid split intentionally excluded."
```

The generated candidate pack covers 124 train images only, adds 178 candidate
boxes, and reclassifies 30 high-overlap boxes. Its final candidate object
counts are `motorcycle=898`, `car=120`, `bus=28`, and `truck=226`. Review the
candidate previews at:

```text
data/derived/private/vision_training/mvp_round1_motorcycle_label_fix_candidates/review/index.html
```

Only rows approved in this candidate review should be finalized into a train
supplement. The original root datasets and the preserved validation split must
remain unchanged during this assisted repair pass.

After operator review, all 124 label-fix candidate rows were accepted and
materialized as a train-only supplement:

```powershell
python scripts/finalize_vision_label_fix_candidates.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor --candidate data/derived/private/vision_training/mvp_round1_motorcycle_label_fix_candidates --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --mark-all-accepted --include-status accepted --privacy-status needs_review --reviewer operator-reviewer --notes "User accepted all round-1 computer-vision assisted label-fix candidates; train-only supplement, valid split unchanged."
```

The resulting dataset preserves validation/test and has 10,491 train, 2,668
validation, and 1,298 test images. Object counts are `car=85958`, `bus=2919`,
`truck=21615`, and `motorcycle=4963`. It remains `privacy_status=needs_review`.

A YOLOv8s fine-tune from the previous best run was attempted on this label-fix
dataset:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/weights/best.pt --epochs 6 --imgsz 416 --batch 16 --device 0 --workers 0 --amp --output data/derived/private/vision_runs --name stwi_yolov8s_motoann_mean_transport_round1_labelfix_cuda416_b16_e6 --model-version stwi_yolov8s_motoann_mean_transport_round1_labelfix_cuda416_b16_e6 --allow-pending-review --optimizer AdamW --lr0 0.00012 --lrf 0.08 --cos-lr --mosaic 0.15 --close-mosaic 2
```

The first attempt timed out after 4 completed epochs. Resume from the saved
checkpoint with:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_round1_labelfix_cuda416_b16_e6/weights/last.pt --epochs 6 --imgsz 416 --batch 16 --device 0 --workers 0 --amp --resume --output data/derived/private/vision_runs --name stwi_yolov8s_motoann_mean_transport_round1_labelfix_cuda416_b16_e6 --model-version stwi_yolov8s_motoann_mean_transport_round1_labelfix_cuda416_b16_e6 --allow-pending-review --optimizer AdamW --lr0 0.00012 --lrf 0.08 --cos-lr --mosaic 0.15 --close-mosaic 2
```

The resumed run completed and wrote `stwi_model_artifact.json`, but the artifact
metrics were `mAP50` 0.6849 and `mAP50-95` 0.4446, below the previous best
YOLOv8s candidate (`mAP50` 0.6902). Do not promote this run; keep
`stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6` as the best gate-metric
candidate until a completed run beats it.

The next optimization attempt added train-only object-centric crops for the weak
AP50 classes while preserving validation/test:

```powershell
python scripts/augment_vehicle_dataset_with_object_crops.py --base data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix_objcrop --class-spec motorcycle:0.040:2200 --class-spec bus:0.020:800 --class-spec car:0.003:1200 --context-scale 5.0 --min-crop-size 160 --min-visibility 0.35 --reviewer codex-object-crop-pass --notes "Train-only object-centric crops for weak AP50 classes; validation/test preserved for honest MVP gate comparison."
```

This created 4,200 train crops and raised train counts to 14,691 images with
`car=97588`, `bus=4167`, `truck=23204`, and `motorcycle=16912` objects.
However, the follow-up run
`stwi_yolov8s_motoann_mean_transport_labelfix_objcrop_cuda416_b16_e6` reached
only `mAP50` 0.6661 and `mAP50-95` 0.4340. Do not promote it, and do not repeat
heavy object-crop augmentation as the primary route unless the crop policy is
redesigned and validated on a smaller ablation first.

Current best per-class AP50 on the preserved validation split is approximately
`bus=0.6830`, `car=0.7216`, `motorcycle=0.5015`, and `truck=0.8557`. Because
truck already clears the MVP threshold while motorcycle, bus, and car do not,
the next useful work is validation/domain error review, not blind oversampling.
The round-2 validation review batch is:

```text
data/derived/private/vision_reviews/mvp_round2_validation_error_review_batch/index.html
```

It combines validation false-negative and false-positive packs for
`motorcycle`, `bus`, and `car`: 43 motorcycle, 130 bus, and 160 car review
images. Use this to decide whether the remaining gap is real detector failure,
class confusion, or validation label/source quality before any more long run.

As a clean ablation, the human-accepted round-1 Vietnam/YOLOR dataset was also
fine-tuned without the label-fix or object-crop supplements:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/weights/best.pt --epochs 8 --imgsz 416 --batch 16 --device 0 --workers 0 --amp --output data/derived/private/vision_runs --name stwi_yolov8s_reviewed_round1_vietnam_yolor_cuda416_b16_e8 --model-version stwi_yolov8s_reviewed_round1_vietnam_yolor_cuda416_b16_e8 --allow-pending-review --optimizer AdamW --lr0 0.00008 --lrf 0.05 --cos-lr --mosaic 0.20 --close-mosaic 3
```

This run reached `mAP50` 0.6900 and `mAP50-95` 0.4507. A per-class validation
check showed AP50 about `bus=0.6960`, `car=0.7171`, `motorcycle=0.4921`, and
`truck=0.8554`. Treat it as a useful box-quality ablation, not a promotion
candidate: it does not beat the current best `mAP50` 0.6902 and remains far
below the 0.85 gate.

The follow-up high-resolution tiny-object fine-tune used the finalized
label-fix dataset at `imgsz=640`, lower LR, and lighter augmentation. The run
timed out once, then was resumed from `weights/last.pt`:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_runs/stwi_yolov8s_labelfix_tiny640_cuda640_b8_e4/weights/last.pt --epochs 4 --imgsz 640 --batch 8 --device 0 --workers 0 --amp --resume --output data/derived/private/vision_runs --name stwi_yolov8s_labelfix_tiny640_cuda640_b8_e4 --model-version stwi_yolov8s_labelfix_tiny640_cuda640_b8_e4 --allow-pending-review --optimizer AdamW --lr0 0.00006 --lrf 0.08 --cos-lr --mosaic 0.08 --close-mosaic 2 --scale 0.20 --translate 0.06 --erasing 0.10
```

The completed artifact reached `mAP50` 0.6893 and `mAP50-95` 0.4432, so it did
not beat the current best `mAP50` 0.6902 candidate and must not be promoted.
This confirms that higher train resolution alone is not enough for the current
MVP gate.

Use validation-error analysis before more long runs. The diagnostic script
computes TP/FN/FP at a fixed confidence and records wrong-class matches as both
target FN and predicted-class FP:

```powershell
python scripts/analyze_vision_validation_errors.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/weights/best.pt --output data/derived/private/vision_diagnostics/best_yolov8s_labelfix_val_conf025 --split val --conf 0.25 --iou-threshold 0.5 --imgsz 416 --device 0
```

The first analysis scanned 2,668 validation images. At confidence 0.25, the
main blocker is tiny-object recall rather than raw class count: `car` has 5,114
tiny FNs, `truck` 503, `bus` 49, and `motorcycle` 23. The largest wrong-class
confusions are `car->truck` 166, `truck->car` 138, `car->bus` 53,
`bus->truck` 29, and `bus->car` 25. Review the round-2 validation batch first,
then decide whether labels need correction, hard tiny-object positives, or
class-confusion relabeling. Avoid repeating object-crop, oversampling, or
short high-resolution fine-tunes without new label/domain evidence.

Sliced inference was tested as a non-training route for tiny objects. The
sample of 300 validation images looked promising at `conf=0.40`, but the full
validation run did not hold up:

```powershell
python scripts/analyze_vision_sliced_validation.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/weights/best.pt --output data/derived/private/vision_diagnostics/best_yolov8s_labelfix_val_sliced640_conf040_full --split val --conf 0.40 --iou-threshold 0.5 --imgsz 416 --device 0 --tile-size 640 --overlap 0.25 --nms-iou 0.50
```

Compared with full-frame inference at the same confidence, slicing slightly
improved recall for `bus`, `car`, and `truck`, but false positives rose sharply
and `motorcycle` precision dropped to about 0.256. Do not make sliced inference
the default MVP policy without a stronger merge/filter rule and AP50 evaluation.

Hard-case replay was also tested by mining train-split errors from the current
best model and duplicating 1,800 high-scoring train records with weights biased
toward `motorcycle` and `bus`:

```powershell
python scripts/analyze_vision_validation_errors.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --model data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/weights/best.pt --output data/derived/private/vision_diagnostics/best_yolov8s_labelfix_train_conf025 --split train --conf 0.25 --iou-threshold 0.5 --imgsz 416 --device 0
python scripts/rebalance_vehicle_training_dataset_from_errors.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix --error-csv data/derived/private/vision_diagnostics/best_yolov8s_labelfix_train_conf025/image_errors.csv --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_labelfix_hardcase_replay_v1 --repeat 1 --max-records 1800 --min-score 1.0 --class-weight motorcycle:5.0 --class-weight bus:3.0 --class-weight car:0.45 --class-weight truck:0.35
```

The resulting dataset has 12,291 train images and preserves the same 2,668
validation and 1,298 test images. A YOLOv8s fine-tune completed after two
resumes, reaching `mAP50` 0.6878 and `mAP50-95` 0.4464. This does not beat the
current best `mAP50` 0.6902. Keep the hard-case replay script as an ablation
tool, but do not promote this run or repeat broad replay without a class cap,
label cleanup, or stronger evidence from the round-2 validation review.

Two additional production-path diagnostics were checked and rejected as default
MVP shortcuts. Ultralytics test-time augmentation on the current best
checkpoint reached only `mAP50` 0.6895 and `mAP50-95` 0.4499, so TTA does not
beat the current best gate metric. An ROI/min-object-area AP50 diagnostic also
showed that removing tiny objects helps `car` AP50 but does not solve the full
four-class MVP gate: on a 500-image validation sample, `min_box_area=0.003`
removed 2,722 of 4,592 targets and raised `car` AP50 to about 0.882, but mean
ROI AP50 was still about 0.416 because `bus`, `motorcycle`, and `truck`
remained weak. At `min_box_area=0.01`, mean ROI AP50 was still only about
0.507 and most labels were removed. Do not claim production readiness from ROI
filtering alone; use it only to define future calibrated camera ROI
requirements after human/domain review.

When the active training path stabilizes, clean unused vision artifacts with an
explicit manifest instead of deleting ad hoc folders:

```powershell
python scripts/cleanup_vision_data_artifacts.py --mode dry-run --manifest data/manifests/vision_data_cleanup_dry_run.json
python scripts/cleanup_vision_data_artifacts.py --mode quarantine --manifest data/manifests/vision_data_cleanup_manifest.json
```

The cleanup script keeps the raw/base datasets, the mean-transportation
candidate, the round-1 accepted Vietnam/YOLOR dataset, the label-fix candidate
pack, review packs, and the best YOLOv8s run. Unused smoke artifacts, loose
mock YOLO layout folders, oversampling sweeps, rejected Vietnam/YOLOR
experiments, and intermediate round-1 staging datasets are moved under
`data/quarantine/vision_data_cleanup/` with a machine-readable manifest. Delete
that quarantine folder only after the next retrain no longer needs rollback.

Create a base-validation review pack when the gate metric stalls. This audits
the exact preserved validation split instead of adding more unreviewed data:

```powershell
python scripts/build_vision_error_review_pack.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --output data/derived/private/vision_reviews/base_val_motorcycle_error_review_v001 --model data/derived/private/vision_runs/stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6/weights/best.pt --target-class motorcycle --split val --max-images 120 --conf 0.25 --iou-threshold 0.5 --imgsz 416 --device 0 --reviewer pending --notes "Base validation motorcycle false-negative review for mAP50 gate improvement."
```

The first base-validation review scanned all 2,668 validation images and
selected 39 motorcycle false-negative previews. Review these before another
long training run; if labels are correct, collect matching train-only hard
positives, and if labels are wrong, fix the validation source then rerun the
gate honestly.

Box-area analysis showed the missed validation motorcycle boxes are mostly
small: median normalized area was about 0.0058. To test that failure mode
without leaking validation data, build a privacy-reviewed train-only boost from
small motorcycle boxes:

```powershell
python scripts/rebalance_vehicle_training_dataset.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --output data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann_smallmoto_area006_r2 --boost-class motorcycle --repeat 2 --max-box-area 0.006
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann_smallmoto_area006_r2
```

This selected 174 train images, added 348 duplicate train records, and raised
motorcycle boxes from 1,283 to 3,185 while preserving validation/test. The
follow-up fine-tune
`stwi_yolov8n_motoann_smallmoto_area006_r2_cuda416_b32_e5` reached `mAP50`
0.6581 and `mAP50-95` 0.4286. It did not beat the current `mAP50` 0.6589
candidate, but it reduced validation motorcycle false-negative preview count
from 39 to 34, so the next step should combine small-object positives with
false-positive/negative review rather than simply increasing duplication.

False-positive review can be generated with the same review tool:

```powershell
python scripts/build_vision_error_review_pack.py --source data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --output data/derived/private/vision_reviews/base_val_motorcycle_false_positive_review_candidate_v001 --model data/derived/private/vision_runs/stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6/weights/best.pt --target-class motorcycle --review-mode false_positive --split val --max-images 200 --conf 0.25 --iou-threshold 0.5 --imgsz 416 --device 0 --reviewer pending --notes "Base validation motorcycle false-positive review for current best candidate."
```

The current candidate produced only 2 motorcycle false-positive preview images
at confidence 0.25, while the small-motorcycle boost produced 5. Precision loss
is therefore not the main motorcycle bottleneck. Per-class AP50 on the
preserved validation split was:

| Model | bus | car | motorcycle | truck | mean |
|---|---:|---:|---:|---:|---:|
| `stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6` | 0.6638 | 0.6976 | 0.4162 | 0.8581 | 0.6589 |
| `stwi_yolov8n_motoann_smallmoto_area006_r2_cuda416_b32_e5` | 0.6658 | 0.7041 | 0.4042 | 0.8594 | 0.6584 |

To reach `mAP50 >= 0.85`, treat truck as near-ready and focus review/training
effort on motorcycle first, then car and bus. Do not spend more long runs on
small-motorcycle duplication alone unless the reviewed data changes.

Train local YOLOv8:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_short --model yolov8n.pt --epochs 50 --imgsz 416 --batch 32 --device 0 --name stwi_yolov8n_roboflow_v001_vehicles_cuda416_b32_e50 --model-version stwi_yolov8n_roboflow_v001_vehicles_cuda416_b32_e50
```

For a quick motorcycle-focused fine-tune, start from the best vehicle-only
candidate instead of retraining from scratch:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --model data/derived/private/vision_runs/stwi_yolov8n_roboflow_v001_vehicles_cuda416_b32_e50/weights/best.pt --epochs 6 --imgsz 416 --batch 32 --device 0 --name stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6 --model-version stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6
```

For controlled fine-tuning experiments, set the optimizer explicitly instead of
leaving Ultralytics on `optimizer=auto`, because auto mode can override LR
choices:

```powershell
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001_stwi_vehicles_moto_ann --model data/derived/private/vision_runs/stwi_yolov8n_vehicles_motoann_finetune_cuda416_b32_e6/weights/best.pt --epochs 4 --imgsz 416 --batch 32 --device 0 --optimizer AdamW --lr0 0.0005 --lrf 0.05 --cos-lr --mosaic 0.2 --close-mosaic 1 --name stwi_yolov8n_motoann_adamw_lowmosaic_cuda416_b32_e4 --model-version stwi_yolov8n_motoann_adamw_lowmosaic_cuda416_b32_e4
```

The first AdamW/low-mosaic run reached `mAP50` 0.6508, also below the current
candidate. Keep it as evidence that data review should take priority over more
short hyperparameter sweeps.

Training outputs stay under:

```text
data/derived/private/vision_runs/
```

For exploratory training before privacy review, add `--allow-pending-review`.
The output artifact is marked `training_only_pending_privacy_review` and cannot
be promoted as the official MVP model.

Every training run writes `stwi_model_artifact.json` with:

- weights path and `sha256`;
- source dataset version and manifest checksum;
- train/val/test metrics, including mAP and per-class errors;
- image size, confidence thresholds, and class mapping;
- calibration/ROI policy needed to publish speed;
- timestamp and reviewer.

## Promotion Gate

Promote the model only when:

- validation/test metrics are recorded and not overclaimed;
- privacy review is complete;
- class mapping covers `car`, `motorcycle`, `bus`, and `truck` or documents any
  missing class limitation;
- camera calibration is valid before publishing `avg_speed_kmh`;
- detector failures, low confidence, or OOD frames mark the camera source
  degraded/offline instead of publishing a valid aggregate;
- no raw video, API key, signed URL, image base64, or large private dataset is
  committed.

After the gate is satisfied, promote a candidate into the official private model
slot:

```powershell
python scripts/promote_vision_model.py --artifact data/derived/private/vision_runs/stwi_yolov8n_roboflow_v001/stwi_model_artifact.json --approver operator-reviewer --notes "Privacy review and validation accepted for MVP detector."
```

The runtime loader reads only:

```text
data/derived/private/vision_models/official/model_artifact.json
```

For the project-native evidence schema that promotion and audit should record
before and after promotion, see:

- `docs/guides/model_registry_evidence.md` — vision detector evidence fields,
  including model/version provenance, dataset/split evidence, metrics,
  calibration, benchmark profile, promotion decision, reviewer, and privacy
  status

This schema is documentation only; if runtime validation of the schema is
needed later, treat it as a separate follow-up implementation issue rather than
changing production promotion behavior in this change.

## Edge RTSP Capture Guardrails

Use `edge_camera_1` as the reviewed source id for the first edge RTSP capture
slice. The id is intentionally lowercase and underscore-only so it passes the
capture script allowlist while remaining stable for later manifest annotation.

The RTSP endpoint must be supplied only through the local `STWI_RTSP_URL`
environment variable. Do not paste the endpoint, credentials, signed URLs, image
base64, raw video paths, or raw video references into repository files, issue
trackers, logs, manifests, or command examples. The capture command should keep
the endpoint out of argv-visible examples:

```powershell
python scripts/data_prep/capture_rtsp_frames.py --source-id edge_camera_1 --interval-seconds 5 --max-frames 24
```

`capture_rtsp_frames.py` writes sparse JPEG frames and a quarantine
`manifest.json` under the configured output root. The manifest may include
source id, session id, frame hashes, sampling interval, privacy status, and
sanitized ffprobe stream metadata; it must not include the RTSP endpoint,
credentials, image base64, or a raw video file reference. If the environment
variable is missing, the URL is not `rtsp://` or `rtsps://`, ffmpeg/ffprobe
fails, or no usable frames are produced, the command fails closed and removes
the partial capture directory.

## Runtime Boundary

The trained detector feeds only the Tier 1 CCTV aggregate path:

```text
local YOLOv8 -> tracking/ROI -> 5-minute aggregate -> tensor builder
```

It does not alter `X[B,12,N,16]`, `M[B,12,N,16]`, `A[N,N]`,
`Y[B,6,N,2]`, the surrogate ensemble, the job API, or the Counterfactual Safety
Loop.
