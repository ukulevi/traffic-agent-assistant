"""MCP server for searching and downloading Roboflow Universe datasets.

The server intentionally has no third-party dependencies. It reads the
Roboflow API key from ROBOFLOW_API_KEY and communicates over MCP stdio.
Downloaded datasets are restricted to the current workspace to avoid writing
outside the repository when the tool is called by an agent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


API_BASE = "https://api.roboflow.com"
DEFAULT_TIMEOUT_SECONDS = 60
EXPORT_FORMATS = {
    "coco",
    "coco-segmentation",
    "createml",
    "darknet",
    "folder",
    "multiclass",
    "tfrecord",
    "voc",
    "yolov5pytorch",
    "yolov7pytorch",
    "yolov8",
    "yolov8-obb",
}
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class RoboflowMcpError(RuntimeError):
    """Typed error surfaced to MCP clients without leaking credentials."""


def api_key_from_env() -> str:
    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        raise RoboflowMcpError(
            "ROBOFLOW_API_KEY is not set. Create a scoped Roboflow API key "
            "and pass it through the MCP server environment."
        )
    return api_key


def validate_slug(value: str, name: str) -> str:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value):
        raise RoboflowMcpError(f"{name} must be a Roboflow slug")
    return value


def validate_export_format(value: str) -> str:
    if not isinstance(value, str) or value not in EXPORT_FORMATS:
        raise RoboflowMcpError(
            f"format must be one of: {', '.join(sorted(EXPORT_FORMATS))}"
        )
    return value


def redact_secrets(value: Any) -> Any:
    """Remove API keys from nested structures before returning data."""
    if isinstance(value, dict):
        return {key: redact_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"([?&]api_key=)[^&]+", r"\1<redacted>", value)
    return value


def http_json(
    path: str,
    params: dict[str, Any],
    *,
    api_base: str = API_BASE,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{api_base.rstrip('/')}/{path.lstrip('/')}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RoboflowMcpError(
            f"Roboflow API returned HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RoboflowMcpError(f"Roboflow API request failed: {exc.reason}") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RoboflowMcpError("Roboflow API returned non-JSON data") from exc
    if not isinstance(data, dict):
        raise RoboflowMcpError("Roboflow API returned an unexpected payload")
    return data


def search_universe_datasets(q: str, page: int = 1) -> dict[str, Any]:
    if not isinstance(q, str) or not q.strip():
        raise RoboflowMcpError("q must be a non-empty search query")
    if not isinstance(page, int) or page < 1:
        raise RoboflowMcpError("page must be an integer greater than zero")
    data = http_json(
        "/universe/search",
        {"q": q.strip(), "page": page, "api_key": api_key_from_env()},
    )
    return redact_secrets(data)


def export_dataset_link(
    workspace: str,
    project: str,
    version: int,
    export_format: str,
) -> dict[str, Any]:
    workspace = validate_slug(workspace, "workspace")
    project = validate_slug(project, "project")
    if not isinstance(version, int) or version < 1:
        raise RoboflowMcpError("version must be an integer greater than zero")
    export_format = validate_export_format(export_format)
    data = http_json(
        f"/{workspace}/{project}/{version}/{export_format}",
        {"api_key": api_key_from_env()},
    )
    return redact_secrets(data)


def ensure_workspace_path(path: Path, workspace_root: Path) -> Path:
    root = workspace_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RoboflowMcpError(
            f"output_dir must stay inside workspace: {root}"
        ) from exc
    return resolved


def safe_extract_zip(zip_path: Path, output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    root = output_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = (output_dir / member.filename).resolve()
            try:
                member_path.relative_to(root)
            except ValueError as exc:
                raise RoboflowMcpError(
                    f"refusing unsafe zip member: {member.filename}"
                ) from exc
        archive.extractall(output_dir)
        for member in archive.infolist():
            if not member.is_dir():
                extracted.append(member.filename)
    return extracted


def download_url(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "stwi-mcp/1"})
    try:
        with urllib.request.urlopen(
            request, timeout=DEFAULT_TIMEOUT_SECONDS
        ) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise RoboflowMcpError(f"dataset download failed: {exc.reason}") from exc


def download_dataset(
    workspace: str,
    project: str,
    version: int,
    export_format: str = "yolov5pytorch",
    output_dir: str | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    export = export_dataset_link(workspace, project, version, export_format)
    link = export.get("export", {}).get("link")
    if not isinstance(link, str) or not link.startswith(("http://", "https://")):
        raise RoboflowMcpError("Roboflow export response did not contain a link")

    workspace_root = workspace_root or Path.cwd()
    if output_dir is None:
        output = Path("data") / "external" / "roboflow" / (
            f"{project}-v{version}-{export_format}"
        )
    else:
        output = Path(output_dir)
    output = ensure_workspace_path(output, workspace_root)

    with tempfile.TemporaryDirectory() as directory:
        zip_path = Path(directory) / "roboflow_dataset.zip"
        download_url(link, zip_path)
        extracted = safe_extract_zip(zip_path, output)
    return {
        "output_dir": str(output),
        "file_count": len(extracted),
        "sample_files": extracted[:20],
        "source": {
            "workspace": workspace,
            "project": project,
            "version": version,
            "format": export_format,
        },
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "roboflow_universe_search": {
        "description": (
            "Search public Roboflow Universe datasets. Query supports Roboflow "
            "filter syntax such as images>1000, stars>=5, class:car, model:yolov8."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
            },
            "required": ["q"],
            "additionalProperties": False,
        },
    },
    "roboflow_export_dataset": {
        "description": "Return a Roboflow dataset export payload with signed link redacted only for API keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "project": {"type": "string"},
                "version": {"type": "integer", "minimum": 1},
                "format": {"type": "string", "default": "yolov5pytorch"},
            },
            "required": ["workspace", "project", "version"],
            "additionalProperties": False,
        },
    },
    "roboflow_download_dataset": {
        "description": (
            "Download and safely extract a Roboflow dataset into this workspace. "
            "Default output is data/external/roboflow/<project>-v<version>-<format>."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "project": {"type": "string"},
                "version": {"type": "integer", "minimum": 1},
                "format": {"type": "string", "default": "yolov5pytorch"},
                "output_dir": {"type": "string"},
            },
            "required": ["workspace", "project", "version"],
            "additionalProperties": False,
        },
    },
}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "roboflow_universe_search":
        return search_universe_datasets(arguments["q"], arguments.get("page", 1))
    if name == "roboflow_export_dataset":
        return export_dataset_link(
            arguments["workspace"],
            arguments["project"],
            arguments["version"],
            arguments.get("format", "yolov5pytorch"),
        )
    if name == "roboflow_download_dataset":
        return download_dataset(
            arguments["workspace"],
            arguments["project"],
            arguments["version"],
            arguments.get("format", "yolov5pytorch"),
            arguments.get("output_dir"),
        )
    raise RoboflowMcpError(f"unknown tool: {name}")


def read_mcp_message(stdin: Any = sys.stdin.buffer) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stdin.readline()
        if line == b"":
            return None
        line_text = line.decode("ascii").strip()
        if not line_text:
            break
        name, _, value = line_text.partition(":")
        headers[name.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(stdin.read(length).decode("utf-8"))


def write_mcp_message(message: dict[str, Any], stdout: Any = sys.stdout.buffer) -> None:
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stdout.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
    stdout.write(payload)
    stdout.flush()


def mcp_success(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def mcp_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        return mcp_success(
            message_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "stwi-roboflow-mcp", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": schema["description"],
                "inputSchema": schema["inputSchema"],
            }
            for name, schema in TOOL_SCHEMAS.items()
        ]
        return mcp_success(message_id, {"tools": tools})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = call_tool(name, arguments)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            return mcp_success(message_id, {"content": [{"type": "text", "text": text}]})
        except RoboflowMcpError as exc:
            return mcp_success(
                message_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                },
            )
    if message_id is None:
        return None
    return mcp_error(message_id, -32601, f"method not found: {method}")


def serve() -> int:
    while True:
        message = read_mcp_message()
        if message is None:
            return 0
        response = handle_message(message)
        if response is not None:
            write_mcp_message(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate server setup")
    args = parser.parse_args()
    if args.check:
        api_key_from_env()
        print("roboflow MCP server configuration is valid")
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
