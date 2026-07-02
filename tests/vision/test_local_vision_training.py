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
from scripts.benchmark_external_vision_model import (
    build_external_verdict,
    load_external_manifest,
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
from scripts.infra.fetch_external_vision_model import (
    normalize_sha256,
    require_https_url,
    write_stream_with_sha256,
)
from scripts.data_prep.prepare_roboflow_yolo_dataset import build_manifest, read_roboflow_yaml
from scripts.training.promote_vision_model import promote_artifact
from scripts.training.rebalance_vehicle_training_dataset import rebalance_dataset
from scripts.training.rebalance_vehicle_training_dataset_from_errors import select_error_rows
from scripts.data_prep.relabel_helmet_dataset_for_motorcycle import (
    RelabelDetection,
    build_relabel_dataset_from_detections,
)
from scripts.infra.register_external_vision_model import register_external_model
from scripts.training.train_vision_model import sha256_file
from stwi.t1_pipeline.local_vision import (
    LocalVisionModelError,
    load_official_vision_model_artifact,
)


class LocalVisionTrainingTest(unittest.TestCase):
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

    def test_augments_vehicle_dataset_with_annotated_motorcycles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            supplement = Path(directory) / "supplement"
            output = Path(directory) / "augmented"
            source.mkdir()
            supplement.mkdir()
            self._write_export(source)
            self._write_export(supplement)
            for index, image_path in enumerate(supplement.rglob("*.jpg"), start=1):
                Image.new("RGB", (8, 8), (index, index, index)).save(image_path)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_manifest(
                supplement,
                dataset_version="unit_moto",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)

            manifest = augment_dataset(
                base_root=vehicle_base,
                output_root=output,
                annotated_sources=[supplement],
                pseudo_sources=[],
                pseudo_model="unused.pt",
                pseudo_conf=0.3,
            )

            self.assertEqual(manifest["supplement"]["new_records"], 3)
            self.assertEqual(manifest["split_counts"], {"train": 4, "val": 1, "test": 1})
            self.assertEqual(manifest["object_counts"]["motorcycle"], 6)

    def test_augments_vehicle_dataset_with_multi_class_yolo_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            supplement = Path(directory) / "vietnam"
            output = Path(directory) / "augmented"
            source.mkdir()
            supplement.mkdir()
            self._write_export(source)
            (supplement / "data.yaml").write_text(
                "\n".join([
                    "train: ../train/images",
                    "val: ../valid/images",
                    "test: ../test/images",
                    "nc: 5",
                    "names: ['bicycle', 'bus', 'car', 'motorcycle', 'truck']",
                ]) + "\n",
                encoding="utf-8",
            )
            for index, split_dir in enumerate(("train", "valid", "test"), start=20):
                image_dir = supplement / split_dir / "images"
                label_dir = supplement / split_dir / "labels"
                image_dir.mkdir(parents=True)
                label_dir.mkdir(parents=True)
                image_path = image_dir / f"{split_dir}_vietnam.jpg"
                Image.new("RGB", (8, 8), (index, index, index)).save(image_path)
                (label_dir / f"{split_dir}_vietnam.txt").write_text(
                    (
                        "0 0.100000 0.100000 0.100000 0.100000\n"
                        "1 0.200000 0.200000 0.100000 0.100000\n"
                        "2 0.300000 0.300000 0.100000 0.100000\n"
                        "3 0.400000 0.400000 0.100000 0.100000\n"
                        "4 0.500000 0.500000 0.100000 0.100000\n"
                    ),
                    encoding="utf-8",
                )
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)

            manifest = augment_with_yolo_sources(
                base_root=vehicle_base,
                output_root=output,
                yolo_sources=[supplement],
                source_splits=["train", "val", "test"],
                require_classes=[],
                max_records_per_source=None,
                privacy_status="needs_review",
                reviewer="tester",
                notes="unit test",
            )

            self.assertEqual(manifest["supplement"]["new_records"], 3)
            self.assertEqual(manifest["ignored_classes"], ["bicycle"])
            self.assertEqual(manifest["split_counts"], {"train": 4, "val": 1, "test": 1})
            self.assertEqual(manifest["object_counts"]["bus"], 3)
            self.assertEqual(manifest["object_counts"]["car"], 6)
            self.assertEqual(manifest["object_counts"]["motorcycle"], 6)
            self.assertEqual(manifest["object_counts"]["truck"], 3)

    def test_rebalances_motorcycle_training_records_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            output = Path(directory) / "rebalanced"
            source.mkdir()
            self._write_export(source)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)

            manifest = rebalance_dataset(
                source_root=vehicle_base,
                output_root=output,
                boost_class="motorcycle",
                repeat=2,
                max_boost_records=None,
            )

            self.assertEqual(manifest["rebalance"]["duplicate_records"], 2)
            self.assertEqual(manifest["split_counts"], {"train": 3, "val": 1, "test": 1})
            self.assertEqual(manifest["object_counts"]["motorcycle"], 5)

    def test_rebalances_only_small_motorcycle_training_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            output = Path(directory) / "small_moto"
            source.mkdir()
            self._write_export(source)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)
            train_label = vehicle_base / "train" / "labels" / "train_000000.txt"
            train_label.write_text(
                (
                    "1 0.500000 0.500000 0.250000 0.250000\n"
                    "2 0.100000 0.100000 0.040000 0.050000\n"
                ),
                encoding="utf-8",
            )

            manifest = rebalance_dataset(
                source_root=vehicle_base,
                output_root=output,
                boost_class="motorcycle",
                repeat=1,
                max_boost_records=None,
                max_box_area=0.003,
            )

            self.assertEqual(manifest["rebalance"]["boost_candidates"], 1)
            self.assertEqual(manifest["rebalance"]["duplicate_records"], 1)
            self.assertEqual(manifest["split_counts"], {"train": 2, "val": 1, "test": 1})

    def test_hardcase_error_selection_uses_train_rows_and_class_weights(self) -> None:
        rows = [
            {
                "split": "val",
                "image": "valid/images/a.jpg",
                "fn": {"motorcycle": 10},
                "confusion": {},
                "fn_area_bins": {},
            },
            {
                "split": "train",
                "image": "train/images/car.jpg",
                "fn": {"car": 3},
                "confusion": {},
                "fn_area_bins": {"car:tiny": 3},
            },
            {
                "split": "train",
                "image": "train/images/moto.jpg",
                "fn": {"motorcycle": 1},
                "confusion": {"motorcycle->car": 1},
                "fn_area_bins": {"motorcycle:tiny": 1},
            },
        ]

        selected = select_error_rows(
            rows,
            class_weights={
                "bus": 2.0,
                "car": 1.0,
                "motorcycle": 4.0,
                "truck": 1.0,
            },
            max_records=2,
            min_score=1.0,
        )

        self.assertEqual(
            [row["image"] for row in selected],
            ["train/images/moto.jpg", "train/images/car.jpg"],
        )

    def test_augments_training_with_object_crops_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            output = Path(directory) / "crop_aug"
            source.mkdir()
            self._write_export(source)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)
            train_image = vehicle_base / "train" / "images" / "train_000000.jpg"
            Image.new("RGB", (320, 240), "white").save(train_image)
            train_label = vehicle_base / "train" / "labels" / "train_000000.txt"
            train_label.write_text(
                (
                    "2 0.500000 0.500000 0.050000 0.050000\n"
                    "1 0.520000 0.520000 0.120000 0.120000\n"
                ),
                encoding="utf-8",
            )

            manifest = augment_with_object_crops(
                base_root=vehicle_base,
                output_root=output,
                specs=[CropSpec("motorcycle", 0.01, 3)],
                context_scale=4.0,
                min_crop_size=96,
                min_visibility=0.2,
                reviewer="tester",
                notes="unit test crop",
            )

            self.assertEqual(manifest["split_counts"], {"train": 2, "val": 1, "test": 1})
            self.assertEqual(
                manifest["object_crop_augmentation"]["created_crops"],
                {"motorcycle": 1},
            )
            crop_records = [
                record for record in manifest["records"]
                if record["source_type"] == "object_crop_training_supplement"
            ]
            self.assertEqual(len(crop_records), 1)
            self.assertTrue((output / crop_records[0]["image"]).is_file())
            self.assertTrue((output / crop_records[0]["label"]).read_text(encoding="utf-8").strip())

    def test_selects_unmatched_review_boxes(self) -> None:
        target_boxes = [
            Box("motorcycle", (10.0, 10.0, 30.0, 30.0)),
            Box("motorcycle", (60.0, 60.0, 90.0, 90.0)),
        ]
        predictions = [Box("motorcycle", (12.0, 12.0, 28.0, 28.0), 0.8)]

        self.assertGreater(box_iou(target_boxes[0], predictions[0]), 0.5)
        misses = unmatched_boxes(target_boxes, predictions, iou_threshold=0.5)

        self.assertEqual(misses, [target_boxes[1]])

    def test_selects_unmatched_false_positive_predictions(self) -> None:
        target_boxes = [Box("motorcycle", (10.0, 10.0, 30.0, 30.0))]
        predictions = [
            Box("motorcycle", (12.0, 12.0, 28.0, 28.0), 0.8),
            Box("motorcycle", (60.0, 60.0, 90.0, 90.0), 0.7),
        ]

        false_positives = unmatched_predictions(
            predictions,
            target_boxes,
            iou_threshold=0.5,
        )

        self.assertEqual(false_positives, [predictions[1]])

    def test_reads_class_names_from_stwi_dataset_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dataset_manifest.json").write_text(
                json.dumps({"classes": ["bus", "car", "motorcycle", "truck"]}),
                encoding="utf-8",
            )

            self.assertEqual(
                read_source_class_names(root),
                ["bus", "car", "motorcycle", "truck"],
            )

    def test_augments_vehicle_dataset_with_review_pack_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            vietnam = Path(directory) / "vietnam"
            review_pack = Path(directory) / "review"
            output = Path(directory) / "augmented"
            source.mkdir()
            vietnam.mkdir()
            review_pack.mkdir()
            self._write_export(source)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)
            (vietnam / "data.yaml").write_text(
                "\n".join([
                    "names: ['bicycle', 'bus', 'car', 'motorcycle', 'truck']",
                ]) + "\n",
                encoding="utf-8",
            )
            image_dir = vietnam / "train" / "images"
            label_dir = vietnam / "train" / "labels"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            image_path = image_dir / "hardcase.jpg"
            Image.new("RGB", (8, 8), "blue").save(image_path)
            (label_dir / "hardcase.txt").write_text(
                (
                    "0 0.100000 0.100000 0.100000 0.100000\n"
                    "3 0.500000 0.500000 0.250000 0.250000\n"
                ),
                encoding="utf-8",
            )
            (review_pack / "review_queue.csv").write_text(
                "\n".join([
                    "review_status,source_image,source_label",
                    "accepted,train/images/hardcase.jpg,train/labels/hardcase.txt",
                ]) + "\n",
                encoding="utf-8",
            )

            manifest = augment_with_review_pack(
                base_root=vehicle_base,
                source_root=vietnam,
                review_pack_root=review_pack,
                output_root=output,
                include_statuses=["accepted"],
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )

            self.assertEqual(manifest["supplement"]["new_records"], 1)
            self.assertEqual(manifest["ignored_classes"], ["bicycle"])
            self.assertEqual(manifest["split_counts"], {"train": 2, "val": 1, "test": 1})
            self.assertEqual(manifest["object_counts"]["motorcycle"], 4)

    def test_review_pack_augmentation_uses_unique_record_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            vietnam = Path(directory) / "vietnam"
            yolor = Path(directory) / "yolor"
            review_one = Path(directory) / "review one"
            review_two = Path(directory) / "review two"
            output_one = Path(directory) / "augmented_one"
            output_two = Path(directory) / "augmented_two"
            source.mkdir()
            vietnam.mkdir()
            yolor.mkdir()
            review_one.mkdir()
            review_two.mkdir()
            self._write_export(source)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)

            for supplement, color in ((vietnam, "blue"), (yolor, "red")):
                (supplement / "data.yaml").write_text(
                    "names: ['motorcycle']\n",
                    encoding="utf-8",
                )
                image_dir = supplement / "train" / "images"
                label_dir = supplement / "train" / "labels"
                image_dir.mkdir(parents=True)
                label_dir.mkdir(parents=True)
                Image.new("RGB", (8, 8), color).save(image_dir / "hardcase.jpg")
                (label_dir / "hardcase.txt").write_text(
                    "0 0.500000 0.500000 0.250000 0.250000\n",
                    encoding="utf-8",
                )

            for review_pack in (review_one, review_two):
                (review_pack / "review_queue.csv").write_text(
                    "\n".join([
                        "review_status,source_image,source_label",
                        "accepted,train/images/hardcase.jpg,train/labels/hardcase.txt",
                    ]) + "\n",
                    encoding="utf-8",
                )

            augment_with_review_pack(
                base_root=vehicle_base,
                source_root=vietnam,
                review_pack_root=review_one,
                output_root=output_one,
                include_statuses=["accepted"],
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            manifest = augment_with_review_pack(
                base_root=output_one,
                source_root=yolor,
                review_pack_root=review_two,
                output_root=output_two,
                include_statuses=["accepted"],
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )

            supplement_records = [
                record for record in manifest["records"]
                if record["source_type"] == "review_pack_vehicle_supplement"
            ]
            self.assertEqual(len(supplement_records), 2)
            self.assertEqual(
                len({record["image"] for record in supplement_records}),
                2,
            )
            self.assertEqual(manifest["object_counts"]["motorcycle"], 5)

    def test_finalizes_accepted_label_fix_candidates_to_train_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            vehicle_base = Path(directory) / "vehicles"
            candidate = Path(directory) / "candidate"
            output = Path(directory) / "augmented"
            source.mkdir()
            candidate.mkdir()
            self._write_export(source)
            build_manifest(
                source,
                dataset_version="unit_v001",
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )
            build_vehicle_dataset(source, vehicle_base)
            image_dir = candidate / "train" / "images"
            label_dir = candidate / "train" / "labels"
            review_dir = candidate / "review"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            review_dir.mkdir()
            Image.new("RGB", (8, 8), "green").save(image_dir / "fix.jpg")
            (label_dir / "fix.txt").write_text(
                "2 0.500000 0.500000 0.250000 0.250000\n",
                encoding="utf-8",
            )
            candidate_manifest = {
                "schema_version": "1.0",
                "dataset_version": "candidate",
                "classes": ["bus", "car", "motorcycle", "truck"],
                "privacy_review": {
                    "reviewer": "pending",
                    "reviewed_at_utc": "pending",
                    "notes": "pending",
                    "human_approval_required_for_external_release": True,
                },
                "records": [
                    {
                        "image": "train/images/fix.jpg",
                        "label": "train/labels/fix.txt",
                        "split": "train",
                        "review_status": "pending",
                        "sha256": sha256_file(image_dir / "fix.jpg"),
                    }
                ],
            }
            (candidate / "dataset_manifest.json").write_text(
                json.dumps(candidate_manifest),
                encoding="utf-8",
            )
            (review_dir / "review_queue.csv").write_text(
                "\n".join([
                    "review_status,image,label,review_note",
                    "pending,train/images/fix.jpg,train/labels/fix.txt,",
                ]) + "\n",
                encoding="utf-8",
            )
            update_candidate_review_status(
                candidate_root=candidate,
                status="accepted",
                reviewer="tester",
                notes="accepted all",
            )

            manifest = finalize_label_fix_candidates(
                base_root=vehicle_base,
                candidate_root=candidate,
                output_root=output,
                include_statuses=["accepted"],
                privacy_status="visual_spot_reviewed_agent",
                reviewer="tester",
                notes="unit test",
            )

            self.assertEqual(manifest["supplement"]["new_records"], 1)
            self.assertEqual(manifest["split_counts"], {"train": 2, "val": 1, "test": 1})
            self.assertEqual(manifest["object_counts"]["motorcycle"], 4)

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
