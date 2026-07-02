"""Legal corpus ingestion for Phase 3.

Downloads from official sources, parses to chunks preserving articles/provisions,
and creates immutable manifests.

Minimum corpus: Luật 35/2024/QH15 and Luật 36/2024/QH15.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stwi.contracts.knowledge import LegalChunk


# Official sources per project_contract.json
OFFICIAL_SOURCES = {
    "law-35-2024-qh15": {
        "number": "35/2024/QH15",
        "title": "Luật Đường bộ",
        "url": "https://vanban.chinhphu.vn/?pageid=27160&docid=211193",
        "effective_from": "2025-01-01",
    },
    "law-36-2024-qh15": {
        "number": "36/2024/QH15",
        "title": "Luật Trật tự, an toàn giao thông đường bộ",
        "url": "https://vanban.chinhphu.vn/?pageid=27160&docid=211194&classid=1&typegroupid=3",
        "effective_from": "2025-01-01",
    },
}

# SOP sources — synthetic_test_only until real SOPs are provided by legal owner.
# Per policy: SOP chỉ được ingest khi có owner, version, ngày duyệt và phạm vi áp dụng.
# These fixtures use internal placeholder URLs and are NOT real documents.
SOP_SOURCES = {
    "sop-incident-01": {
        "number": "SOP-01/SGTVT-HCMC",
        "title": "SOP Xử lý tai nạn giao thông liên hoàn",
        "url": "https://internal.example/sop-01",
        "effective_from": "2025-01-01",
    },
    "sop-incident-02": {
        "number": "SOP-02/SGTVT-HCMC",
        "title": "SOP Xử lý ngập cục bộ trên đường bộ",
        "url": "https://internal.example/sop-02",
        "effective_from": "2025-01-01",
    },
    "sop-incident-03": {
        "number": "SOP-03/SGTVT-HCMC",
        "title": "SOP Xử lý đổ cây trên đường bộ",
        "url": "https://internal.example/sop-03",
        "effective_from": "2025-01-01",
    },
    "sop-incident-04": {
        "number": "SOP-04/SGTVT-HCMC",
        "title": "SOP Xử lý tràn dầu trên đường bộ",
        "url": "https://internal.example/sop-04",
        "effective_from": "2025-01-01",
    },
    "sop-incident-05": {
        "number": "SOP-05/SGTVT-HCMC",
        "title": "SOP Phối hợp CSGT, Cứu hỏa, Y tế trong sự cố giao thông",
        "url": "https://internal.example/sop-05",
        "effective_from": "2025-01-01",
    },
}

PARSER_VERSION = "1.0.0"
logger = logging.getLogger(__name__)


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content.

    Canonical implementation lives in citation_validator; this is a local
    alias kept for backwards-compat within this module.
    """
    from stwi.t3_knowledge.citation_validator import compute_content_hash as _canonical
    return _canonical(content)


def parse_provision(content: str, provision: str) -> str:
    """Extract provision content from full text.

    For synthetic test fixtures, returns the content as-is with provision label.
    Real parser would use regex patterns to extract specific articles.
    """
    # In production, this would parse actual document structure
    return content


def create_chunk(
    document_id: str,
    title: str,
    document_number: str,
    provision: str,
    source_url: str,
    effective_from: str,
    content: str,
) -> LegalChunk:
    """Create a LegalChunk from provision content."""
    return LegalChunk(
        document_id=document_id,
        title=title,
        document_number=document_number,
        provision=provision,
        source_url=source_url,
        effective_from=datetime.strptime(effective_from, "%Y-%m-%d").date(),
        effective_to=None,
        superseded=False,
        jurisdiction="VN",
        content_hash=compute_content_hash(content),
        content=content,
    )


def ingest_law_35_2024_qh15() -> list[LegalChunk]:
    """Ingest Luật Đường bộ 35/2024/QH15.

    Returns list of chunks (one per article/provision).
    For Phase 3 mock-first, uses synthetic fixtures with synthetic_test_only label.
    """
    source_info = OFFICIAL_SOURCES["law-35-2024-qh15"]

    # Synthetic fixture for Phase 3 mock-first development
    # Per policy: SOP chỉ được ingest khi có owner, version, ngày duyệt
    # Legal documents are created as fixtures with verification markers
    chunks = [
        create_chunk(
            document_id="law-35-2024-qh15",
            title=source_info["title"],
            document_number=source_info["number"],
            provision="Điều 1",
            source_url=source_info["url"],
            effective_from=source_info["effective_from"],
            content="[SYNTHETIC_TEST_ONLY] Luật Đường bộ quy định về quyền và nghĩa vụ của người sử dụng đường, "
            "quan hệ pháp luật trong giao thông đường bộ, nguyên tắc quản lý và điều hành "
            "anh hưởng đến an toàn giao thông. Được biết: đường bộ là con đường, cầu đường, "
            "bến phà đường bộ và các công trình phụ trợ khác để phục vụ cho giao thông đường bộ.",
        ),
        create_chunk(
            document_id="law-35-2024-qh15",
            title=source_info["title"],
            document_number=source_info["number"],
            provision="Điều 58",
            source_url=source_info["url"],
            effective_from=source_info["effective_from"],
            content="[SYNTHETIC_TEST_ONLY] Phương tiện giao thông đường bộ không vận hành đúng biển báo, "
            "vạte quy định về tần suất xuyên khẩu, thay đổi làn đi nhanh chậm sẽ bị xử lý vi phạm "
            "hành chính. Vi phạm không chấp hành thực hiện biển báo sau 3 lần sẽ bị tước quyền sử dụng "
            "phương tiện.",
        ),
    ]
    return chunks


