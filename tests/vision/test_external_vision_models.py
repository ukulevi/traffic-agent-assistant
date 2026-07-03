import json
import hashlib
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scripts.data_prep.augment_vehicle_dataset_with_motorcycle import augment_dataset
from scripts.data_prep.augment_vehicle_dataset_with_review_pack import augment_with_review_pack
from scripts.data_prep.augment_vehicle_dataset_with_yolo_sources import (
    augment_dataset as augment_with_yolo_sources,
)
from scripts.data_prep.augment_vehicle_dataset_with_object_crops import (
    CropSpec,
    augment_with_object_crops,
)
from scripts.data_prep.build_vision_error_review_pack import (
    Box,
    box_iou,
    unmatched_boxes,
    unmatched_predictions,
)
from scripts.data_prep.build_vision_error_review_pack import read_source_class_names
from scripts.data_prep.build_stwi_vehicle_yolo_dataset import build_vehicle_dataset
from scripts.infra.finalize_motorcycle_relabel_review import finalize_review
from scripts.infra.finalize_vision_label_fix_candidates import (
    finalize_label_fix_candidates,
    update_candidate_review_status,
)
from scripts.data_prep.prepare_roboflow_yolo_dataset import build_manifest, read_roboflow_yaml
from scripts.training.rebalance_vehicle_training_dataset import rebalance_dataset
from scripts.training.rebalance_vehicle_training_dataset_from_errors import select_error_rows
from scripts.data_prep.relabel_helmet_dataset_for_motorcycle import (
    RelabelDetection,
    build_relabel_dataset_from_detections,
)
from stwi.t1_pipeline.local_vision import (
    LocalVisionModelError,
    load_official_vision_model_artifact,
)
from stwi.tooling.vision_training.external_models import (
    build_external_verdict,
    load_external_manifest,
    normalize_sha256,
    register_external_model,
    require_https_url,
    write_stream_with_sha256,
)
from stwi.tooling.vision_training.promotion import promote_artifact
from stwi.utils.file_hash import sha256_file



class ExternalVisionModelsTest(unittest.TestCase):

    def _write_export(self, root: Path) -> None:
        (root / "data.yaml").write_text(
            "\n".join([
                "train: ../train/images",
                "val: ../valid/images",
                "test: ../test/images",
                "",
                "nc: 4",
                "names: ['bus', 'car', 'motorbike', 'truck']",
                "",
                "roboflow:",
                "  workspace: test-workspace",
                "  project: stwi-test",
                "  version: 1",
                "  license: CC BY 4.0",
            ]) + "\n",
            encoding="utf-8",
        )
        for split_dir in ("train", "valid", "test"):
            image_dir = root / split_dir / "images"
            label_dir = root / split_dir / "labels"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            image_path = image_dir / f"{split_dir}_001.jpg"
            Image.new("RGB", (8, 8), "white").save(image_path)
            (label_dir / f"{split_dir}_001.txt").write_text(
                (
                    "1 0.500000 0.500000 0.250000 0.250000\n"
                    "2 0.100000 0.100000 0.400000 0.100000 "
                    "0.400000 0.300000 0.100000 0.300000\n"
                ),
                encoding="utf-8",
            )

    def test_registers_external_detector_candidate_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"external-weights")

            manifest = register_external_model(
                model_id="owner/traffic-yolo",
                source_url="https://huggingface.co/owner/traffic-yolo",
                source_license="mit",
                weights_path=weights,
                output_root=root / "external",
                model_family="yolo",
                source_classes=["bus", "car", "motor", "truck"],
                class_map_values=[
                    "bus:bus",
                    "car:car",
                    "motor:motorcycle",
                    "truck:truck",
                ],
                class_alias_values=["motor:motorcycle"],
                prompt_classes=None,
                reviewer="tester",
                notes="unit test",
                copy_weights=True,
                overwrite=False,
            )

            manifest_path = Path(manifest["manifest_path"])
            self.assertTrue(manifest_path.is_file())
            self.assertEqual(manifest["candidate_status"], "ready_for_local_benchmark")
            self.assertEqual(manifest["missing_stwi_classes"], [])
            self.assertEqual(manifest["class_aliases"], {"motor": "motorcycle"})
            self.assertEqual(manifest["weights_sha256"], sha256_file(Path(manifest["weights"])))

    def test_external_detector_registration_requires_https_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"external-weights")

            with self.assertRaises(ValueError):
                register_external_model(
                    model_id="owner/traffic-yolo",
                    source_url="http://example.com/model",
                    source_license="mit",
                    weights_path=weights,
                    output_root=root / "external",
                    model_family="yolo",
                    source_classes=[],
                    class_map_values=[],
                    class_alias_values=[],
                    prompt_classes=None,
                    reviewer="tester",
                    notes="unit test",
                    copy_weights=False,
                    overwrite=False,
                )

    def test_external_benchmark_verdict_keeps_sample_runs_non_promotable(self) -> None:
        verdict = build_external_verdict(
            map50=0.91,
            seconds_per_image=0.04,
            min_map50=0.85,
            splits=["val"],
            max_images=200,
            baseline_map50=0.6902,
        )

        self.assertEqual(verdict["status"], "metric_promising_requires_full_gate")
        self.assertIn("sample_only_not_promotable", verdict["reasons"])
        self.assertIn("test_split_not_evaluated", verdict["reasons"])

    def test_external_manifest_loader_rejects_checksum_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"external-weights")
            manifest = register_external_model(
                model_id="owner/traffic-yolo",
                source_url="https://huggingface.co/owner/traffic-yolo",
                source_license="mit",
                weights_path=weights,
                output_root=root / "external",
                model_family="yolo",
                source_classes=["bus", "car", "motor", "truck"],
                class_map_values=[
                    "bus:bus",
                    "car:car",
                    "motor:motorcycle",
                    "truck:truck",
                ],
                class_alias_values=["motor:motorcycle"],
                prompt_classes=None,
                reviewer="tester",
                notes="unit test",
                copy_weights=True,
                overwrite=False,
            )
            Path(manifest["weights"]).write_bytes(b"modified")

            with self.assertRaises(ValueError):
                load_external_manifest(Path(manifest["manifest_path"]))

    def test_fetch_external_weight_stream_verifies_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "best.pt"
            payload = b"external-weights"
            expected_sha = hashlib.sha256(payload).hexdigest()

            result = write_stream_with_sha256(
                source=BytesIO(payload),
                output_path=output,
                expected_sha256=expected_sha,
                overwrite=False,
            )

            self.assertEqual(result["status"], "downloaded")
            self.assertEqual(result["sha256"], expected_sha)
            self.assertEqual(output.read_bytes(), payload)

    def test_fetch_external_weight_stream_rejects_bad_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "best.pt"
            wrong_sha = "0" * 64

            with self.assertRaises(ValueError):
                write_stream_with_sha256(
                    source=BytesIO(b"external-weights"),
                    output_path=output,
                    expected_sha256=wrong_sha,
                    overwrite=False,
                )

            self.assertFalse(output.exists())

    def test_fetch_external_weight_requires_https_and_valid_sha(self) -> None:
        self.assertEqual(
            require_https_url("https://huggingface.co/model/resolve/main/best.pt"),
            "https://huggingface.co/model/resolve/main/best.pt",
        )
        with self.assertRaises(ValueError):
            require_https_url("http://huggingface.co/model/resolve/main/best.pt")
        with self.assertRaises(ValueError):
            normalize_sha256("not-a-sha")


if __name__ == "__main__":
    unittest.main()
