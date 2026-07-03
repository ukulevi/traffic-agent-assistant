"""Register a downloaded open-source detector candidate for local STWI tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stwi.tooling.vision_training.external_models import (
    build_class_map,
    copy_candidate_weights,
    normalize_class_aliases,
    normalize_prompt_classes,
    normalize_source_classes,
    register_external_model,
    slugify_model_id,
)
from stwi.tooling.vision_training.promotion import REQUIRED_STWI_CLASSES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-license", required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/derived/private/vision_external_models"),
    )
    parser.add_argument(
        "--model-family",
        choices=["yolo", "yolo_world", "rtdetr"],
        default="yolo",
    )
    parser.add_argument("--source-class", action="append", default=None)
    parser.add_argument(
        "--class-map",
        action="append",
        default=None,
        help="Map source class to STWI class using SOURCE:TARGET.",
    )
    parser.add_argument(
        "--class-alias",
        action="append",
        default=None,
        help="Map predicted class name during evaluation using SOURCE:TARGET.",
    )
    parser.add_argument("--prompt-class", action="append", default=None)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--copy-weights", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest = register_external_model(
        model_id=args.model_id,
        source_url=args.source_url,
        source_license=args.source_license,
        weights_path=args.weights,
        output_root=args.output_root,
        model_family=args.model_family,
        source_classes=args.source_class,
        class_map_values=args.class_map,
        class_alias_values=args.class_alias,
        prompt_classes=args.prompt_class,
        reviewer=args.reviewer,
        notes=args.notes,
        copy_weights=args.copy_weights,
        overwrite=args.overwrite,
    )
    print(json.dumps({
        "candidate_status": manifest["candidate_status"],
        "manifest": manifest["manifest_path"],
        "weights": manifest["weights"],
        "missing_stwi_classes": manifest["missing_stwi_classes"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
