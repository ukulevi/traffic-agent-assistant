"""Static safety checks for the isolated Phase 3 integration harness."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Phase3HarnessConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.compose = (ROOT / "infra/harness/compose.phase3.yaml").read_text(
            encoding="utf-8"
        )
        self.schema = (ROOT / "infra/harness/timescaledb-init/01_schema.sql").read_text(
            encoding="utf-8"
        )
        self.reader_init = (
            ROOT / "infra/harness/timescaledb-init/00_create_reader_user.sh"
        ).read_text(encoding="utf-8")

    def test_no_default_database_or_reader_passwords(self) -> None:
        combined = self.compose + self.schema + self.reader_init
        self.assertNotIn("stwi_dev_password", combined)
        self.assertNotIn("stwi_reader_dev_password", combined)
        self.assertIn("${STWI_TSDB_PASSWORD:?", self.compose)
        self.assertIn("${STWI_READER_PASSWORD:?", self.compose)

    def test_services_bind_loopback_and_qdrant_requires_keys(self) -> None:
        self.assertIn("${STWI_HARNESS_BIND_ADDRESS:-127.0.0.1}", self.compose)
        self.assertIn("${STWI_QDRANT_API_KEY:?", self.compose)
        self.assertIn("${STWI_QDRANT_READ_ONLY_API_KEY:?", self.compose)
        self.assertNotIn('"${QDRANT_HTTP_PORT:-6333}:6333"', self.compose)

    def test_reader_password_is_injected_not_literal(self) -> None:
        self.assertIn('STWI_READER_PASSWORD is required', self.reader_init)
        self.assertIn("format('CREATE ROLE stwi_reader_user LOGIN PASSWORD %L'", self.reader_init)
        self.assertNotIn("PASSWORD 'stwi_", self.reader_init)


if __name__ == "__main__":
    unittest.main()
