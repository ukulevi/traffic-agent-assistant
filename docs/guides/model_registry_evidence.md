# STWI Model Registry Evidence Format

This guide defines a project-native evidence format for STWI artifacts.
The filesystem format remains service-free; production runtime validation is
implemented by `stwi.t4_orchestrator.runtime_artifacts` and does not add MLflow
or another registry service.

Use it when recording, reviewing, or promoting:

- vision detector artifacts,
- GCN–LSTM baseline artifacts,
- surrogate ensemble artifacts.

## 1. Evidence purpose

STWI needs provenance evidence for every model or artifact that affects
operator-facing outputs. The evidence must show:

- what the artifact is,
- where it came from,
- how it performed,
- who reviewed it,
- whether it is allowed to influence a decision.

This guide records those requirements in a filesystem- and JSON-friendly
format that can be added to existing project scripts later.

## 2. Registry file layout

Keep evidence close to the artifact it describes. The canonical layout is:

```text
model_evidence/
  <artifact_role>/
    <artifact_name>/
      evidence.json
      README.md
      checksums/
        <file>.sha256
```

Recommended values:

- `artifact_role`: `vision_detector`, `baseline_forecaster`, or `surrogate_ensemble`.
- `artifact_name`: a short stable identifier, for example
  `stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6`,
  `gcn_lstm_r1`, or `surrogate_ensemble_r2`.

## 3. Core evidence schema

Each `evidence.json` should contain these top-level sections.

```json
{
  "schema_version": "1.0.0",
  "artifact_role": "vision_detector",
  "artifact_name": "stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6",
  "artifact_path": "data/derived/private/vision_models/candidates/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6/best.pt",
  "model": {
    "model_version": "stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6",
    "model_family": "yolov8s",
    "source_type": "local_finetune",
    "source_reference": "data/derived/private/vision_runs/stwi_yolov8s_motoann_mean_transport_cuda416_b16_e6",
    "weights_path": "weights/best.pt",
    "sha256": "<weights-sha256>"
  },
  "dataset": {
    "dataset_version": "roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix",
    "split_description": "Preserved base train, validation, and test splits plus accepted human review supplement in train only.",
    "split_roles": {
      "train": "train-only review supplement accepted from round-1 review queue",
      "validation": "preserved base validation split unchanged",
      "test": "preserved base test split unchanged"
    },
    "split_timestamp": "2026-07-05",
    "manifest_path": "data/derived/private/vision_training/roboflow_v001_stwi_vehicles_motoann_mean_transport_reviewed_round1_vietnam_yolor_labelfix/dataset_manifest.json",
    "manifest_sha256": "<manifest-sha256>",
    "leakage_check": "Time-based split; scaler fit on train only; no future valid/test rows used in training."
  },
  "pipeline": {
    "framework": "ultralytics",
    "export_format": "pt",
    "runtime_path": "data/derived/private/vision_models/official/model_artifact.json",
    "runtime_loader": "scripts/promote_vision_model.py"
  },
  "metrics": {
    "primary_metric": "mAP50",
    "primary_metric_value": 0.6902,
    "secondary_metrics": {
      "mAP50_95": 0.4453,
      "bus": 0.6830,
      "car": 0.7216,
      "motorcycle": 0.5015,
      "truck": 0.8557
    },
    "split": "validation",
    "scope": "full preserved validation split with confidence 0.05 and IoU 0.5 at imgsz 416"
  },
  "calibration": {
    "confidence_threshold": 0.05,
    "iou_threshold": 0.5,
    "image_size": 416,
    "device": "cpu_or_gpu_under_test",
    "roi_policy": "reviewed_roi_requirements_pending_human_approval",
    "notes": "Record actual device and runtime conditions in each run artifact."
  },
  "benchmark": {
    "profile": "MVP benchmark profile",
    "cpu_cores": 8,
    "ram_gb": 32,
    "gpu_vram_gb_min": 12,
    "gpu_vram_gb_max": 16,
    "device": "cuda:0 NVIDIA",
    "gpu_vram_gb": 16,
    "seconds_per_image_p50": null,
    "seconds_per_image_p99": null,
    "report_path": null
  },
  "promotion": {
    "status": "not_promoted",
    "gate": "mAP50 >= 0.85 with privacy review complete and runtime promotion script pass",
    "decision": "Best current candidate; remains unofficial until gate and privacy review pass.",
    "reviewer": "operator-reviewer",
    "privacy_status": "needs_review"
  },
  "legal_and_privacy": {
    "source_license": "see dataset manifest and source model cards",
    "privacy_status": "needs_review",
    "raw_video_retained": false,
    "citation_required": true,
    "notes": "Do not publish aggregate evidence from this artifact until privacy review is finalized."
  },
  "timestamps": {
    "created_at": "2026-07-05",
    "evidence_last_updated_at": "2026-07-05"
  }
}
```

