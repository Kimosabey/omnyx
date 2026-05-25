CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS embeddings;

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS app.tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS app.equipment (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES app.tenants(id),
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS app.device_points (
  id TEXT PRIMARY KEY,
  equipment_id TEXT NOT NULL REFERENCES app.equipment(id),
  point_id TEXT NOT NULL,
  unit TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS audit.events (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS telemetry.readings (
  measured_at TIMESTAMPTZ NOT NULL,
  point_id TEXT NOT NULL,
  device_id TEXT NOT NULL,
  tenant_id TEXT,
  value_num DOUBLE PRECISION,
  quality_flag TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

SELECT create_hypertable('telemetry.readings', 'measured_at', if_not_exists => TRUE);
