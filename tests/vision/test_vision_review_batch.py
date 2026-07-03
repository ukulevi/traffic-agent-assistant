import csv
import tempfile
import unittest
from pathlib import Path

from scripts.training.apply_vision_review_batch import apply_review_batch
from scripts.data_prep.build_vision_label_fix_candidates import CandidateBox, merge_boxes
from scripts.data_prep.build_vision_label_fix_candidates import write_review_html
from scripts.validation.analyze_vision_validation_errors import LabeledBox, analyze_image
from scripts.validation.analyze_vision_sliced_validation import class_aware_nms, tile_origins
from scripts.data_prep.build_vision_error_review_pack import Box
from scripts.validation.evaluate_vision_roi_ap import (
    PredictionRecord,
    evaluate_class_ap50,
    filter_targets,
)
from scripts.data_prep.prepare_vision_review_batch import prepare_review_batch
from stwi.tooling.vision_training.external_models import (
    normalize_class_aliases,
    normalize_prompt_classes,
)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class VisionReviewBatchTest(unittest.TestCase):
    def create_review_pack(self, root: Path) -> Path:
        pack = root / "pack_a"
        preview_dir = pack / "previews"
        preview_dir.mkdir(parents=True)
        (preview_dir / "0000.jpg").write_bytes(b"fake-preview")
        (preview_dir / "0001.jpg").write_bytes(b"fake-preview")
        (pack / "review_manifest.json").write_text(
            """
{
  "schema_version": "1.0",
  "review_pack_version": "pack_a",
  "task": "vision_error_review",
  "target_class": "motorcycle",
  "review_mode": "false_negative"
}
""".strip()
            + "\n",
            encoding="utf-8",
        )
        write_csv(
            pack / "review_queue.csv",
            [
                {
                    "review_status": "pending",
                    "split": "val",
                    "source_image": "valid/images/a.jpg",
                    "source_label": "valid/labels/a.txt",
                    "preview": "previews/0000.jpg",
                    "target_class": "motorcycle",
                    "target_boxes": "1",
                    "predicted_boxes": "0",
                    "missed_boxes": "1",
                    "false_positive_boxes": "0",
                    "review_note": "",
                },
                {
                    "review_status": "rejected",
                    "split": "val",
                    "source_image": "valid/images/b.jpg",
                    "source_label": "valid/labels/b.txt",
                    "preview": "previews/0001.jpg",
                    "target_class": "motorcycle",
                    "target_boxes": "1",
                    "predicted_boxes": "0",
                    "missed_boxes": "1",
                    "false_positive_boxes": "0",
                    "review_note": "",
                },
            ],
        )
        return pack

    def test_prepare_review_batch_selects_pending_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = self.create_review_pack(root)
            output = root / "batch"
            manifest = prepare_review_batch(
                packs=[pack],
                output_root=output,
                statuses={"pending"},
                limit_per_pack=None,
                title="Batch",
            )

            rows = read_csv(output / "review_batch.csv")
            self.assertEqual(manifest["review_images"], 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_row_index"], "0")
            self.assertTrue((output / rows[0]["batch_preview"]).is_file())
            self.assertTrue((output / "index.html").is_file())

    def test_apply_review_batch_updates_source_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = self.create_review_pack(root)
            output = root / "batch"
            prepare_review_batch(
                packs=[pack],
                output_root=output,
                statuses={"pending"},
                limit_per_pack=None,
                title="Batch",
            )
            batch_csv = output / "review_batch.csv"
            batch_rows = read_csv(batch_csv)
            batch_rows[0]["review_status"] = "accepted"
            batch_rows[0]["review_note"] = "looks correct"
            write_csv(batch_csv, batch_rows)

            result = apply_review_batch(batch_csv)
            source_rows = read_csv(pack / "review_queue.csv")

            self.assertEqual(result["status_counts"], {"accepted": 1})
            self.assertEqual(source_rows[0]["review_status"], "accepted")
            self.assertEqual(source_rows[0]["review_note"], "looks correct")
            self.assertEqual(source_rows[1]["review_status"], "rejected")

    def test_merge_boxes_adds_missing_and_reclasses_high_confidence_overlap(self) -> None:
        source_boxes = [
            CandidateBox(
                class_name="motorcycle",
                xyxy=(10.0, 10.0, 30.0, 30.0),
                confidence=None,
                provenance="source_label",
            )
        ]
        prediction_boxes = [
            CandidateBox(
                class_name="car",
                xyxy=(11.0, 11.0, 31.0, 31.0),
                confidence=0.91,
                provenance="model_prediction",
            ),
            CandidateBox(
                class_name="motorcycle",
                xyxy=(60.0, 60.0, 90.0, 90.0),
                confidence=0.82,
                provenance="model_prediction",
            ),
        ]

        merged, added, reclassified = merge_boxes(
            source_boxes=source_boxes,
            prediction_boxes=prediction_boxes,
            add_iou_threshold=0.45,
            reclass_iou_threshold=0.65,
            reclass_confidence=0.55,
        )

        self.assertEqual(added, 1)
        self.assertEqual(reclassified, 1)
        self.assertEqual([box.class_name for box in merged], ["car", "motorcycle"])

    def test_label_fix_html_uses_review_relative_preview_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "review" / "previews").mkdir(parents=True)
            write_review_html(
                root,
                [
                    {
                        "review_status": "pending",
                        "source_image": "train/images/a.jpg",
                        "preview": "review/previews/a.jpg",
                        "source_box_count": 1,
                        "prediction_box_count": 2,
                        "final_box_count": 3,
                        "added_box_count": 1,
                        "reclassified_box_count": 0,
                        "label": "train/labels/a.txt",
                    }
                ],
            )

            html = (root / "review" / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="previews/a.jpg"', html)
            self.assertNotIn('src="review/previews/a.jpg"', html)

    def test_validation_error_analysis_counts_wrong_class_as_fn_and_fp(self) -> None:
        targets = [
            LabeledBox(
                class_name="motorcycle",
                xyxy=(10.0, 10.0, 30.0, 30.0),
                normalized_area=0.002,
            )
        ]
        predictions = [
            LabeledBox(
                class_name="car",
                xyxy=(11.0, 11.0, 31.0, 31.0),
                confidence=0.8,
                normalized_area=0.002,
            )
        ]

        result = analyze_image(
            targets=targets,
            predictions=predictions,
            iou_threshold=0.5,
        )

        self.assertEqual(result["false_negative"], {"motorcycle": 1})
        self.assertEqual(result["false_positive"], {"car": 1})
        self.assertEqual(result["confusion"], {"motorcycle->car": 1})
        self.assertEqual(result["fn_area_bins"], {"motorcycle:tiny": 1})

    def test_sliced_tile_origins_cover_image_end(self) -> None:
        self.assertEqual(tile_origins(500, 640, 0.25), [0])
        origins = tile_origins(1500, 640, 0.25)
        self.assertEqual(origins[0], 0)
        self.assertEqual(origins[-1], 860)
        self.assertLessEqual(max(left + 640 for left in origins), 1500)

    def test_sliced_nms_is_class_aware(self) -> None:
        boxes = [
            Box("car", (10.0, 10.0, 50.0, 50.0), 0.9),
            Box("car", (12.0, 12.0, 52.0, 52.0), 0.7),
            Box("truck", (12.0, 12.0, 52.0, 52.0), 0.8),
        ]

        kept = class_aware_nms(boxes, iou_threshold=0.5)

        self.assertEqual([(box.class_name, box.confidence) for box in kept], [
            ("car", 0.9),
            ("truck", 0.8),
        ])

    def test_roi_ap_filters_targets_and_computes_class_ap50(self) -> None:
        targets = [
            LabeledBox("car", (0.0, 0.0, 10.0, 10.0), normalized_area=0.001),
            LabeledBox("car", (20.0, 20.0, 60.0, 60.0), normalized_area=0.02),
        ]
        kept_targets = filter_targets(targets, min_box_area=0.003)
        predictions = [
            PredictionRecord(
                class_name="car",
                image_id="a.jpg",
                box=Box("car", (20.0, 20.0, 60.0, 60.0), 0.9),
                confidence=0.9,
                normalized_area=0.02,
            ),
            PredictionRecord(
                class_name="car",
                image_id="a.jpg",
                box=Box("car", (70.0, 70.0, 90.0, 90.0), 0.8),
                confidence=0.8,
                normalized_area=0.01,
            ),
        ]

        metrics = evaluate_class_ap50(
            class_name="car",
            targets_by_image={"a.jpg": kept_targets},
            predictions=predictions,
            iou_threshold=0.5,
        )

        self.assertEqual(metrics["targets"], 1)
        self.assertEqual(metrics["tp"], 1)
        self.assertEqual(metrics["fp"], 1)
        self.assertAlmostEqual(metrics["ap50"], 1.0)

    def test_normalize_prompt_classes_dedupes_for_open_vocabulary_models(self) -> None:
        self.assertEqual(
            normalize_prompt_classes([" Car ", "bus", "car", "", " MOTORCYCLE "]),
            ["car", "bus", "motorcycle"],
        )

    def test_normalize_class_aliases_maps_external_names_to_stwi_names(self) -> None:
        self.assertEqual(
            normalize_class_aliases([" Motor : Motorcycle ", "van:truck"]),
            {"motor": "motorcycle", "van": "truck"},
        )

    def test_normalize_class_aliases_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            normalize_class_aliases(["motorcycle"])


if __name__ == "__main__":
    unittest.main()
