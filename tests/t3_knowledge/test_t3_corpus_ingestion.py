"""Tests for Phase 3 legal corpus ingestion integrity."""

from __future__ import annotations

import json
import tempfile
import unittest
import unicodedata
from datetime import datetime
from pathlib import Path

from scripts.infra.ingest_legal_corpus import parse_articles
from stwi.t3_knowledge.corpus_ingestion import (
    OFFICIAL_SOURCES,
    compute_content_hash,
    load_official_corpus,
)


class TestOfficialCorpusLoading(unittest.TestCase):
    """Official corpus snapshots must be integrity-checked on load."""

    def _write_minimal_official_corpus(self, root: Path, content: str, content_hash: str) -> None:
        for doc_id, meta in OFFICIAL_SOURCES.items():
            doc_dir = root / doc_id
            doc_dir.mkdir(parents=True, exist_ok=True)
            payload = [
                {
                    "document_id": doc_id,
                    "title": meta["title"],
                    "document_number": meta["number"],
                    "provision": "Điều 1",
                    "source_url": meta["url"],
                    "effective_from": meta["effective_from"],
                    "effective_to": None,
                    "superseded": False,
                    "jurisdiction": "VN",
                    "content_hash": content_hash,
                    "content": content,
                }
            ]
            (doc_dir / "chunks.json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

    def test_load_official_corpus_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_official_corpus(
                root,
                content="Điều 1. Nội dung đã bị sửa.",
                content_hash="sha256:" + "0" * 64,
            )

            self.assertIsNone(load_official_corpus(root))

    def test_load_official_corpus_accepts_matching_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "Điều 1. Nội dung hợp lệ."
            self._write_minimal_official_corpus(
                root,
                content=content,
                content_hash=compute_content_hash(content),
            )

            chunks = load_official_corpus(root)

            self.assertIsNotNone(chunks)
            self.assertEqual(len(chunks), len(OFFICIAL_SOURCES))


class TestPdfArticleParsing(unittest.TestCase):
    """PDF text parser should handle Unicode normalization."""

    def test_parse_articles_handles_nfd_dieu_marker(self):
        meta = {
            "title": "Luật kiểm thử",
            "number": "00/2025/QH00",
            "effective_from": "2025-01-01",
            "source_page_url": "https://vanban.chinhphu.vn/test",
        }
        text = unicodedata.normalize(
            "NFD",
            "Lời mở đầu\nĐiều 1. Nội dung điều một đủ dài để được giữ lại.\n"
            "Điều 2. Nội dung điều hai cũng đủ dài để được giữ lại.",
        )

        chunks = parse_articles(text, "law-test", meta)

        self.assertEqual([c.provision for c in chunks], ["Điều 1", "Điều 2"])
        self.assertEqual(chunks[0].effective_from, datetime(2025, 1, 1).date())


if __name__ == "__main__":
    unittest.main()
