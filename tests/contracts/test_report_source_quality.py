"""Regression guards for release-blocking LaTeX source defects."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReportSourceQualityTests(unittest.TestCase):
    def test_report_has_no_malformed_texttt_commands(self) -> None:
        malformed = []
        for path in (ROOT / "report" / "chapters").glob("*.tex"):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "exttt{" in line and "\\texttt{" not in line:
                    malformed.append(f"{path.relative_to(ROOT)}:{line_number}")

        self.assertEqual(malformed, [])

    def test_job_snapshot_path_is_wrapped_inside_api_table(self) -> None:
        appendix = (ROOT / "report" / "chapters" / "appendix_api.tex").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            r"\texttt{/api/v1/what-if-jobs/}\newline\texttt{\{job\_id\}}",
            appendix,
        )


if __name__ == "__main__":
    unittest.main()
