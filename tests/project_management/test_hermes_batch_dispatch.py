"""Safety checks for the parallel Hermes sidecar dispatcher."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
SCRIPT_DIR = ROOT / "scripts" / "project_management"
sys.path.insert(0, str(SCRIPT_DIR))
MODULE_PATH = SCRIPT_DIR / "hermes_batch_dispatch.py"
SPEC = importlib.util.spec_from_file_location("hermes_batch_dispatch", MODULE_PATH)
assert SPEC and SPEC.loader
batch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = batch
SPEC.loader.exec_module(batch)


def packet(identifier: str, allowed_files: list[str], approval: str = "Approved: yes"):
    return batch.DispatchPacket(
        identifier=identifier,
        title="Test packet",
        allowed_files=allowed_files,
        raw_text="",
        sections={"External Code Transfer Approval": approval},
    )


class TestHermesBatchDispatch(unittest.TestCase):
    def test_external_transfer_requires_explicit_packet_approval(self) -> None:
        self.assertTrue(batch.packet_has_external_transfer_approval(packet("TRA-1", ["src/a.py"])))
        self.assertFalse(batch.packet_has_external_transfer_approval(packet("TRA-1", ["src/a.py"], "Pending")))

    def test_exact_file_scopes_can_run_in_parallel(self) -> None:
        self.assertFalse(
            batch.scopes_overlap(packet("TRA-1", ["src/a.py"]), packet("TRA-2", ["tests/a.py"]))
        )

    def test_overlapping_or_wildcard_scope_is_rejected(self) -> None:
        self.assertTrue(
            batch.scopes_overlap(packet("TRA-1", ["src/stwi"]), packet("TRA-2", ["src/stwi/api.py"]))
        )
        self.assertTrue(
            batch.scopes_overlap(packet("TRA-1", ["src/**/*.py"]), packet("TRA-2", ["tests/a.py"]))
        )

    def test_concurrency_cap_is_two_workers(self) -> None:
        self.assertEqual(batch.MAX_CONCURRENT_WORKERS, 2)


if __name__ == "__main__":
    unittest.main()
