"""Parameterized SQL builder for SimulationQuery.

This module constructs SQL from typed SimulationQuery specifications ONLY.
No raw SQL from LLM/user input is ever accepted.
"""

from __future__ import annotations

from typing import Any

from stwi.contracts.knowledge import Aggregation, Metric, OrderBy, SimulationQuery


class SQLQueryBuilder:
    """Builds parameterized SQL queries from SimulationQuery specifications.

    Security constraints enforced:
    - Only SELECT statements
    - Parameter binding for all values
    - Allowlist for metrics, aggregations, order-by fields
    - Row limit enforced
    - Tenant isolation via job_id filter
    - No semicolor, DDL/DML, comments, or raw identifiers
    """

    ALLOWED_METRICS = {
        Metric.TRAFFIC_VOLUME_5M,
        Metric.AVG_SPEED_KMH,
        Metric.HEAVY_VEHICLE_RATIO,
        Metric.VC_RATIO,
        Metric.GREEN_TIME_RATIO,
    }
    ALLOWED_AGGREGATIONS = {Aggregation.AVG, Aggregation.SUM, Aggregation.MAX, Aggregation.MIN}
    ALLOWED_ORDER_BY = {OrderBy.HORIZON_MINUTES, OrderBy.NODE_ID, OrderBy.TIMESTAMP}

    def __init__(self, default_tenant: str = "default") -> None:
        self.default_tenant = default_tenant

    def build(self, query: SimulationQuery) -> tuple[str, tuple[Any, ...]]:
        """Build parameterized SQL from SimulationQuery.

        Returns:
            Tuple of (sql_string, parameters) for parameterized execution.

        Raises:
            ValueError: If query contains disallowed values.
        """
        # Validate metrics
        for metric in query.metrics:
            if metric not in self.ALLOWED_METRICS:
                raise ValueError(f"Metric not in allowlist: {metric}")

        # Validate aggregation
        if query.aggregation and query.aggregation not in self.ALLOWED_AGGREGATIONS:
            raise ValueError(f"Aggregation not in allowlist: {query.aggregation}")

        # Validate order_by
        if query.order_by and query.order_by not in self.ALLOWED_ORDER_BY:
            raise ValueError(f"OrderBy not in allowlist: {query.order_by}")

        # Build query
        # Always include identification columns so callers can interpret rows
        # without depending on metric names alone.
        identifier_cols = ["node_id", "horizon_minutes"]
        if query.aggregation:
            agg_fn = query.aggregation.value.upper()
            metric_cols = [
                f"{agg_fn}({m.value}) AS {query.aggregation.value}_{m.value}"
                for m in query.metrics
            ]
            select_clause = ", ".join(identifier_cols + metric_cols)
        else:
            metric_cols = [m.value for m in query.metrics]
            select_clause = ", ".join(identifier_cols + metric_cols)

        params: list[Any] = []
        where_clauses = ["job_id = %s"]
        params.append(str(query.job_id))

        if query.horizons_minutes:
            placeholders = ", ".join(["%s"] * len(query.horizons_minutes))
            where_clauses.append(f"horizon_minutes IN ({placeholders})")
            params.extend(query.horizons_minutes)

        if query.node_ids:
            placeholders = ", ".join(["%s"] * len(query.node_ids))
            where_clauses.append(f"node_id IN ({placeholders})")
            params.extend(query.node_ids)

        if query.tenant_id:
            where_clauses.append("tenant_id = %s")
            params.append(query.tenant_id)
        else:
            where_clauses.append("tenant_id = %s")
            params.append(self.default_tenant)

        where_clause = " AND ".join(where_clauses)

        sql = f"SELECT {select_clause} FROM simulation_results WHERE {where_clause}"

        if query.order_by:
            sql += f" ORDER BY {query.order_by.value}"

        sql += f" LIMIT %s"
        params.append(query.limit)

        return sql, tuple(params)

    def validate_sql_safety(self, sql: str) -> bool:
        """Validate that SQL string is safe (for defense in depth).

        Checks for:
        - Only SELECT
        - No semicolon
        - No DDL/DML keywords
        - No comments
        """
        upper = sql.upper()

        if not upper.startswith("SELECT"):
            return False

        dangerous_keywords = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "TRUNCATE",
            "UNION",
            "EXEC",
            "EXECUTE",
        ]
        for kw in dangerous_keywords:
            if kw in upper:
                return False

        if ";" in sql:
            return False

        if "--" in sql or "/*" in sql:
            return False

        return True


__all__ = ["SQLQueryBuilder"]
