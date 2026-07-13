"""Runtime boundary tests for Tier 4 refactor safety."""

from __future__ import annotations

import ast
import importlib.util
import os
import unittest
from pathlib import Path

from stwi.config.runtime import RuntimeMode, get_runtime_settings
from stwi.t4_orchestrator.api import create_app
from stwi.t4_orchestrator.fake_adapters import (
    FakeBaselineForecaster,
    FakeSurrogateForecaster,
)
from stwi.t4_orchestrator.job_store import InMemoryJobStore
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator


ROOT = Path(__file__).resolve().parents[1]


class TestRuntimeSettings(unittest.TestCase):
    def test_runtime_mode_aliases(self):
        self.assertEqual(
            get_runtime_settings({"STWI_RUNTIME_MODE": "prod"}).mode,
            RuntimeMode.PRODUCTION,
        )
        self.assertEqual(
            get_runtime_settings({"STWI_RUNTIME_MODE": "ci"}).mode,
            RuntimeMode.TEST,
        )

    def test_runtime_mode_rejects_unknown_values(self):
        with self.assertRaises(ValueError):
            get_runtime_settings({"STWI_RUNTIME_MODE": "unsafe"})

    def test_auto_job_concurrency_is_cpu_bounded(self):
        settings = get_runtime_settings({}, cpu_count=lambda: 16)
        self.assertEqual(settings.job_concurrency, 4)

    def test_explicit_job_concurrency_is_preserved(self):
        settings = get_runtime_settings(
            {"STWI_JOB_CONCURRENCY": "2"}, cpu_count=lambda: 16
        )
        self.assertEqual(settings.job_concurrency, 2)

    def test_job_concurrency_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            get_runtime_settings({"STWI_JOB_CONCURRENCY": "0"})


class TestProductionCompositionGuard(unittest.TestCase):
    def setUp(self):
        self._old_mode = os.environ.get("STWI_RUNTIME_MODE")
        os.environ["STWI_RUNTIME_MODE"] = "production"

    def tearDown(self):
        if self._old_mode is None:
            os.environ.pop("STWI_RUNTIME_MODE", None)
        else:
            os.environ["STWI_RUNTIME_MODE"] = self._old_mode

    def test_orchestrator_rejects_implicit_fake_defaults_in_production(self):
        with self.assertRaisesRegex(RuntimeError, "explicit baseline"):
            WhatIfOrchestrator()

    def test_api_rejects_implicit_in_memory_defaults_in_production(self):
        with self.assertRaisesRegex(RuntimeError, "explicit job store"):
            create_app()

    def test_orchestrator_allows_explicit_adapters_in_production(self):
        orchestrator = WhatIfOrchestrator(
            baseline=FakeBaselineForecaster(),
            surrogate=FakeSurrogateForecaster(),
            t3=object_with_legal_evidence(),
        )
        self.assertIsInstance(orchestrator, WhatIfOrchestrator)

    def test_api_allows_explicit_store_and_orchestrator_in_production(self):
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("fastapi is not installed in the base test environment")
        orchestrator = WhatIfOrchestrator(
            baseline=FakeBaselineForecaster(),
            surrogate=FakeSurrogateForecaster(),
            t3=object_with_legal_evidence(),
        )
        app = create_app(store=InMemoryJobStore(), orchestrator=orchestrator)
        self.assertIsNotNone(app)


class TestArchitectureDirection(unittest.TestCase):
    def test_runtime_modules_do_not_import_tests_or_scripts(self):
        src_root = ROOT / "src" / "stwi"
        offenders: list[str] = []
        for path in src_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom):
                    module = node.module
                elif isinstance(node, ast.Import):
                    module = node.names[0].name if node.names else None
                if module and (module == "tests" or module.startswith("tests.")):
                    offenders.append(f"{path.relative_to(ROOT)} imports {module}")
                if module and (module == "scripts" or module.startswith("scripts.")):
                    offenders.append(f"{path.relative_to(ROOT)} imports {module}")
        self.assertEqual(offenders, [])


class object_with_legal_evidence:
    """Tiny legal evidence provider for composition tests.

    The tests only verify production composition wiring; they do not execute a
    full workflow, so this intentionally avoids importing T3 fake adapters.
    """

    def query_legal_evidence(self, query_text, scenario_time, jurisdiction="VN"):
        raise AssertionError("composition test should not execute T3")


if __name__ == "__main__":
    unittest.main()
