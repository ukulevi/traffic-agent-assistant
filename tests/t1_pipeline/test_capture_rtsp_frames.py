import hashlib
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.data_prep.capture_rtsp_frames import (
    CaptureConfig,
    build_video_filter,
    frame_recorded_at,
    remove_exact_duplicates,
    remove_size_outliers,
    sha256_file,
    validate_rtsp_url,
)


class CaptureRtspFramesTest(unittest.TestCase):
    def test_filter_samples_and_limits_width(self) -> None:
        self.assertEqual(
            build_video_filter(5.0, 1344),
            "fps=1/5,scale='min(iw,1344)':-2:flags=lanczos",
        )

    def test_config_rejects_unsafe_source_id(self) -> None:
        config = CaptureConfig(source_id="../camera")
        with self.assertRaises(ValueError):
            config.validate()

    def test_rtsp_url_validation(self) -> None:
        validate_rtsp_url("rtsp://camera.example.test/live")
        with self.assertRaises(ValueError):
            validate_rtsp_url("https://camera.example.test/live")

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


if __name__ == "__main__":
    unittest.main()
