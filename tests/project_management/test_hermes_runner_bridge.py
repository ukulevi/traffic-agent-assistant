from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "project_management" / "hermes_runner_bridge.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hermes_runner_bridge", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PACKET = """# Current Hermes Dispatch Packet

## Ticket

`TRA-99` / `STWI-SYM-099` - Test bridge packet

## Goal

Prepare a safe worker prompt.

## Allowed Files

```text
docs/project_management/symphony/board.json
scripts/project_management/symphony_report.py
```

## Forbidden Changes

- project_contract.json
- commit, push, PR, staging, branch change, or Linear state changes

## Acceptance Criteria

- Bridge can parse the packet.

## Exact Checks

```powershell
python scripts/project_management/symphony_report.py
```

## Required Final Report

```text
Result:
Changed files:
Checks:
Contract/artifact impact:
Risks/blockers:
Recommended next state:
```
"""


class HermesRunnerBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = load_module()

    def test_parses_packet_and_allowed_files(self) -> None:
        packet = self.bridge.parse_dispatch_packet(PACKET)

        self.assertEqual(packet.identifier, "TRA-99")
        self.assertEqual(packet.title, "Test bridge packet")
        self.assertEqual(
            packet.allowed_files,
            [
                "docs/project_management/symphony/board.json",
                "scripts/project_management/symphony_report.py",
            ],
        )
        self.assertEqual(self.bridge.validate_packet(packet), [])

    def test_rejects_allowed_source_of_truth_file(self) -> None:
        packet = self.bridge.parse_dispatch_packet(
            PACKET.replace(
                "scripts/project_management/symphony_report.py",
                "project_contract.json",
            )
        )

        errors = self.bridge.validate_packet(packet)

        self.assertIn("source-of-truth", errors[0])

    def test_builds_prompt_with_executor_boundaries(self) -> None:
        packet = self.bridge.parse_dispatch_packet(PACKET)

        prompt = self.bridge.build_hermes_prompt(packet, Path("C:/repo"))

        self.assertIn("Execute only the dispatch packet below", prompt)
        self.assertIn("Do not change Linear", prompt)
        self.assertIn("docs/project_management/symphony/board.json", prompt)
        self.assertIn("Recommended next state:", prompt)

    def test_writes_prompt_and_manifest_without_running(self) -> None:
        packet = self.bridge.parse_dispatch_packet(PACKET)
        prompt = self.bridge.build_hermes_prompt(packet, Path("C:/repo"))
        with tempfile.TemporaryDirectory() as temp:
            prompt_file, manifest_file, artifact_base = self.bridge.write_artifacts(
                packet,
                prompt,
                Path(temp),
                Path("packet.md"),
                None,
            )

            self.assertTrue(prompt_file.exists())
            self.assertTrue(manifest_file.exists())
            self.assertTrue(artifact_base.startswith("TRA-99_"))
            self.assertIn("prepared", manifest_file.read_text(encoding="utf-8"))

    def test_renders_command_placeholders(self) -> None:
        command = self.bridge.render_command(
            ["hermes", "--oneshot", "{prompt_file}", "--packet", "{packet_file}"],
            Path("prompt.md"),
            Path("packet.md"),
        )

        self.assertEqual(
            command,
            ["hermes", "--oneshot", "prompt.md", "--packet", "packet.md"],
        )

    def test_permission_denied_candidate_is_treated_as_callable(self) -> None:
        original_path = self.bridge.Path

        class DeniedPath:
            def __init__(self, _value: str) -> None:
                pass

            def exists(self) -> bool:
                raise PermissionError("sandbox")

        self.bridge.Path = DeniedPath
        try:
            self.assertTrue(self.bridge.candidate_path_exists("C:/hermes.exe"))
        finally:
            self.bridge.Path = original_path


if __name__ == "__main__":
    unittest.main()
