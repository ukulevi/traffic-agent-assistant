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



class VisionDatasetPreparationTest(unittest.TestCase):

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

    def test_prepares_roboflow_export_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_export(root)
            source = read_roboflow_yaml(root / "data.yaml")
            self.assertEqual(source["names"], ["bus", "car", "motorbike", "truck"])

            manifest = build_manifest(
                root,
                dataset_version="unit_v001",
                privacy_status="needs_review",
                reviewer="tester",
                notes="unit test",
            )

            self.assertTrue((root / "dataset.yaml").is_file())
            self.assertEqual(len(manifest["records"]), 3)
            self.assertEqual(manifest["split_counts"], {"train": 1, "val": 1, "test": 1})
            self.assertEqual(manifest["stwi_class_map"]["motorbike"], "motorcycle")
            self.assertEqual(
                manifest["label_transform"]["converted_label_count"],
                3,
            )

    def test_builds_vehicle_only_dataset_with_short_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            output = Path(directory) / "vehicles"
            root.mkdir()
            self._write_export(root)
            build_manifest(
                root,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )

            manifest = build_vehicle_dataset(root, output)

            self.assertEqual(manifest["classes"], ["bus", "car", "motorcycle", "truck"])
            self.assertEqual(manifest["object_counts"], {"car": 3, "motorcycle": 3})
            self.assertEqual(len(manifest["records"]), 3)
            first_record = manifest["records"][0]
            self.assertEqual(first_record["image"], "train/images/train_000000.jpg")
            label = output / first_record["label"]
            self.assertIn("2 0.250000", label.read_text(encoding="utf-8"))
