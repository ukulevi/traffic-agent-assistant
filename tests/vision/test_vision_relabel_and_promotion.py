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
from stwi.tooling.vision_training.promotion import (
    DEFAULT_MVP_MAP50,
    promote_artifact,
    validate_artifact_for_promotion,
)
from stwi.utils.file_hash import sha256_file



class VisionRelabelAndPromotionTest(unittest.TestCase):

    def _promotion_artifact(self, weights: Path) -> dict[str, object]:
        return {
            "model_version": "unit",
            "weights": str(weights),
            "weights_sha256": sha256_file(weights),
            "dataset_version": "unit_v001",
            "stwi_class_map": {
                "bus": "bus",
                "car": "car",
                "motorbike": "motorcycle",
                "truck": "truck",
            },
            "privacy_status": "visual_spot_reviewed_agent",
            "metrics": {"metrics/mAP50(B)": 0.99},
            "calibration": {
                "confidence_threshold": 0.25,
                "iou_threshold": 0.5,
                "image_size": 640,
                "roi_policy": "reviewed_camera_roi_v1",
            },
            "benchmark": {
                "profile": "unit_cpu",
                "seconds_per_image_p50": 0.01,
                "seconds_per_image_p99": 0.02,
            },
            "legal_and_privacy": {
                "source_license": "MIT",
                "privacy_status": "visual_spot_reviewed_agent",
            },
        }

    def test_promotion_rejects_invalid_required_metadata_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "best.pt"
            weights.write_bytes(b"weights")
            cases = (
                ("calibration", "confidence_threshold", "0.25"),
                ("calibration", "roi_policy", "   "),
                ("benchmark", "seconds_per_image_p99", -0.01),
                ("legal_and_privacy", "source_license", ""),
            )
            for section, field, value in cases:
                with self.subTest(section=section, field=field):
                    artifact = self._promotion_artifact(weights)
                    artifact[section][field] = value
                    with self.assertRaisesRegex(ValueError, f"invalid {section}.{field}"):
                        validate_artifact_for_promotion(artifact, min_map50=0.85)

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

    def test_promotion_rejects_pending_privacy_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"weights")
            artifact = {
                "model_version": "unit",
                "weights": str(weights),
                "weights_sha256": sha256_file(weights),
                "dataset_version": "unit_v001",
                "classes": ["bus", "car", "motorbike", "truck"],
                "stwi_class_map": {
                    "bus": "bus",
                    "car": "car",
                    "motorbike": "motorcycle",
                    "truck": "truck",
                },
                "privacy_status": "needs_review",
                "metrics": {"metrics/mAP50(B)": 0.99},
            }
            artifact_path = root / "artifact.json"
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

            with self.assertRaises(ValueError):
                promote_artifact(
                    artifact_path,
                    root / "official",
                    min_map50=0.85,
                    approver="tester",
                    notes="unit test",
                )

    def test_builds_helmet_relabel_candidate_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "helmet"
            output = Path(directory) / "relabel"
            image_dir = source / "train" / "images"
            label_dir = source / "train" / "labels"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            image_path = image_dir / "helmet_001.jpg"
            Image.new("RGB", (16, 16), "white").save(image_path)
            (label_dir / "helmet_001.txt").write_text(
                "0 0.500000 0.250000 0.100000 0.100000\n",
                encoding="utf-8",
            )
            (source / "data.yaml").write_text(
                "\n".join([
                    "train: ../train/images",
                    "val: ../valid/images",
                    "test: ../test/images",
                    "nc: 1",
                    "names: ['helmet']",
                ]) + "\n",
                encoding="utf-8",
            )

            manifest = build_relabel_dataset_from_detections(
                source_root=source,
                output_root=output,
                detections_by_image={
                    image_path: [RelabelDetection(0.5, 0.5, 0.4, 0.4, 0.92)]
                },
                dataset_version="helmet_relabel_unit",
                model_path="unit.pt",
                min_confidence=0.55,
                max_images=10,
                reviewer="tester",
            )

            self.assertEqual(manifest["classes"], ["motorcycle"])
            self.assertEqual(manifest["privacy_status"], "needs_review")
            self.assertEqual(manifest["split_counts"], {"train": 1})
            first_record = manifest["records"][0]
            self.assertEqual(first_record["review_status"], "needs_human_spot_review")
            label = output / first_record["label"]
            self.assertTrue(label.read_text(encoding="utf-8").startswith("0 0.500000"))
            self.assertTrue((output / "review" / "review_queue.csv").is_file())

    def test_finalizes_only_accepted_relabel_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "helmet"
            relabel = Path(directory) / "relabel"
            reviewed = Path(directory) / "reviewed"
            image_dir = source / "train" / "images"
            label_dir = source / "train" / "labels"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            image_path = image_dir / "helmet_001.jpg"
            Image.new("RGB", (16, 16), "white").save(image_path)
            (label_dir / "helmet_001.txt").write_text(
                "0 0.500000 0.250000 0.100000 0.100000\n",
                encoding="utf-8",
            )
            (source / "data.yaml").write_text(
                "names: ['helmet']\n",
                encoding="utf-8",
            )
            build_relabel_dataset_from_detections(
                source_root=source,
                output_root=relabel,
                detections_by_image={
                    image_path: [RelabelDetection(0.5, 0.5, 0.4, 0.4, 0.92)]
                },
                dataset_version="helmet_relabel_unit",
                model_path="unit.pt",
                min_confidence=0.55,
                max_images=10,
                reviewer="tester",
            )
            review_queue = relabel / "review" / "review_queue.csv"
            review_queue.write_text(
                review_queue.read_text(encoding="utf-8").replace("pending", "accepted"),
                encoding="utf-8",
            )

            manifest = finalize_review(
                relabel_root=relabel,
                output_root=reviewed,
                reviewer="tester",
                notes="unit accepted",
            )

            self.assertEqual(manifest["privacy_status"], "visual_spot_reviewed_agent")
            self.assertEqual(manifest["split_counts"], {"train": 1})
            self.assertEqual(manifest["records"][0]["review_status"], "accepted")

    def test_official_loader_requires_promoted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"weights")
            manifest = {
                "model_version": "unit",
                "weights": str(weights),
                "weights_sha256": sha256_file(weights),
                "dataset_version": "unit_v001",
                "classes": ["bus", "car", "motorbike", "truck"],
                "stwi_class_map": {
                    "bus": "bus",
                    "car": "car",
                    "motorbike": "motorcycle",
                    "truck": "truck",
                },
                "privacy_status": "visual_spot_reviewed_agent",
                "promotion_status": "candidate_ready_for_review",
                "metrics": {"metrics/mAP50(B)": 0.99},
            }
            manifest_path = root / "model_artifact.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(LocalVisionModelError):
                load_official_vision_model_artifact(manifest_path)

            manifest["promotion_status"] = "official_mvp_primary"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_official_vision_model_artifact(manifest_path)
            self.assertEqual(loaded.model_version, "unit")

            weights.write_bytes(b"tampered")
            with self.assertRaisesRegex(LocalVisionModelError, "checksum mismatch"):
                load_official_vision_model_artifact(manifest_path)

    def test_official_loader_rejects_below_gate_metric(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / "best.pt"
            weights.write_bytes(b"weights")
            manifest = {
                "model_version": "below-gate",
                "weights": str(weights),
                "weights_sha256": sha256_file(weights),
                "dataset_version": "unit_v001",
                "classes": ["bus", "car", "motorbike", "truck"],
                "stwi_class_map": {
                    "bus": "bus",
                    "car": "car",
                    "motorbike": "motorcycle",
                    "truck": "truck",
                },
                "privacy_status": "visual_spot_reviewed_agent",
                "promotion_status": "official_mvp_primary",
                "metrics": {"metrics/mAP50(B)": DEFAULT_MVP_MAP50 - 0.01},
            }
            manifest_path = root / "model_artifact.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(LocalVisionModelError, "mAP50 promotion gate"):
                load_official_vision_model_artifact(manifest_path)
