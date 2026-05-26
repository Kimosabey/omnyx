-- =============================================================
-- OMNYX TimescaleDB — Migration 001: Telemetry Schema
-- High-volume time-series only — hypertables, compression,
-- continuous aggregates, retention policies
-- =============================================================

CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

COMMENT ON SCHEMA telemetry IS 'High-volume time-series data — hypertables only';

-- =============================================================
-- TABLES
-- =============================================================

-- Raw + DQ-annotated sensor readings (primary write target for db-writer)
CREATE TABLE telemetry.readings (
  measured_at   TIMESTAMPTZ NOT NULL,
  point_id      TEXT NOT NULL,
  device_id     TEXT NOT NULL,
  tenant_id     TEXT NOT NULL,
  value_num     DOUBLE PRECISION,
  value_str     TEXT,
  quality_flag  TEXT NOT NULL DEFAULT 'GOOD',
  quality_score NUMERIC(4,3) NOT NULL DEFAULT 1.000,
  dq_flags      TEXT[] NOT NULL DEFAULT '{}',
  payload       JSONB NOT NULL DEFAULT '{}'
);

SELECT create_hypertable(
  'telemetry.readings', 'measured_at',
  if_not_exists       => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- Digital-twin predictions / FDD residuals
CREATE TABLE telemetry.twin_predictions (
  measured_at     TIMESTAMPTZ NOT NULL,
  point_id        TEXT NOT NULL,
  tenant_id       TEXT NOT NULL,
  model_id        TEXT NOT NULL,
  predicted_value DOUBLE PRECISION,
  residual        DOUBLE PRECISION,
  z_score         DOUBLE PRECISION,
  fault_code      TEXT,
  rul_hours       DOUBLE PRECISION,
  payload         JSONB NOT NULL DEFAULT '{}'
);

SELECT create_hypertable(
  'telemetry.twin_predictions', 'measured_at',
  if_not_exists       => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- RL agent decisions (shadow + live)
CREATE TABLE telemetry.rl_decisions (
  decided_at      TIMESTAMPTZ NOT NULL,
  agent_id        TEXT NOT NULL,
  tenant_id       TEXT NOT NULL,
  state_snapshot  JSONB NOT NULL,
  action_taken    JSONB NOT NULL,
  reward_received DOUBLE PRECISION,
  episode_id      TEXT
);

SELECT create_hypertable(
  'telemetry.rl_decisions', 'decided_at',
  if_not_exists       => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- =============================================================
-- INDEXES
-- =============================================================

CREATE INDEX readings_point_time   ON telemetry.readings (point_id, measured_at DESC);
CREATE INDEX readings_tenant_time  ON telemetry.readings (tenant_id, measured_at DESC);
CREATE INDEX readings_device_time  ON telemetry.readings (device_id, measured_at DESC);
CREATE INDEX readings_bad_quality  ON telemetry.readings (measured_at DESC) WHERE quality_flag != 'GOOD';

CREATE INDEX twin_pred_point_time  ON telemetry.twin_predictions (point_id, measured_at DESC);
CREATE INDEX twin_pred_fault       ON telemetry.twin_predictions (fault_code, measured_at DESC) WHERE fault_code IS NOT NULL;

CREATE INDEX rl_dec_agent_time     ON telemetry.rl_decisions (agent_id, decided_at DESC);

-- =============================================================
-- CONTINUOUS AGGREGATES — OHLC roll-ups for dashboards
-- =============================================================

CREATE MATERIALIZED VIEW telemetry.readings_1m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', measured_at) AS bucket,
  point_id, tenant_id,
  first(value_num, measured_at) AS open,
  max(value_num)                AS high,
  min(value_num)                AS low,
  last(value_num, measured_at)  AS close,
  avg(value_num)                AS avg,
  count(*)                      AS sample_count
FROM telemetry.readings WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

CREATE MATERIALIZED VIEW telemetry.readings_5m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('5 minutes', measured_at) AS bucket,
  point_id, tenant_id,
  first(value_num, measured_at) AS open,
  max(value_num)                AS high,
  min(value_num)                AS low,
  last(value_num, measured_at)  AS close,
  avg(value_num)                AS avg,
  count(*)                      AS sample_count
FROM telemetry.readings WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

CREATE MATERIALIZED VIEW telemetry.readings_1h
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', measured_at) AS bucket,
  point_id, tenant_id,
  first(value_num, measured_at) AS open,
  max(value_num)                AS high,
  min(value_num)                AS low,
  last(value_num, measured_at)  AS close,
  avg(value_num)                AS avg,
  count(*)                      AS sample_count
FROM telemetry.readings WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

CREATE MATERIALIZED VIEW telemetry.readings_1d
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 day', measured_at) AS bucket,
  point_id, tenant_id,
  first(value_num, measured_at) AS open,
  max(value_num)                AS high,
  min(value_num)                AS low,
  last(value_num, measured_at)  AS close,
  avg(value_num)                AS avg,
  count(*)                      AS sample_count
FROM telemetry.readings WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

-- Refresh policies
SELECT add_continuous_aggregate_policy('telemetry.readings_1m',
  start_offset => INTERVAL '10 minutes',
  end_offset   => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('telemetry.readings_5m',
  start_offset => INTERVAL '1 hour',
  end_offset   => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '5 minutes', if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('telemetry.readings_1h',
  start_offset => INTERVAL '2 days',
  end_offset   => INTERVAL '1 hour',
  schedule_interval => INTERVAL '30 minutes', if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('telemetry.readings_1d',
  start_offset => INTERVAL '14 days',
  end_offset   => INTERVAL '1 day',
  schedule_interval => INTERVAL '6 hours', if_not_exists => TRUE);

-- =============================================================
-- COMPRESSION — 90%+ disk savings on chunks older than 7 days
-- =============================================================

ALTER TABLE telemetry.readings SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'point_id,tenant_id',
  timescaledb.compress_orderby   = 'measured_at DESC'
);

ALTER TABLE telemetry.twin_predictions SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'point_id,tenant_id',
  timescaledb.compress_orderby   = 'measured_at DESC'
);

ALTER TABLE telemetry.rl_decisions SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'agent_id,tenant_id',
  timescaledb.compress_orderby   = 'decided_at DESC'
);

SELECT add_compression_policy('telemetry.readings',         INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('telemetry.twin_predictions', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('telemetry.rl_decisions',     INTERVAL '7 days', if_not_exists => TRUE);

-- =============================================================
-- RETENTION — Raw 90d, _1h aggregate 1y, _1d aggregate 5y
-- =============================================================

SELECT add_retention_policy('telemetry.readings',         INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry.twin_predictions', INTERVAL '180 days', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry.rl_decisions',     INTERVAL '1 year', if_not_exists => TRUE);

-- =============================================================
-- ROLES
-- =============================================================

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'omnyx_writer') THEN CREATE ROLE omnyx_writer; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'omnyx_reader') THEN CREATE ROLE omnyx_reader; END IF;
END $$;

GRANT USAGE ON SCHEMA telemetry TO omnyx_writer, omnyx_reader;
GRANT SELECT  ON ALL TABLES IN SCHEMA telemetry TO omnyx_reader;
GRANT INSERT  ON telemetry.readings, telemetry.twin_predictions, telemetry.rl_decisions TO omnyx_writer;

ALTER ROLE omnyx_reader SET statement_timeout = '30s';
ALTER ROLE omnyx_writer SET statement_timeout = '60s';
