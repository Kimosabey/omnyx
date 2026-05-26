# 08 · Storage — Two-Database PostgreSQL Architecture

OMNYX uses **two PostgreSQL instances** (no MySQL anywhere):

- **`postgres`** (pgvector/pgvector:pg16, port 5432) — primary OLTP DB, holds `source` + `app` + `audit` + `embeddings`
- **`timescaledb`** (timescale/timescaledb:latest-pg16, port 5434) — pure time-series, holds `telemetry` only

The api-service is the only consumer that connects to both; all other services touch exactly one of them. Two pools, two backup policies, independent scaling.

## 1 · Database layout

### Primary DB (`postgres`)

| Schema | Purpose | Engine feature |
|---|---|---|
| `source` | Unicharm IBMS mirror — DDC registry, point catalog, historical readings/alarms, setpoints | Native partitioning on `ibms_readings` by month |
| `app` | Equipment, alerts, work orders, agent runs, approvals, DQ config | RLS per tenant + JSONB GIN + partial indexes |
| `audit` | Immutable append-only event log | INSERT-only role |
| `embeddings` | RAG vectors (1536-dim) | pgvector ivfflat (cosine) |

### Time-series DB (`timescaledb`)

| Schema | Purpose | Engine feature |
|---|---|---|
| `telemetry` | All readings, DQ outputs, twin predictions, RL actions | Hypertables + continuous aggregates (1m/5m/1h/1d) + auto-compression after 7d + auto-retention |

## 2 · Core hypertable — `telemetry.readings`

This **replaces** the legacy per-equipment tables (`chiller_1_normalized`, `cooling_tower_1_normalized`, …). Generic shape, indexed for the query patterns we actually use.

```sql
CREATE SCHEMA telemetry;
CREATE SCHEMA app;

CREATE TABLE telemetry.readings (
  measured_at      TIMESTAMPTZ      NOT NULL,
  received_at      TIMESTAMPTZ      NOT NULL,
  site_id          TEXT             NOT NULL,
  device_id        TEXT             NOT NULL,
  point_id         TEXT             NOT NULL,            -- "chiller_1.kw_per_tr"
  value_num        DOUBLE PRECISION,                     -- numeric values
  value_bool       BOOLEAN,                              -- binary values
  value_text       TEXT,                                 -- enum / string values
  unit             TEXT,
  quality_flag     TEXT             NOT NULL,            -- GOOD/SUSPECT/IMPUTED/BAD/MISSING/STALE
  quality_detail   JSONB,
  original_value   DOUBLE PRECISION,
  imputation_method TEXT,
  drift_corrected  BOOLEAN          NOT NULL DEFAULT FALSE,
  tier2_validated  BOOLEAN          NOT NULL DEFAULT FALSE,
  cycle_id         UUID,
  source           TEXT             NOT NULL DEFAULT 'bacnet'  -- bacnet | replay | synthetic
);

SELECT create_hypertable('telemetry.readings','measured_at',chunk_time_interval => INTERVAL '1 day');
CREATE INDEX ON telemetry.readings (point_id, measured_at DESC);
CREATE INDEX ON telemetry.readings (device_id, measured_at DESC);
CREATE INDEX ON telemetry.readings (site_id,  measured_at DESC);
CREATE INDEX ON telemetry.readings (quality_flag, measured_at DESC) WHERE quality_flag <> 'GOOD';

ALTER TABLE telemetry.readings SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'point_id',
  timescaledb.compress_orderby   = 'measured_at DESC'
);
SELECT add_compression_policy('telemetry.readings', INTERVAL '7 days');
SELECT add_retention_policy   ('telemetry.readings', INTERVAL '730 days');  -- 2 years live
```

### 2.1 Why one wide table instead of per-equipment tables

| Concern | Per-equipment tables (legacy) | One generic hypertable (new) |
|---|---|---|
| New equipment type | DDL change required | Just new rows in `app.device_points` |
| Cross-equipment query | UNION ALLs | Single `WHERE point_id IN (...)` |
| Backup / migrate | 131 tables | 1 logical table |
| Twin training across types | Multiple connectors | One scan |
| Compression efficiency | Per-table tuning | Native Timescale compression by `point_id` (10–20× ratio in practice) |

