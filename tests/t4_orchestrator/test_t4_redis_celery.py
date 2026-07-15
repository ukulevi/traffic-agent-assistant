"""Focused Redis persistence and Celery dispatch contract tests."""

from __future__ import annotations

import unittest
from datetime import datetime

from stwi.t4_orchestrator.contracts import JobStatus, WhatIfJobRequest
from stwi.t4_orchestrator.fake_adapters import FakeSurrogateForecaster, safe_scenario
from stwi.t4_orchestrator.job_dispatch import (
    CeleryJobDispatcher,
    JOB_TASK_NAME,
    register_celery_job_task,
)
from stwi.t4_orchestrator.job_store import InMemoryJobStore
from stwi.t4_orchestrator.orchestrator import WhatIfOrchestrator
from stwi.t4_orchestrator.redis_job_store import RedisJobStore


def request() -> WhatIfJobRequest:
    return WhatIfJobRequest(
        tenant_id="tenant-a",
        scenario_time=datetime(2025, 6, 1, 8, 0),
        candidate_action={"node_id": "node-A", "green_time_ratio": 0.7},
        node_ids=["node-A"],
        scenario_query="traffic safety",
    )


class MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    def pipeline(self, transaction: bool = True):
        return MemoryPipeline(self, transaction=transaction)

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: object, nx: bool = False, ex: int | None = None):
        del ex
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    def rpush(self, key: str, value: object):
        self.lists.setdefault(key, []).append(str(value))
        return len(self.lists[key])

    def lrange(self, key: str, start: int, end: int):
        values = self.lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def delete(self, key: str):
        return int(self.values.pop(key, None) is not None)


class MemoryPipeline:
    def __init__(self, backend: MemoryRedis, *, transaction: bool) -> None:
        self.backend = backend
        self.transaction = transaction
        self.commands: list[tuple[str, tuple, dict]] = []
        self.in_multi = transaction

    def __enter__(self):
        return self

    def __exit__(self, *_args: object):
        self.commands.clear()

    def watch(self, *_keys: str):
        self.in_multi = False

    def unwatch(self):
        self.commands.clear()

    def multi(self):
        self.in_multi = True

    def get(self, key: str):
        return self.backend.get(key)

    def set(self, *args: object, **kwargs: object):
        self.commands.append(("set", args, kwargs))
        return self

    def rpush(self, *args: object, **kwargs: object):
        self.commands.append(("rpush", args, kwargs))
        return self

    def delete(self, *args: object, **kwargs: object):
        self.commands.append(("delete", args, kwargs))
        return self

    def execute(self):
        results = []
        for name, args, kwargs in self.commands:
            results.append(getattr(self.backend, name)(*args, **kwargs))
        self.commands.clear()
        return results


class TestRedisJobStore(unittest.TestCase):
    def setUp(self) -> None:
        self.redis = MemoryRedis()
        self.store = RedisJobStore(self.redis, prefix="test")

    def test_job_and_events_survive_api_store_recreation(self) -> None:
        envelope = self.store.create(request())
        self.store.update_status(envelope.job_id, JobStatus.RUNNING)

        restarted_store = RedisJobStore(self.redis, prefix="test")
        persisted = restarted_store.get(envelope.job_id)
        events = restarted_store.events_since(envelope.job_id)

        self.assertEqual(persisted.status, JobStatus.RUNNING)
        self.assertEqual([event.id for event in events], [1, 2])
        self.assertEqual([event.status for event in events], [JobStatus.QUEUED, JobStatus.RUNNING])

    def test_terminal_state_is_immutable_and_resume_is_idempotent(self) -> None:
        envelope = self.store.create(request())
        self.store.update_status(envelope.job_id, JobStatus.FAILED, "safe-code")
        self.store.update_status(envelope.job_id, JobStatus.RUNNING)

        self.assertEqual(self.store.get(envelope.job_id).status, JobStatus.FAILED)
        self.assertEqual(
            [event.id for event in self.store.events_since(envelope.job_id, 1)],
            [2],
        )
        self.assertEqual(
            [event.id for event in self.store.events_since(envelope.job_id, 2)],
            [],
        )

    def test_execution_lock_blocks_duplicate_worker(self) -> None:
        envelope = self.store.create(request())
        self.assertTrue(self.store.acquire_execution(envelope.job_id, 180))
        self.assertFalse(self.store.acquire_execution(envelope.job_id, 180))
        self.store.release_execution(envelope.job_id)
        self.assertTrue(self.store.acquire_execution(envelope.job_id, 180))


class FakeCelery:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_task(self, name: str, **kwargs: object) -> None:
        self.calls.append({"name": name, **kwargs})


class TestCeleryDispatcher(unittest.TestCase):
    def test_dispatch_uses_job_id_as_idempotent_task_id(self) -> None:
        celery = FakeCelery()
        dispatcher = CeleryJobDispatcher(celery)

        dispatcher.dispatch("job-123", request())

        self.assertEqual(len(celery.calls), 1)
        self.assertEqual(celery.calls[0]["name"], JOB_TASK_NAME)
        self.assertEqual(celery.calls[0]["task_id"], "job-123")
        self.assertEqual(celery.calls[0]["args"][0], "job-123")
        self.assertEqual(celery.calls[0]["args"][1]["tenant_id"], "tenant-a")

    def test_registered_celery_task_executes_persisted_job_once(self) -> None:
        from celery import Celery

        app = Celery("stwi-test", broker="memory://", backend="cache+memory://")
        store = InMemoryJobStore()
        envelope = store.create(request())
        orchestrator = WhatIfOrchestrator(
            surrogate=FakeSurrogateForecaster(default_scenario=safe_scenario())
        )
        task = register_celery_job_task(
            app,
            store_factory=lambda: store,
            orchestrator_factory=lambda: orchestrator,
        )

        result = task.apply(
            args=[envelope.job_id, request().model_dump(mode="json")],
            throw=True,
        )
        task.apply(
            args=[envelope.job_id, request().model_dump(mode="json")],
            throw=True,
        )

        self.assertTrue(result.successful())
        self.assertIn(store.get(envelope.job_id).status, {JobStatus.SUCCEEDED, JobStatus.NEEDS_REVIEW})
        result_events = [
            event
            for event in store.events_since(envelope.job_id)
            if event.event == "result"
        ]
        self.assertEqual(len(result_events), 1)


if __name__ == "__main__":
    unittest.main()
