-- =============================================================
-- OMNYX Primary DB — Migration 007: Seed Data
-- 1) Tenant
-- 2) source.ddc_registry (11 DDCs from Unicharm)
-- 3) source.point_catalog (363 points from CSV)
-- 4) app.equipment (linked to source.ddc_registry)
-- 5) app.device_points (linked to source.point_catalog)
-- =============================================================

-- ---- Tenant ------------------------------------------------
INSERT INTO app.tenants (id, name, plan, metadata) VALUES
  ('unicharm', 'Unicharm Thailand — HVAC (THERMYNX)', 'poc',
   '{"site":"chennai","vertical":"thermynx","ddc_count":11,"point_count":363,"simulator":"gl_pbs"}');

-- ---- source.ddc_registry — 11 Unicharm DDCs ----------------
INSERT INTO source.ddc_registry
  (ddc_id, name, ip_address, bacnet_port, device_instance, building, location, vendor, model, is_active) VALUES
  ('DDC01',     'Chiller Plant Main Controller',   '127.0.0.1', 2001, 1001, 'Main Plant', 'Plant Room', 'GL Sim', 'PBS-SIM-2026', true),
  ('DDC01_01',  'Chiller Plant Sub Controller',    '127.0.0.1', 2002, 1002, 'Main Plant', 'Plant Room', 'GL Sim', 'PBS-SIM-2026', true),
  ('DDC02',     'Cooling Tower Controller',        '127.0.0.1', 2003, 1003, 'Main Plant', 'Rooftop',    'GL Sim', 'PBS-SIM-2026', true),
  ('DDC03',     'AHU Zone 3 Controller',           '127.0.0.1', 2004, 1004, 'Block A',    'Level 3',    'GL Sim', 'PBS-SIM-2026', true),
  ('DDC04',     'AHU Zone 4 Controller',           '127.0.0.1', 2005, 1005, 'Block A',    'Level 4',    'GL Sim', 'PBS-SIM-2026', true),
  ('DDC05',     'AHU Zone 5 Controller',           '127.0.0.1', 2006, 1006, 'Block B',    'Level 5',    'GL Sim', 'PBS-SIM-2026', true),
  ('DDC06',     'FCU Zone Controller',             '127.0.0.1', 2007, 1007, 'Block B',    'All Floors', 'GL Sim', 'PBS-SIM-2026', true),
  ('DDC07',     'Pump & Condenser Controller',     '127.0.0.1', 2008, 1008, 'Main Plant', 'Plant Room', 'GL Sim', 'PBS-SIM-2026', true),
  ('DDC07_01',  'Pump Sub Controller',             '127.0.0.1', 2009, 1009, 'Main Plant', 'Plant Room', 'GL Sim', 'PBS-SIM-2026', true),
  ('DDC09',     'Primary Plant Controller',        '127.0.0.1', 2010, 1010, 'Main Plant', 'Plant Room', 'GL Sim', 'PBS-SIM-2026', true),
  ('DDC10',     'Secondary Plant Controller',      '127.0.0.1', 2011, 1011, 'Main Plant', 'Plant Room', 'GL Sim', 'PBS-SIM-2026', true);

-- ---- source.point_catalog — loaded from CSV ----------------
-- The CSV is mounted at /seeds/eqp_name_handling.csv via compose volume
-- Staging table then transform into normalized catalog
CREATE TEMP TABLE _csv_points (
  ddc_id       TEXT,
  obj_type     TEXT,
  obj_id       INTEGER,
  eqp          TEXT,
  gl_param_name TEXT,
  display_name TEXT,
  gl_code      TEXT,
  skip         TEXT
);

\COPY _csv_points (ddc_id, obj_type, obj_id, eqp, gl_param_name, display_name, gl_code, skip) FROM '/seeds/eqp_name_handling.csv' WITH (FORMAT csv, HEADER true);

INSERT INTO source.point_catalog
  (gl_code, ddc_id, obj_type, obj_id, eqp, param_name, display_name, data_type, is_writable, is_active)
SELECT
  TRIM(gl_code),
  ddc_id,
  obj_type,
  obj_id,
  eqp,
  gl_param_name,
  display_name,
  CASE
    WHEN obj_type LIKE 'analog%'     THEN 'analog'
    WHEN obj_type LIKE 'binary%'     THEN 'binary'
    WHEN obj_type LIKE 'multistate%' THEN 'multistate'
    ELSE 'analog'
  END,
  obj_type LIKE '%Output%',
  COALESCE(skip, '') != 'true'
FROM _csv_points
WHERE gl_code IS NOT NULL AND TRIM(gl_code) != ''
ON CONFLICT (gl_code) DO NOTHING;

-- ---- app.equipment — link to source.ddc_registry -----------
INSERT INTO app.equipment
  (id, tenant_id, source_ddc_id, name, type, subtype, building, location, metadata)
SELECT
  'equip-' || LOWER(REPLACE(d.ddc_id, '_', '-')),
  'unicharm',
  d.ddc_id,
  d.name,
  'ddc',
  CASE
    WHEN d.ddc_id IN ('DDC01','DDC01_01') THEN 'chiller'
    WHEN d.ddc_id = 'DDC02'                 THEN 'cooling_tower'
    WHEN d.ddc_id IN ('DDC03','DDC04','DDC05') THEN 'ahu'
    WHEN d.ddc_id = 'DDC06'                 THEN 'fcu'
    WHEN d.ddc_id IN ('DDC07','DDC07_01')   THEN 'pump'
    WHEN d.ddc_id = 'DDC09'                 THEN 'primary_plant'
    WHEN d.ddc_id = 'DDC10'                 THEN 'secondary_plant'
  END,
  d.building,
  d.location,
  jsonb_build_object('bacnet_port', d.bacnet_port, 'ip', host(d.ip_address), 'source_id', d.id)
FROM source.ddc_registry d;

-- ---- app.device_points — link to source.point_catalog ------
INSERT INTO app.device_points
  (tenant_id, equipment_id, source_gl_code, point_id, object_type, is_active)
SELECT
  'unicharm',
  'equip-' || LOWER(REPLACE(pc.ddc_id, '_', '-')),
  pc.gl_code,
  pc.gl_code,
  pc.obj_type,
  pc.is_active
FROM source.point_catalog pc
ON CONFLICT (tenant_id, point_id) DO NOTHING;