### 2.2 Continuous aggregates — for fast UI

Pre-computed 1-min, 5-min, 1-h roll-ups so dashboards never scan raw rows.

```sql
CREATE MATERIALIZED VIEW telemetry.readings_1m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', measured_at) AS bucket,
  point_id,
  AVG(value_num) FILTER (WHERE quality_flag IN ('GOOD','SUSPECT','IMPUTED')) AS avg_val,
  MIN(value_num) FILTER (WHERE quality_flag = 'GOOD') AS min_val,
  MAX(value_num) FILTER (WHERE quality_flag = 'GOOD') AS max_val,
  COUNT(*) AS samples,
  SUM(CASE WHEN quality_flag='GOOD' THEN 1 ELSE 0 END) AS good_samples
FROM telemetry.readings
GROUP BY bucket, point_id;

SELECT add_continuous_aggregate_policy('telemetry.readings_1m',
  start_offset => INTERVAL '7 days',
  end_offset   => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute');

-- And a 5-minute and 1-hour aggregate the same way.
```

## 3 · Other hypertables

```sql
-- DQ events from Tier 1 + Tier 2 (audit + dashboard)
CREATE TABLE telemetry.quality_events (
  time             TIMESTAMPTZ NOT NULL,
  device_id        TEXT NOT NULL,
  point_id         TEXT NOT NULL,
  event_type       TEXT NOT NULL,   -- FROZEN | SPIKE | RANGE | DRIFT | MISSING | STALE | CROSS_SENSOR | ...
  flag_applied     TEXT NOT NULL,
  original_value   DOUBLE PRECISION,
  corrected_value  DOUBLE PRECISION,
  imputation_method TEXT,
  source           TEXT NOT NULL    -- TIER1 | TIER2
);
SELECT create_hypertable('telemetry.quality_events','time');

-- Twin predictions (parallel timeline to readings)
CREATE TABLE telemetry.twin_states (
  time             TIMESTAMPTZ NOT NULL,
  device_id        TEXT NOT NULL,
  twin_model_id    TEXT NOT NULL,
  state            JSONB NOT NULL,        -- predicted values for every twin output
  uncertainty      JSONB,                 -- per-output sigma
  fdd_active       BOOLEAN NOT NULL,      -- false during BAD/MISSING input
  rul_estimates    JSONB                  -- {component: days_remaining}
);
SELECT create_hypertable('telemetry.twin_states','time');

-- RL actions (every recommend OR write)
CREATE TABLE telemetry.rl_actions (
  time             TIMESTAMPTZ NOT NULL,
  agent_id         TEXT NOT NULL,
  device_id        TEXT NOT NULL,
  mode             TEXT NOT NULL,         -- SHADOW | LIVE
  state            JSONB NOT NULL,
  action           JSONB NOT NULL,        -- {point_id: new_value}
  reward           DOUBLE PRECISION,
  applied          BOOLEAN NOT NULL,
  approved_by      TEXT                   -- user_id if Tier 3+ approval
);
SELECT create_hypertable('telemetry.rl_actions','time');
```

## 4 · Relational `app.*` schema

