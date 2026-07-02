import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stwi.contracts.project import (  # noqa: E402
    feature_names,
    feature_units,
    scaled_feature_indices,
)
from stwi.t1_pipeline.mock_data import (  # noqa: E402
    generate_load_aggregates,
    generate_mock_network,
    generate_mock_timeseries,
)
from stwi.t1_pipeline.schemas import (  # noqa: E402
    DeadLetter,
    SensorRecord,
    camera_source_status,
    publish_camera_aggregate,
    validate_sensor_record,
)
from stwi.t1_pipeline.tensor_builder import (  # noqa: E402
    apply_quality_and_impute,
    build_tensor_windows,
    chronological_split_indices,
    fit_train_scaler,
)


class Phase1PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.start = datetime.fromisoformat("2025-05-01T00:00:00+07:00")
        cls.network = generate_mock_network(seed=11)
        cls.raw = generate_mock_timeseries(
            cls.network, start=cls.start, days=2, seed=11
        )
        cls.quality = apply_quality_and_impute(
            cls.raw.values, cls.raw.observed_mask, cls.network.adjacency
        )

    def test_network_contract(self) -> None:
        self.assertEqual(len(self.network.node_ids), 20)
        self.assertEqual(self.network.adjacency.shape, (20, 20))
        np.testing.assert_allclose(
            self.network.adjacency, self.network.adjacency.T
        )
        self.assertTrue(np.all(self.network.capacities_vph > 0))

    def test_feature_contract_is_machine_derived(self) -> None:
        self.assertEqual(len(feature_names()), 16)
        self.assertEqual(feature_names()[-1], "green_time_ratio")
        self.assertEqual(len(scaled_feature_indices()), 10)

    def test_quality_imputes_without_hiding_mask(self) -> None:
        self.assertTrue(np.all(np.isfinite(self.quality.values)))
        self.assertGreater(self.quality.missing_ratio, 0)
        self.assertGreater(self.quality.outlier_count, 0)
        self.assertTrue(np.any(~self.quality.observed_mask))

    def test_gate_p1_tensor_shapes(self) -> None:
        scaler = fit_train_scaler(
            self.quality.values, self.quality.observed_mask, 200
        )
        scaled = scaler.transform(self.quality.values)
        dataset = build_tensor_windows(
            scaled,
            self.quality.observed_mask,
            self.network.adjacency,
            target_values=self.quality.values,
        )
        self.assertEqual(dataset.X[:32].shape, (32, 12, 20, 16))
        self.assertEqual(dataset.M[:32].shape, (32, 12, 20, 16))
        self.assertEqual(dataset.A.shape, (20, 20))
        self.assertEqual(dataset.Y[:32].shape, (32, 6, 20, 2))
        self.assertTrue(np.all(dataset.Y >= 0))

    def test_chronological_split_has_purged_boundaries(self) -> None:
        dataset = build_tensor_windows(
            self.quality.values,
            self.quality.observed_mask,
            self.network.adjacency,
        )
        splits = chronological_split_indices(dataset, len(self.raw.timestamps))
        self.assertTrue(all(len(indices) > 0 for indices in splits.values()))
        self.assertLess(splits["train"][-1], splits["val"][0])
        self.assertLess(splits["val"][-1], splits["test"][0])

    def test_sensor_schema_fails_closed(self) -> None:
        payload = {
            "schema_version": "1.0",
            "source_id": "sensor_00",
            "node_id": "node_00",
            "feature": "co_ppm",
            "value": 0.8,
            "unit": feature_units()["co_ppm"],
            "observed_at": self.start,
            "received_at": self.start + timedelta(minutes=20),
        }
        result = validate_sensor_record(
            payload, frozenset(self.network.node_ids), feature_units()
        )
        self.assertIsInstance(result, SensorRecord)
        self.assertEqual(result.quality_flag, "late_event")
        bad = dict(payload, unit="wrong")
        self.assertIsInstance(
            validate_sensor_record(
                bad, frozenset(self.network.node_ids), feature_units()
            ),
            DeadLetter,
        )

    def test_camera_speed_requires_calibration(self) -> None:
        aggregate = publish_camera_aggregate(
            source_id="camera_00",
            node_id="node_00",
            window_start=self.start,
            traffic_volume_5m=25,
            avg_speed_kmh=48,
            heavy_vehicle_ratio=0.12,
            calibration_approved=False,
        )
        self.assertIsNone(aggregate.avg_speed_kmh)
        self.assertEqual(aggregate.quality_flag, "calibration_required")
        self.assertEqual(
            camera_source_status(self.start, self.start + timedelta(minutes=16)),
            "offline",
        )

    def test_load_generator_is_aggregate_only(self) -> None:
        records = generate_load_aggregates(self.network, self.start)
        self.assertEqual(len(records), 1000)
        self.assertTrue(all(record["synthetic"] for record in records))
        self.assertTrue(all("frame" not in record for record in records))


if __name__ == "__main__":
    unittest.main()