## 4. Required fields by artifact role

### 4.1 Vision detector

Required fields:

- `model.model_version`
- `model.model_family`
- `artifact_role`
- `artifact_path`
- `model.sha256`
- `dataset.dataset_version`
- `dataset.split_description`
- dataset leakage check / chronological split note
- `metrics.primary_metric` and split scope
- calibration evidence: confidence, IoU, image size, ROI policy
- benchmark profile and latency evidence when available
- `promotion.status`, `promotion.decision`, `reviewer`, timestamp
- `legal_and_privacy.privacy_status`
- aggregate-only runtime boundary note

Optional notes:

- `source_type` can be `local_finetune`, `pretrained_fallback`, or `external_candidate`.
- `runtime_loader` should name the promotion script or loader that reads the official artifact.

### 4.2 GCN–LSTM baseline

Required fields:

- `model.model_version`
- `model.model_family`
- `artifact_role`
- `artifact_path`
- `model.sha256`
- split description with chronological notes
- train/validation/test counts or supported horizon counts
- metrics by target (`traffic_volume_5m`, `avg_speed_kmh`) and horizon
- baseline comparison: persistence, historical average, seasonal linear
- `normalization.normalizer_artifact_path` and fit scope if stored outside code
- calibration evidence if uncertainty intervals are emitted
- benchmark profile and latency evidence if runtime artifact is published
- `promotion.status`, `promotion.decision`, `reviewer`, timestamp
- OOD and fail-closed behavior note

Optional notes:

- Store adjacency version and node-order stability evidence if node order changes between training and serving.

### 4.3 Surrogate ensemble

Required fields:

- `model.model_version`
- `model.model_family`
- `artifact_role`
- `artifact_path`
- `model.sha256`
- dataset version and scenario-family split description
- SUMO offline training source and calibration record
- member model metadata: MLP, CNN-1D, Light Transformer versions and checksums
- metrics vs SUMO: MAE/RMSE, max-V/C error, ranking/action consistency
- uncertainty calibration evidence: coverage, interval width, error by uncertainty decile
- threshold selection notes and held-out validation source
- benchmark profile and latency evidence:
  surrogate P99 target < 500 ms on the benchmark profile
- `promotion.status`, `promotion.decision`, `reviewer`, timestamp
- OOD / high-uncertainty handling note:
  `needs_review` or fail-closed, never automatic actuation

Optional notes:

- If the ensemble weights or scenario coverage policy change, record the previous version as `previous_evidence`.

## 5. Current artifact mapping

### 5.1 Vision

The repository already records many of these fields in local scripts and
datasets, but not yet in one normalized `evidence.json` file:

- model name, training dataset version, and split notes exist in run commands.
- metrics exist in run outputs and review tables.
- privacy status, reviewer, and promotion decision exist in dataset manifest
  and promotion command examples, but may remain `needs_review` or
  `not_promoted` without a single machine-readable registry file.
- benchmark/latency evidence is implied but not fully recorded in one place
  for every candidate.
- raw video retention remains false by contract.

Honest mapping:

| Evidence field | Current status |
|---|---|
| `model_version` / `model_family` | Present in run names and scripts |
| `sha256` | Present for some external models; official promotion artifact records weights path |
| `dataset_version` | Present in dataset paths and runner notes |
| `leakage_check` / chronological split | Implied by preserved validation/test and train-only supplements |
| `metrics` | Recorded in runbook tables and script output files |
| `confidence_threshold` / `iou_threshold` / `imgsz` | Present in evaluator commands |
| `reviewer` | Present in manifest and review batch notes |
| `privacy_status` | Present and enforced before promotion |
| `benchmark latency` | Partial; not fully consolidated per candidate |

