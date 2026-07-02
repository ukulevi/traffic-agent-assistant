"""Legal corpus ingestion script — Phase 3.

Downloads official PDFs from datafiles.chinhphu.vn, parses by article (Điều),
computes SHA256 content hashes, and writes immutable manifests.

Usage:
    python scripts/infra/ingest_legal_corpus.py

Output:
    data/derived/private/phase3_knowledge/corpus/
        law-35-2024-qh15/  chunks.json  source.pdf
        law-36-2024-qh15/  chunks.json  source.pdf  source_tiep.pdf
        corpus_manifest.json

IMPORTANT — Legal/high-stakes data policy (from AGENTS.md):
    - Content fetched directly from official sources at ingest time.
    - LLM-recalled content is NEVER used.
    - Each chunk gets content_hash and source_url.
    - If download fails, script exits non-zero — no silent fallback to synthetic.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── optional: pypdf required only when extracting PDF text ─────────────
try:
    import pypdf
except ImportError:
    pypdf = None

# ── project imports ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from stwi.contracts.knowledge import LegalChunk  # noqa: E402

PARSER_VERSION = "2.0.0"  # bumped from synthetic 1.0.0 to signal real ingest

CORPUS_SOURCES: dict[str, dict[str, Any]] = {
    "law-35-2024-qh15": {
        "number": "35/2024/QH15",
        "title": "Luật Đường bộ",
        "effective_from": "2025-01-01",
        "source_page_url": "https://vanban.chinhphu.vn/?pageid=27160&docid=211193",
        "pdf_urls": [
            "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/35-2024-qh15.pdf",
        ],
    },
    "law-36-2024-qh15": {
        "number": "36/2024/QH15",
        "title": "Luật Trật tự, an toàn giao thông đường bộ",
        "effective_from": "2025-01-01",
        "source_page_url": "https://vanban.chinhphu.vn/?pageid=27160&docid=211194&classid=1&typegroupid=3",
        "pdf_urls": [
            "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/36-2024-qh15.pdf",
            "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/36-2024-qh15_tiep.pdf",
        ],
    },
}

# Article boundary pattern: "Điều <number>." at start of a token sequence
_DIEU_PATTERN = re.compile(r"(Điều\s+\d+[\.\s])")


def compute_hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def fetch_pdf(url: str, timeout: int = 30) -> bytes:
    """Download PDF bytes from URL."""
    print(f"  Fetching: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "STWI-Corpus-Ingest/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if not data[:4] == b"%PDF":
        raise ValueError(f"URL did not return a PDF: {url}")
    print(f"  Downloaded {len(data):,} bytes")
    return data


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract full text from PDF bytes using pypdf."""
    if pypdf is None:
        raise ImportError("pypdf is required. Install with: pip install pypdf>=4.0")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return unicodedata.normalize("NFC", "\n".join(pages))


def parse_articles(full_text: str, document_id: str, meta: dict[str, Any]) -> list[LegalChunk]:
    """Split full PDF text into per-article chunks.

    Strategy:
    1. Split on "Điều <N>." boundaries.
    2. Merge duplicate provision numbers (ToC entries, cross-refs, page-splits)
       by concatenating all body fragments in order of appearance.
    3. Keep the merged content for each article number as one chunk.
    """
    full_text = unicodedata.normalize("NFC", full_text)
    parts = _DIEU_PATTERN.split(full_text)
    # parts alternates: [pre-text, "Điều N.", body, "Điều M.", body, ...]

    # Collect all fragments per article number (ordered)
    from collections import OrderedDict
    article_fragments: dict[str, list[str]] = OrderedDict()

    i = 1  # skip pre-text (index 0)
    while i < len(parts) - 1:
        header = parts[i].strip()
        body = parts[i + 1].strip()
        i += 2

        if not header:
            continue
        num_match = re.search(r"\d+", header)
        if not num_match:
            continue
        article_num = num_match.group()

        # Clean noise: remove page-header lines (CÔNG BÁO/Số ...)
        body = re.sub(r"CÔNG BÁO/Số[^\n]*\n?", "", body).strip()
        if len(body) < 20:
            continue

        article_fragments.setdefault(article_num, []).append(body)

    # Build final chunks: merge all fragments of same article
    chunks: list[LegalChunk] = []
    for article_num, fragments in article_fragments.items():
        provision = f"Điều {article_num}"
        merged_body = "\n".join(fragments)
        content = f"{provision}. {merged_body}"
        chunks.append(
            LegalChunk(
                document_id=document_id,
                title=meta["title"],
                document_number=meta["number"],
                provision=provision,
                source_url=meta["source_page_url"],
                effective_from=datetime.strptime(meta["effective_from"], "%Y-%m-%d").date(),
                effective_to=None,
                superseded=False,
                jurisdiction="VN",
                content_hash=compute_hash(content),
                content=content,
            )
        )

    print(f"  Parsed {len(chunks)} articles (merged duplicates)")
    return chunks


