"""Runtime mode configuration.

This module is intentionally small: it centralizes environment-derived runtime
mode without duplicating contract constants from ``project_contract.json``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class RuntimeMode(str, Enum):
    """Supported runtime modes for composition and safety guards."""

    DEVELOPMENT = "development"
    TEST = "test"
    DEMO = "demo"
    PRODUCTION = "production"


_ALIASES = {
    "dev": RuntimeMode.DEVELOPMENT,
    "development": RuntimeMode.DEVELOPMENT,
    "local": RuntimeMode.DEVELOPMENT,
    "test": RuntimeMode.TEST,
    "ci": RuntimeMode.TEST,
    "demo": RuntimeMode.DEMO,
    "prod": RuntimeMode.PRODUCTION,
    "production": RuntimeMode.PRODUCTION,
}


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings for app composition."""

    mode: RuntimeMode

    @property
    def allow_provisional_adapters(self) -> bool:
        """Whether fake/in-memory adapters may be auto-wired."""
        return self.mode in {
            RuntimeMode.DEVELOPMENT,
            RuntimeMode.TEST,
            RuntimeMode.DEMO,
        }


def get_runtime_settings(environ: dict[str, str] | None = None) -> RuntimeSettings:
    """Resolve runtime settings from environment variables.

    ``STWI_RUNTIME_MODE`` is deliberately the single mode knob for now. The
    default remains development so existing tests and local demos are stable.
    """
    env = environ if environ is not None else os.environ
    raw_mode = env.get("STWI_RUNTIME_MODE", RuntimeMode.DEVELOPMENT.value).strip().lower()
    try:
        mode = _ALIASES[raw_mode]
    except KeyError as exc:
        allowed = ", ".join(sorted(_ALIASES))
        raise ValueError(
            f"Unsupported STWI_RUNTIME_MODE={raw_mode!r}; expected one of: {allowed}"
        ) from exc
    return RuntimeSettings(mode=mode)


def is_production_mode(environ: dict[str, str] | None = None) -> bool:
    """Return whether the resolved runtime mode is production."""
    return get_runtime_settings(environ).mode == RuntimeMode.PRODUCTION


__all__ = [
    "RuntimeMode",
    "RuntimeSettings",
    "get_runtime_settings",
    "is_production_mode",
]
