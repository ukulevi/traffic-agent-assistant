"""Capture sparse RTSP frames into a privacy-review quarantine.

The source URL is read from ``STWI_RTSP_URL``. It is intentionally excluded
from command output and manifests to avoid leaking camera endpoints or secrets.
No video container is created or retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DEFAULT_OUTPUT_ROOT = Path("data/quarantine/rtsp_frames")
SAFE_SOURCE_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789-_"
)
RTSP_URL_PATTERN = re.compile(r"\brtsps?://[^\s'\"<>]+", re.IGNORECASE)
IMAGE_BASE64_PATTERN = re.compile(
    r"\bdata:image/[^;\s]+;base64,[A-Za-z0-9+/=\r\n]+",
    re.IGNORECASE,
)
LONG_BASE64_PATTERN = re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b")
STREAM_METADATA_FIELDS = (
    "codec_name",
    "codec_type",
    "width",
    "height",
    "avg_frame_rate",
    "pix_fmt",
)


class CaptureError(RuntimeError):
    """A media command or stream validation failed safely."""


@dataclass(frozen=True)
class CaptureConfig:
    """Validated settings for one bounded capture session."""

    source_id: str
    interval_seconds: float = 5.0
    max_frames: int = 180
    max_width: int = 1344
    output_root: Path = DEFAULT_OUTPUT_ROOT
    recorded_start: datetime | None = None

    def validate(self) -> None:
        if not self.source_id or not set(self.source_id) <= SAFE_SOURCE_CHARACTERS:
            raise ValueError(
                "source_id must use lowercase letters, digits, '-' or '_' only"
            )
        if self.interval_seconds < 1:
            raise ValueError("interval_seconds must be at least 1")
        if not 1 <= self.max_frames <= 10_000:
            raise ValueError("max_frames must be between 1 and 10000")
        if not 320 <= self.max_width <= 2688:
            raise ValueError("max_width must be between 320 and 2688")
        if (
            self.recorded_start is not None
            and self.recorded_start.utcoffset() is None
        ):
            raise ValueError("recorded_start must include a UTC offset")


def run_media_command(
    command: list[str], timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg/ffprobe without echoing a command containing the RTSP URL."""
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise CaptureError("media command timed out") from exc
    except subprocess.CalledProcessError as exc:
        detail = redact_sensitive_text(exc.stderr or "unknown media error")
        detail = detail.strip()[-500:] or "unknown media error"
        raise CaptureError(f"media command failed: {detail}") from exc
    except OSError as exc:
        raise CaptureError("could not start ffmpeg/ffprobe") from exc


def redact_sensitive_text(text: str) -> str:
    """Remove RTSP endpoints and image payloads from operator-facing errors."""
    redacted = IMAGE_BASE64_PATTERN.sub("[redacted-image-base64]", text)
    redacted = RTSP_URL_PATTERN.sub("[redacted-rtsp-url]", redacted)
    return LONG_BASE64_PATTERN.sub("[redacted-base64]", redacted)


def validate_rtsp_url(rtsp_url: str) -> None:
    """Accept only a network RTSP endpoint and reject malformed input."""
    parsed = urlsplit(rtsp_url)
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.hostname:
        raise ValueError("STWI_RTSP_URL must be a valid rtsp:// or rtsps:// URL")


def sanitize_stream_metadata(stream: dict[str, Any]) -> dict[str, Any]:
    """Keep only non-sensitive ffprobe fields needed for capture review."""
    return {
        field: stream[field]
        for field in STREAM_METADATA_FIELDS
        if field in stream
    }


def probe_stream(rtsp_url: str) -> dict[str, Any]:
    """Return the single video stream description or fail closed."""
    result = run_media_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-rtsp_transport",
            "tcp",
            "-rw_timeout",
            "12000000",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,avg_frame_rate,pix_fmt",
            "-of",
            "json",
            rtsp_url,
        ],
        timeout_seconds=20,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CaptureError("ffprobe returned invalid JSON") from exc

    video_streams = [
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    ]
    if len(video_streams) != 1:
        raise CaptureError("expected exactly one video stream")
    return video_streams[0]


