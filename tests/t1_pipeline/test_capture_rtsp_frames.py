import contextlib
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from scripts.data_prep import capture_rtsp_frames
from scripts.data_prep.capture_rtsp_frames import (
    CaptureConfig,
    CaptureError,
    build_video_filter,
    capture,
    frame_recorded_at,
    remove_exact_duplicates,
    remove_size_outliers,
    run_media_command,
    sha256_file,
    validate_rtsp_url,
)


def sample_rtsp_url(
    scheme: str = "rtsp",
    userinfo: str | None = None,
    host: str = "camera.invalid",
) -> str:
    authority = host if userinfo is None else f"{userinfo}@{host}"
    return f"{scheme}://{authority}/live"


class CaptureRtspFramesTest(unittest.TestCase):
    def test_filter_samples_and_limits_width(self) -> None:
        self.assertEqual(
            build_video_filter(5.0, 1344),
            "fps=1/5,scale='min(iw,1344)':-2:flags=lanczos",
        )

    def test_config_rejects_unsafe_source_id(self) -> None:
        for source_id in ("../camera", "Edge_Camera_1", "edge camera 1"):
            with self.subTest(source_id=source_id):
                config = CaptureConfig(source_id=source_id)
                with self.assertRaises(ValueError):
                    config.validate()

    def test_config_accepts_edge_camera_source_id(self) -> None:
        CaptureConfig(source_id="edge_camera_1").validate()

    def test_rtsp_url_validation(self) -> None:
        sensitive_user = "u" * 6
        sensitive_token = "p" * 12
        validate_rtsp_url(sample_rtsp_url())
        validate_rtsp_url(
            sample_rtsp_url(
                "rtsps", userinfo=f"{sensitive_user}:{sensitive_token}"
            )
        )
        for url in (
            sample_rtsp_url("https"),
            f"{'rtsp'}:///missing-host",
            "not-a-url",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_rtsp_url(url)

    def test_main_requires_rtsp_env_without_opening_stream(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(capture_rtsp_frames, "capture") as capture_mock,
            contextlib.redirect_stderr(stderr),
        ):
            result = capture_rtsp_frames.main(
                ["--source-id", "edge_camera_1"]
            )

        self.assertEqual(result, 2)
        self.assertEqual(stderr.getvalue(), "STWI_RTSP_URL is required\n")
        capture_mock.assert_not_called()

    def test_invalid_url_fails_closed_before_stream_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = CaptureConfig(
                source_id="edge_camera_1",
                output_root=Path(directory),
            )
            with (
                mock.patch.object(
                    capture_rtsp_frames, "probe_stream"
                ) as probe_mock,
                mock.patch.object(
                    capture_rtsp_frames.shutil, "which"
                ) as which_mock,
            ):
                with self.assertRaises(ValueError):
                    capture(config, sample_rtsp_url("https"))

            probe_mock.assert_not_called()
            which_mock.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_media_command_error_redacts_sensitive_output(self) -> None:
        image_payload = "A" * 120
        sensitive_user = "u" * 6
        sensitive_token = "p" * 12
        sensitive_host = "camera.invalid"
        endpoint = sample_rtsp_url(
            userinfo=f"{sensitive_user}:{sensitive_token}",
            host=sensitive_host,
        )
        stderr = (
            f"failed to open {endpoint} "
            f"preview data:image/jpeg;base64,{image_payload}"
        )
        with mock.patch.object(
            capture_rtsp_frames.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(
                1, ["ffprobe"], stderr=stderr
            ),
        ):
            with self.assertRaises(CaptureError) as context:
                run_media_command(["ffprobe", "placeholder"], 1)

        message = str(context.exception)
        self.assertIn("[redacted-rtsp-url]", message)
        self.assertIn("[redacted-image-base64]", message)
        self.assertNotIn("rtsp://", message)
        self.assertNotIn(sensitive_user, message)
        self.assertNotIn(sensitive_token, message)
        self.assertNotIn(sensitive_host, message)
        self.assertNotIn(image_payload, message)

    def test_manifest_excludes_endpoint_credentials_and_payloads(self) -> None:
        def fake_run_media_command(
            command: list[str], timeout_seconds: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout_seconds
            if command[0] == "ffmpeg":
                output_pattern = Path(command[-1])
                for index, payload in enumerate(
                    (b"frame-one", b"frame-two"), start=1
                ):
                    frame = Path(
                        str(output_pattern).replace(
                            "%06d", f"{index:06d}"
                        )
                    )
                    frame.write_bytes(payload * 32)
            return subprocess.CompletedProcess(command, 0, "", "")

        sensitive_user = "u" * 6
        sensitive_token = "p" * 12
        sensitive_host = "camera.invalid"
        endpoint = sample_rtsp_url(
            userinfo=f"{sensitive_user}:{sensitive_token}",
            host=sensitive_host,
        )
        with tempfile.TemporaryDirectory() as directory:
            config = CaptureConfig(
                source_id="edge_camera_1",
                max_frames=2,
                output_root=Path(directory),
            )
            with (
                mock.patch.object(
                    capture_rtsp_frames.shutil,
                    "which",
                    return_value="ffmpeg",
                ),
                mock.patch.object(
                    capture_rtsp_frames,
                    "probe_stream",
                    return_value={
                        "codec_name": "h264",
                        "codec_type": "video",
                        "width": 1280,
                        "height": 720,
                        "avg_frame_rate": "25/1",
                        "pix_fmt": "yuv420p",
                        "debug_source": endpoint,
                        "thumbnail": f"data:image/jpeg;base64,{'B' * 120}",
                    },
                ),
                mock.patch.object(
                    capture_rtsp_frames,
                    "run_media_command",
                    side_effect=fake_run_media_command,
                ),
            ):
                session_dir = capture(config, endpoint)

            manifest_text = (session_dir / "manifest.json").read_text(
                encoding="utf-8"
            )
            manifest = json.loads(manifest_text)

        self.assertEqual(manifest["source_id"], "edge_camera_1")
        self.assertFalse(manifest["raw_video_retained"])
        self.assertEqual(
            set(manifest["stream"]),
            {
                "avg_frame_rate",
                "codec_name",
                "codec_type",
                "height",
                "pix_fmt",
                "width",
            },
        )
        for forbidden in (
            "rtsp://",
            sensitive_user,
            sensitive_token,
            sensitive_host,
            "data:image",
            "base64",
            ".mp4",
            ".mkv",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, manifest_text)

    def test_recorded_start_requires_timezone(self) -> None:
        config = CaptureConfig(
            source_id="camera_1",
            recorded_start=datetime.fromisoformat("2025-05-30T10:15:18"),
        )
        with self.assertRaises(ValueError):
            config.validate()

    def test_frame_recorded_at_uses_sequence_number(self) -> None:
        recorded_start = datetime.fromisoformat("2025-05-30T10:15:18+07:00")
        self.assertEqual(
            frame_recorded_at(
                Path("frame_000003.jpg"), recorded_start, 2.0
            ),
            "2025-05-30T10:15:22+07:00",
        )

    def test_sha256_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.jpg"
            path.write_bytes(b"frame")
            self.assertEqual(
                sha256_file(path), hashlib.sha256(b"frame").hexdigest()
            )

    def test_remove_exact_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "frame_001.jpg"
            duplicate = root / "frame_002.jpg"
            unique = root / "frame_003.jpg"
            first.write_bytes(b"same")
            duplicate.write_bytes(b"same")
            unique.write_bytes(b"different")

            retained, removed = remove_exact_duplicates(
                [first, duplicate, unique]
            )

            self.assertEqual(retained, [first, unique])
            self.assertEqual(removed, 1)
            self.assertFalse(duplicate.exists())

    def test_remove_size_outliers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corrupt = root / "frame_001.jpg"
            valid_one = root / "frame_002.jpg"
            valid_two = root / "frame_003.jpg"
            corrupt.write_bytes(b"x" * 10)
            valid_one.write_bytes(b"x" * 100)
            valid_two.write_bytes(b"x" * 120)

            retained, removed = remove_size_outliers(
                [corrupt, valid_one, valid_two]
            )

            self.assertEqual(retained, [valid_one, valid_two])
            self.assertEqual(removed, 1)
            self.assertFalse(corrupt.exists())

    def test_cli_error_boundary_redacts_credentials_and_payloads(self) -> None:
        sensitive_user = "user_secret"
        sensitive_pass = "pass_secret"
        sensitive_host = "secret.host"
        url = f"rtsp://{sensitive_user}:{sensitive_pass}@{sensitive_host}/live"
        image_payload = "ABCDEF" * 50
        error_msg = f"failed to load from {url} base64 payload: data:image/jpeg;base64,{image_payload}"

        stderr = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"STWI_RTSP_URL": "rtsp://localhost/live"}),
            mock.patch.object(
                capture_rtsp_frames, "capture", side_effect=CaptureError(error_msg)
            ),
            contextlib.redirect_stderr(stderr),
        ):
            result = capture_rtsp_frames.main(["--source-id", "edge_camera_1"])

        self.assertEqual(result, 1)
        stderr_output = stderr.getvalue()

        # Stderr must not contain the sensitive details
        self.assertNotIn("rtsp://", stderr_output)
        self.assertNotIn(sensitive_user, stderr_output)
        self.assertNotIn(sensitive_pass, stderr_output)
        self.assertNotIn(sensitive_host, stderr_output)
        self.assertNotIn("data:image", stderr_output)
        self.assertNotIn(image_payload, stderr_output)

        # Stderr must contain the redaction markers
        self.assertIn("[redacted-rtsp-url]", stderr_output)
        self.assertIn("[redacted-image-base64]", stderr_output)


if __name__ == "__main__":
    unittest.main()
