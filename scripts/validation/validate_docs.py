"""Validate the canonical STWI contract and its published documentation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "project_contract.json"
DOCS = ROOT / "docs"


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_contract(errors: list[str], contract: dict) -> None:
    data = contract["data_contract"]
    if data["input_shape"] != "X[B,12,N,16]":
        fail(errors, "Canonical input shape must be X[B,12,N,16]")
    if data["forecast_shape"] != "Y[B,6,N,2]":
        fail(errors, "Canonical forecast shape must be Y[B,6,N,2]")
    if len(data["features"]) != 16:
        fail(errors, "Canonical feature list must contain exactly 16 features")
    if data["features"][-1]["name"] != "green_time_ratio":
        fail(errors, "Feature 16 must be green_time_ratio")
    statuses = contract["api"]["statuses"]
    expected = ["queued", "running", "succeeded", "needs_review", "failed", "expired"]
    if statuses != expected:
        fail(errors, f"Job statuses must be {expected}")


def validate_doc_versions(errors: list[str], contract: dict) -> None:
    for filename, expected_version in contract["documentation_versions"].items():
        path = DOCS / filename
        if not path.exists():
            fail(errors, f"Missing canonical document: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        version = re.search(r"\| \*\*Phiên bản\*\* \| ([^|]+) \|", text)
        updated = re.search(r"\| \*\*Cập nhật lần cuối\*\* \| ([^|]+) \|", text)
        if not version or version.group(1).strip() != expected_version:
            fail(errors, f"{filename}: expected version {expected_version}")
        if not updated or updated.group(1).strip() != "21/06/2026":
            fail(errors, f"{filename}: expected update date 21/06/2026")


def validate_markdown_links(errors: list[str]) -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
    for path in DOCS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in link_pattern.findall(text):
            clean = target.split("#", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                fail(errors, f"{path.relative_to(ROOT)}: broken link {target}")


def validate_json_examples(errors: list[str]) -> None:
    fence = re.compile(r"```json\s*(.*?)```", re.DOTALL)

    # Try importing contracts for semantic validation
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from stwi.t4_orchestrator.contracts import WhatIfJobRequest, WhatIfJobResult
        contracts_available = True
    except Exception as exc:
        contracts_available = False
        print(f"Warning: could not import contract classes for semantic validation: {exc}")

    for path in DOCS.glob("0[0-5]_*.md"):
        for index, snippet in enumerate(fence.findall(path.read_text(encoding="utf-8")), 1):
            try:
                data = json.loads(snippet)
            except json.JSONDecodeError as exc:
                fail(errors, f"{path.name}: invalid JSON example #{index}: {exc}")
                continue

            if not contracts_available or not isinstance(data, dict):
                continue

            # Semantic checking
            if "candidate_action" in data and "scenario_query" in data:
                try:
                    WhatIfJobRequest(**data)
                except Exception as exc:
                    fail(errors, f"{path.name}: JSON example #{index} is not a valid WhatIfJobRequest: {exc}")
            elif "safety_checks" in data or "audit_record" in data:
                try:
                    WhatIfJobResult(**data)
                except Exception as exc:
                    fail(errors, f"{path.name}: JSON example #{index} is not a valid WhatIfJobResult: {exc}")


def validate_public_artifacts(errors: list[str], contract: dict) -> None:
    presentation = (ROOT / "slides" / "js" / "presentation.js").read_text(encoding="utf-8")
    slide_paths = re.findall(r"'([^']+\.html)'", presentation)
    for relative in slide_paths:
        if not (ROOT / "slides" / relative).exists():
            fail(errors, f"presentation.js references missing slide: {relative}")
        if re.search(r"(?:stgcn|ade|xiyan|cfvla)", relative, re.IGNORECASE):
            fail(errors, f"presentation.js uses obsolete slide filename: {relative}")

    checked_files = [ROOT / ".github" / "workflows" / "build.yml"]
    checked_files += list((ROOT / "slides" / "sections").glob("*.html"))
    checked_files += [
        p for p in (ROOT / "report" / "chapters").glob("*.tex")
        if p.name != "ch02_co_so_ly_thuyet.tex"
    ]
    checked_files += list(DOCS.glob("0[0-5]_*.md"))

    banned = {
        r"\[B,\s*12,\s*(?:14|16)\]": "old tensor shape without node axis",
        r"\[Batch,\s*12,\s*14\]": "old tensor shape without node axis",
        r"B\s*\\times\s*12\s*\\times\s*14": "old LaTeX tensor shape without node axis",
        r"\[B,\s*N,\s*T'?\s*=\s*6,\s*3\]": "old three-target forecast shape",
        r"B\s*\\times\s*6\s*\\times\s*3": "old three-target forecast shape",
        r"N\s*\\times\s*6\s*\\times\s*3": "old three-target forecast shape",
        r"\b3D Tensor\b": "3D Tensor terminology",
        r"\bXiYan(?:SQL|-SQL)?\b": "XiYan in active architecture",
        r"\bRealGen\b": "RealGen in active architecture",
        r"\bADE(?:\s+Surrogate)?\b": "ADE in active architecture",
        r"\bCF-VLA Engine\b": "CF-VLA presented as implemented engine",
        r"\bSTGCN\b": "STGCN in active architecture",
        r"\b(?:LangChain|CrewAI)\b": "obsolete orchestration stack",
        r"\b(?:InfluxDB|FAISS|Weaviate)\b": "obsolete storage/retrieval stack",
        r"\b12 tuần\b": "obsolete 12-week timeline",
        r"legal(?:\\_|_|\s+)grounding": "obsolete unstructured legal grounding",
        r"\b(?:1\.000|1000) nút\b": "obsolete 1000-node MVP scope",
        r"\b50 nút\b": "obsolete 50-node MVP scope",
        r"\b80/10/10\b": "unspecified random split instead of chronological split",
    }
    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        for pattern, label in banned.items():
            if (
                path.name == "02_ML_and_Simulation_Specification.md"
                and pattern == r"\bSTGCN\b"
            ):
                continue
            if re.search(pattern, text, re.IGNORECASE):
                fail(errors, f"{path.relative_to(ROOT)}: contains {label}")

    chapter_corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "report" / "chapters").glob("*.tex")
    )
    slide_corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "slides" / "sections").glob("*.html")
    )
    cross_artifact_terms = [
        "X[B,12,N,16]",
        "M[B,12,N,16]",
        "A[N,N]",
        "[B,6,N,2]",
        "green_time_ratio",
        "Counterfactual Safety Loop",
        "POST /api/v1/what-if-jobs",
        "needs_review",
        "35/2024/QH15",
        "36/2024/QH15",
    ]
    normalized_chapters = chapter_corpus.replace("\\_", "_")
    for label, corpus in (("report", normalized_chapters), ("slides", slide_corpus)):
        compact_corpus = re.sub(r"\s+", "", corpus)
        for token in cross_artifact_terms:
            if re.sub(r"\s+", "", token) not in compact_corpus:
                fail(errors, f"{label} is missing canonical token: {token}")

    feature_text = (ROOT / "report" / "chapters" / "ch04_data_pipeline.tex").read_text(
        encoding="utf-8"
    ).replace("\\_", "_")
    for feature in contract["data_contract"]["features"]:
        if feature["name"] not in feature_text:
            fail(errors, f"report feature table is missing: {feature['name']}")

def validate_required_terms(errors: list[str]) -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in DOCS.glob("0[0-5]_*.md")
    )
    required = [
        "X[B,12,N,16]",
        "[B,6,N,2]",
        "green_time_ratio",
        "Counterfactual Safety Loop",
        "POST /api/v1/what-if-jobs",
        "needs_review",
        "35/2024/QH15",
        "36/2024/QH15"
    ]
    for token in required:
        if token not in corpus:
            fail(errors, f"Canonical docs are missing required token: {token}")


def main() -> int:
    errors: list[str] = []
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_contract(errors, contract)
    validate_doc_versions(errors, contract)
    validate_markdown_links(errors)
    validate_json_examples(errors)
    validate_public_artifacts(errors, contract)
    validate_required_terms(errors)
    if errors:
        print("STWI documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("STWI documentation validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
