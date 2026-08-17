from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.validation import validate_ci_guardrails as guardrails


class ValidateCiGuardrailsTest(unittest.TestCase):
    def make_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / ".codexignore").write_text(
            "\n".join(guardrails.REQUIRED_CODEXIGNORE_PATTERNS) + "\n",
            encoding="utf-8",
        )
        (root / "WORKFLOW.md").write_text(
            "\n".join(
                [
                    "max_concurrent_agents: 1",
                    "max_turns: 1",
                    "max_retry_backoff_ms: 900000",
                    "interval_ms: 300000",
                    "approval_policy: never",
                    "SYMPHONY_REPO_REFERENCE",
                ]
            ),
            encoding="utf-8",
        )
        return root

    def test_passes_minimal_clean_root(self) -> None:
        root = self.make_root()
        with (
            mock.patch.object(guardrails, "git_ls_files", return_value=["src/app.py"]),
            mock.patch.object(guardrails, "git_staged_files", return_value=[]),
        ):
            self.assertEqual(guardrails.validate(root), [])

    def test_rejects_forbidden_tracked_artifacts(self) -> None:
        root = self.make_root()
        tracked = ["src/app.py", "data/derived/private/frame.jpg", "model.pt"]
        with mock.patch.object(guardrails, "git_ls_files", return_value=tracked):
            errors = guardrails.validate_tracked_files(root)

        self.assertIn("Forbidden tracked artifact: data/derived/private/frame.jpg", errors)
        self.assertIn("Forbidden tracked artifact: model.pt", errors)

    def test_rejects_blanket_json_codexignore(self) -> None:
        root = self.make_root()
        with (root / ".codexignore").open("a", encoding="utf-8") as handle:
            handle.write("*.json\n")

        errors = guardrails.validate_codexignore(root)

        self.assertIn(".codexignore must not blanket-ignore *.json", errors)

    def test_rejects_workflow_without_budget_limits(self) -> None:
        root = self.make_root()
        (root / "WORKFLOW.md").write_text("max_turns: 2\n", encoding="utf-8")

        errors = guardrails.validate_workflow(root)

        self.assertTrue(any("max_turns: 1" in error for error in errors))
        self.assertTrue(any("interval_ms: 300000" in error for error in errors))

    def test_candidate_files_union_tracked_and_staged(self) -> None:
        root = self.make_root()
        with (
            mock.patch.object(
                guardrails,
                "git_ls_files",
                return_value=["src/app.py", "docs/readme.md"],
            ),
            mock.patch.object(
                guardrails,
                "git_staged_files",
                return_value=["docs/readme.md", "tests/test_app.py"],
            ),
        ):
            self.assertEqual(
                guardrails.candidate_repository_files(root),
                ["docs/readme.md", "src/app.py", "tests/test_app.py"],
            )

    def test_rejects_private_and_generated_candidate_paths(self) -> None:
        errors = guardrails.validate_forbidden_files(
            [
                "docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/form.docx",
                "report/internship_main.tex",
                "tmp/render/page-01.png",
                "output/pdf/report.pdf",
            ]
        )

        self.assertEqual(
            errors,
            [
                "Forbidden repository artifact: docs/guides/TTNT_HD_BM_HuongDan_BieuMau_ShareSV+CB/form.docx",
                "Forbidden repository artifact: report/internship_main.tex",
                "Forbidden repository artifact: tmp/render/page-01.png",
                "Forbidden repository artifact: output/pdf/report.pdf",
            ],
        )

    def test_reports_private_key_marker_without_value(self) -> None:
        root = self.make_root()
        leak = root / "src" / "leak.py"
        leak.parent.mkdir()
        leak.write_text(
            "-----BEGIN " + "PRIVATE KEY-----\\nprivate material\\n",
            encoding="utf-8",
        )

        self.assertEqual(
            guardrails.validate_sensitive_content(root, ["src/leak.py"]),
            ["Sensitive content (private-key): src/leak.py"],
        )

    def test_rejects_public_workflow_referencing_internship_report(self) -> None:
        root = self.make_root()
        workflow = root / ".github" / "workflows" / "build.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("root_file: internship_main.tex\\n", encoding="utf-8")

        self.assertEqual(
            guardrails.validate_public_workflows(root),
            [
                "Public workflow references private internship artifact: .github/workflows/build.yml"
            ],
        )


if __name__ == "__main__":
    unittest.main()
