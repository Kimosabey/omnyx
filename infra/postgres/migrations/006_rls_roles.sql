-- =============================================================
-- OMNYX Primary DB — Migration 006: RLS Policies & Roles
-- =============================================================

-- Enable RLS on every multi-tenant table
ALTER TABLE app.equipment         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.device_points     ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.alert_rules       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.alerts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.technicians       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.work_orders       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.notifications     ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.data_quality_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.twin_models       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.rl_agents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.rl_episodes       ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_workflows   ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.agent_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.knowledge_docs    ENABLE ROW LEVEL SECURITY;

-- Policy template: tenant_id must match session-set current_tenant_id
-- USING covers SELECT/UPDATE/DELETE; WITH CHECK covers INSERT/UPDATE
CREATE POLICY tenant_iso ON app.equipment
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.device_points
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.alert_rules
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.alerts
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.technicians
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.work_orders
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.notifications
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.data_quality_config
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.twin_models
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.rl_agents
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.rl_episodes
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.agent_workflows
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.agent_runs
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.approval_requests
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tenant_iso ON app.knowledge_docs
  USING       (tenant_id = current_setting('app.current_tenant_id', true))
  WITH CHECK  (tenant_id = current_setting('app.current_tenant_id', true));

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

GRANT USAGE ON SCHEMA source, app, audit, embeddings TO omnyx_writer, omnyx_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA source, app, audit, embeddings TO omnyx_reader;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO omnyx_writer;
GRANT INSERT ON audit.events TO omnyx_writer;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA source, app, audit, embeddings TO omnyx_writer;

-- Statement timeout to prevent runaway queries (per role)
ALTER ROLE omnyx_reader SET statement_timeout = '30s';
ALTER ROLE omnyx_writer SET statement_timeout = '60s';
