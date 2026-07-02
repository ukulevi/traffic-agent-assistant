import os
import tempfile
import unittest
from pathlib import Path

from stwi.t1_pipeline.roboflow_workflow import (
    RoboflowImageInput,
    RoboflowWorkflowRequestError,
    RoboflowWorkflowResult,
    parse_workflow_response,
    run_stwi_traffic_workflow,
    workflow_output_names,
    workflow_parameter_names,
    write_image_outputs,
)


SAMPLE_IMAGE_URL = (
    "https://source.roboflow.com/x7ue3g34EbVgYS7WvQy9Ls9Tgyw2/"
    "oy10BM76QxdI4X9hjMou/original.jpg"
)


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run_workflow(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class RoboflowWorkflowClientTest(unittest.TestCase):
    def test_declares_no_runtime_parameters(self) -> None:
        self.assertEqual(workflow_parameter_names(), ())

    def test_validates_https_url_input(self) -> None:
        with self.assertRaises(ValueError):
            RoboflowImageInput.https_url("http://example.test/image.jpg")
        image = RoboflowImageInput.https_url("https://example.test/image.jpg")
        self.assertEqual(image.kind, "url")

    def test_runs_workflow_with_declared_output_keys(self) -> None:
        output_name = workflow_output_names()[0]
        fake = FakeClient([{output_name: {"predictions": []}}])
        result = run_stwi_traffic_workflow(
            RoboflowImageInput.https_url(SAMPLE_IMAGE_URL),
            client=fake,
            retries=0,
        )
        self.assertEqual(result.output_names, workflow_output_names())
        self.assertIn(output_name, result.first())
        self.assertEqual(fake.calls[0]["workflow_id"], "stwi-traffic-unified-phase-2-v1-logic")
        self.assertEqual(fake.calls[0]["workspace_name"], "lymphaticvesselsegmentation")

    def test_rejects_missing_declared_output_key(self) -> None:
        with self.assertRaises(RoboflowWorkflowRequestError):
            parse_workflow_response([{"unexpected": []}])

    def test_writes_image_shaped_outputs(self) -> None:
        result = RoboflowWorkflowResult(
            output_names=("visualization",),
            entries=(
                {
                    "visualization": {
                        "type": "base64",
                        "value": "iVBORw0KGgo=",
                    }
                },
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            written = write_image_outputs(result, Path(directory))
            self.assertEqual(len(written["visualization"]), 1)
            self.assertTrue(written["visualization"][0].is_file())

    def test_validates_base64_jpeg_input(self) -> None:
        import base64
        jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x00\x00"
        jpeg_b64 = base64.b64encode(jpeg_data).decode()
        
        image = RoboflowImageInput.base64(jpeg_b64)
        self.assertEqual(image.kind, "base64")
        self.assertIn("value_len", repr(image))
        self.assertNotIn(jpeg_b64, repr(image))

    def test_validates_data_url_png_input(self) -> None:
        import base64
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00"
        png_b64 = base64.b64encode(png_data).decode()
        data_url = f"data:image/png;base64,{png_b64}"
        
        image = RoboflowImageInput.base64(data_url)
        self.assertEqual(image.kind, "base64")
        self.assertIn("value_len", repr(image))
        self.assertNotIn(png_b64, repr(image))

    def test_rejects_invalid_base64_chars(self) -> None:
        with self.assertRaises(ValueError):
            RoboflowImageInput.base64("not-base64-at-all!!!")

    def test_rejects_wrong_image_signature(self) -> None:
        import base64
        wrong_data = b"wrongsignature!!!"
        wrong_b64 = base64.b64encode(wrong_data).decode()
        with self.assertRaises(ValueError):
            RoboflowImageInput.base64(wrong_b64)


@unittest.skipUnless(
    os.environ.get("STWI_RUN_ROBOFLOW_SMOKE") == "1"
    and bool(os.environ.get("ROBOFLOW_API_KEY")),
    "set STWI_RUN_ROBOFLOW_SMOKE=1 and ROBOFLOW_API_KEY to run live Roboflow smoke test",
)
class RoboflowWorkflowLiveSmokeTest(unittest.TestCase):
    def test_live_workflow_returns_declared_outputs(self) -> None:
        result = run_stwi_traffic_workflow(
            RoboflowImageInput.https_url(
                os.environ.get("STWI_ROBOFLOW_SMOKE_IMAGE_URL", SAMPLE_IMAGE_URL)
            ),
            timeout_seconds=45,
            retries=1,
        )
        self.assertGreaterEqual(len(result.entries), 1)
        self.assertEqual(result.output_names, workflow_output_names())
        for output_name in workflow_output_names():
            self.assertIn(output_name, result.first())


if __name__ == "__main__":
    unittest.main()
