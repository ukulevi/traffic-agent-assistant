import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.infra.roboflow_mcp_server import (
    RoboflowMcpError,
    ensure_workspace_path,
    handle_message,
    redact_secrets,
    safe_extract_zip,
    validate_export_format,
    validate_slug,
)


class RoboflowMcpServerTest(unittest.TestCase):
    def test_redacts_api_keys_in_nested_payload(self) -> None:
        payload = {
            "link": "https://api.roboflow.com/x?api_key=secret&format=yolo",
            "items": ["https://example.test/path?ok=1&api_key=secret"],
        }
        redacted = redact_secrets(payload)
        self.assertNotIn("secret", json.dumps(redacted))
        self.assertIn("api_key=<redacted>", redacted["link"])

    def test_validates_slugs_and_export_format(self) -> None:
        self.assertEqual(validate_slug("traffic-light_01", "project"), "traffic-light_01")
        self.assertEqual(validate_export_format("yolov5pytorch"), "yolov5pytorch")
        with self.assertRaises(RoboflowMcpError):
            validate_slug("../outside", "project")
        with self.assertRaises(RoboflowMcpError):
            validate_export_format("raw-video")

    def test_output_dir_must_stay_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inside = ensure_workspace_path(root / "data/external/roboflow/a", root)
            self.assertTrue(str(inside).startswith(str(root.resolve())))
            with self.assertRaises(RoboflowMcpError):
                ensure_workspace_path(root.parent / "outside", root)

    def test_safe_extract_rejects_zip_slip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../escape.txt", "nope")
            with self.assertRaises(RoboflowMcpError):
                safe_extract_zip(archive, root / "out")

    def test_safe_extract_accepts_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "ok.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("train/labels/a.txt", "0 0.5 0.5 0.1 0.1")
            extracted = safe_extract_zip(archive, root / "out")
            self.assertEqual(extracted, ["train/labels/a.txt"])
            self.assertTrue((root / "out/train/labels/a.txt").is_file())

    def test_mcp_tools_list_response(self) -> None:
        response = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )
        self.assertIsNotNone(response)
        tools = response["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("roboflow_universe_search", names)
        self.assertIn("roboflow_download_dataset", names)

    def test_mcp_content_length_round_trip_shape(self) -> None:
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        body = json.dumps(message).encode("utf-8")
        stream = io.BytesIO(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        from scripts.infra.roboflow_mcp_server import read_mcp_message

        self.assertEqual(read_mcp_message(stream), message)


if __name__ == "__main__":
    unittest.main()
