import tempfile
import unittest
from pathlib import Path

from scripts.data_prep.prepare_vision_training_data import (
    box_center_in_road_roi,
    generate_mock_dataset,
    split_for_mock,
    yolo_line,
)


class VisionTrainingDataTest(unittest.TestCase):
    def test_yolo_line_is_normalized(self) -> None:
        self.assertEqual(
            yolo_line(0, (10, 20, 30, 60), 100, 100),
            "0 0.200000 0.400000 0.200000 0.400000",
        )

    def test_mock_split_boundaries(self) -> None:
        self.assertEqual(split_for_mock(0, 100), "train")
        self.assertEqual(split_for_mock(70, 100), "val")
        self.assertEqual(split_for_mock(85, 100), "test")

    def test_mock_generation_has_image_label_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = generate_mock_dataset(root, count=30, seed=7)
            self.assertEqual(len(records), 30)
            for record in records:
                self.assertTrue((root / record["image"]).is_file())
                self.assertTrue((root / record["label"]).is_file())

    def test_road_roi_excludes_private_frontage(self) -> None:
        self.assertTrue(box_center_in_road_roi((500, 100, 700, 300), 1344, 760))
        self.assertFalse(
            box_center_in_road_roi((1100, 20, 1300, 200), 1344, 760)
        )


if __name__ == "__main__":
    unittest.main()
