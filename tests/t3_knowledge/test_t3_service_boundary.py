"""Focused fail-closed tests for production Tier-3 service boundaries."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from stwi.contracts.knowledge import Metric, RetrievalQuery, SimulationQuery
from stwi.t3_knowledge.qdrant_retriever import QdrantRetriever
from stwi.t3_knowledge.tier3_facade import RealT3Adapter, T3KnowledgeTier
from stwi.t3_knowledge.timescale_executor import TimescaleQueryExecutor


class TestProductionConfiguration(unittest.TestCase):
    def test_real_adapter_has_no_embedded_dev_credential_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "STWI_QDRANT_URL"):
                RealT3Adapter()


class _Encoder:
    def embed(self, _texts: list[str]):
        return [[0.0] * 1024]


class _QdrantClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.kwargs = None

    def search_batch(self, **kwargs: object) -> list[list[SimpleNamespace]]:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        payload = {
            "document_id": "law-35",
            "title": "Law 35",
            "document_number": "35/2024/QH15",
            "provision": "Article 1",
            "source_url": "https://example.test/law-35",
            "effective_from": "2025-01-01",
            "effective_to": None,
            "superseded": False,
            "content_hash": "sha256:" + "0" * 64,
            "content": "traffic safety evidence",
        }
        point = SimpleNamespace(id=1, payload=payload)
        return [[point], [point]]


class TestQdrantBoundary(unittest.TestCase):
    def _retriever(self, client: _QdrantClient) -> QdrantRetriever:
        retriever = QdrantRetriever(url="http://qdrant.test")
        retriever._client = client
        retriever._encoder = _Encoder()
        return retriever

    def test_hybrid_query_uses_pinned_client_rrf_api_and_effective_filter(self) -> None:
        from qdrant_client.models import NamedSparseVector, NamedVector

        client = _QdrantClient()
        result = self._retriever(client).retrieve(
            RetrievalQuery(
                query_text="traffic safety",
                scenario_time=datetime(2025, 6, 1),
            )
        )

        self.assertIsNone(result.structured_failure)
        self.assertEqual(len(result.citations), 1)
        requests = client.kwargs["requests"]
        self.assertEqual(len(requests), 2)
        self.assertIsInstance(requests[0].vector, NamedVector)
        self.assertIsInstance(requests[1].vector, NamedSparseVector)

    def test_qdrant_failure_redacts_service_text(self) -> None:
        result = self._retriever(
            _QdrantClient(error=RuntimeError("api-key=secret qdrant-host"))
        ).retrieve(
            RetrievalQuery(
                query_text="traffic safety",
                scenario_time=datetime(2025, 6, 1),
            )
        )

        failure = result.structured_failure
        self.assertIsNotNone(failure)
        self.assertIsNotNone(failure.trace_id)
        self.assertNotIn("secret", failure.message)
        self.assertNotIn("qdrant-host", failure.message)

    def test_pinned_client_local_engine_executes_hybrid_query(self) -> None:
        import numpy as np
        from qdrant_client import QdrantClient
        from stwi.t3_knowledge.corpus_ingestion import ingest_law_35_2024_qh15

        # qdrant-client 1.9 local mode references the NumPy 1.x alias. The
        # network client used in production does not, but the shim keeps this
        # service-free compatibility test useful under the repo's NumPy 2.x.
        had_ninf = hasattr(np, "NINF")
        if not had_ninf:
            np.NINF = -np.inf
        with tempfile.TemporaryDirectory() as directory:
            client = QdrantClient(path=directory)
            try:
                retriever = QdrantRetriever(
                    url="http://unused.local",
                    collection="stwi_legal_boundary_test",
                )
                retriever._client = client
                retriever._encoder = _Encoder()
                retriever.ensure_collection()
                retriever.index_chunk(ingest_law_35_2024_qh15()[0])

                result = retriever.retrieve(
                    RetrievalQuery(
                        query_text="traffic safety",
                        scenario_time=datetime(2025, 6, 1),
                    )
                )

                self.assertIsNone(result.structured_failure)
                self.assertEqual(len(result.citations), 1)
            finally:
                client.close()
                if not had_ninf:
                    del np.NINF


class _FailingConnection:
    closed = False

    def cursor(self):
        class Cursor:
            def __enter__(self):
                raise RuntimeError("postgresql://user:password@host SELECT secret")

            def __exit__(self, *_args: object) -> None:
                return None

        return Cursor()


class TestTimescaleBoundary(unittest.TestCase):
    def test_database_failure_redacts_dsn_and_sql(self) -> None:
        executor = TimescaleQueryExecutor("postgresql://user:password@host/db")
        executor._conn = _FailingConnection()
        result = executor.execute(
            SimulationQuery(
                job_id=UUID("00000000-0000-0000-0000-000000000001"),
                tenant_id="tenant-a",
                metrics=[Metric.TRAFFIC_VOLUME_5M],
            )
        )

        failure = result.structured_failure
        self.assertIsNotNone(failure)
        self.assertIsNotNone(failure.trace_id)
        serialized = failure.model_dump_json()
        self.assertNotIn("password", serialized)
        self.assertNotIn("SELECT", serialized)


class TestFacadeBoundary(unittest.TestCase):
    def test_internal_failure_is_stable_and_redacted(self) -> None:
        class ExplodingAdapter:
            def get_legal_evidence(self, *_args: object, **_kwargs: object):
                raise RuntimeError("dsn=secret internal stack")

        failure = T3KnowledgeTier(adapter=ExplodingAdapter()).query_legal_evidence(
            "traffic safety", datetime(2025, 6, 1)
        )

        self.assertIsNotNone(failure.trace_id)
        self.assertEqual(failure.message, "Legal evidence service is unavailable.")
        self.assertNotIn("secret", failure.model_dump_json())


if __name__ == "__main__":
    unittest.main()