```sql
-- Hierarchy: organization → campus → building → floor → zone → site → device → point
-- Matches Unicharm shape so we can replay metadata 1:1.

CREATE TABLE app.organization ( id TEXT PRIMARY KEY, name TEXT NOT NULL );
CREATE TABLE app.campus       ( id TEXT PRIMARY KEY, name TEXT NOT NULL, organization_id TEXT REFERENCES app.organization(id) );
CREATE TABLE app.building     ( id TEXT PRIMARY KEY, name TEXT NOT NULL, campus_id TEXT REFERENCES app.campus(id) );
CREATE TABLE app.floor        ( id TEXT PRIMARY KEY, name TEXT NOT NULL, building_id TEXT REFERENCES app.building(id) );
CREATE TABLE app.zone         ( id TEXT PRIMARY KEY, name TEXT NOT NULL, floor_id TEXT REFERENCES app.floor(id) );
CREATE TABLE app.area         ( id TEXT PRIMARY KEY, name TEXT NOT NULL, zone_id TEXT REFERENCES app.zone(id) );

CREATE TABLE app.site         ( id TEXT PRIMARY KEY, name TEXT NOT NULL, campus_id TEXT REFERENCES app.campus(id), metadata JSONB );

CREATE TABLE app.equipment (
  id              TEXT PRIMARY KEY,                      -- "chiller_1"
  name            TEXT NOT NULL,                         -- "Chiller 1"
  type            TEXT NOT NULL,                         -- chiller | cooling_tower | pump | ahu | meter | breaker | plant
  site_id         TEXT REFERENCES app.site(id),
  parent_id       TEXT REFERENCES app.equipment(id),
  twin_model_id   TEXT,
  rl_agent_id     TEXT,
  metadata        JSONB,                                 -- vendor, model, serial, install_date
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.device_points (
  id                       TEXT PRIMARY KEY,             -- "chiller_1.kw_per_tr"
  device_id                TEXT NOT NULL REFERENCES app.equipment(id),
  name                     TEXT NOT NULL,
  display_name             TEXT,
  unit                     TEXT,
  point_type               TEXT NOT NULL,                -- measurement | setpoint | command | state
  bacnet_object_id         TEXT,
  bacnet_property          TEXT,
  legacy_table             TEXT,                          -- "chiller_1_normalized"
  legacy_column            TEXT,                          -- "kw_per_tr"
  expected_poll_seconds    INT NOT NULL DEFAULT 60,
  twin_protected           BOOLEAN NOT NULL DEFAULT FALSE,
  rl_observation           BOOLEAN NOT NULL DEFAULT FALSE,
  active                   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE app.data_quality_config (
  point_id              TEXT PRIMARY KEY REFERENCES app.device_points(id),
  config                JSONB NOT NULL,                  -- see 06_DATA_QUALITY_LAYER §2.2
  drift_coefficient     DOUBLE PRECISION DEFAULT 0,
  bias_offset           DOUBLE PRECISION DEFAULT 0,
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.sensor_health_scores (
  point_id              TEXT PRIMARY KEY REFERENCES app.device_points(id),
  score                 DOUBLE PRECISION,
  drift_pct             DOUBLE PRECISION,
  availability_pct      DOUBLE PRECISION,
  spike_rate_pct        DOUBLE PRECISION,
  last_calibration      TIMESTAMPTZ,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.alerts (
  id              TEXT PRIMARY KEY,
  source          TEXT NOT NULL,                         -- rule | twin_fdd | dq | system
  severity        TEXT NOT NULL,                         -- info | warning | critical
  fault_code      TEXT,
  device_id       TEXT REFERENCES app.equipment(id),
  point_id        TEXT REFERENCES app.device_points(id),
  fired_at        TIMESTAMPTZ NOT NULL,
  acknowledged_at TIMESTAMPTZ,
  acknowledged_by TEXT,
  resolved_at     TIMESTAMPTZ,
  payload         JSONB NOT NULL
);

CREATE TABLE app.work_orders (
  id                 TEXT PRIMARY KEY,
  title              TEXT NOT NULL,
  status             TEXT NOT NULL,                       -- open|assigned|in_progress|resolved|closed
  severity           TEXT NOT NULL,
  device_id          TEXT REFERENCES app.equipment(id),
  created_by         TEXT NOT NULL,                       -- user | twin_fdd | agentic_ai | schedule
  diagnosis          JSONB,
  recommended_parts  JSONB,
  technician_id      TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  sla_due_at         TIMESTAMPTZ,
  closed_at          TIMESTAMPTZ
);

CREATE TABLE app.twin_models (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  device_type     TEXT NOT NULL,                          -- chiller | cooling_tower | pump
  version         TEXT NOT NULL,
  config          JSONB NOT NULL,                         -- physics params, fault library link
  active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE app.rl_agents (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  device_id       TEXT REFERENCES app.equipment(id),
  kpi             TEXT NOT NULL,                          -- "energy_efficiency" etc.
  mode            TEXT NOT NULL,                          -- SHADOW | LIVE | PAUSED
  reward_config   JSONB NOT NULL,
  safety_bounds   JSONB NOT NULL,
  current_policy  JSONB,
  version         TEXT NOT NULL
);

CREATE TABLE app.agent_workflows (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  trigger         TEXT NOT NULL,                          -- "alert_created" | "scheduled:0 6 * * *"
  plan_template   JSONB NOT NULL,
  approval_tier   INT NOT NULL DEFAULT 2,
  active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE app.agent_runs (
  id              TEXT PRIMARY KEY,
  workflow_id     TEXT REFERENCES app.agent_workflows(id),
  trigger_payload JSONB,
  status          TEXT NOT NULL,                          -- running | succeeded | failed | awaiting_approval
  result          JSONB,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at        TIMESTAMPTZ
);

CREATE TABLE app.users (
  id              TEXT PRIMARY KEY,
  keycloak_id     TEXT UNIQUE NOT NULL,
  display_name    TEXT NOT NULL,
  roles           TEXT[] NOT NULL                          -- ['operator','technician'] etc.
);

CREATE TABLE audit.events (
  id              BIGSERIAL PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor           TEXT NOT NULL,                          -- user_id or agent_id
  action          TEXT NOT NULL,
  target_type     TEXT,                                   -- equipment | work_order | rl_agent | ...
  target_id       TEXT,
  payload         JSONB
);

CREATE TABLE embeddings.knowledge (
  id              TEXT PRIMARY KEY,
  source          TEXT NOT NULL,                          -- "knowledge_base/HVAC_CHILLER_EFFICIENCY.md"
  chunk_text      TEXT NOT NULL,
  embedding       VECTOR(768)                              -- nomic-embed-text dim; swap to 1024 for Voyage / OpenAI
);
CREATE INDEX ON embeddings.knowledge USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## 5 · Migration from Unicharm MySQL

`dal-replay` (see [04_SIMULATOR_AS_DATA_SOURCE.md §2](04_SIMULATOR_AS_DATA_SOURCE.md)) does the heavy lift. The schema mapping is **fully data-driven** via `app.device_points.legacy_table` + `legacy_column`.

### 5.1 Seed `app.equipment` and `app.device_points` from Unicharm

Run once. Example for the chillers:

```sql
INSERT INTO app.equipment (id, name, type, site_id, metadata) VALUES
  ('chiller_1','Chiller 1','chiller','unicharm_chennai','{"vendor":"...","model":"..."}'),
  ('chiller_2','Chiller 2','chiller','unicharm_chennai','{}'),
  ('cooling_tower_1','Cooling Tower 1','cooling_tower','unicharm_chennai','{}'),
  ('cooling_tower_2','Cooling Tower 2','cooling_tower','unicharm_chennai','{}'),
  ('condenser_pump_1','Condenser Pump 1-2','pump','unicharm_chennai','{}'),
  ('condenser_pump_3','Condenser Pump 3','pump','unicharm_chennai','{}'),
  ('primary_pump_1','Primary Pump 1','pump','unicharm_chennai','{}'),
  ('primary_pump_2','Primary Pump 2','pump','unicharm_chennai','{}'),
  ('primary_pump_3','Primary Pump 3','pump','unicharm_chennai','{}'),
  ('plant','Plant rollup','plant','unicharm_chennai','{}');

