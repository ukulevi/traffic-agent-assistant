# Roboflow MCP connector

This repository includes a small stdio MCP server for Roboflow Universe data
discovery and dataset export. It is intended for dataset research and offline
vision training only; it does not change the STWI runtime contract and does not
enable automatic traffic actuation.

## Credentials

Create a scoped Roboflow API key and provide it through the environment. Do not
commit the key to the repository.

```powershell
$env:ROBOFLOW_API_KEY = "<your-scoped-api-key>"
python scripts/roboflow_mcp_server.py --check
```

If `python` is not on PATH, use an absolute Python executable path in both the
check command and MCP config.

## MCP client configuration

Add a server entry similar to the following in the MCP client that will call
Codex or another agent:

```json
{
  "mcpServers": {
    "stwi-roboflow": {
      "command": "python",
      "args": [
        "C:/Users/PC/Downloads/DADN/traffic-agent-assistant/scripts/roboflow_mcp_server.py"
      ],
      "cwd": "C:/Users/PC/Downloads/DADN/traffic-agent-assistant",
      "env": {
        "ROBOFLOW_API_KEY": "<your-scoped-api-key>"
      }
    }
  }
}
```

If your MCP client inherits shell environment variables, omit the `env` block
and set `ROBOFLOW_API_KEY` before launching the client.

## Tools

- `roboflow_universe_search`: searches public Roboflow Universe datasets.
- `roboflow_export_dataset`: returns the Roboflow export payload for a known
  workspace/project/version/format.
- `roboflow_download_dataset`: downloads and safely extracts a dataset into the
  repository. The default output is
  `data/external/roboflow/<project>-v<version>-<format>`.

Useful Universe search queries for STWI:

```text
traffic camera object detection images>1000
vehicle detection object detection images>3000
class:car class:truck object detection images>1000
traffic light object detection images>1000
motorbike scooter traffic object detection
accident CCTV object detection
```

## STWI data policy

Downloaded Roboflow data stays under `data/external/`, which is ignored by git.
For the current local training path, export in YOLOv8/Ultralytics format and
promote the approved dataset to
`data/derived/private/vision_training/roboflow_v001`. The promoted directory
must contain the Roboflow YOLO layout `train/images`, `train/labels`,
`valid/images`, `valid/labels`, `test/images`, `test/labels`, plus generated
`dataset.yaml` and `dataset_manifest.json`.

Before using any dataset for STWI training, record its source, license, classes,
download timestamp, checksum, class map, split counts, and privacy review
outcome in the manifest. The manifest must include image/label records with
hashes so `scripts/validate_vision_dataset.py` can verify split integrity before
training. Run validation before training:

```powershell
python scripts/prepare_roboflow_yolo_dataset.py data/derived/private/vision_training/roboflow_v001 --dataset-version roboflow_v001 --privacy-status needs_review --reviewer pending
python scripts/validate_vision_dataset.py data/derived/private/vision_training/roboflow_v001 --allow-pending-review
python scripts/train_vision_model.py --dataset data/derived/private/vision_training/roboflow_v001 --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0 --name stwi_yolov8n_roboflow_v001 --model-version stwi_yolov8n_roboflow_v001
```

Do not store or publish raw video. Do not treat Roboflow datasets as online
runtime inputs to the GCN-LSTM or surrogate model; they are only supporting data
for local perception model training, calibration, and offline validation.
Promoted weights remain private artifacts and detector outputs are used only as
camera aggregate evidence.
