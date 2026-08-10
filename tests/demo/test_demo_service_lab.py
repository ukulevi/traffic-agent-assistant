from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stwi.demo.evidence import CapabilityStatus
from stwi.demo.service_lab import (
    ServiceUnavailable,
    evaluate_service_probes,
    run_service_profile,
)


class DemoServiceLabTest(unittest.TestCase):
    def test_unavailable_probe_is_not_verified(self) -> None:
        capabilities = evaluate_service_probes(
            {"docker": lambda: (_ for _ in ()).throw(ServiceUnavailable())}
        )
        self.assertEqual(capabilities[0].status, CapabilityStatus.NOT_VERIFIED)

    def test_failed_probe_is_fail_without_exception_details(self) -> None:
        capabilities = evaluate_service_probes(
            {"redis_celery": lambda: (_ for _ in ()).throw(RuntimeError("secret"))}
        )
        self.assertEqual(capabilities[0].status, CapabilityStatus.FAIL)
        self.assertNotIn("secret", capabilities[0].model_dump_json())

    def test_passing_probe_is_pass(self) -> None:
        capabilities = evaluate_service_probes({"qdrant": lambda: True})
        self.assertEqual(capabilities[0].status, CapabilityStatus.PASS)

    def test_incomplete_service_profile_is_persisted_and_nonpassing(self) -> None:
        probes = {
            "docker": lambda: True,
            "redis_celery": lambda: (_ for _ in ()).throw(ServiceUnavailable()),
            "qdrant": lambda: True,
            "timescaledb": lambda: True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            evidence = run_service_profile(
                Path(temporary) / "services.json",
                probes=probes,
            )
        self.assertEqual(evidence.verdict, "incomplete")
        self.assertTrue(evidence.live_services_contacted)


if __name__ == "__main__":
    unittest.main()
