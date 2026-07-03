from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.project_management.sync_codex_claude_mcp import build_claude_config


CODEX_CONFIG = """
[mcp_servers.roboflow]
enabled = true
url = "https://mcp.roboflow.com/mcp"
bearer_token_env_var = "ROBOFLOW_MCP_TOKEN"

[mcp_servers.node_repl]
enabled = true
command = "C:\\\\Codex\\\\node_repl.exe"

[mcp_servers.harness-mcp]
enabled = true
command = "npx"
args = ["-y", "harness-mcp-v2@latest"]
env_vars = ["HARNESS_API_KEY"]

[mcp_servers.data-science]
enabled = true
command = "C:\\\\Python\\\\python.exe"
args = ["C:\\\\Users\\\\PC\\\\.codex\\\\mcp\\\\data_science_mcp_server.py"]
env_vars = ["HF_TOKEN"]

[mcp_servers.disabled]
enabled = false
command = "ignored"
"""


class SyncCodexClaudeMcpTest(unittest.TestCase):
    def write_config(self, text: str = CODEX_CONFIG) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "config.toml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_desktop_default_keeps_safe_local_stdio_only(self) -> None:
        config, included, skipped = build_claude_config(self.write_config())

        self.assertEqual(included, ["data-science"])
        self.assertIn("data-science", config["mcpServers"])
        self.assertEqual(
            config["mcpServers"]["data-science"]["env"]["HF_TOKEN"],
            "${HF_TOKEN}",
        )
        self.assertIn("remote HTTP MCP", skipped["roboflow"])
        self.assertIn("Codex-internal", skipped["node_repl"])
        self.assertIn("network/package-manager", skipped["harness-mcp"])
        self.assertEqual(skipped["disabled"], "disabled")

    def test_remote_http_can_be_included_with_env_reference(self) -> None:
        config, included, skipped = build_claude_config(
            self.write_config(),
            include_remote_http=True,
        )

        self.assertIn("roboflow", included)
        self.assertNotIn("roboflow", skipped)
        self.assertEqual(config["mcpServers"]["roboflow"]["type"], "http")
        self.assertEqual(
            config["mcpServers"]["roboflow"]["headers"]["Authorization"],
            "Bearer ${ROBOFLOW_MCP_TOKEN}",
        )

    def test_existing_claude_servers_are_preserved(self) -> None:
        existing = {"mcpServers": {"custom": {"command": "custom-server"}}}
        config, _included, _skipped = build_claude_config(
            self.write_config(),
            existing_config=existing,
        )

        self.assertEqual(
            config["mcpServers"]["custom"],
            {"command": "custom-server"},
        )


if __name__ == "__main__":
    unittest.main()
