"""Tests for the strict public-proxy demo data importer."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from stwi.t2_forecast.public_proxy import (  # noqa: E402
    build_public_proxy_dataset,
    load_source_spec,
)


class PublicProxyIngestionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.node_ids = [f"proxy_{index:02d}" for index in range(20)]
        self.source_ids = [f"source_{index:02d}" for index in range(20)]

    def _write_spec(self, *, asymmetric: bool = False) -> Path:
        adjacency = np.eye(20, dtype=float)
        adjacency[0, 1] = 1.0
        adjacency[1, 0] = 0.0 if asymmetric else 1.0
        payload = {
            "schema_version": "1.0",
            "data_classification": "public_proxy_demo_only",
            "source": {
                "provider_name": "Example public traffic archive",
                "source_url": "https://example.invalid/traffic",
                "license_reference": "demo-test-license",
                "access_confirmed_by": "test owner",
                "downloaded_at_utc": "2026-07-17T00:00:00+00:00",
                "data_scope_notice": "Demo proxy only; not local traffic evidence.",
            },
            "network": {
                "network_version": "example_proxy_v1",
                "nodes": [
                    {
                        "node_id": node_id,
                        "source_node_id": self.source_ids[index],
                        "capacity_vph": 1200 + index,
                        "free_flow_speed_kmh": 55.0,
                    }
                    for index, node_id in enumerate(self.node_ids)
                ],
                "adjacency": adjacency.tolist(),
            },
        }
        path = self.root / "spec.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _write_csv(self, *, gap: bool = False) -> Path:
        path = self.root / "traffic.csv"
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "timestamp", "source_node_id", "traffic_volume_5m", "avg_speed_kmh",
            ])
            writer.writeheader()
            for step in range(128):
                if gap and step == 20:
                    continue
                timestamp = start + timedelta(minutes=5 * step)
                for node_index, source_id in enumerate(self.source_ids):
                    writer.writerow({
                        "timestamp": timestamp.isoformat(),
                        "source_node_id": source_id,
                        "traffic_volume_5m": 20 + node_index + step,
                        "avg_speed_kmh": 35 + node_index / 10,
                    })
        return path

    def test_builds_traceable_contract_dataset(self) -> None:
        output = self.root / "output"
        manifest = build_public_proxy_dataset(
            self._write_csv(), self._write_spec(), output
        )
        self.assertEqual(manifest["data_classification"], "public_proxy_demo_only")
        self.assertFalse(manifest["intervention_calibration_eligible"])
        self.assertTrue((output / "dataset_manifest.json").is_file())
        with np.load(output / "tensor_dataset.npz", allow_pickle=False) as tensors:
            self.assertEqual(tensors["X"].shape[1:], (12, 20, 16))
            self.assertEqual(tensors["Y"].shape[1:], (6, 20, 2))
            self.assertEqual(tensors["M"].dtype, np.bool_)
            self.assertFalse(np.all(tensors["M"][:, :, :, 2]))
        with np.load(output / "timeseries.npz", allow_pickle=False) as time_series:
            self.assertTrue(np.all(time_series["raw_observed_mask"][:, :, 0:2]))
            self.assertFalse(np.any(time_series["raw_observed_mask"][:, :, 2:11]))

    def test_rejects_non_contiguous_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "contiguous"):
            build_public_proxy_dataset(
                self._write_csv(gap=True), self._write_spec(), self.root / "output"
            )

    def test_rejects_asymmetric_adjacency(self) -> None:
        with self.assertRaisesRegex(ValueError, "symmetric"):
            load_source_spec(self._write_spec(asymmetric=True))


if __name__ == "__main__":
    unittest.main()
