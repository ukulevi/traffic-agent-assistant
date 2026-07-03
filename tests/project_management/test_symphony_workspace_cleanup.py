from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "project_management" / "symphony_workspace_cleanup.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "symphony_workspace_cleanup", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SymphonyWorkspaceCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cleanup = load_module()
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "workspaces"
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir)

    def make_workspace(self, name: str, *, dirty: bool = False) -> Path:
        path = self.root / name
        path.mkdir()
        subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
        if dirty:
            (path / "note.txt").write_text("pending\n", encoding="utf-8")
        old = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
        os.utime(path, (old, old))
        return path

    def test_marks_stale_clean_git_workspace_as_candidate(self) -> None:
        self.make_workspace("TRA-1")

        records = self.cleanup.collect_workspaces(
            self.root,
            stale_days=7,
            protected_names=set(),
            now=datetime(2026, 1, 20, tzinfo=timezone.utc),
        )

        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].candidate)
        self.assertIn("stale clean workspace", records[0].reasons)

    def test_keeps_dirty_workspace(self) -> None:
        self.make_workspace("TRA-2", dirty=True)

        records = self.cleanup.collect_workspaces(
            self.root,
            stale_days=7,
            protected_names=set(),
            now=datetime(2026, 1, 20, tzinfo=timezone.utc),
        )

        self.assertFalse(records[0].candidate)
        self.assertIn("git workspace has uncommitted changes", records[0].reasons)

    def test_delete_candidates_stays_under_root(self) -> None:
        outside = self.tmpdir / "outside"
        outside.mkdir()
        records = [
            self.cleanup.WorkspaceRecord(
                name="outside",
                path=str(outside),
                modified_at="2026-01-01T00:00:00+00:00",
                age_days=30,
                has_git=True,
                git_dirty=False,
                candidate=True,
                reasons=["stale clean workspace"],
            )
        ]

        with self.assertRaises(ValueError):
            self.cleanup.delete_candidates(self.root, records)


if __name__ == "__main__":
    unittest.main()