def build_video_filter(interval_seconds: float, max_width: int) -> str:
    """Build a sparse sampler that preserves aspect ratio and limits storage."""
    return (
        f"fps=1/{interval_seconds:g},"
        f"scale='min(iw,{max_width})':-2:flags=lanczos"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_recorded_at(
    frame: Path,
    recorded_start: datetime | None,
    interval_seconds: float,
) -> str | None:
    """Derive event time from the retained ffmpeg sequence number."""
    if recorded_start is None:
        return None
    try:
        sequence_number = int(frame.stem.rsplit("_", maxsplit=1)[1])
    except (IndexError, ValueError) as exc:
        raise CaptureError(f"invalid frame filename: {frame.name}") from exc
    event_time = recorded_start + timedelta(
        seconds=(sequence_number - 1) * interval_seconds
    )
    return event_time.isoformat()


def remove_exact_duplicates(frames: list[Path]) -> tuple[list[Path], int]:
    """Remove byte-identical frames and return retained frames plus count."""
    retained: list[Path] = []
    known_hashes: set[str] = set()
    for frame in frames:
        digest = sha256_file(frame)
        if digest in known_hashes:
            frame.unlink()
            continue
        known_hashes.add(digest)
        retained.append(frame)
    return retained, len(frames) - len(retained)


def remove_size_outliers(
    frames: list[Path], minimum_median_ratio: float = 0.25
) -> tuple[list[Path], int]:
    """Drop abnormally small startup frames caused by incomplete HEVC GOPs."""
    if not frames:
        return [], 0
    median_size = statistics.median(frame.stat().st_size for frame in frames)
    minimum_size = median_size * minimum_median_ratio
    retained: list[Path] = []
    for frame in frames:
        if frame.stat().st_size < minimum_size:
            frame.unlink()
        else:
            retained.append(frame)
    return retained, len(frames) - len(retained)


def capture(config: CaptureConfig, rtsp_url: str) -> Path:
    """Capture one bounded session and return its quarantine directory."""
    config.validate()
    validate_rtsp_url(rtsp_url)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise CaptureError("ffmpeg and ffprobe must be available on PATH")

    stream = probe_stream(rtsp_url)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
    session_dir = config.output_root / config.source_id / session_id
    session_dir.mkdir(parents=True, exist_ok=False)
    output_pattern = session_dir / "frame_%06d.jpg"

    try:
        run_media_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-fflags",
                "+discardcorrupt",
                "-i",
                rtsp_url,
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                build_video_filter(
                    config.interval_seconds, config.max_width
                ),
                "-frames:v",
                str(config.max_frames),
                "-q:v",
                "3",
                "-map_metadata",
                "-1",
                str(output_pattern),
            ],
            timeout_seconds=int(
                config.interval_seconds * config.max_frames + 45
            ),
        )

        frames, quality_reject_count = remove_size_outliers(
            sorted(session_dir.glob("frame_*.jpg"))
        )
        frames, duplicate_count = remove_exact_duplicates(frames)
        if not frames:
            raise CaptureError("stream produced no usable frames")

        manifest = {
            "schema_version": "1.0",
            "source_id": config.source_id,
            "session_id": session_id,
            "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
            "sampling_interval_seconds": config.interval_seconds,
            "recorded_start": (
                config.recorded_start.isoformat()
                if config.recorded_start is not None
                else None
            ),
            "recorded_time_source": (
                "operator_confirmed_burned_in_overlay"
                if config.recorded_start is not None
                else "unknown"
            ),
            "split_group": (
                f"{config.source_id}:{config.recorded_start.date().isoformat()}"
                if config.recorded_start is not None
                else session_id
            ),
            "privacy_status": "needs_review",
            "retention_class": "temporary_quarantine",
            "raw_video_retained": False,
            "quality_rejects_removed": quality_reject_count,
            "exact_duplicates_removed": duplicate_count,
            "stream": sanitize_stream_metadata(stream),
            "frames": [
                {
                    "path": frame.name,
                    "sha256": sha256_file(frame),
                    "size_bytes": frame.stat().st_size,
                    "recorded_at": frame_recorded_at(
                        frame,
                        config.recorded_start,
                        config.interval_seconds,
                    ),
                    "privacy_status": "needs_review",
                }
                for frame in frames
            ],
        }
        (session_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (CaptureError, OSError):
        shutil.rmtree(session_dir, ignore_errors=True)
        raise
    return session_dir


def parse_args(argv: list[str]) -> CaptureConfig:
    parser = argparse.ArgumentParser(
        description="Capture sparse RTSP frames into an untracked quarantine."
    )
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--max-frames", type=int, default=180)
    parser.add_argument("--max-width", type=int, default=1344)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--recorded-start",
        type=datetime.fromisoformat,
        help="Event time of frame_000001, including UTC offset",
    )
    args = parser.parse_args(argv)
    return CaptureConfig(
        source_id=args.source_id,
        interval_seconds=args.interval_seconds,
        max_frames=args.max_frames,
        max_width=args.max_width,
        output_root=args.output_root,
        recorded_start=args.recorded_start,
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv if argv is not None else sys.argv[1:])
    rtsp_url = os.environ.get("STWI_RTSP_URL")
    if not rtsp_url:
        print("STWI_RTSP_URL is required", file=sys.stderr)
        return 2
    try:
        session_dir = capture(config, rtsp_url)
    except (CaptureError, ValueError) as exc:
        redacted_msg = redact_sensitive_text(str(exc))
        print(f"capture failed: {redacted_msg}", file=sys.stderr)
        return 1
    print(session_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
