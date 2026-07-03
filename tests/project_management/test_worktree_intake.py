from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "project_management" / "worktree_intake.py"


def load_module():
    spec = importlib.util.spec_from_file_location("worktree_intake", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorktreeIntakeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.intake = load_module()

    def test_groups_current_dirty_tree_domains(self) -> None:
        records = self.intake.parse_status(
            "\n".join(
                [
                    " M .github/workflows/build.yml",
                    " M AGENTS.md",
                    "?? data/manifests/post_mvp_cleanup_dry_run.json",
                    "?? scripts/project_management/worktree_intake.py",
                    "?? src/stwi/tooling/scope.py",
                    "?? tests/vision/test_detector.py",
                ]
            )
        )

        groups = self.intake.group_records(records)

        self.assertIn("ci-release", groups)
        self.assertIn("source-of-truth-docs", groups)
        self.assertIn("data-vision", groups)
        self.assertIn("project-management", groups)
        self.assertIn("runtime-src", groups)

    def test_flags_source_truth_ci_and_manifest_risks(self) -> None:
        records = self.intake.parse_status(
            "\n".join(
                [
                    " M WORKFLOW.md",
                    "?? .github/workflows/stwi-fast-ci.yml",
                    "?? data/manifests/post_mvp_cleanup_dry_run.json",
                ]
            )
        )

        workflow, ci, manifest = records
        self.assertIn("source-of-truth", workflow.risks)
        self.assertIn("ci-workflow", ci.risks)
        self.assertIn("untracked", ci.risks)
        self.assertIn("evidence-manifest", manifest.risks)

    def test_rename_parsing_preserves_original_path(self) -> None:
        record = self.intake.parse_status_line("R  old/name.py -> src/stwi/tooling/name.py")

        self.assertEqual(record.original_path, "old/name.py")
        self.assertEqual(record.path, "src/stwi/tooling/name.py")
        self.assertEqual(record.group, "runtime-src")


if __name__ == "__main__":
    unittest.main()
