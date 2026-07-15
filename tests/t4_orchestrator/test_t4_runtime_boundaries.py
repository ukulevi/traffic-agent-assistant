"""Runtime boundary tests for Tier 4 refactor safety."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stwi.config.runtime import RuntimeMode, get_runtime_settings
from stwi.t3_knowledge.corpus_ingestion import ingest_minimal_corpus
from stwi.t3_knowledge.tier3_facade import T3KnowledgeTier
from stwi.t4_orchestrator.api import create_app
from stwi.t4_orchestrator.fake_adapters import (
    FakeBaselineForecaster,
    FakeSurrogateForecaster,
)
from stwi.t4_orchestrator.job_store import InMemoryJobStore
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator
from stwi.t4_orchestrator.runtime_artifacts import (
    RuntimeArtifactError,
    RuntimeArtifactSet,
)


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

    def test_orchestrator_rejects_explicit_provisional_adapters_in_production(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "rejects provisional adapters"):
                WhatIfOrchestrator(
                    baseline=FakeBaselineForecaster(),
                    surrogate=FakeSurrogateForecaster(),
                    t3=object_with_legal_evidence(),
                    runtime_artifacts=write_runtime_artifacts(Path(directory)),
                )

    def test_api_rejects_explicit_in_memory_store_in_production(self):
        with self.assertRaisesRegex(RuntimeError, "rejects provisional"):
            create_app(store=InMemoryJobStore(), orchestrator=object())

    def test_orchestrator_rejects_t3_facade_with_provisional_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "rejects provisional adapters"):
                WhatIfOrchestrator(
                    baseline=object(),
                    surrogate=object(),
                    t3=T3KnowledgeTier(adapter=ProvisionalT3Adapter()),
                    runtime_artifacts=write_runtime_artifacts(Path(directory)),
                )

    def test_orchestrator_allows_nonprovisional_explicit_adapters_in_production(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = write_runtime_artifacts(Path(directory))
            orchestrator = WhatIfOrchestrator(
                baseline=object(),
                surrogate=object(),
                t3=object_with_legal_evidence(),
                runtime_artifacts=artifacts,
            )
            self.assertFalse(orchestrator.uses_provisional_adapters)

    def test_orchestrator_requires_validated_artifacts_in_production(self):
        with self.assertRaisesRegex(RuntimeError, "validated runtime artifacts"):
            WhatIfOrchestrator(
                baseline=object(),
                surrogate=object(),
                t3=object_with_legal_evidence(),
            )


class TestRuntimeArtifactRegistry(unittest.TestCase):
    def test_promoted_artifacts_bind_versions_thresholds_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = write_runtime_artifacts(Path(directory))

            self.assertEqual(artifacts.model_version, "baseline-v1+surrogate-v2")
            self.assertEqual(artifacts.surrogate.ood_threshold, 0.4)
            audit = artifacts.audit_dict()
            self.assertTrue(
                audit["surrogate_ensemble"]["artifact_sha256"].startswith("sha256:")
            )
            self.assertTrue(
                audit["surrogate_ensemble"]["manifest_sha256"].startswith("sha256:")
            )

    def test_checksum_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_runtime_artifacts(root)
            (root / "surrogate.bin").write_bytes(b"tampered")

            with self.assertRaisesRegex(RuntimeArtifactError, "checksum mismatch"):
                RuntimeArtifactSet.load(
                    baseline_manifest=root / "baseline.json",
                    surrogate_manifest=root / "surrogate.json",
                )

    def test_provisional_uncalibrated_and_stale_artifacts_fail_closed(self):
        cases = (
            ("promotion", {"status": "provisional", "provisional": True}, "not production-promoted"),
            ("calibration", {"status": "pending"}, "uncalibrated"),
            ("expires_at", "2020-01-01T00:00:00+00:00", "stale"),
        )
        for field, value, message in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_runtime_artifacts(root)
                manifest_path = root / "surrogate.json"
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                if field == "calibration":
                    payload[field].update(value)
                else:
                    payload[field] = value
                manifest_path.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(RuntimeArtifactError, message):
                    RuntimeArtifactSet.load(
                        baseline_manifest=root / "baseline.json",
                        surrogate_manifest=manifest_path,
                    )


class TestNonProductionComposition(unittest.TestCase):
    def test_test_mode_auto_wires_provisional_adapters(self):
        settings = get_runtime_settings({"STWI_RUNTIME_MODE": "test"})
        orchestrator = WhatIfOrchestrator(settings=settings)

        self.assertTrue(orchestrator.uses_provisional_adapters)


class TestCorpusManifestEncoding(unittest.TestCase):
    def test_manifest_is_written_as_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "corpus_manifest.json"
            ingest_minimal_corpus(Path(directory))

            self.assertIn("Điều", manifest_path.read_text(encoding="utf-8"))


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


class ProvisionalT3Adapter:
    """Marker-only adapter for production composition tests."""

    is_provisional_adapter = True


def write_runtime_artifacts(root: Path) -> RuntimeArtifactSet:
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    definitions = (
        ("baseline", "baseline_forecaster", "baseline-v1", "baseline-data-v1", 0.8, 0.6),
        ("surrogate", "surrogate_ensemble", "surrogate-v2", "sumo-data-v2", 0.6, 0.4),
    )
    for name, role, model_version, data_version, uncertainty, ood in definitions:
        artifact_path = root / f"{name}.bin"
        artifact_path.write_bytes(f"{name}-weights".encode())
        digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        payload = {
            "artifact_role": role,
            "artifact_name": f"{name}-official",
            "artifact_path": artifact_path.name,
            "artifact_sha256": "sha256:" + digest,
            "model_version": model_version,
            "data_version": data_version,
            "expires_at": expires_at,
            "calibration": {
                "status": "calibrated",
                "uncertainty_threshold": uncertainty,
                "ood_threshold": ood,
            },
            "promotion": {"status": "promoted", "provisional": False},
        }
        (root / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    return RuntimeArtifactSet.load(
        baseline_manifest=root / "baseline.json",
        surrogate_manifest=root / "surrogate.json",
    )


if __name__ == "__main__":
    unittest.main()