Follow-up issues if implementation is desired:

1. Add a script that writes `evidence.json` from the official
   `model_artifact.json` plus runbook metadata.
2. Add SHA256 recording for every training-run weights file at save time.
3. Record `seconds_per_image_p50` and `seconds_per_image_p99` in the
   benchmark summary script output.
4. Validate required fields before promotion with a small pre-promotion
   evidence checker.

### 5.2 GCN–LSTM baseline

Current status:

- tensor contract, node order, normalization rules, and split rules are
  specified in `docs/02_ML_and_Simulation_Specification.md`.
- metrics, baseline comparison, and uncertainty calibration requirements
  are defined there too.
- baseline artifact evidence is not yet consolidated into a project-native
  registry file.

Honest mapping:

| Evidence field | Current status |
|---|---|
| `model_version` / `model_family` | Specified but not stored as a registry artifact file |
| `split_description` | Specified as chronological, no row-level leakage |
| `normalization.source_splits_only` | Specified in contract |
| `metrics` | Target shapes and baselines are specified; per-run values are not yet captured in registry form |
| `benchmark` | Profile is specified; runtime artifact evidence is not yet captured |
| `promotion` | Baseline promotion is implicit; registry file does not exist yet |

Follow-up issues:

1. Define a baseline artifact manifest schema after the first training run.
2. Record predictor version, scaler checksum, and adjacency version
   together with the baseline weights.
3. Add a baseline evidence validation pass in training/evaluation release QA.

### 5.3 Surrogate ensemble

Current status:

- offline SUMO source, scenario split, member models, uncertainty policy,
  and OOD behavior are specified in `docs/02_ML_and_Simulation_Specification.md`.
- surrogate runtime profile and P99 target are fixed in
  `project_contract.json`.
- ensemble registry evidence is not yet consolidated into a project-native
  registry file.

Honest mapping:

| Evidence field | Current status |
|---|---|
| `model_version` / `model_family` | Specified; not yet stored as registry artifact |
| `dataset_version` | Implied by scenario family and SUMO dataset |
| `member_model_metadata` | Not yet captured centrally |
| `calibration` | Policy specified; coverage records not yet required |
| `benchmark` | P99 target specified; per-artifact latency evidence not yet required |
| `promotion` | Not yet defined in registry form |

Follow-up issues:

1. Add surrogate ensemble evidence generation to the scenario training
   release script.
2. Store SUMO scenario family metadata, calibration record, and
   prediction-interval coverage with each promoted surrogate version.
3. Validate that `needs_review` is emitted for high uncertainty / OOD
   inputs before any downstream workflow completes.

## 6. Promotion and runtime boundary

Use this evidence format together with the existing gates in
`docs/guides/vision_local_training_runbook.md` and the surrogate
acceptance gates in `docs/02_ML_and_Simulation_Specification.md`.

STWI runtime boundaries remain unchanged:

- vision detection is five-minute aggregate evidence only,
- baseline forecast provides no-intervention traffic evidence,
- surrogate ensemble estimates scenario impact only,
- no automatic actuation is allowed from any model registry evidence file,
- fail-closed and `needs_review` behavior must be preserved.

For baseline and surrogate production manifests, the runtime loader additionally
requires `artifact_name`, `artifact_path`, `artifact_sha256`, `model_version`,
`data_version`, `expires_at`, `promotion.status=promoted`,
`promotion.provisional=false`, and `calibration.status=calibrated`. Calibration
must contain bounded `uncertainty_threshold` and `ood_threshold`. Missing,
expired, provisional, uncalibrated, or checksum-mismatched evidence prevents
production composition. Audit records store both artifact and manifest SHA-256
values so the evidence matches the exact inference inputs.

## 7. Privacy and security rules

- Do not store raw video paths, signed URLs, image base64 outputs,
  credentials, API keys, or private dataset contents in evidence files.
- Store only checksums and sanitized source references for external weights.
- If a registry artifact is moved to a shared location, review it for
  private path leakage before publishing.
- Keep evidence files deterministic and machine-readable so audit review
  does not need access to raw training environments.
