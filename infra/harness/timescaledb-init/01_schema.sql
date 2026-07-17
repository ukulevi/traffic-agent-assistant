-- STWI Phase 3 — TimescaleDB schema initialisation
-- Run once on container startup via docker-entrypoint-initdb.d.
--
-- Security model:
--   stwi_admin  — DDL owner (used only for setup)
--   stwi_reader — read-only role used by T3 SQLQueryBuilder at runtime
--
-- Statement timeout and row limits are enforced in the application layer
-- (SQLQueryBuilder) and additionally by the reader role's connection defaults.

-- ============================================================
-- 1. Read-only role
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stwi_reader') THEN
    CREATE ROLE stwi_reader NOLOGIN;
  END IF;
END
$$;

GRANT stwi_reader TO stwi_reader_user;

-- Default statement timeout: 10 s for all reader connections
ALTER ROLE stwi_reader_user SET statement_timeout = '10s';

-- ============================================================
-- 2. TimescaleDB extension
-- ============================================================
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 3. simulation_results hypertable
-- ============================================================
CREATE TABLE IF NOT EXISTS simulation_results (
    id                  BIGSERIAL,
    job_id              UUID        NOT NULL,
    tenant_id           TEXT        NOT NULL,
    node_id             TEXT        NOT NULL,
    horizon_minutes     INTEGER     NOT NULL CHECK (horizon_minutes > 0),
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    traffic_volume_5m   REAL,
    avg_speed_kmh       REAL,
    heavy_vehicle_ratio REAL,
    vc_ratio            REAL,
    green_time_ratio    REAL,
    model_version       TEXT        NOT NULL DEFAULT 'unknown',
    scenario_id         TEXT,
    PRIMARY KEY (id, timestamp)
);

-- Convert to hypertable partitioned by timestamp
SELECT create_hypertable(
    'simulation_results',
    'timestamp',
    if_not_exists => TRUE
);

-- Index for T3 query patterns: job_id + tenant_id + horizon_minutes + node_id
CREATE INDEX IF NOT EXISTS idx_sim_results_job_tenant
    ON simulation_results (job_id, tenant_id, horizon_minutes);

CREATE INDEX IF NOT EXISTS idx_sim_results_node
    ON simulation_results (node_id, timestamp DESC);

-- ============================================================
-- 4. Grant read-only access to reader role
-- ============================================================
GRANT USAGE ON SCHEMA public TO stwi_reader;
GRANT SELECT ON simulation_results TO stwi_reader;

-- ============================================================
-- 5. Seed data for contract tests (labelled synthetic_test_only)
-- ============================================================
INSERT INTO simulation_results
    (job_id, tenant_id, node_id, horizon_minutes, traffic_volume_5m,
     avg_speed_kmh, vc_ratio, model_version, scenario_id)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'test-tenant', 'node-A', 5,  120.0, 45.0, 0.72, 'synthetic_test_only', 'scenario-001'),
    ('00000000-0000-0000-0000-000000000001', 'test-tenant', 'node-A', 10, 135.0, 42.0, 0.81, 'synthetic_test_only', 'scenario-001'),
    ('00000000-0000-0000-0000-000000000001', 'test-tenant', 'node-B', 5,   90.0, 50.0, 0.55, 'synthetic_test_only', 'scenario-001'),
    ('00000000-0000-0000-0000-000000000002', 'other-tenant', 'node-A', 5, 200.0, 30.0, 0.95, 'synthetic_test_only', 'scenario-002')
ON CONFLICT DO NOTHING;
