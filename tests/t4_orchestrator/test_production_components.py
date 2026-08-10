from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from stwi.production_components import (
    ProductionComponents,
    ProductionConfigurationError,
    ProductionSettings,
    build_production_runtime,
    load_component_factory,
    validate_components,
)
from stwi.t4_orchestrator.network_context import AuthorizedNetworkContextProvider


VALID_ENV = {
    "STWI_RUNTIME_MODE": "production",
    "STWI_REDIS_URL": "redis://redis:6379/0",
    "STWI_TSDB_DSN": "postgresql://reader@timescaledb/stwi",
    "STWI_QDRANT_URL": "http://qdrant:6333",
    "STWI_BASELINE_MANIFEST": "/run/stwi/baseline/manifest.json",
    "STWI_SURROGATE_MANIFEST": "/run/stwi/surrogate/manifest.json",
    "STWI_LEGAL_CORPUS_DIR": "/run/stwi/legal-corpus",
    "STWI_PRODUCTION_COMPONENT_FACTORY": (
        f"{__name__}:trusted_factory"
    ),
}


class TrustedComponent:
    pass


class ProvisionalComponent:
    is_provisional_adapter = True
    is_provisional_resolver = True
    is_provisional_provider = True


def trusted_factory(_settings: ProductionSettings) -> ProductionComponents:
    return ProductionComponents(
        baseline=TrustedComponent(),
        surrogate=TrustedComponent(),
        principal_resolver=TrustedComponent(),
        ui_context_provider=TrustedComponent(),
    )


class ProductionSettingsTest(unittest.TestCase):
    def test_valid_environment_is_typed(self) -> None:
        settings = ProductionSettings.from_environ(VALID_ENV)

        self.assertEqual(settings.redis_url, VALID_ENV["STWI_REDIS_URL"])
        self.assertEqual(
            settings.baseline_manifest,
            Path(VALID_ENV["STWI_BASELINE_MANIFEST"]),
        )

    def test_missing_component_factory_fails_closed(self) -> None:
        environ = {**VALID_ENV}
        environ.pop("STWI_PRODUCTION_COMPONENT_FACTORY")

        with self.assertRaisesRegex(
            ProductionConfigurationError,
            "COMPONENT_FACTORY_REQUIRED",
        ):
            ProductionSettings.from_environ(environ)

    def test_nonproduction_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ProductionConfigurationError,
            "PRODUCTION_MODE_REQUIRED",
        ):
            ProductionSettings.from_environ(
                {**VALID_ENV, "STWI_RUNTIME_MODE": "demo"}
            )

    def test_missing_required_connection_is_redacted(self) -> None:
        environ = {**VALID_ENV}
        environ.pop("STWI_REDIS_URL")

        with self.assertRaisesRegex(
            ProductionConfigurationError,
            "REDIS_URL_REQUIRED",
        ) as context:
            ProductionSettings.from_environ(environ)
        self.assertNotIn("postgresql://", str(context.exception))

    def test_missing_legal_corpus_fails_closed(self) -> None:
        environ = {**VALID_ENV}
        environ.pop("STWI_LEGAL_CORPUS_DIR")
        with self.assertRaisesRegex(
            ProductionConfigurationError,
            "LEGAL_CORPUS_REQUIRED",
        ):
            ProductionSettings.from_environ(environ)

    def test_factory_path_must_use_module_callable_shape(self) -> None:
        with self.assertRaisesRegex(
            ProductionConfigurationError,
            "COMPONENT_FACTORY_INVALID",
        ):
            load_component_factory("not-a-module-path")

    def test_load_component_factory_returns_callable(self) -> None:
        factory = load_component_factory(
            VALID_ENV["STWI_PRODUCTION_COMPONENT_FACTORY"]
        )
        self.assertIs(factory, trusted_factory)


class ProductionComponentValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = trusted_factory(ProductionSettings.from_environ(VALID_ENV))

    def test_trusted_components_are_accepted(self) -> None:
        self.assertIs(validate_components(self.valid), self.valid)

    def test_each_provisional_component_is_rejected(self) -> None:
        for field in (
            "baseline",
            "surrogate",
            "principal_resolver",
            "ui_context_provider",
        ):
            with self.subTest(field=field):
                components = replace(
                    self.valid,
                    **{field: ProvisionalComponent()},
                )
                with self.assertRaisesRegex(
                    ProductionConfigurationError,
                    f"PROVISIONAL_COMPONENT:{field}",
                ):
                    validate_components(components)

    def test_missing_component_is_rejected(self) -> None:
        components = replace(self.valid, baseline=None)
        with self.assertRaisesRegex(
            ProductionConfigurationError,
            "COMPONENT_REQUIRED:baseline",
        ):
            validate_components(components)


class ProductionRuntimeCompositionTest(unittest.TestCase):
    @patch("stwi.production_components.RealT3Adapter")
    @patch("stwi.production_components.RuntimeArtifactSet.load")
    @patch("stwi.production_components.RedisJobStore.from_url")
    def test_builds_real_infrastructure_without_provisional_fallback(
        self,
        store_from_url: MagicMock,
        artifact_load: MagicMock,
        real_t3: MagicMock,
    ) -> None:
        settings = ProductionSettings.from_environ(VALID_ENV)
        artifacts = MagicMock()
        artifacts.model_version = "baseline+surrogate"
        artifacts.data_version = "dataset-v1+sumo-v1"
        artifacts.surrogate.uncertainty_threshold = 0.4
        artifacts.surrogate.ood_threshold = 0.3
        artifact_load.return_value = artifacts
        store_from_url.return_value.is_provisional_store = False
        real_t3.return_value.is_provisional_adapter = False

        runtime = build_production_runtime(settings)

        store_from_url.assert_called_once_with(settings.redis_url)
        real_t3.assert_called_once_with(
            qdrant_url=settings.qdrant_url,
            tsdb_dsn=settings.tsdb_dsn,
            corpus_dir=settings.legal_corpus_dir,
        )
        self.assertFalse(runtime.dispatcher.is_provisional_dispatcher)
        self.assertFalse(runtime.store.is_provisional_store)
        self.assertFalse(runtime.orchestrator.uses_provisional_adapters)
        self.assertIs(runtime.components.principal_resolver, runtime.principal_resolver)
        self.assertIsInstance(
            runtime.network_context_provider,
            AuthorizedNetworkContextProvider,
        )
        self.assertIs(
            runtime.network_context_provider.ui_context_provider,
            runtime.ui_context_provider,
        )

    def test_factory_returning_wrong_shape_fails_closed(self) -> None:
        with patch(
            "stwi.production_components.load_component_factory",
            return_value=lambda _settings: object(),
        ):
            with self.assertRaisesRegex(
                ProductionConfigurationError,
                "COMPONENT_FACTORY_RESULT_INVALID",
            ):
                build_production_runtime(ProductionSettings.from_environ(VALID_ENV))


if __name__ == "__main__":
    unittest.main()
