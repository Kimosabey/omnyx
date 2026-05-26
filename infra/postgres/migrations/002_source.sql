-- =============================================================
-- OMNYX Primary DB — Migration 002: Source Schema
-- Mirrors what Unicharm IBMS provides — DDCs, points, history
-- =============================================================

-- DDC controller registry (one row per physical/simulated DDC)
CREATE TABLE source.ddc_registry (
  id              SERIAL PRIMARY KEY,
  ddc_id          TEXT NOT NULL UNIQUE,         -- e.g. DDC01, DDC01_01
  name            TEXT NOT NULL,
  ip_address      INET,
  bacnet_port     INTEGER,
  device_instance INTEGER,                       -- BACnet device instance
  building        TEXT,
  location        TEXT,
  vendor          TEXT,
  model           TEXT,
  firmware        TEXT,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  commissioned_at DATE,
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE source.ddc_registry IS
  'Master DDC list from Unicharm IBMS — physical/simulated controllers';

-- BACnet point catalog (one row per BACnet object across all DDCs)
CREATE TABLE source.point_catalog (
  id            SERIAL PRIMARY KEY,
  gl_code       TEXT NOT NULL UNIQUE,            -- "GL 01 00 01 C0 0 003"
  ddc_id        TEXT NOT NULL REFERENCES source.ddc_registry(ddc_id),
  obj_type      TEXT NOT NULL,                   -- analogInput | binaryInput | analogOutput | ...
  obj_id        INTEGER NOT NULL,
  eqp           TEXT,                            -- equipment code: C0, B0, P0, etc.
  param_name    TEXT,                            -- internal name: par_cdw_sup_temp_00
  display_name  TEXT,                            -- human label
  unit          TEXT,                            -- degC, kW, %, bool
  data_type     TEXT NOT NULL DEFAULT 'analog',  -- analog | binary | multistate
  low_limit     NUMERIC,
  high_limit    NUMERIC,
  normal_value  NUMERIC,
  is_writable   BOOLEAN NOT NULL DEFAULT false,
  is_active     BOOLEAN NOT NULL DEFAULT true,
  cov_threshold NUMERIC(5,2),                    -- Change-of-Value % threshold
  metadata      JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ddc_id, obj_type, obj_id)
);

COMMENT ON TABLE source.point_catalog IS
  'Full BACnet point catalog — every measurable/writable point from IBMS';

-- Historical raw readings from IBMS (replay source)
-- Note: NOT a hypertable (this DB has no TimescaleDB) — use native PG partitioning if scaling needed
CREATE TABLE source.ibms_readings (
  id            BIGSERIAL,
  gl_code       TEXT NOT NULL REFERENCES source.point_catalog(gl_code),
  ddc_id        TEXT NOT NULL,
  value_num     DOUBLE PRECISION,
  value_str     TEXT,
  quality       TEXT NOT NULL DEFAULT 'GOOD',    -- GOOD | UNCERTAIN | BAD | OFFLINE
  recorded_at   TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Initial monthly partitions (production: add a cron to auto-create future months)
CREATE TABLE source.ibms_readings_2026_05 PARTITION OF source.ibms_readings
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE source.ibms_readings_2026_06 PARTITION OF source.ibms_readings
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE source.ibms_readings_2026_07 PARTITION OF source.ibms_readings
  FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

COMMENT ON TABLE source.ibms_readings IS
  'Historical raw readings from Unicharm IBMS — read by dal-replay';

-- Historical alarms from IBMS
CREATE TABLE source.ibms_alarms (
  id            BIGSERIAL PRIMARY KEY,
  ddc_id        TEXT NOT NULL,
  gl_code       TEXT REFERENCES source.point_catalog(gl_code),
  alarm_type    TEXT NOT NULL,                   -- high_limit | low_limit | offline | comm_fault
  severity      TEXT NOT NULL DEFAULT 'warning', -- info | warning | critical
  message       TEXT,
  triggered_at  TIMESTAMPTZ NOT NULL,
  cleared_at    TIMESTAMPTZ,
  metadata      JSONB NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE source.ibms_alarms IS
  'Original alarm records from Unicharm IBMS';

-- Configured setpoints (writable points + their target values)
CREATE TABLE source.setpoints (
  id              SERIAL PRIMARY KEY,
  gl_code         TEXT NOT NULL REFERENCES source.point_catalog(gl_code),
  ddc_id          TEXT NOT NULL,
  setpoint_name   TEXT NOT NULL,
  value           NUMERIC NOT NULL,
  unit            TEXT,
  effective_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_until TIMESTAMPTZ,
  set_by          TEXT,
  reason          TEXT,
  metadata        JSONB NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE source.setpoints IS
  'Setpoint history — every change tracked for traceability';
