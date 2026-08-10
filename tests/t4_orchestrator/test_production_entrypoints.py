from __future__ import annotations

import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from stwi.t4_orchestrator.job_dispatch import JOB_TASK_NAME

from tests.t4_orchestrator.test_production_components import VALID_ENV


class ProductionEntrypointTest(unittest.TestCase):
    def tearDown(self) -> None:
        sys.modules.pop("stwi.production", None)
        sys.modules.pop("stwi.production_worker", None)

    @staticmethod
    def _runtime() -> SimpleNamespace:
        return SimpleNamespace(
            store=MagicMock(is_provisional_store=False),
            orchestrator=MagicMock(uses_provisional_adapters=False),
            dispatcher=MagicMock(is_provisional_dispatcher=False),
            principal_resolver=MagicMock(is_provisional_resolver=False),
            ui_context_provider=MagicMock(is_provisional_provider=False),
            network_context_provider=MagicMock(is_provisional_provider=False),
            celery_app=MagicMock(),
        )

    def test_api_entrypoint_uses_shared_fail_closed_runtime(self) -> None:
        runtime = self._runtime()
        sentinel_app = object()
        with (
            patch.dict(os.environ, VALID_ENV, clear=True),
            patch(
                "stwi.production_components.build_production_runtime",
                return_value=runtime,
            ) as build_runtime,
            patch(
                "stwi.t4_orchestrator.api.create_app",
                return_value=sentinel_app,
            ) as create_app,
        ):
            module = importlib.import_module("stwi.production")

        self.assertIs(module.app, sentinel_app)
        build_runtime.assert_called_once()
        create_app.assert_called_once_with(
            store=runtime.store,
            orchestrator=runtime.orchestrator,
            settings=build_runtime.call_args.args[0].runtime,
            principal_resolver=runtime.principal_resolver,
            dispatcher=runtime.dispatcher,
            ui_context_provider=runtime.ui_context_provider,
            network_context_provider=runtime.network_context_provider,
        )

    def test_worker_entrypoint_registers_stable_task(self) -> None:
        runtime = self._runtime()
        with (
            patch.dict(os.environ, VALID_ENV, clear=True),
            patch(
                "stwi.production_components.build_production_runtime",
                return_value=runtime,
            ),
            patch(
                "stwi.t4_orchestrator.job_dispatch.register_celery_job_task"
            ) as register,
        ):
            module = importlib.import_module("stwi.production_worker")

        self.assertIs(module.app, runtime.celery_app)
        register.assert_called_once()
        self.assertEqual(module.JOB_TASK_NAME, JOB_TASK_NAME)
        self.assertIs(register.call_args.args[0], runtime.celery_app)
        self.assertIs(register.call_args.kwargs["store_factory"](), runtime.store)
        self.assertIs(
            register.call_args.kwargs["orchestrator_factory"](),
            runtime.orchestrator,
        )


if __name__ == "__main__":
    unittest.main()
