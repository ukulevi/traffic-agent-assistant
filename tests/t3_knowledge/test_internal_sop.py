"""Tests for the project-owned SOP approval boundary."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stwi.t3_knowledge.internal_sop import (
    InternalSopValidationError,
    content_hash,
    validate_internal_sop_record,
)


class InternalSopValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.document = self.root / "docs" / "ops" / "sop.md"
        self.document.parent.mkdir(parents=True)
        self.document.write_text("# Draft SOP\n", encoding="utf-8")
        self.record = {
            "document_id": "demo-sop",
            "title": "Demo SOP",
            "version": "1.0",
            "owner": "pending_user_approval",
            "approval_status": "draft",
            "approval_date": None,
            "approved_for_index": False,
            "scope": "Demo only",
            "source_path": "docs/ops/sop.md",
            "content_hash": "pending_validation",
        }

    def test_draft_is_registered_but_not_indexable(self) -> None:
        report = validate_internal_sop_record(self.record, repository_root=self.root)
        self.assertEqual(report["approval_status"], "draft")
        self.assertFalse(report["eligible_for_index"])

    def test_draft_cannot_enable_indexing(self) -> None:
        self.record["approved_for_index"] = True
        with self.assertRaisesRegex(InternalSopValidationError, "must not be approved"):
            validate_internal_sop_record(self.record, repository_root=self.root)

    def test_approved_record_requires_matching_hash_and_owner(self) -> None:
        self.record.update({
            "owner": "operations-owner",
            "approval_status": "approved",
            "approval_date": "2026-07-17",
            "approved_by": "operations-owner",
            "approved_for_index": True,
            "content_hash": content_hash(self.document),
        })
        report = validate_internal_sop_record(self.record, repository_root=self.root)
        self.assertTrue(report["eligible_for_index"])


if __name__ == "__main__":
    unittest.main()
