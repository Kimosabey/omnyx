-- =============================================================
-- OMNYX Bootstrap Migration — 001
-- PostgreSQL 16 + TimescaleDB 2.14 + pgvector 0.6
-- Run order: schemas → extensions → tables → hypertables →
--            aggregates → indexes → compression → RLS → roles
-- =============================================================

-- ---- Schemas ------------------------------------------------
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS embeddings;

-- ---- Extensions ---------------------------------------------
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
-- pgvector is available in timescaledb-ha; gracefully skip if not installed
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN undefined_file THEN
  RAISE NOTICE 'pgvector not available — AI embedding features will be disabled';
END $$;

-- =============================================================
-- APP SCHEMA — relational business tables
-- =============================================================

-- Tenants (one row per customer install in production; RLS pivots on this)
CREATE TABLE IF NOT EXISTS app.tenants (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  plan        TEXT NOT NULL DEFAULT 'standard',
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Equipment catalogue (DDCs, chillers, AHUs, etc.)
CREATE TABLE IF NOT EXISTS app.equipment (
  id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id    TEXT NOT NULL REFERENCES app.tenants(id),
  name         TEXT NOT NULL,
  type         TEXT NOT NULL,          -- 'chiller','cooling_tower','ahu','ddc'
  subtype      TEXT,
  location     TEXT,
  floor        TEXT,
  building     TEXT,
  is_active    BOOLEAN NOT NULL DEFAULT true,
  metadata     JSONB NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- BACnet / sensor points linked to equipment
CREATE TABLE IF NOT EXISTS app.device_points (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  equipment_id  TEXT NOT NULL REFERENCES app.equipment(id),
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  point_id      TEXT NOT NULL,         -- canonical ID e.g. "DDC01_AI_001"
  object_type   TEXT NOT NULL,         -- 'analogInput','binaryInput', etc.
  unit          TEXT,
  description   TEXT,
  legacy_table  TEXT,                  -- Unicharm MySQL table (backfill reference only)
  legacy_column TEXT,                  -- Unicharm MySQL column
  is_active     BOOLEAN NOT NULL DEFAULT true,
  metadata      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, point_id)
);

-- Alert rule definitions
CREATE TABLE IF NOT EXISTS app.alert_rules (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  description     TEXT,
  condition_type  TEXT NOT NULL,       -- 'threshold','offline','anomaly','semantic'
  condition_json  JSONB NOT NULL,
  severity        TEXT NOT NULL DEFAULT 'warning',
  enabled         BOOLEAN NOT NULL DEFAULT true,
  equipment_filter TEXT[],
  notify_roles    TEXT[] NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Active and historical alerts
CREATE TABLE IF NOT EXISTS app.alerts (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id    TEXT REFERENCES app.equipment(id),
  point_id        TEXT,
  rule_id         TEXT REFERENCES app.alert_rules(id),
  severity        TEXT NOT NULL DEFAULT 'warning',
  status          TEXT NOT NULL DEFAULT 'open',   -- 'open','acknowledged','resolved'
  title           TEXT NOT NULL,
  detail          TEXT,
  payload         JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  acknowledged_at TIMESTAMPTZ,
  resolved_at     TIMESTAMPTZ,
  acknowledged_by TEXT
);

-- Technician registry
CREATE TABLE IF NOT EXISTS app.technicians (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  user_id       TEXT NOT NULL,         -- Keycloak user ID
  name          TEXT NOT NULL,
  email         TEXT NOT NULL,
  is_available  BOOLEAN NOT NULL DEFAULT true,
  location      TEXT,
  metadata      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Technician skills (many-per-technician)
CREATE TABLE IF NOT EXISTS app.technician_skills (
  technician_id TEXT NOT NULL REFERENCES app.technicians(id) ON DELETE CASCADE,
  skill         TEXT NOT NULL,         -- 'hvac','electrical','plumbing','controls'
  proficiency   TEXT NOT NULL DEFAULT 'basic',  -- 'basic','intermediate','expert'
  certified_at  TIMESTAMPTZ,
  PRIMARY KEY (technician_id, skill)
);

-- Work orders
CREATE TABLE IF NOT EXISTS app.work_orders (
  id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id        TEXT NOT NULL REFERENCES app.tenants(id),
  alert_id         TEXT REFERENCES app.alerts(id),
  title            TEXT NOT NULL,
  description      TEXT,
  priority         TEXT NOT NULL DEFAULT 'medium',  -- 'low','medium','high','critical'
  status           TEXT NOT NULL DEFAULT 'open',    -- 'open','in_progress','completed','cancelled'
  assigned_to      TEXT REFERENCES app.technicians(id),
  created_by       TEXT NOT NULL,
  scheduled_at     TIMESTAMPTZ,
  completed_at     TIMESTAMPTZ,
  resolution_notes TEXT,
  estimated_hours  NUMERIC(5,2),
  actual_hours     NUMERIC(5,2),
  metadata         JSONB NOT NULL DEFAULT '{}',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- In-app and email notifications
CREATE TABLE IF NOT EXISTS app.notifications (
  id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id   TEXT NOT NULL REFERENCES app.tenants(id),
  user_id     TEXT NOT NULL,
  type        TEXT NOT NULL,          -- 'alert','work_order','agent','system'
  channel     TEXT NOT NULL DEFAULT 'in_app',
  payload     JSONB NOT NULL DEFAULT '{}',
  read_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-point DQ check configuration (Tier 1 rules live here)
CREATE TABLE IF NOT EXISTS app.data_quality_config (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  point_pattern TEXT NOT NULL,        -- glob, e.g. "DDC*_AI_*"
  check_type    TEXT NOT NULL,        -- 'range','spike','stale','frozen','unit','cross_sensor','null','format'
  params        JSONB NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  priority      INTEGER NOT NULL DEFAULT 100,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Registered digital twin models
CREATE TABLE IF NOT EXISTS app.twin_models (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id  TEXT NOT NULL REFERENCES app.equipment(id),
  model_type    TEXT NOT NULL,        -- 'chiller_v1','cooling_tower_v1'
  version       TEXT NOT NULL,
  params        JSONB NOT NULL DEFAULT '{}',
  calibrated_at TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'draft',   -- 'draft','active','retired'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Registered RL agents
CREATE TABLE IF NOT EXISTS app.rl_agents (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id    TEXT NOT NULL REFERENCES app.equipment(id),
  agent_type      TEXT NOT NULL,      -- 'chiller_efficiency_v1'
  version         TEXT NOT NULL,
  config          JSONB NOT NULL DEFAULT '{}',
  mode            TEXT NOT NULL DEFAULT 'shadow', -- 'shadow','advisory','live'
  last_trained_at TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'inactive',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RL episode log (state/action/reward triples)
CREATE TABLE IF NOT EXISTS app.rl_episodes (
  id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  agent_id   TEXT NOT NULL REFERENCES app.rl_agents(id),
  tenant_id  TEXT NOT NULL,
  state      JSONB NOT NULL,
  action     JSONB NOT NULL,
  reward     NUMERIC(10,6),
  next_state JSONB,
  ts         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent workflow definitions (YAML-authored, stored as JSON)
CREATE TABLE IF NOT EXISTS app.agent_workflows (
  id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id      TEXT NOT NULL REFERENCES app.tenants(id),
  name           TEXT NOT NULL,
  description    TEXT,
  trigger_type   TEXT NOT NULL,      -- 'alert','schedule','manual','event'
  trigger_config JSONB NOT NULL DEFAULT '{}',
  steps          JSONB NOT NULL DEFAULT '[]',
  enabled        BOOLEAN NOT NULL DEFAULT true,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent run history (one row per workflow execution)
CREATE TABLE IF NOT EXISTS app.agent_runs (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  workflow_id     TEXT REFERENCES app.agent_workflows(id),
  trigger_payload JSONB NOT NULL DEFAULT '{}',
  status          TEXT NOT NULL DEFAULT 'running',  -- 'running','completed','failed','halted'
  result          JSONB,
  cost_usd        NUMERIC(10,6),
  token_count     INTEGER,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at    TIMESTAMPTZ
);

-- Approval requests raised by the agent (Tier 2-5 actions)
CREATE TABLE IF NOT EXISTS app.approval_requests (
  id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id      TEXT NOT NULL REFERENCES app.tenants(id),
  run_id         TEXT REFERENCES app.agent_runs(id),
  action_type    TEXT NOT NULL,
  action_payload JSONB NOT NULL,
  tier           INTEGER NOT NULL,    -- 1-5
  requested_by   TEXT NOT NULL,       -- agent run ID
  approved_by    TEXT,                -- Keycloak user ID
  status         TEXT NOT NULL DEFAULT 'pending',  -- 'pending','approved','rejected','expired'
  expires_at     TIMESTAMPTZ NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ
);

-- Knowledge base document index (chunks stored in embeddings schema)
CREATE TABLE IF NOT EXISTS app.knowledge_docs (
  id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id   TEXT NOT NULL REFERENCES app.tenants(id),
  title       TEXT NOT NULL,
  source_type TEXT NOT NULL,          -- 'manual','equipment_spec','fault_history','procedure'
  content     TEXT NOT NULL,
  checksum    TEXT NOT NULL,
  metadata    JSONB NOT NULL DEFAULT '{}',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================
-- TELEMETRY SCHEMA — time-series data (TimescaleDB hypertables)
-- =============================================================

-- Raw + DQ-annotated sensor readings
CREATE TABLE IF NOT EXISTS telemetry.readings (
  measured_at   TIMESTAMPTZ NOT NULL,
  point_id      TEXT NOT NULL,
  device_id     TEXT NOT NULL,
  tenant_id     TEXT,
  value_num     DOUBLE PRECISION,
  value_str     TEXT,
  quality_flag  TEXT NOT NULL DEFAULT 'GOOD',
  quality_score NUMERIC(4,3) NOT NULL DEFAULT 1.000,
  dq_flags      TEXT[] NOT NULL DEFAULT '{}',
  payload       JSONB NOT NULL DEFAULT '{}'
);

SELECT create_hypertable(
  'telemetry.readings', 'measured_at',
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- Digital twin model predictions and FDD residuals
CREATE TABLE IF NOT EXISTS telemetry.twin_predictions (
  measured_at     TIMESTAMPTZ NOT NULL,
  point_id        TEXT NOT NULL,
  tenant_id       TEXT,
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
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- RL agent decisions (shadow and live modes)
CREATE TABLE IF NOT EXISTS telemetry.rl_decisions (
  decided_at      TIMESTAMPTZ NOT NULL,
  agent_id        TEXT NOT NULL,
  tenant_id       TEXT,
  state_snapshot  JSONB NOT NULL,
  action_taken    JSONB NOT NULL,
  reward_received DOUBLE PRECISION,
  episode_id      TEXT
);

SELECT create_hypertable(
  'telemetry.rl_decisions', 'decided_at',
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- =============================================================
-- AUDIT SCHEMA — append-only event log
-- =============================================================

CREATE TABLE IF NOT EXISTS audit.events (
  id         BIGSERIAL PRIMARY KEY,
  actor      TEXT NOT NULL,           -- user ID or 'system' or agent run ID
  action     TEXT NOT NULL,
  target     TEXT,
  payload    JSONB NOT NULL DEFAULT '{}',
  tenant_id  TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_tenant_time ON audit.events (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_actor_time  ON audit.events (actor, created_at DESC);

-- =============================================================
-- EMBEDDINGS SCHEMA — pgvector for RAG retrieval (requires pgvector)
-- =============================================================

DO $$ BEGIN
  -- Only create if pgvector is available
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    CREATE TABLE IF NOT EXISTS embeddings.knowledge_chunks (
      id          BIGSERIAL PRIMARY KEY,
      doc_id      TEXT NOT NULL REFERENCES app.knowledge_docs(id) ON DELETE CASCADE,
      tenant_id   TEXT NOT NULL,
      chunk_index INTEGER NOT NULL,
      content     TEXT NOT NULL,
      embedding   vector(1536),
      metadata    JSONB NOT NULL DEFAULT '{}',
      created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
      ON embeddings.knowledge_chunks
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
  ELSE
    -- Stub table without vector column for forward-compatibility
    CREATE TABLE IF NOT EXISTS embeddings.knowledge_chunks (
      id          BIGSERIAL PRIMARY KEY,
      doc_id      TEXT NOT NULL REFERENCES app.knowledge_docs(id) ON DELETE CASCADE,
      tenant_id   TEXT NOT NULL,
      chunk_index INTEGER NOT NULL,
      content     TEXT NOT NULL,
      metadata    JSONB NOT NULL DEFAULT '{}',
      created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    RAISE NOTICE 'Embedding table created without vector column (pgvector not installed)';
  END IF;
END $$;

-- =============================================================
-- INDEXES — query-pattern driven
-- =============================================================

-- telemetry.readings
CREATE INDEX IF NOT EXISTS readings_point_time  ON telemetry.readings (point_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS readings_tenant_time ON telemetry.readings (tenant_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS readings_device_time ON telemetry.readings (device_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS readings_quality     ON telemetry.readings (quality_flag) WHERE quality_flag != 'GOOD';

-- telemetry.twin_predictions
CREATE INDEX IF NOT EXISTS twin_pred_point_time ON telemetry.twin_predictions (point_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS twin_pred_fault      ON telemetry.twin_predictions (fault_code, measured_at DESC) WHERE fault_code IS NOT NULL;

-- app.alerts
CREATE INDEX IF NOT EXISTS alerts_tenant_status ON app.alerts (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS alerts_equipment     ON app.alerts (equipment_id, status);

-- app.work_orders
CREATE INDEX IF NOT EXISTS wo_tenant_status     ON app.work_orders (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS wo_assigned          ON app.work_orders (assigned_to, status);

-- app.notifications
CREATE INDEX IF NOT EXISTS notif_user_time      ON app.notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS notif_unread         ON app.notifications (user_id, read_at) WHERE read_at IS NULL;

-- app.agent_runs
CREATE INDEX IF NOT EXISTS agent_runs_tenant    ON app.agent_runs (tenant_id, started_at DESC);
CREATE INDEX IF NOT EXISTS agent_runs_workflow  ON app.agent_runs (workflow_id, started_at DESC);

-- app.approval_requests
CREATE INDEX IF NOT EXISTS approvals_pending    ON app.approval_requests (tenant_id, status, expires_at) WHERE status = 'pending';

-- =============================================================
-- CONTINUOUS AGGREGATES — OHLC rollups for the UI
-- =============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.readings_1m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', measured_at)  AS bucket,
  point_id,
  tenant_id,
  first(value_num, measured_at)         AS open,
  max(value_num)                        AS high,
  min(value_num)                        AS low,
  last(value_num, measured_at)          AS close,
  avg(value_num)                        AS avg,
  count(*)                              AS sample_count
FROM telemetry.readings
WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.readings_5m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('5 minutes', measured_at) AS bucket,
  point_id,
  tenant_id,
  first(value_num, measured_at)         AS open,
  max(value_num)                        AS high,
  min(value_num)                        AS low,
  last(value_num, measured_at)          AS close,
  avg(value_num)                        AS avg,
  count(*)                              AS sample_count
FROM telemetry.readings
WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.readings_1h
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', measured_at)    AS bucket,
  point_id,
  tenant_id,
  first(value_num, measured_at)         AS open,
  max(value_num)                        AS high,
  min(value_num)                        AS low,
  last(value_num, measured_at)          AS close,
  avg(value_num)                        AS avg,
  count(*)                              AS sample_count
FROM telemetry.readings
WHERE value_num IS NOT NULL
GROUP BY bucket, point_id, tenant_id
WITH NO DATA;

-- Refresh policies
SELECT add_continuous_aggregate_policy('telemetry.readings_1m',
  start_offset      => INTERVAL '10 minutes',
  end_offset        => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute',
  if_not_exists     => TRUE);

SELECT add_continuous_aggregate_policy('telemetry.readings_5m',
  start_offset      => INTERVAL '1 hour',
  end_offset        => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '5 minutes',
  if_not_exists     => TRUE);

SELECT add_continuous_aggregate_policy('telemetry.readings_1h',
  start_offset      => INTERVAL '2 days',
  end_offset        => INTERVAL '1 hour',
  schedule_interval => INTERVAL '30 minutes',
  if_not_exists     => TRUE);

-- =============================================================
-- COMPRESSION — reduce disk for raw readings after 7 days
-- =============================================================

ALTER TABLE telemetry.readings SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'point_id,tenant_id',
  timescaledb.compress_orderby   = 'measured_at DESC'
);

SELECT add_compression_policy('telemetry.readings',
  INTERVAL '7 days', if_not_exists => TRUE);

-- Retention: drop raw readings older than 90 days (aggregates survive)
SELECT add_retention_policy('telemetry.readings',
  INTERVAL '90 days', if_not_exists => TRUE);

-- =============================================================
-- ROW-LEVEL SECURITY — api-service sets app.current_tenant_id
-- per connection before any query; postgres superuser bypasses
-- =============================================================

ALTER TABLE app.equipment         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.device_points     ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.alert_rules       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.alerts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.work_orders       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.notifications     ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.twin_models       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.rl_agents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_workflows   ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.knowledge_docs    ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.equipment
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.device_points
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.alert_rules
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.alerts
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.work_orders
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.notifications
  USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY tenant_isolation ON app.twin_models
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.rl_agents
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.agent_workflows
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.agent_runs
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.approval_requests
  USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_isolation ON app.knowledge_docs
  USING (tenant_id = current_setting('app.current_tenant_id', true));

-- =============================================================
-- ROLES — least-privilege service accounts
-- =============================================================

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'omnyx_writer') THEN
    CREATE ROLE omnyx_writer;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'omnyx_reader') THEN
    CREATE ROLE omnyx_reader;
  END IF;
END $$;

GRANT USAGE ON SCHEMA app, telemetry, audit, embeddings TO omnyx_writer, omnyx_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA app, telemetry, audit, embeddings TO omnyx_reader;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO omnyx_writer;
GRANT INSERT ON telemetry.readings, telemetry.twin_predictions, telemetry.rl_decisions TO omnyx_writer;
GRANT INSERT ON audit.events TO omnyx_writer;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app, audit, embeddings TO omnyx_writer;
