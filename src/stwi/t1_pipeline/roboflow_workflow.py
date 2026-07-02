"""Roboflow workflow client for STWI camera-frame inference.

The workflow is used only to convert single images/frames into detection
evidence for downstream five-minute aggregates. It does not publish raw video
or make traffic-control decisions.
"""

from __future__ import annotations

import base64
import concurrent.futures
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


WORKSPACE_NAME = "lymphaticvesselsegmentation"
WORKFLOW_ID = "stwi-traffic-unified-phase-2-v1-logic"
API_URL = "https://serverless.roboflow.com"
API_KEY_ENV = "ROBOFLOW_API_KEY"

WORKFLOW_DEFINITION: dict[str, Any] = {
    "version": "1.0",
    "inputs": [{"type": "InferenceImage", "name": "image"}],
    "steps": [
        {
            "type": "roboflow_core/inner_workflow@v1",
            "name": "model",
            "workflow_workspace_id": "lymphaticvesselsegmentation",
            "workflow_id": "stwi-traffic-unified-phase-2",
            "workflow_version_id": None,
            "parameter_bindings": {
                "image": "$inputs.image",
                "model_id": "stwi-traffic-unified-phase-2/1",
            },
        }
    ],
    "outputs": [
        {
            "type": "JsonField",
            "name": "predictions",
            "coordinates_system": "own",
            "selector": "$steps.model.predictions",
        }
    ],
}


class RoboflowWorkflowError(RuntimeError):
    """Base error for STWI Roboflow workflow integration failures."""


class RoboflowWorkflowConfigError(RoboflowWorkflowError):
    """Raised when credentials, SDK, or workflow configuration is missing."""


class RoboflowWorkflowRequestError(RoboflowWorkflowError):
    """Raised when workflow inference fails after retries."""


