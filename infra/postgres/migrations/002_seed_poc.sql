-- =============================================================
-- OMNYX Seed Migration — 002 (POC / development data)
-- =============================================================

-- POC tenant (Unicharm HVAC site, THERMYNX vertical)
INSERT INTO app.tenants (id, name, plan, metadata) VALUES
  ('unicharm', 'Unicharm Thailand — HVAC (THERMYNX)', 'poc',
   '{"site":"chennai","vertical":"thermynx","simulator":"gl_pbs","ddc_count":11,"point_count":363}')
ON CONFLICT (id) DO NOTHING;

-- Default DQ config rules for gl_pbs simulator points
INSERT INTO app.data_quality_config (tenant_id, point_pattern, check_type, params, enabled, priority)
VALUES
  ('unicharm', 'DDC*_AI_*', 'range',  '{"min":-10,"max":200,"unit":"degC"}',       true, 100),
  ('unicharm', 'DDC*_AI_*', 'spike',  '{"max_delta_pct":50,"window_s":60}',         true, 90),
  ('unicharm', 'DDC*_AI_*', 'stale',  '{"max_age_s":300}',                          true, 80),
  ('unicharm', 'DDC*_AI_*', 'frozen', '{"min_unique_in_window":2,"window_s":600}',  true, 70),
  ('unicharm', 'DDC*_AO_*', 'range',  '{"min":0,"max":100,"unit":"pct"}',           true, 100),
  ('unicharm', 'DDC*_BI_*', 'null',   '{}',                                          true, 100),
  ('unicharm', 'DDC*_BO_*', 'null',   '{}',                                          true, 100),
  ('unicharm', '*',          'format', '{"required_fields":["point_id","measured_at"]}', true, 50)
ON CONFLICT DO NOTHING;

-- Default alert rules
INSERT INTO app.alert_rules (tenant_id, name, condition_type, condition_json, severity, notify_roles) VALUES
  ('unicharm', 'High Supply Air Temperature', 'threshold',
   '{"point_pattern":"DDC*_AI_SAT*","operator":"gt","value":28,"duration_s":300}',
   'warning', ARRAY['site_operator','approver']),

  ('unicharm', 'DDC Offline', 'offline',
   '{"max_silence_s":600}',
   'critical', ARRAY['site_operator','platform_admin']),

  ('unicharm', 'Chiller COP Anomaly', 'anomaly',
   '{"point_pattern":"DDC*_AI_COP*","z_score_threshold":3.0}',
   'warning', ARRAY['site_operator'])
ON CONFLICT DO NOTHING;
