"""Read-only access to the machine-readable STWI project contract."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_project_contract() -> dict[str, Any]:
    contract_path = Path(__file__).resolve().parents[3] / "project_contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def feature_names() -> tuple[str, ...]:
    return tuple(
        feature["name"]
        for feature in load_project_contract()["data_contract"]["features"]
    )


def feature_units() -> dict[str, str]:
    return {
        feature["name"]: feature["unit"]
        for feature in load_project_contract()["data_contract"]["features"]
    }


def scaled_feature_indices() -> tuple[int, ...]:
    return tuple(
        index
        for index, feature in enumerate(
            load_project_contract()["data_contract"]["features"]
        )
        if feature["encoding"] == "scaled_continuous"
    )
