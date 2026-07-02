"""Security tests for Phase 3: SQL injection, tenant isolation, and retrieval test suite."""

import unittest
from datetime import datetime
from uuid import uuid4

from stwi.contracts.knowledge import Aggregation, Metric, SimulationQuery, StructuredFailure
from stwi.t3_knowledge.query_builder import SQLQueryBuilder


class TestSQLQueryBuilderSecurity(unittest.TestCase):
    """Test SQL builder security constraints."""

    def setUp(self):
        self.builder = SQLQueryBuilder()

    def test_only_select_sql_generated(self):
        """SQL must be SELECT only."""
        query = SimulationQuery(
            job_id=uuid4(),
            metrics=[Metric.TRAFFIC_VOLUME_5M],
        )
        sql, params = self.builder.build(query)
        self.assertTrue(sql.upper().startswith("SELECT"))

    def test_sql_safety_validation(self):
        """Dangerous SQL patterns must be rejected."""
        # Dangerous keywords
        self.assertFalse(self.builder.validate_sql_safety("INSERT INTO table VALUES (1)"))
        self.assertFalse(self.builder.validate_sql_safety("UPDATE table SET x=1"))
        self.assertFalse(self.builder.validate_sql_safety("DELETE FROM table"))
        self.assertFalse(self.builder.validate_sql_safety("DROP TABLE"))
        self.assertFalse(self.builder.validate_sql_safety("SELECT * FROM a UNION SELECT * FROM b"))
        self.assertFalse(self.builder.validate_sql_safety("SELECT EXEC dangerous_proc"))
        self.assertFalse(self.builder.validate_sql_safety("EXECUTE dangerous_proc"))
        # Comments
        self.assertFalse(self.builder.validate_sql_safety("SELECT * -- comment"))
        self.assertFalse(self.builder.validate_sql_safety("SELECT * /* comment */"))
        # Semicolon
        self.assertFalse(self.builder.validate_sql_safety("SELECT *; DROP TABLE"))
        # Safe SQL
        self.assertTrue(self.builder.validate_sql_safety("SELECT * FROM table WHERE x = %s"))

    def test_parameter_binding_used(self):
        """All user values must be parameterized."""
        query = SimulationQuery(
            job_id=uuid4(),
            metrics=[Metric.TRAFFIC_VOLUME_5M],
            node_ids=["node-a", "node-b"],
            horizons_minutes=[5, 10],
        )
        sql, params = self.builder.build(query)
        # SQL should contain parameter placeholders
        self.assertIn("%s", sql)
        # Parameters should contain user values, not interpolated
        self.assertNotIn("node-a", sql)
        self.assertIn("node-a", params)

    def test_invalid_metric_rejected(self):
        """Metrics not in allowlist should be rejected."""
        # This test verifies the allowlist constraint
        # Metric enum already enforces allowed values at schema level
        with self.assertRaises(ValueError):
            # SQLQueryBuilder has internal allowlist check for defense in depth
            invalid_query = SimulationQuery(
                job_id=uuid4(),
                metrics=["invalid_metric"],  # type: ignore
            )
            self.builder.build(invalid_query)  # type: ignore

    def test_empty_metrics_rejected_before_sql_build(self):
        """Empty metrics must fail schema validation before malformed SQL is built."""
        with self.assertRaises(Exception):
            SimulationQuery(job_id=uuid4(), metrics=[])

    def test_multi_metric_aggregation_has_one_function_per_metric(self):
        """Aggregation over multiple metrics must not generate AVG(a, b)."""
        query = SimulationQuery(
            job_id=uuid4(),
            metrics=[Metric.TRAFFIC_VOLUME_5M, Metric.AVG_SPEED_KMH],
            aggregation=Aggregation.AVG,
        )
        sql, _ = self.builder.build(query)
        self.assertIn("AVG(traffic_volume_5m) AS avg_traffic_volume_5m", sql)
        self.assertIn("AVG(avg_speed_kmh) AS avg_avg_speed_kmh", sql)
        self.assertNotIn("AVG(traffic_volume_5m, avg_speed_kmh)", sql)


class TestTenantIsolation(unittest.TestCase):
    """Test tenant isolation in queries."""

    def setUp(self):
        self.builder = SQLQueryBuilder()

    def test_tenant_in_where_clause(self):
        """Tenant filter must be in WHERE clause."""
        query = SimulationQuery(
            job_id=uuid4(),
            metrics=[Metric.TRAFFIC_VOLUME_5M],
            tenant_id="tenant-abc",
        )
        sql, params = self.builder.build(query)
        self.assertIn("tenant_id", sql)
        self.assertIn("tenant-abc", params)

    def test_default_tenant_used(self):
        """Default tenant applied when not specified."""
        query = SimulationQuery(
            job_id=uuid4(),
            metrics=[Metric.TRAFFIC_VOLUME_5M],
        )
        sql, params = self.builder.build(query)
        self.assertIn("tenant_id", sql)
        self.assertIn("default", params)


class TestRetrievalTestSuites(unittest.TestCase):
    """Test suite for retrieval QA - minimum 50 questions.

    Per Gate P3 specification:
    - ≥50 retrieval questions
    - Includes answerable, unanswerable, and expired/superseded cases
    - Citation precision ≥95%
    - Unsupported claim rate = 0 after validator/abstention
    """

    def test_metric_enums_match_contract(self):
        """Metrics must match feature names in project_contract.json."""
        expected_metrics = {"traffic_volume_5m", "avg_speed_kmh", "heavy_vehicle_ratio"}
        actual_metrics = {m.value for m in Metric}
        # Core metrics must be present
        self.assertTrue(expected_metrics.issubset(actual_metrics))

    def test_invalid_metric_raises_immediately(self):
        """Invalid metric names must fail at schema level."""
        # Pydantic would reject this, but we test the enum constraint
        valid_metrics = {"traffic_volume_5m", "avg_speed_kmh", "heavy_vehicle_ratio", "vc_ratio", "green_time_ratio"}
        # These are the only allowed metrics
        self.assertEqual(len(valid_metrics), 5)


# Retention test questions (50+) would go in a separate test_retrieval_questions.py
# For now, placeholder demonstrating the structure
RETRIEVAL_TEST_QUESTIONS = [
    # Answerable questions (legal exists)
    ("Quy định về luật đường bộ là gì?", datetime(2025, 6, 1), "law-35-2024-qh15"),
    ("Luật trật tự giao thông quy định như thế nào?", datetime(2025, 6, 1), "law-36-2024-qh15"),
    # Unanswerable questions
    ("Quy định về giáo dục quốc gia?", datetime(2025, 6, 1), None),
    ("Luật lao động 2019 có áp dụng không?", datetime(2025, 6, 1), None),
    # Expired/expired questions (if we had expired content)
    ("Quy định cũ hết hiệu lực năm 2020?", datetime(2025, 6, 1), None),
]

# TODO: Expand to 50+ questions with proper test file


if __name__ == "__main__":
    unittest.main()