def _validate_image_bytes(data: bytes) -> None:
    size = len(data)
    if size < 10:
        raise ValueError("Image data too small")
    # Guard: Max 25 MB
    if size > 25 * 1024 * 1024:
        raise ValueError("Image data exceeds maximum allowed size (25 MB)")

    # JPEG starts with FF D8 FF
    if data.startswith(b"\xff\xd8\xff"):
        return
    # PNG starts with 89 50 4E 47 0D 0A 1A 0A
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    # GIF starts with GIF87a or GIF89a
    if data.startswith(b"GIF8"):
        return
    # BMP starts with BM
    if data.startswith(b"BM"):
        return
    # WEBP: RIFF + WEBP
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return
    # HEIF/HEIC signature
    if len(data) >= 12 and data[4:12] in (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1", b"ftypmsf1"):
        return

    raise ValueError("Unsupported or invalid image format signature")


@dataclass(frozen=True)
class RoboflowImageInput:
    """Image input accepted by the Roboflow workflow."""

    kind: str
    value: str

    def __repr__(self) -> str:
        if self.kind == "base64":
            return f"RoboflowImageInput(kind='base64', value_len={len(self.value)})"
        return f"RoboflowImageInput(kind={self.kind!r}, value={self.value!r})"

    @classmethod
    def https_url(cls, url: str) -> "RoboflowImageInput":
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Roboflow URL inputs must use https://")
        return cls(kind="url", value=url)

    @classmethod
    def base64(cls, value: str) -> "RoboflowImageInput":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("base64 image input must be a non-empty string")
        
        cleaned = value.strip()
        data_url_match = re.match(r"^data:image/(jpeg|jpg|png|gif|webp|heic|heif|bmp);base64,(.*)$", cleaned, re.IGNORECASE)
        if data_url_match:
            base64_data = data_url_match.group(2).strip()
        else:
            base64_data = cleaned

        # Ensure base64 string length is a multiple of 4
        pad_len = len(base64_data) % 4
        if pad_len > 0:
            base64_data += "=" * (4 - pad_len)

        try:
            decoded = base64.b64decode(base64_data, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 encoding") from exc

        _validate_image_bytes(decoded)
        return cls(kind="base64", value=value)


@dataclass(frozen=True)
class RoboflowWorkflowResult:
    """Parsed workflow response keyed by the workflow's declared outputs."""

    output_names: tuple[str, ...]
    entries: tuple[Mapping[str, Any], ...]

    def first(self) -> Mapping[str, Any]:
        if not self.entries:
            raise RoboflowWorkflowRequestError("Roboflow workflow returned no entries")
        return self.entries[0]


def workflow_input_names() -> tuple[str, ...]:
    return tuple(item["name"] for item in WORKFLOW_DEFINITION["inputs"])


def workflow_output_names() -> tuple[str, ...]:
    return tuple(item["name"] for item in WORKFLOW_DEFINITION["outputs"])


def workflow_parameter_names() -> tuple[str, ...]:
    return tuple(item["name"] for item in WORKFLOW_DEFINITION.get("parameters", []))


def api_key_from_env(env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    api_key = env.get(API_KEY_ENV, "").strip()
    if not api_key:
        raise RoboflowWorkflowConfigError(
            f"{API_KEY_ENV} is not set. Create a Roboflow API key at "
            "app.roboflow.com/settings/api and provide it via the environment."
        )
    return api_key


def _load_inference_client_class() -> type[Any]:
    try:
        from inference_sdk import InferenceHTTPClient
    except ImportError as exc:
        raise RoboflowWorkflowConfigError(
            "inference-sdk is required for Roboflow workflow inference. "
            "Install the project with the vision extra."
        ) from exc
    return InferenceHTTPClient


def _create_default_client(api_key: str) -> Any:
    client_class = _load_inference_client_class()
    return client_class(api_url=API_URL, api_key=api_key)


def _validate_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    declared = set(workflow_parameter_names())
    extra = set(parameters) - declared
    if extra:
        names = ", ".join(sorted(extra))
        raise ValueError(f"unknown Roboflow workflow parameter(s): {names}")
    return dict(parameters)


def _call_with_timeout(
    client: Any,
    image: RoboflowImageInput,
    parameters: Mapping[str, Any],
    timeout_seconds: float,
) -> Any:
    images = {workflow_input_names()[0]: image.value}
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        client.run_workflow,
        workspace_name=WORKSPACE_NAME,
        workflow_id=WORKFLOW_ID,
        images=images,
        parameters=dict(parameters),
    )
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def parse_workflow_response(response: Any) -> RoboflowWorkflowResult:
    """Validate and retain only fields declared by the workflow outputs."""

    output_names = workflow_output_names()
    if not isinstance(response, list):
        raise RoboflowWorkflowRequestError("Roboflow workflow response must be a list")
    parsed: list[Mapping[str, Any]] = []
    for index, item in enumerate(response):
        if not isinstance(item, Mapping):
            raise RoboflowWorkflowRequestError(
                f"Roboflow workflow entry {index} must be an object"
            )
        missing = [name for name in output_names if name not in item]
        if missing:
            raise RoboflowWorkflowRequestError(
                "Roboflow workflow response missing output key(s): "
                + ", ".join(missing)
            )
        parsed.append({name: item[name] for name in output_names})
    return RoboflowWorkflowResult(output_names=output_names, entries=tuple(parsed))


def run_stwi_traffic_workflow(
    image: RoboflowImageInput,
    *,
    parameters: Mapping[str, Any] | None = None,
    timeout_seconds: float = 30.0,
    retries: int = 2,
    backoff_seconds: float = 1.0,
    client: Any | None = None,
    env: Mapping[str, str] | None = None,
) -> RoboflowWorkflowResult:
    """Run the STWI Roboflow workflow on one image and parse declared outputs."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if retries < 0:
        raise ValueError("retries must be non-negative")
    safe_parameters = _validate_parameters(parameters or {})
    client = client or _create_default_client(api_key_from_env(env))

    last_error: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            response = _call_with_timeout(
                client,
                image,
                safe_parameters,
                timeout_seconds,
            )
            return parse_workflow_response(response)
        except (TimeoutError, Exception) as exc:  # SDK surfaces transport-specific types.
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(backoff_seconds * (2**attempt))
    raise RoboflowWorkflowRequestError(
        f"Roboflow workflow {WORKFLOW_ID} failed after {retries + 1} attempt(s)"
    ) from last_error


_DATA_URL_RE = re.compile(r"^data:image/([A-Za-z0-9.+-]+);base64,(.+)$")
_PLAIN_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def write_image_outputs(
    result: RoboflowWorkflowResult,
    output_dir: Path,
) -> dict[str, list[Path]]:
    """Decode image-shaped base64 outputs to disk without logging payloads."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, list[Path]] = {}
    for entry_index, entry in enumerate(result.entries):
        for output_name, value in entry.items():
            for image_index, encoded in enumerate(_iter_base64_images(value)):
                suffix, payload = encoded
                path = output_dir / f"{output_name}_{entry_index}_{image_index}.{suffix}"
                path.write_bytes(base64.b64decode(payload, validate=True))
                written.setdefault(output_name, []).append(path)
    return written


def _iter_base64_images(value: Any) -> list[tuple[str, str]]:
    if isinstance(value, str):
        match = _DATA_URL_RE.match(value)
        if match:
            return [(match.group(1).lower().replace("jpeg", "jpg"), match.group(2))]
        if len(value) > 4096 and _PLAIN_BASE64_RE.fullmatch(value):
            return [("png", value)]
        return []
    if isinstance(value, Mapping):
        kind = str(value.get("type", "")).lower()
        payload = value.get("value")
        if kind == "base64" and isinstance(payload, str):
            return [("png", payload)]
        found: list[tuple[str, str]] = []
        for nested in value.values():
            found.extend(_iter_base64_images(nested))
        return found
    if isinstance(value, list):
        found = []
        for nested in value:
            found.extend(_iter_base64_images(nested))
        return found
    return []