def build_manifest(
    all_chunks: list[LegalChunk],
    source_meta: dict[str, dict[str, Any]],
    retrieved_at: str,
) -> dict[str, Any]:
    """Build immutable corpus manifest."""
    by_doc: dict[str, list[dict]] = {}
    for chunk in all_chunks:
        by_doc.setdefault(chunk.document_id, []).append(
            {
                "provision": chunk.provision,
                "content_hash": chunk.content_hash,
                "source_url": chunk.source_url,
                "effective_from": chunk.effective_from.isoformat(),
                "effective_to": chunk.effective_to.isoformat() if chunk.effective_to else None,
                "superseded": chunk.superseded,
                "content_length": len(chunk.content),
            }
        )

    return {
        "schema_version": "2.0",
        "parser_version": PARSER_VERSION,
        "retrieved_at": retrieved_at,
        "corpus_type": "official_ingest",
        "synthetic_test_only": False,
        "sources": {
            doc_id: {
                "number": meta["number"],
                "title": meta["title"],
                "effective_from": meta["effective_from"],
                "source_page_url": meta["source_page_url"],
                "pdf_urls": meta["pdf_urls"],
            }
            for doc_id, meta in source_meta.items()
        },
        "documents": by_doc,
        "total_chunks": len(all_chunks),
    }


def main() -> None:
    corpus_root = (
        ROOT
        / "data"
        / "derived"
        / "private"
        / "phase3_knowledge"
        / "corpus"
    )
    corpus_root.mkdir(parents=True, exist_ok=True)

    retrieved_at = datetime.now(timezone.utc).isoformat()
    all_chunks: list[LegalChunk] = []

    for doc_id, meta in CORPUS_SOURCES.items():
        print(f"\n[{doc_id}] {meta['title']}")
        doc_dir = corpus_root / doc_id
        doc_dir.mkdir(exist_ok=True)

        # Download and cache PDFs
        combined_text = ""
        for idx, pdf_url in enumerate(meta["pdf_urls"]):
            pdf_name = f"source{'_tiep' if idx > 0 else ''}.pdf"
            pdf_path = doc_dir / pdf_name

            # Use cached PDF if exists and non-empty
            if pdf_path.exists() and pdf_path.stat().st_size > 10_000:
                print(f"  Using cached: {pdf_path}")
                pdf_bytes = pdf_path.read_bytes()
            else:
                pdf_bytes = fetch_pdf(pdf_url)
                pdf_path.write_bytes(pdf_bytes)
                print(f"  Saved to: {pdf_path}")

            combined_text += "\n" + extract_text_from_pdf(pdf_bytes)

        # Parse articles
        chunks = parse_articles(combined_text, doc_id, meta)
        all_chunks.extend(chunks)

        # Save per-document chunks
        chunks_data = [
            {
                "document_id": c.document_id,
                "title": c.title,
                "document_number": c.document_number,
                "provision": c.provision,
                "source_url": c.source_url,
                "effective_from": c.effective_from.isoformat(),
                "effective_to": c.effective_to.isoformat() if c.effective_to else None,
                "superseded": c.superseded,
                "jurisdiction": c.jurisdiction,
                "content_hash": c.content_hash,
                "content": c.content,
            }
            for c in chunks
        ]
        chunks_path = doc_dir / "chunks.json"
        chunks_path.write_text(
            json.dumps(chunks_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Saved {len(chunks)} chunks to {chunks_path}")

    # Write corpus manifest
    manifest = build_manifest(all_chunks, CORPUS_SOURCES, retrieved_at)
    manifest_path = corpus_root / "corpus_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nManifest written: {manifest_path}")
    print(f"Total chunks: {manifest['total_chunks']}")
    print(f"Retrieved at: {retrieved_at}")

    # Detect duplicate content hashes across all chunks
    hashes = [c.content_hash for c in all_chunks]
    dups = [h for h in set(hashes) if hashes.count(h) > 1]
    if dups:
        print(f"WARNING: {len(dups)} duplicate content hash(es) detected.", file=sys.stderr)
    else:
        print("No duplicate content hashes.")


if __name__ == "__main__":
    main()