def ingest_law_36_2024_qh15() -> list[LegalChunk]:
    """Ingest Luật Trật tự, an toàn giao thông đường bộ 36/2024/QH15.

    Returns list of chunks (one per article/provision).
    For Phase 3 mock-first, uses synthetic fixtures.
    """
    source_info = OFFICIAL_SOURCES["law-36-2024-qh15"]

    chunks = [
        create_chunk(
            document_id="law-36-2024-qh15",
            title=source_info["title"],
            document_number=source_info["number"],
            provision="Điều 10",
            source_url=source_info["url"],
            effective_from=source_info["effective_from"],
            content="[SYNTHETIC_TEST_ONLY] Người tham gia giao thông đường bộ phải tuân thự quy định "
            "về trật tự, an toàn trên đường; vi phạm sẽ bị xử lý kỷ luật, hành chính hoặc hình sự "
            "tùy mức độ nghiêm trọng. Bao gồm: người lái xe, người ngồi trên xe, người đi bộ và người dẫn xe.",
        ),
        create_chunk(
            document_id="law-36-2024-qh15",
            title=source_info["title"],
            document_number=source_info["number"],
            provision="Điều 43",
            source_url=source_info["url"],
            effective_from=source_info["effective_from"],
            content="[SYNTHETIC_TEST_ONLY] Người lái xe có trách nhiệm dừng xe, dừng xe nguy hiểm "
            "để tránh tai nạn, kiểm tra phương tiện, cảnh báo người tham gia giao thông khác khi "
            "phát hiện sự cố, bẩn hổ trợ kỹ thuật số cho động cơ, phanh, hệ thống lái, đèn, còi.",
        ),
    ]
    return chunks


def build_corpus_manifest(chunks: list[LegalChunk]) -> dict[str, Any]:
    """Build immutable manifest for ingested corpus.

    Includes: URL, retrieval timestamp, effective dates, content hash, parser version.
    """
    by_document: dict[str, list[dict]] = {}
    for chunk in chunks:
        if chunk.document_id not in by_document:
            by_document[chunk.document_id] = []
        by_document[chunk.document_id].append({
            "provision": chunk.provision,
            "content_hash": chunk.content_hash,
            "source_url": chunk.source_url,
            "effective_from": chunk.effective_from.isoformat(),
            "effective_to": chunk.effective_to.isoformat() if chunk.effective_to else None,
            "superseded": chunk.superseded,
        })

    return {
        "schema_version": "1.0",
        "parser_version": PARSER_VERSION,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "documents": by_document,
    }


def load_official_corpus(corpus_dir: Path) -> list[LegalChunk] | None:
    """Load officially ingested corpus from chunks.json files if available.

    Returns None if official corpus has not been ingested yet.
    Official corpus is written by scripts/infra/ingest_legal_corpus.py.
    """
    chunks: list[LegalChunk] = []
    try:
        for doc_id in OFFICIAL_SOURCES:
            chunks_path = corpus_dir / doc_id / "chunks.json"
            if not chunks_path.exists():
                return None
            raw = json.loads(chunks_path.read_text(encoding="utf-8"))
            for item in raw:
                content = item["content"]
                stored_hash = item["content_hash"]
                computed_hash = compute_content_hash(content)
                if stored_hash != computed_hash:
                    logger.warning(
                        "Official corpus hash mismatch for %s/%s: stored=%s computed=%s",
                        item.get("document_id", doc_id),
                        item.get("provision", "unknown"),
                        stored_hash,
                        computed_hash,
                    )
                    return None

                chunks.append(
                    LegalChunk(
                        document_id=item["document_id"],
                        title=item["title"],
                        document_number=item["document_number"],
                        provision=item["provision"],
                        source_url=item["source_url"],
                        effective_from=datetime.strptime(item["effective_from"], "%Y-%m-%d").date(),
                        effective_to=(
                            datetime.strptime(item["effective_to"], "%Y-%m-%d").date()
                            if item.get("effective_to")
                            else None
                        ),
                        superseded=item.get("superseded", False),
                        jurisdiction=item.get("jurisdiction", "VN"),
                        content_hash=stored_hash,
                        content=content,
                    )
                )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Could not load official corpus from %s: %s", corpus_dir, exc)
        return None
    return chunks if chunks else None


def ingest_minimal_corpus(corpus_dir: Path) -> tuple[list[LegalChunk], dict[str, Any]]:
    """Load or create the minimum required legal corpus.

    Priority:
    1. Load official corpus from scripts/infra/ingest_legal_corpus.py output if present.
    2. Fall back to synthetic test fixtures (labelled SYNTHETIC_TEST_ONLY).

    Returns (chunks, manifest).
    """
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Try loading officially ingested corpus first
    official = load_official_corpus(corpus_dir)
    if official:
        manifest_path = corpus_dir / "corpus_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = build_corpus_manifest(official)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        return official, manifest

    # Fallback: synthetic fixtures
    all_chunks: list[LegalChunk] = []
    all_chunks.extend(ingest_law_35_2024_qh15())
    all_chunks.extend(ingest_law_36_2024_qh15())

    manifest = build_corpus_manifest(all_chunks)
    manifest_path = corpus_dir / "corpus_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    return all_chunks, manifest


if __name__ == "__main__":
    # Default corpus directory
    corpus_dir = Path(__file__).resolve().parents[3] / "data" / "derived" / "private" / "phase3_knowledge" / "corpus"
    chunks, manifest = ingest_minimal_corpus(corpus_dir)
    print(f"Ingested {len(chunks)} chunks")
    print(f"Manifest written to {corpus_dir / 'corpus_manifest.json'}")
