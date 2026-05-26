-- =============================================================
-- OMNYX Primary DB — Migration 005: Indexes
-- Query-pattern driven + JSONB GIN + Partial indexes
-- =============================================================

-- SOURCE schema
CREATE INDEX ddc_registry_building   ON source.ddc_registry (building) WHERE is_active;
CREATE INDEX point_catalog_ddc       ON source.point_catalog (ddc_id);
CREATE INDEX point_catalog_obj       ON source.point_catalog (ddc_id, obj_type);
CREATE INDEX point_catalog_writable  ON source.point_catalog (gl_code) WHERE is_writable;
CREATE INDEX point_catalog_metadata  ON source.point_catalog USING GIN (metadata);

-- ibms_readings (partitioned) — indexes on each partition automatically inherited via partition
CREATE INDEX ibms_readings_gl_time   ON source.ibms_readings (gl_code, recorded_at DESC);
CREATE INDEX ibms_readings_ddc_time  ON source.ibms_readings (ddc_id, recorded_at DESC);
CREATE INDEX ibms_readings_bad       ON source.ibms_readings (recorded_at DESC) WHERE quality != 'GOOD';

-- ibms_alarms
CREATE INDEX ibms_alarms_ddc_time    ON source.ibms_alarms (ddc_id, triggered_at DESC);
CREATE INDEX ibms_alarms_active      ON source.ibms_alarms (triggered_at DESC) WHERE cleared_at IS NULL;

-- setpoints
CREATE INDEX setpoints_gl_active     ON source.setpoints (gl_code, effective_from DESC) WHERE effective_until IS NULL;

-- APP schema
CREATE INDEX equipment_tenant_type   ON app.equipment (tenant_id, type) WHERE is_active;
CREATE INDEX equipment_building      ON app.equipment (tenant_id, building);
CREATE INDEX equipment_metadata_gin  ON app.equipment USING GIN (metadata);
CREATE INDEX equipment_source        ON app.equipment (source_ddc_id) WHERE source_ddc_id IS NOT NULL;

CREATE INDEX device_points_equipment ON app.device_points (equipment_id) WHERE is_active;
CREATE INDEX device_points_source    ON app.device_points (source_gl_code) WHERE source_gl_code IS NOT NULL;

CREATE INDEX alerts_tenant_status    ON app.alerts (tenant_id, status, created_at DESC);
CREATE INDEX alerts_open             ON app.alerts (tenant_id, severity, created_at DESC) WHERE status = 'open';
CREATE INDEX alerts_equipment        ON app.alerts (equipment_id, status);
CREATE INDEX alerts_payload_gin      ON app.alerts USING GIN (payload);

CREATE INDEX wo_tenant_status        ON app.work_orders (tenant_id, status, created_at DESC);
CREATE INDEX wo_assigned             ON app.work_orders (assigned_to, status) WHERE assigned_to IS NOT NULL;
CREATE INDEX wo_scheduled            ON app.work_orders (scheduled_at) WHERE status IN ('open','in_progress');

CREATE INDEX notif_user_time         ON app.notifications (user_id, created_at DESC);
CREATE INDEX notif_unread            ON app.notifications (user_id, read_at) WHERE read_at IS NULL;

CREATE INDEX agent_runs_tenant       ON app.agent_runs (tenant_id, started_at DESC);
CREATE INDEX agent_runs_workflow     ON app.agent_runs (workflow_id, started_at DESC);
CREATE INDEX agent_runs_active       ON app.agent_runs (status, started_at DESC) WHERE status = 'running';

CREATE INDEX approvals_pending       ON app.approval_requests (tenant_id, expires_at) WHERE status = 'pending';

CREATE INDEX twin_models_equipment   ON app.twin_models (equipment_id, status);
CREATE INDEX rl_agents_equipment     ON app.rl_agents (equipment_id, mode) WHERE status = 'active';
CREATE INDEX rl_episodes_agent_time  ON app.rl_episodes (agent_id, ts DESC);

-- AUDIT
CREATE INDEX audit_events_tenant_time ON audit.events (tenant_id, created_at DESC);
CREATE INDEX audit_events_actor_time  ON audit.events (actor, created_at DESC);
CREATE INDEX audit_events_action      ON audit.events (action, created_at DESC);
CREATE INDEX audit_events_payload_gin ON audit.events USING GIN (payload);
