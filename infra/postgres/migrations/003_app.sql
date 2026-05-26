-- =============================================================
-- OMNYX Primary DB — Migration 003: App Schema
-- OMNYX operational tables (multi-tenant via RLS)
-- =============================================================

-- Tenants (root of multi-tenancy)
CREATE TABLE app.tenants (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  plan        TEXT NOT NULL DEFAULT 'standard',
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Equipment catalogue — links to source.ddc_registry
CREATE TABLE app.equipment (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  source_ddc_id TEXT REFERENCES source.ddc_registry(ddc_id),  -- nullable for non-IBMS equipment
  name          TEXT NOT NULL,
  type          TEXT NOT NULL,        -- ddc | chiller | cooling_tower | ahu | fcu | pump
  subtype       TEXT,
  building      TEXT,
  floor         TEXT,
  location      TEXT,
  is_active     BOOLEAN NOT NULL DEFAULT true,
  metadata      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sensor points (links to source.point_catalog for IBMS-sourced points)
CREATE TABLE app.device_points (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id    TEXT NOT NULL REFERENCES app.equipment(id),
  source_gl_code  TEXT REFERENCES source.point_catalog(gl_code),  -- optional FK to IBMS catalog
  point_id        TEXT NOT NULL,         -- canonical ID used in telemetry stream
  object_type     TEXT NOT NULL,
  unit            TEXT,
  description     TEXT,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, point_id)
);

-- Alert rule definitions
CREATE TABLE app.alert_rules (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  description     TEXT,
  condition_type  TEXT NOT NULL,       -- threshold | offline | anomaly | semantic
  condition_json  JSONB NOT NULL,
  severity        TEXT NOT NULL DEFAULT 'warning',
  enabled         BOOLEAN NOT NULL DEFAULT true,
  equipment_filter TEXT[],
  notify_roles    TEXT[] NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Active and historical alerts
CREATE TABLE app.alerts (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id    TEXT REFERENCES app.equipment(id),
  point_id        TEXT,
  rule_id         TEXT REFERENCES app.alert_rules(id),
  severity        TEXT NOT NULL DEFAULT 'warning',
  status          TEXT NOT NULL DEFAULT 'open',  -- open | acknowledged | resolved
  title           TEXT NOT NULL,
  detail          TEXT,
  payload         JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  acknowledged_at TIMESTAMPTZ,
  resolved_at     TIMESTAMPTZ,
  acknowledged_by TEXT
);

-- Technicians
CREATE TABLE app.technicians (
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

CREATE TABLE app.technician_skills (
  technician_id TEXT NOT NULL REFERENCES app.technicians(id) ON DELETE CASCADE,
  skill         TEXT NOT NULL,
  proficiency   TEXT NOT NULL DEFAULT 'basic',
  certified_at  TIMESTAMPTZ,
  PRIMARY KEY (technician_id, skill)
);

-- Work orders
CREATE TABLE app.work_orders (
  id               TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id        TEXT NOT NULL REFERENCES app.tenants(id),
  alert_id         TEXT REFERENCES app.alerts(id),
  title            TEXT NOT NULL,
  description      TEXT,
  priority         TEXT NOT NULL DEFAULT 'medium',
  status           TEXT NOT NULL DEFAULT 'open',
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

-- Notifications
CREATE TABLE app.notifications (
  id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id   TEXT NOT NULL REFERENCES app.tenants(id),
  user_id     TEXT NOT NULL,
  type        TEXT NOT NULL,
  channel     TEXT NOT NULL DEFAULT 'in_app',
  payload     JSONB NOT NULL DEFAULT '{}',
  read_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Data quality rule config (Tier 1 checks)
CREATE TABLE app.data_quality_config (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  point_pattern TEXT NOT NULL,
  check_type    TEXT NOT NULL,
  params        JSONB NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  priority      INTEGER NOT NULL DEFAULT 100,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Digital twin models
CREATE TABLE app.twin_models (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id     TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id  TEXT NOT NULL REFERENCES app.equipment(id),
  model_type    TEXT NOT NULL,
  version       TEXT NOT NULL,
  params        JSONB NOT NULL DEFAULT '{}',
  calibrated_at TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'draft',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RL agents
CREATE TABLE app.rl_agents (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  equipment_id    TEXT NOT NULL REFERENCES app.equipment(id),
  agent_type      TEXT NOT NULL,
  version         TEXT NOT NULL,
  config          JSONB NOT NULL DEFAULT '{}',
  mode            TEXT NOT NULL DEFAULT 'shadow',
  last_trained_at TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'inactive',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.rl_episodes (
  id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  agent_id   TEXT NOT NULL REFERENCES app.rl_agents(id),
  tenant_id  TEXT NOT NULL,
  state      JSONB NOT NULL,
  action     JSONB NOT NULL,
  reward     NUMERIC(10,6),
  next_state JSONB,
  ts         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent workflows
CREATE TABLE app.agent_workflows (
  id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id      TEXT NOT NULL REFERENCES app.tenants(id),
  name           TEXT NOT NULL,
  description    TEXT,
  trigger_type   TEXT NOT NULL,
  trigger_config JSONB NOT NULL DEFAULT '{}',
  steps          JSONB NOT NULL DEFAULT '[]',
  enabled        BOOLEAN NOT NULL DEFAULT true,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.agent_runs (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  workflow_id     TEXT REFERENCES app.agent_workflows(id),
  trigger_payload JSONB NOT NULL DEFAULT '{}',
  status          TEXT NOT NULL DEFAULT 'running',
  result          JSONB,
  cost_usd        NUMERIC(10,6),
  token_count     INTEGER,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at    TIMESTAMPTZ
);

CREATE TABLE app.approval_requests (
  id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id      TEXT NOT NULL REFERENCES app.tenants(id),
  run_id         TEXT REFERENCES app.agent_runs(id),
  action_type    TEXT NOT NULL,
  action_payload JSONB NOT NULL,
  tier           INTEGER NOT NULL,
  requested_by   TEXT NOT NULL,
  approved_by    TEXT,
  status         TEXT NOT NULL DEFAULT 'pending',
  expires_at     TIMESTAMPTZ NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ
);

-- Knowledge docs (chunks live in embeddings.*)
CREATE TABLE app.knowledge_docs (
  id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  tenant_id   TEXT NOT NULL REFERENCES app.tenants(id),
  title       TEXT NOT NULL,
  source_type TEXT NOT NULL,
  content     TEXT NOT NULL,
  checksum    TEXT NOT NULL,
  metadata    JSONB NOT NULL DEFAULT '{}',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
