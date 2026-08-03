DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stwi_reader') THEN
    CREATE ROLE stwi_reader NOLOGIN;
  END IF;
END
$$;

GRANT stwi_reader TO stwi_reader_user;
ALTER ROLE stwi_reader_user SET statement_timeout = '10s';

CREATE EXTENSION IF NOT EXISTS timescaledb;

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
    model_version       TEXT        NOT NULL,
    scenario_id         TEXT,
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable(
    'simulation_results',
    'timestamp',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_sim_results_job_tenant
    ON simulation_results (job_id, tenant_id, horizon_minutes);
CREATE INDEX IF NOT EXISTS idx_sim_results_node
    ON simulation_results (node_id, timestamp DESC);

GRANT USAGE ON SCHEMA public TO stwi_reader;
GRANT SELECT ON simulation_results TO stwi_reader;