-- Chiller points (column list cross-checked against DATABASE_SCHEMA_REFERENCE.md §3.1)
INSERT INTO app.device_points (id, device_id, name, display_name, unit, point_type, legacy_table, legacy_column, twin_protected, rl_observation, expected_poll_seconds)
SELECT 'chiller_1.'||col, 'chiller_1', col, display_name, unit, 'measurement', 'chiller_1_normalized', col, twin_protected, rl_obs, 60
FROM (VALUES
  ('kw',                  'Electrical input',  'kW',     true,  true),
  ('tr',                  'Cooling load',      'TR',     true,  true),
  ('kw_per_tr',           'Efficiency',        'kW/TR',  true,  true),
  ('evap_entering_temp',  'Evap entering temp','C',      true,  true),
  ('evap_leaving_temp',   'Evap leaving temp', 'C',      true,  true),
  ('evap_flow',           'Evap flow',         'L/min',  false, true),
  ('cond_entering_temp',  'Cond entering temp','C',      true,  false),
  ('cond_leaving_temp',   'Cond leaving temp', 'C',      true,  false),
  ('cond_flow',           'Cond flow',         'L/min',  false, false),
  ('ambient_temp',        'Ambient temp',      'C',      false, true),
  ('humidity_monitoring', 'Humidity',          '%',      false, true),
  ('chw_delta_t',         'CHW ΔT',            'C',      true,  false),
  ('kwh',                 'Energy',            'kWh',    false, false),
  ('chiller_load',        'Load',              '%',      true,  true),
  ('wet_bulb_temp',       'Wet bulb temp',     'C',      false, true)
) v(col, display_name, unit, twin_protected, rl_obs);
-- repeat for chiller_2 with legacy_table='chiller_2_normalized'
```

A YAML version of this seed lives at `infra/postgres/seeds/unicharm_equipment.yaml` and is executed by `make seed-unicharm`.

### 5.2 Backfill the hypertable

For each legacy table, in 1-day chunks:

```python
for day in date_range(start, end, step="1d"):
    rows = mysql.execute(f"""
        SELECT slot_time, is_running, kw, tr, kw_per_tr, evap_entering_temp, evap_leaving_temp,
               evap_flow, run_hours, cond_entering_temp, cond_leaving_temp, cond_flow,
               ambient_temp, humidity_monitoring, chw_delta_t, kwh, chiller_load, wet_bulb_temp,
               cumulative_kwh, cumulative_trh, btu_inlet_temp, btu_outlet_temp, btu_delta_t, trh
        FROM chiller_1_normalized
        WHERE slot_time >= %s AND slot_time < %s
        ORDER BY slot_time
    """, (day, day + 1*DAY))

    batches = []
    for r in rows:
        for col, val in r.items():
            if col == 'slot_time' or col == 'is_running': continue
            batches.append(PointReading(
                device_id="chiller_1",
                point_id=f"chiller_1.{col}",
                site_id="unicharm_chennai",
                value=val, unit=UNIT_LOOKUP[col],
                measured_at=r['slot_time'], received_at=now(),
                quality=QualityEnvelope(flag="GOOD", tier2_validated=True),
                source="replay",
            ))
    kafka_publish_in_chunks(batches, topic=f"raw.bacnet.chiller_1")
