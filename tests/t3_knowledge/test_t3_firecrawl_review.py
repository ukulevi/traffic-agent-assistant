"""Tests for Firecrawl owner review promotion gate."""

from __future__ import annotations

import unittest

from stwi.t3_knowledge.firecrawl_review import (
    FirecrawlReviewError,
    review_firecrawl_snapshot_manifest,
)
from stwi.t3_knowledge.firecrawl_snapshot import build_firecrawl_snapshot_manifest


def _manifest():
    long_legal_text = "Article 1. Official legal content. " * 30
    return build_firecrawl_snapshot_manifest(
        {
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
                        "description": "Public traffic context.",
                    },
                ]
            }
        },
        created_at="2026-07-02T00:00:00+00:00",
    )


class TestFirecrawlReviewGate(unittest.TestCase):
    """Owner review must be explicit and fail closed."""

    def test_promotes_only_explicit_eligible_document(self):
        manifest = _manifest()
        legal_id = manifest["documents"][0]["snapshot_id"]

        reviewed = review_firecrawl_snapshot_manifest(
            manifest,
            reviewer="legal-owner",
            approved_snapshot_ids=[legal_id],
            reviewed_at="2026-07-02T01:00:00+00:00",
        )

        legal_doc = reviewed["documents"][0]
        public_doc = reviewed["documents"][1]
        self.assertTrue(legal_doc["approved_for_index"])
        self.assertEqual(legal_doc["review_status"], "approved")
        self.assertEqual(legal_doc["reviewed_by"], "legal-owner")
        self.assertFalse(public_doc["approved_for_index"])
        self.assertEqual(public_doc["review_status"], "needs_owner_review")
        self.assertEqual(reviewed["counts"]["approved_for_index"], 1)
        self.assertFalse(reviewed["review_policy"]["qdrant_indexing_performed"])

    def test_rejects_public_source_approval(self):
        manifest = _manifest()
        public_id = manifest["documents"][1]["snapshot_id"]

        with self.assertRaises(FirecrawlReviewError):
            review_firecrawl_snapshot_manifest(
                manifest,
                reviewer="sop-owner",
                approved_snapshot_ids=[public_id],
            )

    def test_requires_reviewer_and_known_id(self):
        manifest = _manifest()
        legal_id = manifest["documents"][0]["snapshot_id"]

        with self.assertRaises(FirecrawlReviewError):
            review_firecrawl_snapshot_manifest(manifest, reviewer="", approved_snapshot_ids=[legal_id])

        with self.assertRaises(FirecrawlReviewError):
            review_firecrawl_snapshot_manifest(
                manifest,
                reviewer="legal-owner",
                approved_snapshot_ids=["missing-id"],
            )

    def test_rejection_records_reason_without_indexing(self):
        manifest = _manifest()
        public_id = manifest["documents"][1]["snapshot_id"]

        reviewed = review_firecrawl_snapshot_manifest(
            manifest,
            reviewer="sop-owner",
            rejected_snapshot_ids=[public_id],
            rejection_reason="not an owned SOP",
            reviewed_at="2026-07-02T01:00:00+00:00",
        )

        public_doc = reviewed["documents"][1]
        self.assertFalse(public_doc["approved_for_index"])
        self.assertEqual(public_doc["review_status"], "rejected")
        self.assertEqual(public_doc["review_reason"], "not an owned SOP")
        self.assertEqual(reviewed["counts"]["rejected_by_reviewer"], 1)


if __name__ == "__main__":
    unittest.main()
