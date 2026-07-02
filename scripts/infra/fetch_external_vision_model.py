"""Fetch an external detector weight file with SHA256 verification."""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Any
from urllib.parse import urlparse

try:
    from scripts.training.train_vision_model import sha256_file
except ModuleNotFoundError:
    from train_vision_model import sha256_file


def normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ValueError("expected-sha256 must be a 64-character hex digest")
    return normalized


def require_https_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("url must be an https URL")
    return url


def write_stream_with_sha256(
    *,
    source: BinaryIO,
    output_path: Path,
    expected_sha256: str,
    overwrite: bool,
    chunk_size: int = 1024 * 1024,
) -> dict[str, Any]:
    expected = normalize_sha256(expected_sha256)
    if output_path.exists():
        existing_sha = sha256_file(output_path)
        if existing_sha == expected:
            return {
                "status": "already_present",
                "path": str(output_path),
                "sha256": existing_sha,
                "size_bytes": output_path.stat().st_size,
            }
        if not overwrite:
            raise FileExistsError(
                f"existing file has different sha256 and overwrite is disabled: {output_path}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_name(output_path.name + ".part")
    if partial_path.exists():
        partial_path.unlink()
    with partial_path.open("wb") as handle:
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            handle.write(chunk)

    actual_sha = sha256_file(partial_path)
    if actual_sha != expected:
        partial_path.unlink(missing_ok=True)
        raise ValueError(
            f"downloaded file sha256 mismatch: expected {expected}, got {actual_sha}"
        )
    partial_path.replace(output_path)
    return {
        "status": "downloaded",
        "path": str(output_path),
        "sha256": actual_sha,
        "size_bytes": output_path.stat().st_size,
    }


def fetch_external_weight(
    *,
    url: str,
    output_path: Path,
    expected_sha256: str,
    overwrite: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    safe_url = require_https_url(url)
    expected = normalize_sha256(expected_sha256)
    if output_path.exists() and sha256_file(output_path) == expected:
        result = {
            "status": "already_present",
            "path": str(output_path),
            "sha256": expected,
            "size_bytes": output_path.stat().st_size,
        }
    else:
        with urllib.request.urlopen(safe_url, timeout=timeout_seconds) as response:
            result = write_stream_with_sha256(
                source=response,
                output_path=output_path,
                expected_sha256=expected,
                overwrite=overwrite,
            )
    manifest = {
        "schema_version": "1.0",
        "task": "external_vision_model_weight_fetch",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": safe_url,
        "expected_sha256": expected,
        "result": result,
    }
    manifest_path = output_path.with_name(output_path.name + ".fetch_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    manifest = fetch_external_weight(
        url=args.url,
        output_path=args.output,
        expected_sha256=args.expected_sha256,
        overwrite=args.overwrite,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({
        "status": manifest["result"]["status"],
        "path": manifest["result"]["path"],
        "sha256": manifest["result"]["sha256"],
        "manifest": str(args.output.with_name(args.output.name + ".fetch_manifest.json")),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
