"""TimescaleDB read-only executor for SimulationQuery.

Executes parameterized queries built by SQLQueryBuilder against
the simulation_results hypertable.

Security constraints enforced at this layer:
- Read-only database role (stwi_reader_user)
- Statement timeout inherited from role default (10 s)
- Row limit from query.limit
- Tenant/job ownership filter always present (built by SQLQueryBuilder)

This module is ONLY imported in integration tests and production code.
Contract tests must use the DuckDB-based FakeQueryExecutor instead.

Dependencies (not in pyproject base):
    pip install psycopg[binary]>=3.1
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from stwi.contracts.knowledge import (
    FailureCode,
    SimulationQuery,
    SimulationQueryResult,
    StructuredFailure,
)
from stwi.t3_knowledge.query_builder import SQLQueryBuilder

logger = logging.getLogger(__name__)


class TimescaleQueryExecutor:
    """Executes SimulationQuery against TimescaleDB using a read-only role.

    Usage:
        executor = TimescaleQueryExecutor(dsn="postgresql://stwi_reader_user:...@localhost/stwi")
        result = executor.execute(query)
    """

    def __init__(
        self,
        dsn: str,
        builder: SQLQueryBuilder | None = None,
        row_limit_override: int | None = None,
    ) -> None:
        self._dsn = dsn
        self._builder = builder or SQLQueryBuilder()
        self._row_limit_override = row_limit_override
        self._conn: Any = None

    def _get_conn(self) -> Any:
        """Lazy-init psycopg3 connection (read-only role, autocommit)."""
        if self._conn is None or self._conn.closed:
            try:
                import psycopg
            except ImportError as exc:
                raise ImportError(
                    "psycopg is required for TimescaleQueryExecutor. "
                    "Install with: pip install 'psycopg[binary]>=3.1'"
                ) from exc
            self._conn = psycopg.connect(self._dsn, autocommit=True)
        return self._conn

    def execute(self, query: SimulationQuery) -> SimulationQueryResult:
        """Execute a SimulationQuery and return rows as SimulationQueryResult.

        Returns StructuredFailure on:
        - Query validation failure (QUERY_INVALID)
        - Statement timeout (TIMEOUT)
        - No results (MISSING_EVIDENCE)
        - Any other DB error (QUERY_INVALID with details)
        """
        # Override limit if configured (defence in depth)
        if self._row_limit_override is not None and query.limit > self._row_limit_override:
            query = query.model_copy(update={"limit": self._row_limit_override})

        # Build parameterized SQL
        try:
            sql, params = self._builder.build(query)
        except ValueError:
            trace_id = str(uuid.uuid4())
            return SimulationQueryResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.QUERY_INVALID,
                    message="Simulation query was rejected by policy.",
                    details={},
                    trace_id=trace_id,
                )
            )

        # Validate SQL safety (defence in depth)
        if not self._builder.validate_sql_safety(sql):
            trace_id = str(uuid.uuid4())
            return SimulationQueryResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.QUERY_INVALID,
                    message="SQL failed safety validation",
                    details={},
                    trace_id=trace_id,
                )
            )

        # Execute
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                col_names = [d[0] for d in cur.description]
                raw_rows = cur.fetchall()
                logger.info(
                    "SimulationQuery executed: job_id=%s rows=%d",
                    query.job_id,
                    len(raw_rows),
                )
                if not raw_rows:
                    return SimulationQueryResult(
                        structured_failure=StructuredFailure(
                            code=FailureCode.MISSING_EVIDENCE,
                            message="No simulation results found.",
                            details={"job_id": str(query.job_id)},
                        )
                    )
                rows = [dict(zip(col_names, r)) for r in raw_rows]
                return SimulationQueryResult(rows=rows)
        except Exception as exc:
            trace_id = str(uuid.uuid4())
            code = (
                FailureCode.TIMEOUT
                if "timeout" in type(exc).__name__.lower()
                else FailureCode.QUERY_INVALID
            )
            logger.error("TimescaleDB query failed trace_id=%s", trace_id)
            return SimulationQueryResult(
                structured_failure=StructuredFailure(
                    code=code,
                    message="Simulation database request failed.",
                    details={},
                    trace_id=trace_id,
                )
            )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> TimescaleQueryExecutor:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class DuckDBFakeExecutor:
    """Offline/contract-test executor using DuckDB (no TimescaleDB needed).

    Per project_contract.json: DuckDB is for offline analysis/contract tests only.
    Never use in production or online inference path.
    """

    def __init__(self, builder: SQLQueryBuilder | None = None) -> None:
        self._builder = builder or SQLQueryBuilder()
        self._db: Any = None

    def _get_db(self) -> Any:
        try:
            import duckdb
        except ImportError as exc:
            raise ImportError(
                "duckdb is required for DuckDBFakeExecutor. "
                "Install with: pip install duckdb>=0.10"
            ) from exc
        if self._db is None:
            import duckdb
            self._db = duckdb.connect(":memory:")
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS simulation_results (
                    job_id       VARCHAR,
                    tenant_id    VARCHAR,
                    node_id      VARCHAR,
                    horizon_minutes INTEGER,
                    timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    traffic_volume_5m FLOAT,
                    avg_speed_kmh     FLOAT,
                    heavy_vehicle_ratio FLOAT,
                    vc_ratio          FLOAT,
                    green_time_ratio  FLOAT,
                    model_version VARCHAR DEFAULT 'synthetic_test_only'
                )
            """)
            # Seed with synthetic test data (labelled)
            self._db.execute("""
                INSERT INTO simulation_results
                    (job_id, tenant_id, node_id, horizon_minutes,
                     traffic_volume_5m, avg_speed_kmh, vc_ratio)
                VALUES
                    ('00000000-0000-0000-0000-000000000001', 'test-tenant', 'node-A', 5,  120.0, 45.0, 0.72),
                    ('00000000-0000-0000-0000-000000000001', 'test-tenant', 'node-A', 10, 135.0, 42.0, 0.81),
                    ('00000000-0000-0000-0000-000000000001', 'test-tenant', 'node-B', 5,   90.0, 50.0, 0.55),
                    ('00000000-0000-0000-0000-000000000002', 'other-tenant','node-A', 5,  200.0, 30.0, 0.95)
            """)
        return self._db

    def execute(self, query: SimulationQuery) -> SimulationQueryResult:
        """Execute SimulationQuery using DuckDB in-memory (contract tests only)."""
        try:
            sql, params = self._builder.build(query)
        except ValueError as exc:
            return SimulationQueryResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.QUERY_INVALID,
                    message=str(exc),
                    details={},
                )
            )

        if not self._builder.validate_sql_safety(sql):
            return SimulationQueryResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.QUERY_INVALID,
                    message="SQL failed safety validation",
                    details={},
                )
            )

        # DuckDB uses ? placeholders; convert %s → ?
        duckdb_sql = sql.replace("%s", "?")
        try:
            db = self._get_db()
            rel = db.execute(duckdb_sql, list(params))
            col_names = [d[0] for d in rel.description]
            raw_rows = rel.fetchall()
            if not raw_rows:
                return SimulationQueryResult(
                    structured_failure=StructuredFailure(
                        code=FailureCode.MISSING_EVIDENCE,
                        message="No simulation results found for query.",
                        details={"job_id": str(query.job_id)},
                    )
                )
            rows = [dict(zip(col_names, r)) for r in raw_rows]
            return SimulationQueryResult(rows=rows)
        except Exception as exc:
            return SimulationQueryResult(
                structured_failure=StructuredFailure(
                    code=FailureCode.QUERY_INVALID,
                    message=f"DuckDB error: {exc}",
                    details={},
                )
            )


__all__ = ["TimescaleQueryExecutor", "DuckDBFakeExecutor"]