```

After `dal-replay` finishes, `MAX(measured_at)` in `telemetry.readings` matches Unicharm's `MAX(slot_time)`. Twin training, RL replay, agentic context queries all work over the same hypertable from then on.

### 5.3 Verification queries

```sql
-- Row count parity per equipment
SELECT 'unicharm' AS src, 'chiller_1_normalized' AS tbl, COUNT(*) FROM chiller_1_normalized
UNION ALL
SELECT 'omnyx', 'telemetry.readings', COUNT(*) FROM telemetry.readings
 WHERE device_id='chiller_1' AND point_id LIKE 'chiller_1.%' AND source='replay';

-- Freshness
SELECT device_id, MAX(measured_at) FROM telemetry.readings GROUP BY device_id ORDER BY 2 DESC;
```

## 6 · Sizing

| Quantity | Number | Notes |
|---|---|---|
| Sites in POC | 1 | Plus the Unicharm replay |
| Devices | 21 (11 simulated + 10 from Unicharm) | |
| Points | ~500 | 363 sim + ~140 legacy |
| Poll period | 60 s | Matches Unicharm cadence |
| Real msg/s | ~10 | After COV 3 % |
| Hot data (uncompressed) | ~50 MB / day | |
| Compressed (>7 d old) | ~3 MB / day | 16× ratio assumed |
| 2-year hot+cold | ~3 GB | trivial |

For the 500-site target the same math gives ~1.5 TB / 2 y — within reach of a 4-TB SSD. Production cuts that further with tighter `add_retention_policy` for raw vs aggregates.
