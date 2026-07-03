"""Sync portable Codex MCP declarations into Claude client config.

The script copies MCP server declarations, not secret values. Token settings
such as ``bearer_token_env_var`` are represented as environment references so
the Claude-side process must read the real value from the user's environment.

Claude Desktop primarily supports local stdio MCP servers through
``claude_desktop_config.json``. Remote HTTP MCP servers are reported as
connector candidates by default; pass ``--include-remote-http`` only for Claude
clients/configurations that explicitly support HTTP MCP entries in JSON config.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CODEX_INTERNAL_SERVERS = {"node_repl"}
NETWORK_STDIO_COMMANDS = {"npx", "npm", "pnpm", "yarn"}


@dataclass(frozen=True)
class SyncResult:
    written: bool
    output_path: Path
    included: list[str]
    skipped: dict[str, str]
    backup_path: Path | None = None


def claude_desktop_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def env_ref(name: str) -> str:
    return "${" + name + "}"


def command_name(command: str) -> str:
    return Path(command.strip("\"'")).name.lower()


def convert_server(
    name: str,
    config: dict[str, Any],
    *,
    include_remote_http: bool,
    include_network_stdio: bool,
    include_internal: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    if config.get("enabled") is False:
        return None, "disabled"
    if name in CODEX_INTERNAL_SERVERS and not include_internal:
        return None, "Codex-internal server"

    url = config.get("url")
    if isinstance(url, str) and url:
        if not include_remote_http:
            return None, "remote HTTP MCP; add as Claude connector or rerun with --include-remote-http"
        entry: dict[str, Any] = {"type": "http", "url": url}
        token_env = config.get("bearer_token_env_var")
        if isinstance(token_env, str) and token_env:
            entry["headers"] = {"Authorization": f"Bearer {env_ref(token_env)}"}
        return entry, None

    command = config.get("command")
    if not isinstance(command, str) or not command:
        return None, "missing command/url"
    if command_name(command) in NETWORK_STDIO_COMMANDS and not include_network_stdio:
        return None, "network/package-manager stdio server; rerun with --include-network-stdio"

    entry = {"command": command}
    args = config.get("args")
    if isinstance(args, list):
        entry["args"] = args

    env: dict[str, str] = {}
    env_vars = config.get("env_vars")
    if isinstance(env_vars, list):
        for item in env_vars:
            if isinstance(item, str) and item:
                env[item] = env_ref(item)

    inline_env = config.get("env")
    if isinstance(inline_env, dict):
        for key, value in inline_env.items():
            if isinstance(key, str) and isinstance(value, str):
                env[key] = value

    if env:
        entry["env"] = env
    return entry, None


def load_codex_servers(codex_config: Path) -> dict[str, dict[str, Any]]:
    data = tomllib.loads(codex_config.read_text(encoding="utf-8"))
    servers = data.get("mcp_servers", {})
    if not isinstance(servers, dict):
        return {}
    return {name: cfg for name, cfg in servers.items() if isinstance(cfg, dict)}


def load_existing_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_claude_config(
    codex_config: Path,
    *,
    existing_config: dict[str, Any] | None = None,
    include_remote_http: bool = False,
    include_network_stdio: bool = False,
    include_internal: bool = False,
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    config = dict(existing_config or {})
    existing_servers = config.get("mcpServers")
    if not isinstance(existing_servers, dict):
        existing_servers = {}

    included: list[str] = []
    skipped: dict[str, str] = {}
    merged = dict(existing_servers)
    for name, server_config in load_codex_servers(codex_config).items():
        entry, reason = convert_server(
            name,
            server_config,
            include_remote_http=include_remote_http,
            include_network_stdio=include_network_stdio,
            include_internal=include_internal,
        )
        if entry is None:
            skipped[name] = reason or "not portable"
            continue
        merged[name] = entry
        included.append(name)

    config["mcpServers"] = merged
    return config, sorted(included), dict(sorted(skipped.items()))


def sync(
    codex_config: Path,
    output_path: Path,
    *,
    write: bool,
    include_remote_http: bool = False,
    include_network_stdio: bool = False,
    include_internal: bool = False,
) -> SyncResult:
    existing = load_existing_config(output_path)
    config, included, skipped = build_claude_config(
        codex_config,
        existing_config=existing,
        include_remote_http=include_remote_http,
        include_network_stdio=include_network_stdio,
        include_internal=include_internal,
    )
    payload = json.dumps(config, indent=2, ensure_ascii=False) + "\n"

    backup_path = None
    if write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            backup_path = output_path.with_suffix(output_path.suffix + ".bak")
            shutil.copy2(output_path, backup_path)
        output_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    return SyncResult(
        written=write,
        output_path=output_path,
        included=included,
        skipped=skipped,
        backup_path=backup_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-config",
        type=Path,
        default=Path.home() / ".codex" / "config.toml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=claude_desktop_config_path(),
        help="Claude Desktop claude_desktop_config.json path.",
    )
    parser.add_argument("--write", action="store_true", help="Write the output file.")
    parser.add_argument(
        "--include-remote-http",
        action="store_true",
        help="Include remote HTTP MCP entries for Claude clients that support them.",
    )
    parser.add_argument(
        "--include-network-stdio",
        action="store_true",
        help="Include stdio MCP servers launched by package managers such as npx.",
    )
    parser.add_argument(
        "--include-internal",
        action="store_true",
        help="Include Codex-internal MCP servers. Usually not portable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = sync(
        args.codex_config,
        args.output,
        write=args.write,
        include_remote_http=args.include_remote_http,
        include_network_stdio=args.include_network_stdio,
        include_internal=args.include_internal,
    )
    mode = "Wrote" if result.written else "Rendered"
    print(f"{mode}: {result.output_path}", file=sys.stderr)
    if result.backup_path:
        print(f"Backup: {result.backup_path}", file=sys.stderr)
    print("Included: " + (", ".join(result.included) or "none"), file=sys.stderr)
    if result.skipped:
        print("Skipped:", file=sys.stderr)
        for name, reason in result.skipped.items():
            print(f"- {name}: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
