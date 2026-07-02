"""Tests for Firecrawl candidate snapshot gating."""

from __future__ import annotations

import unittest

from stwi.t3_knowledge.firecrawl_snapshot import build_firecrawl_snapshot_manifest
from stwi.t3_knowledge.source_registry import (
    SourceRegistryError,
    SourceTier,
    canonical_https_host,
    require_trusted_source,
)


class TestSourceRegistry(unittest.TestCase):
    """Trusted source registry must fail closed."""

    def test_https_required(self):
        with self.assertRaises(SourceRegistryError):
            canonical_https_host("http://vanban.chinhphu.vn/?docid=1")

    def test_official_legal_source_resolves(self):
        source = require_trusted_source("https://vanban.chinhphu.vn/?pageid=27160&docid=211193")

        self.assertEqual(source.tier, SourceTier.OFFICIAL_LEGAL)
        self.assertTrue(source.can_seed_legal_corpus)


class TestFirecrawlSnapshotManifest(unittest.TestCase):
    """Firecrawl snapshots are candidates, never approved corpus directly."""

    def test_manifest_classifies_and_rejects_sources(self):
        long_legal_text = "Article 1. Official legal content. " * 30
        payload = {
            "id": "fc_test_search",
            "data": {
                "web": [
                    {
                        "url": "https://vanban.chinhphu.vn/?pageid=27160&docid=211193",
                        "title": "Law 35/2024/QH15",
                        "markdown": long_legal_text,
                    },
                    {
                        "url": "https://tphcm.chinhphu.vn/public-traffic-response.htm",
                        "title": "Public operations context",
                        "description": "Public HCMC traffic response context.",
                    },
                    {
                        "url": "http://vanban.chinhphu.vn/insecure",
                        "title": "Insecure official URL",
                        "description": "Should be rejected.",
                    },
                    {
                        "url": "https://example.com/untrusted",
                        "title": "Untrusted source",
                        "description": "Should be rejected.",
                    },
                ]
            },
        }

        manifest = build_firecrawl_snapshot_manifest(payload, created_at="2026-07-02T00:00:00+00:00")

        self.assertEqual(manifest["firecrawl_job_id"], "fc_test_search")
        self.assertEqual(manifest["counts"]["records_seen"], 4)
        self.assertEqual(manifest["counts"]["accepted"], 2)
        self.assertEqual(manifest["counts"]["rejected"], 2)

        official = manifest["documents"][0]
        self.assertEqual(official["source_tier"], "official_legal")
        self.assertTrue(official["ready_for_chunking"])
        self.assertTrue(official["eligible_for_promotion"])
        self.assertFalse(official["approved_for_index"])
        self.assertEqual(official["review_status"], "needs_legal_review")

        public_context = manifest["documents"][1]
        self.assertEqual(public_context["source_tier"], "public_operational")
        self.assertFalse(public_context["ready_for_chunking"])
        self.assertFalse(public_context["eligible_for_promotion"])
        self.assertEqual(public_context["review_status"], "needs_owner_review")


if __name__ == "__main__":
    unittest.main()
