from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from stwi.production_migrate import main


class FakeCursor:
    def __init__(self, table_exists: bool = True) -> None:
        self.statements: list[str] = []
        self.table_exists = table_exists

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def fetchone(self) -> tuple[str | None]:
        return ("simulation_results" if self.table_exists else None,)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


class ProductionMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = {
            "STWI_RUNTIME_MODE": "production",
            "STWI_TSDB_ADMIN_DSN": "postgresql://admin:secret@timescaledb/stwi",
            "STWI_TSDB_DSN": "postgresql://reader:secret@timescaledb/stwi",
        }

    def test_apply_requires_explicit_approval(self) -> None:
        output = io.StringIO()
        calls: list[str] = []

        code = main(
            ["apply"],
            environ=self.environment,
            connection_factory=lambda dsn: calls.append(dsn),
            stdout=output,
        )

        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertEqual(json.loads(output.getvalue())["code"], "APPROVAL_REQUIRED")

    def test_apply_requires_distinct_admin_dsn(self) -> None:
        output = io.StringIO()
        same_dsn = self.environment["STWI_TSDB_DSN"]

        code = main(
            ["apply", "--approved"],
            environ={**self.environment, "STWI_TSDB_ADMIN_DSN": same_dsn},
            connection_factory=lambda _dsn: None,
            stdout=output,
        )

        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["code"], "ADMIN_DSN_REQUIRED")

    def test_apply_uses_admin_dsn_and_schema(self) -> None:
        output = io.StringIO()
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as temporary:
            schema = Path(temporary) / "01_schema.sql"
            schema.write_text(
                "CREATE TABLE IF NOT EXISTS simulation_results(id BIGINT);",
                encoding="utf-8",
            )

            code = main(
                ["apply", "--approved"],
                environ=self.environment,
                connection_factory=lambda dsn: calls.append(dsn) or connection,
                schema_path=schema,
                stdout=output,
            )

        self.assertEqual(code, 0)
        self.assertEqual(calls, [self.environment["STWI_TSDB_ADMIN_DSN"]])
        self.assertNotIn(self.environment["STWI_TSDB_DSN"], calls)
        self.assertIn("CREATE TABLE", cursor.statements[0])
        self.assertTrue(connection.committed)
        self.assertNotIn("secret", output.getvalue())

    def test_apply_uses_schema_path_from_environment(self) -> None:
        output = io.StringIO()
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        with tempfile.TemporaryDirectory() as temporary:
            schema = Path(temporary) / "container-schema.sql"
            schema.write_text(
                "SELECT 'container-schema-marker';",
                encoding="utf-8",
            )

            code = main(
                ["apply", "--approved"],
                environ={
                    **self.environment,
                    "STWI_PRODUCTION_SCHEMA_PATH": str(schema),
                },
                connection_factory=lambda _dsn: connection,
                stdout=output,
            )

        self.assertEqual(code, 0)
        self.assertIn("container-schema-marker", cursor.statements[0])
        self.assertTrue(connection.committed)

    def test_check_reports_schema_missing_without_exposing_dsn(self) -> None:
        output = io.StringIO()
        cursor = FakeCursor(table_exists=False)
        connection = FakeConnection(cursor)

        code = main(
            ["check"],
            environ=self.environment,
            connection_factory=lambda _dsn: connection,
            stdout=output,
        )

        payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "SCHEMA_NOT_APPLIED")
        self.assertNotIn("secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
