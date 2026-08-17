from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validation import validate_docs


class ValidateDocumentedScriptPathsTest(unittest.TestCase):
    def test_reports_missing_active_documented_script(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "README.md").write_text(
            "Run `python scripts/missing.py`.\n", encoding="utf-8"
        )

        errors: list[str] = []
        validate_docs.validate_documented_script_paths(errors, root)

        self.assertEqual(errors, ["README.md: missing documented script scripts/missing.py"])

    def test_ignores_historical_docs_and_accepts_existing_script(self) -> None:
        root = Path(tempfile.mkdtemp())
        script = root / "scripts" / "validation" / "check.py"
        script.parent.mkdir(parents=True)
        script.write_text("print('ok')\n", encoding="utf-8")
        (root / "README.md").write_text(
            "Run `python scripts/validation/check.py`.\n", encoding="utf-8"
        )
        historical = root / "docs" / "superpowers" / "plans" / "old.md"
        historical.parent.mkdir(parents=True)
        historical.write_text("Run `python scripts/removed.py`.\n", encoding="utf-8")

        errors: list[str] = []
        validate_docs.validate_documented_script_paths(errors, root)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
