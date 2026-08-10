from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from stwi.demo.evidence import (
    CapabilityEvidence,
    CapabilityStatus,
    DemoEvidence,
    write_evidence_atomic,
)


def passing_job(**updates: object) -> CapabilityEvidence:
    payload = {
        "name": "safe_approval",
        "kind": "job",
        "status": CapabilityStatus.PASS,
        "mandatory": True,
        "expected": "succeeded",
        "observed": "succeeded",
        "terminal_status": "succeeded",
        "trace_id": "trace-1",
        "model_version": "model-v1",
        "data_version": "data-v1",
        "terminal_event_count": 1,
        "recommended_action": {
            "node_id": "node_00",
            "executable": False,
            "automatic_actuation": False,
        },
    }
    payload.update(updates)
    return CapabilityEvidence.model_validate(payload)


class CapabilityEvidenceTest(unittest.TestCase):
    def test_executable_action_is_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            passing_job(
                recommended_action={
                    "node_id": "node_00",
                    "executable": True,
                    "automatic_actuation": False,
                }
            )

    def test_duplicate_terminal_events_are_forbidden(self) -> None:
        with self.assertRaises(ValidationError):
            passing_job(terminal_event_count=2)

    def test_passing_job_requires_trace_and_versions(self) -> None:
        for field in ("trace_id", "model_version", "data_version"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                passing_job(**{field: None})

    def test_needs_review_cannot_publish_recommended_action(self) -> None:
        with self.assertRaises(ValidationError):
            passing_job(
                terminal_status="needs_review",
                observed="needs_review",
                candidate_action=None,
            )


class DemoEvidenceWriterTest(unittest.TestCase):
    def test_atomic_writer_round_trips_versioned_manifest(self) -> None:
        evidence = DemoEvidence(
            profile="offline",
            verdict="pass",
            live_services_contacted=False,
            capabilities=[passing_job()],
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evidence.json"
            output.write_text("old", encoding="utf-8")
            write_evidence_atomic(output, evidence)

            loaded = DemoEvidence.model_validate_json(output.read_text(encoding="utf-8"))
            self.assertEqual(loaded, evidence)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema_version"], "1.0")
            self.assertEqual(list(Path(temporary).glob("*.tmp")), [])

    def test_duplicate_capability_names_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DemoEvidence(
                profile="offline",
                verdict="pass",
                live_services_contacted=False,
                capabilities=[passing_job(), passing_job()],
            )


if __name__ == "__main__":
    unittest.main()
