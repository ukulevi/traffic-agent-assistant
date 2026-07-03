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



class VisionDatasetAugmentationTest(unittest.TestCase):

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
