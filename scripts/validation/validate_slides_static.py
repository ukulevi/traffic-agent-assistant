"""Static integrity checks for the STWI slide deck."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SLIDES_ROOT = ROOT / "slides"
PRESENTATION_JS = SLIDES_ROOT / "js" / "presentation.js"
SECTION_PATTERN = re.compile(r"['\"](sections/[^'\"]+\.html)['\"]")


def main() -> int:
    if not PRESENTATION_JS.exists():
        print(f"Missing presentation script: {PRESENTATION_JS}", file=sys.stderr)
        return 1

    presentation_source = PRESENTATION_JS.read_text(encoding="utf-8")
    section_paths = SECTION_PATTERN.findall(presentation_source)
    if not section_paths:
        print("No slide sections referenced in presentation.js", file=sys.stderr)
        return 1

    missing: list[str] = []
    malformed: list[str] = []
    for relative_path in section_paths:
        section_path = SLIDES_ROOT / relative_path
        if not section_path.exists():
            missing.append(relative_path)
            continue
        content = section_path.read_text(encoding="utf-8")
        if 'class="slide' not in content and "class='slide" not in content:
            malformed.append(relative_path)

    if missing:
        print("Missing slide section files:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        return 1

    if malformed:
        print("Slide section files without .slide root:", file=sys.stderr)
        for item in malformed:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(f"Validated {len(section_paths)} referenced slide section files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
