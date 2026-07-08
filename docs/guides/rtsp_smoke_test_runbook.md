# STWI — Supervised RTSP-to-Quarantine Smoke Test Runbook

**Ticket:** `TRA-10` / `STWI-RTSP-002`
**Status:** Draft
**Scope:** Documentation only. No code change, no credential, no live-stream automation outside the approved `STWI_RTSP_URL` boundary.

## 1. Goal

Provide a supervised, human-reviewed smoke test procedure for one approved RTSP
source (`edge_camera_1`) that:
- reads the live endpoint only from `STWI_RTSP_URL`,
- captures sparse frames into `data/quarantine/rtsp_frames/<source_id>/<session_id>/`,
- never retains a raw video container,
- never logs endpoints, image base64, or raw-video references,
- produces only offline evidence suitable for privacy review and aggregate calibration.

This runbook does **not** replace TRA-11 or authorize autonomous field capture.
It documents the exact manual workflow that a human operator can repeat under
supervision.

## 2. Prerequisites

| Requirement | How to verify |
|---|---|
| ffmpeg / ffprobe on PATH | `ffmpeg -version`, `ffprobe -version` |
| Python extra installed | `pip install -e .[vision]` |
| Approved source | Human confirms `edge_camera_1` is safe to probe |
| Endpoint in env only | `STWI_RTSP_URL` is set locally; it is **not** in repo, Linear, logs, or manifests |
| Quarantine dir ignored | `data/quarantine/` is untracked/gitignored; confirm with `git status --short` |
| Review bucket empty | Start with no sensitive payloads in current working directory |

## 3. One-shot Capture Procedure

### 3.1 Set approved source

```bash
export STWI_RTSP_URL="rtsp://<hidden>:<hidden>@<approved-host>/..."
```

Use only `edge_camera_1` as the source id in this procedure. Do not substitute
other camera paths without another human review.

### 3.2 Run capture

```bash
python scripts/data_prep/capture_rtsp_frames.py \
  --source-id edge_camera_1 \
  --interval-seconds 5 \
  --max-frames 60 \
  --max-width 1344
```

This command prints only the session directory path on success.
On failure, it prints a redacted error message that hides the RTSP URL and
image base64.

### 3.3 Verify quarantine manifest

Open `data/quarantine/rtsp_frames/edge_camera_1/<session_id>/manifest.json`
and verify:

- `privacy_status: needs_review`
- `retention_class: temporary_quarantine`
- `raw_video_retained: false`
- `stream` contains only non-sensitive fields (`codec_name`, `width`, `height`,
  `avg_frame_rate`, `pix_fmt`)
- `frames` lists `sha256`, `size_bytes`, and `recorded_at` only

### 3.4 Redaction checks before any share

Run these commands in the session directory and confirm zero matches:

```bash
rg -n "rtsp://|rtsps://|data:image/[^;]+;base64," .
rg -n "\[redacted-rtsp-url\]|\[redacted-image-base64\]|\[redacted-base64\]" manifest.json
```

The second command should show the redaction placeholders were **not** injected
because the original payload never leaked into command output.

### 3.5 Offline verification after supervised capture

```bash
python scripts/validate_vision_dataset.py data/quarantine/rtsp_frames/edge_camera_1/<session_id>
```

Use validation results to decide:
- **Accept:** forward selected frames into reviewed aggregate evidence through a
  later issue.
- **Keep in quarantine:** retain for privacy review without leaving quarantine.
- **Delete:** remove all frames and manifest after inspection.

## 4. Allowed Next Steps

| Action | Required approval |
|---|---|
| Inspect frames locally for calibration review | Operator |
| Select frames for reviewed aggregate evidence | TRA-11 / later ticket |
| Retain frames in quarantine for audit | Privacy review record |
| Delete quarantine session | Operator after review |

This runbook does **not** authorize:
- autonomous scheduled capture,
- publishing raw video or endpoint metadata,
- treating RTSP output as executable action.

## 5. Exact Offline Verification Commands

```bash
python scripts/validate_vision_dataset.py data/quarantine/rtsp_frames/edge_camera_1/<session_id>
python scripts/data_prep/capture_rtsp_frames.py --help
git status --short
rg -n "rtsp://|rtsps://|data:image/[^;]+;base64," data/quarantine/rtsp_frames/edge_camera_1/<session_id>
```

## 6. Acceptance Criteria

- Runbook explains how an operator sets `STWI_RTSP_URL` locally without writing it
  to repo, Linear, logs, or manifests.
- Procedure captures only sparse frames into
  `data/quarantine/rtsp_frames/edge_camera_1` and never stores a raw video
  container.
- Procedure lists privacy review, retention, cleanup, and aggregate-only next steps
  before any frame leaves quarantine.
- Procedure includes exact offline verification commands that can run after
  supervised capture.
