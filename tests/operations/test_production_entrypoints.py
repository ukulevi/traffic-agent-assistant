from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from stwi.production_health import main as health_main
from stwi.production_preflight import main as preflight_main

from tests.t4_orchestrator.test_production_components import VALID_ENV


PASSING_PROBES = {
    "redis": lambda _settings: None,
    "qdrant": lambda _settings: None,
    "timescaledb": lambda _settings: None,
}


class ProductionReadinessEntrypointTest(unittest.TestCase):
    def test_missing_configuration_fails_closed(self) -> None:
        output = io.StringIO()
        code = health_main(["readiness"], environ={}, stdout=output)

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(
            payload["checks"][0]["code"],
            "PRODUCTION_MODE_REQUIRED",
        )

    @patch("stwi.production_health.validate_static_configuration")
    def test_dependency_failure_is_redacted(self, validate_static) -> None:
        secret = "redis://default:do-not-print@redis:6379/0"
        validate_static.return_value = object()
        probes = {
            **PASSING_PROBES,
            "redis": lambda _settings: (_ for _ in ()).throw(RuntimeError(secret)),
        }
        output = io.StringIO()

        code = health_main(
            ["readiness"],
            environ=VALID_ENV,
            probes=probes,
            stdout=output,
        )

        rendered = output.getvalue()
        payload = json.loads(rendered)
        self.assertEqual(code, 1)
        self.assertNotIn(secret, rendered)
        self.assertEqual(payload["checks"][1]["code"], "REDIS_UNAVAILABLE")

    @patch("stwi.production_health.validate_static_configuration")
    def test_all_checks_pass_with_injected_dependencies(self, validate_static) -> None:
        validate_static.return_value = object()
        output = io.StringIO()

        code = health_main(
            ["readiness"],
            environ=VALID_ENV,
            probes=PASSING_PROBES,
            stdout=output,
        )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "pass")
        self.assertTrue(all(item["status"] == "pass" for item in payload["checks"]))

    @patch("stwi.production_health.validate_static_configuration")
    def test_preflight_uses_same_readiness_contract(self, validate_static) -> None:
        validate_static.return_value = object()
        output = io.StringIO()

        code = preflight_main(
            [],
            environ=VALID_ENV,
            probes=PASSING_PROBES,
            stdout=output,
        )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["command"], "preflight")


if __name__ == "__main__":
    unittest.main()
