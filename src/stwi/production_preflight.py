"""Container-start preflight for fail-closed STWI production composition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TextIO

from stwi.production_health import Probe, run_cli


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    probes: Mapping[str, Probe] | None = None,
    stdout: TextIO | None = None,
) -> int:
    del argv
    return run_cli(
        command="preflight",
        environ=environ,
        probes=probes,
        stdout=stdout,
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
