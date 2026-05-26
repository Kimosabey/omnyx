# 08a · Database Design (PostgreSQL only — 2 instances)

> One sentence: **OMNYX runs on TWO PostgreSQL 16 instances — a pure `postgres` (with pgvector) for source + app + audit + embeddings, and a `timescaledb` for the time-series telemetry layer. No MySQL anywhere. Unicharm IBMS data is modelled in the `source` schema of the primary DB — after cutover the OMNYX runtime has zero MySQL dependencies.**

This is the deep-dive design doc. Bring-up DDL and the storage overview live in [`08_STORAGE_TIMESCALEDB.md`](08_STORAGE_TIMESCALEDB.md).

---

## 1 · Design principles

1. **Two databases, separated by access pattern.** Pure PG16 (`postgres`) holds OLTP and source-of-truth data; TimescaleDB (`timescaledb`) holds high-volume time-series. Backups, retention, and scaling policies can differ per workload. The api-service is the only consumer that connects to both pools.
2. **Generic telemetry hypertable, not per-equipment tables.** The Unicharm shape of `chiller_1_normalized`, `chiller_2_normalized`, … is the *anti-pattern* we are leaving behind. New equipment must never require DDL.
3. **Relational dimension model for everything that isn't a measurement.** Equipment hierarchy, alerts, work orders, agent runs, audit — strict typed tables on the primary `postgres` DB.
4. **Source-of-truth in PostgreSQL, not MySQL.** The `source` schema mirrors what Unicharm IBMS provides (DDC registry, point catalog, historical readings, alarms, setpoints) — all in PostgreSQL. `dal-replay` reads from here, not from MySQL.
5. **Quality is a column, never a side table.** Every reading carries its `QualityEnvelope`. No JOIN to find out if a value is trustworthy.
6. **Multi-tenancy by row, not by schema.** A `tenant_id` column on every business table, enforced by Postgres Row-Level Security on the primary DB. New tenant = new row in `app.tenants`, never a new schema.
7. **Time goes in TIMESTAMPTZ, always UTC.** Display timezone is a UI concern.
8. **Migrations are versioned and reversible.** Two migration directories: `infra/postgres/migrations/` for the primary DB, `infra/timescaledb/migrations/` for the time-series DB.
9. **Read paths use continuous aggregates, not raw rows.** UI dashboards query `telemetry.readings_1m/_5m/_1h/_1d` continuous aggregates on TimescaleDB.
10. **No cross-database JOINs.** The api-service does two-step queries: resolve equipment → list of point_ids in `postgres`, then query telemetry in `timescaledb`. The boundary is enforced by separate connection pools.
11. **DB roles are real.** `omnyx_writer` (INSERT/UPDATE), `omnyx_reader` (analytics read-only). Statement timeouts set per role.
12. **No mixed unit columns.** Every reading has explicit `unit`. We refuse to repeat the Unicharm trap where `wet_bulb_c` and `wet_bulb_temp` coexisted with ambiguous meaning.

---

## 2 · Why PostgreSQL+TimescaleDB instead of MySQL

| Need | Postgres + TimescaleDB | MySQL | Decision |
|---|---|---|---|
| Native time-series partitioning + compression | Yes (hypertables, 10–20× compression) | No, manual partitioning + InnoDB | **Postgres** |
| Continuous aggregates (auto-refresh roll-ups) | Yes | No (must hand-roll cron + summary tables) | **Postgres** |
| JSONB for flexible payloads (quality_detail, alerts.payload, twin_states.state) | Excellent indexable JSONB | Generic JSON, weaker indexing | **Postgres** |
| Vector embeddings | pgvector in same DB | None first-party | **Postgres** |
| Row-Level Security for multi-tenancy | Native | Limited | **Postgres** |
| Materialised views, CTEs, window functions | Strong | Weaker | **Postgres** |
| Operational ecosystem | CloudNativePG, pgBackRest, logical replication | Galera/InnoDB Cluster | tied |
| Familiarity in current team | Already using Postgres in `thermynx_app` | Read-only consumer of Unicharm | **Postgres** |

Outcome: one engine handles telemetry hypertable + relational + vector + audit. The whole `thermynx_app` Postgres-and-pgvector approach folds in directly; the parts that were in MySQL are re-expressed cleanly.

---

## 3 · Schemas

```
postgres (primary)  —  pgvector/pgvector:pg16  —  port 5432
├── source          ← Unicharm IBMS mirror (system of record)
│   ├── ddc_registry         11 DDCs (master controller list)
│   ├── point_catalog        363 BACnet points (gl_code, obj_type, unit, limits)
│   ├── ibms_readings        Historical raw readings (partitioned monthly)
│   ├── ibms_alarms          Original alarm records
│   └── setpoints            Configured setpoints + history
│
├── app             ← OMNYX operational (multi-tenant via RLS)
│   ├── tenants
│   ├── equipment            ← links to source.ddc_registry via source_ddc_id
│   ├── device_points        ← links to source.point_catalog via source_gl_code
│   ├── alert_rules
│   ├── alerts
│   ├── work_orders
│   ├── technicians + technician_skills
│   ├── notifications
│   ├── data_quality_config
│   ├── twin_models
│   ├── rl_agents + rl_episodes
│   ├── agent_workflows + agent_runs
│   ├── approval_requests
│   └── knowledge_docs
│
├── audit           ← immutable append-only
│   └── events
│
└── embeddings      ← pgvector (1536-dim, ivfflat cosine)
    └── knowledge_chunks


timescaledb         —  timescale/timescaledb:latest-pg16  —  port 5434
└── telemetry       ← hypertables only
    ├── readings              every reading from every device (1d chunks)
    ├── readings_1m  (cagg)   1-min OHLC continuous aggregate
    ├── readings_5m  (cagg)   5-min OHLC
    ├── readings_1h  (cagg)   1-hour OHLC
    ├── readings_1d  (cagg)   1-day OHLC
    ├── twin_predictions      twin predictions + residuals + fault codes
    └── rl_decisions          every RL action (shadow + live)
```

**Compression / retention** (TimescaleDB only):
- `readings`: compress after 7d, drop raw after 90d (aggregates survive)
- `twin_predictions`: compress 7d, drop 180d
- `rl_decisions`: compress 7d, drop 1y
- `readings_1h` aggregate kept 1y, `readings_1d` aggregate kept 5y

---

## 4 · ERD overview (logical)

```
                              ┌──────────────┐
                              │ app.tenants  │
                              └──────┬───────┘
                                     │ 1..n
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
       app.organization        app.users          app.feature_flags
              │
              ▼
          app.campus
              │
              ▼
        app.building
              │
              ▼
          app.floor
              │
              ▼
          app.zone
              │
              ▼
          app.area
              │
              ▼
          app.site
              │
              ▼
        app.equipment ─────────────┬─────────────┬─────────────────┐
              │                    │             │                 │
              │ 1..n               │ 1..1        │ 1..1            │ 1..n
              ▼                    ▼             ▼                 ▼
    app.device_points       app.twin_models  app.rl_agents     app.work_orders
              │                                                    │
              │ 1..1                                                │ 1..n
              ▼                                                     ▼
   app.data_quality_config                                      app.parts
              │
              │ 1..n
              ▼
   telemetry.readings  ◄───────────── telemetry.quality_events
              │
              ▼
   telemetry.readings_1m / _5m / _1h  (continuous aggregates)


  Independent flows:

   telemetry.twin_states     ⇆  app.equipment + app.twin_models
   telemetry.rl_actions      ⇆  app.equipment + app.rl_agents
   app.alerts                ⇆  app.equipment + app.device_points + app.rules
   app.agent_runs            ⇆  app.agent_workflows + audit.events
   embeddings.knowledge      (RAG corpus, joined by source_id when relevant)
   audit.events              (every write everywhere lands a row here)
```

---

## 5 · Time-series design

### 5.1 The one hypertable that matters — `telemetry.readings`

Already DDL'd in [`08_STORAGE_TIMESCALEDB.md §2`](08_STORAGE_TIMESCALEDB.md). Key choices:

| Choice | Why |
|---|---|
| `value_num`, `value_bool`, `value_text` as separate nullable columns | Strict typing without per-type tables. Numeric values dominate; bool and text exist for state/enum points. |
| `quality_flag` + `quality_detail` JSONB inline | Quality is queried on every read — must not require a JOIN |
| `point_id` as `<device_id>.<param_name>` | Compound natural key; partition + index segmentation are point-id ordered, which is the dominant query pattern |
| `chunk_time_interval = 1 day` | Right size for 100–1 000 sites; chunks neither too many nor too few |
| `segment_by = point_id`, `order_by = measured_at DESC` for compression | Highest cardinality first, then time-ordered scan — yields the 10–20× ratio TimescaleDB documents |
| `compress` after **7 days**, `retention` after **2 years** | Hot data uncompressed for live UI; older data compressed for analytics; oldest expired |
| Indexes on `(point_id, measured_at DESC)`, `(device_id, measured_at DESC)`, `(site_id, measured_at DESC)` | Three dominant access paths |
| Partial index on `quality_flag <> 'GOOD'` | Cheap "show me anomalies" without scanning the full table |

### 5.2 Continuous aggregates

```sql
-- 1-min: dashboards + live chart
CREATE MATERIALIZED VIEW telemetry.readings_1m WITH (timescaledb.continuous) AS
SELECT time_bucket('1 minute', measured_at) AS bucket, point_id,
       AVG(value_num) FILTER (WHERE quality_flag IN ('GOOD','SUSPECT','IMPUTED')) AS avg_val,
       MIN(value_num) FILTER (WHERE quality_flag = 'GOOD')                        AS min_val,
       MAX(value_num) FILTER (WHERE quality_flag = 'GOOD')                        AS max_val,
       COUNT(*)                                                                    AS samples,
       SUM(CASE WHEN quality_flag = 'GOOD' THEN 1 ELSE 0 END)                     AS good_samples
FROM telemetry.readings
GROUP BY bucket, point_id;

-- 5-min and 1-h follow the same shape.
```

Refresh policies: 1-min refreshes every 1 min, 5-min every 5 min, 1-h every 15 min. Real-time portion (`end_offset = INTERVAL '1 minute'`) means the chart never lags more than that.

### 5.3 Why we keep `quality_events` as a hypertable

DQ events arrive at ~5 % of telemetry volume (most points are GOOD). Hypertable shape is correct: time-ordered, occasionally bulk-deleted by retention policy, dashboard queries are time-window scans. Same retention/compression policy as `readings`.

### 5.4 Why `twin_states` and `rl_actions` are hypertables

They are **parallel timelines** to `readings`. Twin predictions every step (∼1/min) and RL decisions every cycle (∼1/min) per protected device. Volume similar to readings; query patterns identical (time window per device).

### 5.5 What is NOT a hypertable

- All `app.*` rows (small, business state)
- `audit.events` (append-only, small enough for a regular table; partition by month if we ever exceed ~100 M rows)
- `embeddings.knowledge` (corpus is small; pgvector ivfflat index)

---

## 6 · Full DDL — relational tables (`app.*`)

```sql
-- 6.1 Tenancy
CREATE TABLE app.tenants (
  id              TEXT PRIMARY KEY,          -- "graylinx_demo" | "unicharm" | …
  name            TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | SUSPENDED | DELETED
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata        JSONB NOT NULL DEFAULT '{}'
);

-- 6.2 Hierarchy (matches Unicharm shape so historical analytics keep parity)
CREATE TABLE app.organization (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE app.campus (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  organization_id TEXT NOT NULL REFERENCES app.organization(id),
  name            TEXT NOT NULL
);
CREATE TABLE app.building (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  campus_id       TEXT NOT NULL REFERENCES app.campus(id),
  name            TEXT NOT NULL
);
CREATE TABLE app.floor (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  building_id     TEXT NOT NULL REFERENCES app.building(id),
  name            TEXT NOT NULL
);
CREATE TABLE app.zone (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  floor_id        TEXT NOT NULL REFERENCES app.floor(id),
  name            TEXT NOT NULL
);
CREATE TABLE app.area (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  zone_id         TEXT NOT NULL REFERENCES app.zone(id),
  name            TEXT NOT NULL
);
CREATE TABLE app.site (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  campus_id       TEXT NOT NULL REFERENCES app.campus(id),
  name            TEXT NOT NULL,
  metadata        JSONB NOT NULL DEFAULT '{}'  -- {timezone:"Asia/Kolkata",address:..,lat/lon}
);

-- 6.3 Equipment + points
CREATE TYPE app.equipment_type AS ENUM
  ('chiller','cooling_tower','pump','ahu','meter','breaker','plant_rollup','generic');

CREATE TABLE app.equipment (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  site_id         TEXT NOT NULL REFERENCES app.site(id),
  parent_id       TEXT REFERENCES app.equipment(id),
  name            TEXT NOT NULL,
  type            app.equipment_type NOT NULL,
  twin_model_id   TEXT,                                       -- FK app.twin_models(id) NOT enforced (forward ref)
  rl_agent_id     TEXT,
  vendor          TEXT, model TEXT, serial TEXT, install_date DATE,
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE app.point_type AS ENUM ('measurement','setpoint','command','state');

CREATE TABLE app.device_points (
  id                       TEXT PRIMARY KEY,                  -- "chiller_1.kw_per_tr"
  tenant_id                TEXT NOT NULL REFERENCES app.tenants(id),
  device_id                TEXT NOT NULL REFERENCES app.equipment(id),
  name                     TEXT NOT NULL,                      -- "kw_per_tr"
  display_name             TEXT,
  unit                     TEXT NOT NULL,
  point_type               app.point_type NOT NULL,
  value_kind               TEXT NOT NULL,                      -- numeric | boolean | text
  bacnet_object_id         TEXT,                                -- "analogValue:42"
  bacnet_property          TEXT,                                -- "presentValue"
  legacy_table             TEXT,                                -- Unicharm bridge only
  legacy_column            TEXT,
  expected_poll_seconds    INT NOT NULL DEFAULT 60,
  twin_protected           BOOLEAN NOT NULL DEFAULT FALSE,
  rl_observation           BOOLEAN NOT NULL DEFAULT FALSE,
  active                   BOOLEAN NOT NULL DEFAULT TRUE,
  metadata                 JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ON app.device_points (device_id);
CREATE INDEX ON app.device_points (tenant_id);

-- 6.4 DQ config + supporting tables (fed by Tier 2)
CREATE TABLE app.data_quality_config (
  point_id              TEXT PRIMARY KEY REFERENCES app.device_points(id) ON DELETE CASCADE,
  config                JSONB NOT NULL,        -- see 06_DATA_QUALITY_LAYER §2.2
  drift_coefficient     DOUBLE PRECISION DEFAULT 0,
  bias_offset           DOUBLE PRECISION DEFAULT 0,
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.sensor_health_scores (
  point_id              TEXT PRIMARY KEY REFERENCES app.device_points(id) ON DELETE CASCADE,
  score                 DOUBLE PRECISION,
  drift_pct             DOUBLE PRECISION,
  availability_pct      DOUBLE PRECISION,
  spike_rate_pct        DOUBLE PRECISION,
  last_calibration      TIMESTAMPTZ,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.baseline_profiles (
  point_id              TEXT NOT NULL REFERENCES app.device_points(id) ON DELETE CASCADE,
  hour_of_day           INT NOT NULL,         -- 0..23
  day_of_week           INT NOT NULL,         -- 0..6
  month                 INT NOT NULL,         -- 1..12
  expected_mean         DOUBLE PRECISION,
  expected_std          DOUBLE PRECISION,
  sample_count          INT,
  profile_version       TEXT NOT NULL,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (point_id, hour_of_day, day_of_week, month)
);

CREATE TABLE app.cross_sensor_rules (
  id              TEXT PRIMARY KEY,
  equipment_type  app.equipment_type NOT NULL,
  sensor_a        TEXT NOT NULL,
  sensor_b        TEXT NOT NULL,
  rule_type       TEXT NOT NULL,              -- MUST_BE_LESS | MUST_BE_POSITIVE_DIFF | …
  tolerance       DOUBLE PRECISION,
  active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE app.gap_registry (
  id              BIGSERIAL PRIMARY KEY,
  point_id        TEXT NOT NULL REFERENCES app.device_points(id) ON DELETE CASCADE,
  gap_start       TIMESTAMPTZ NOT NULL,
  gap_end         TIMESTAMPTZ NOT NULL,
  gap_seconds     INT GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (gap_end - gap_start))::INT) STORED,
  imputation_used TEXT,
  retro_filled    BOOLEAN NOT NULL DEFAULT FALSE
);

-- 6.5 Rules engine + Alerts
CREATE TYPE app.rule_kind AS ENUM ('threshold','offline','anomaly','delta','semantic');
CREATE TABLE app.rules (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  kind            app.rule_kind NOT NULL,
  device_id       TEXT REFERENCES app.equipment(id),
  point_id        TEXT REFERENCES app.device_points(id),
  params          JSONB NOT NULL,         -- threshold ranges, hold-time, etc.
  severity        TEXT NOT NULL,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE app.alert_severity AS ENUM ('info','warning','critical');
CREATE TYPE app.alert_source   AS ENUM ('rule','twin_fdd','dq','system');
CREATE TABLE app.alerts (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  source          app.alert_source NOT NULL,
  severity        app.alert_severity NOT NULL,
  fault_code      TEXT,
  device_id       TEXT REFERENCES app.equipment(id),
  point_id        TEXT REFERENCES app.device_points(id),
  rule_id         TEXT REFERENCES app.rules(id),
  fired_at        TIMESTAMPTZ NOT NULL,
  acknowledged_at TIMESTAMPTZ,
  acknowledged_by TEXT REFERENCES app.users(id),
  resolved_at     TIMESTAMPTZ,
  resolved_by     TEXT REFERENCES app.users(id),
  resolution_note TEXT,
  payload         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ON app.alerts (device_id, fired_at DESC);
CREATE INDEX ON app.alerts (tenant_id, severity, fired_at DESC) WHERE resolved_at IS NULL;

-- 6.6 Work orders
CREATE TYPE app.wo_status AS ENUM ('open','assigned','in_progress','resolved','closed','cancelled');
CREATE TABLE app.work_orders (
  id                 TEXT PRIMARY KEY,
  tenant_id          TEXT NOT NULL REFERENCES app.tenants(id),
  title              TEXT NOT NULL,
  status             app.wo_status NOT NULL DEFAULT 'open',
  severity           app.alert_severity NOT NULL,
  device_id          TEXT REFERENCES app.equipment(id),
  alert_id           TEXT REFERENCES app.alerts(id),
  created_by         TEXT NOT NULL,            -- user_id | "twin_fdd" | "agentic_ai" | "schedule"
  diagnosis          JSONB,
  recommended_parts  JSONB,
  technician_id      TEXT REFERENCES app.technicians(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  sla_due_at         TIMESTAMPTZ,
  started_at         TIMESTAMPTZ,
  closed_at          TIMESTAMPTZ,
  notes              TEXT
);
CREATE INDEX ON app.work_orders (status, created_at);

CREATE TABLE app.parts (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  sku             TEXT NOT NULL,
  name            TEXT NOT NULL,
  description     TEXT,
  uom             TEXT NOT NULL DEFAULT 'each',
  cost            NUMERIC(10,2),
  on_hand         INT NOT NULL DEFAULT 0,
  metadata        JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE app.work_order_parts (
  work_order_id   TEXT NOT NULL REFERENCES app.work_orders(id) ON DELETE CASCADE,
  part_id         TEXT NOT NULL REFERENCES app.parts(id),
  quantity        INT NOT NULL,
  PRIMARY KEY (work_order_id, part_id)
);

CREATE TABLE app.technicians (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  user_id         TEXT REFERENCES app.users(id),
  name            TEXT NOT NULL,
  skills          TEXT[] NOT NULL DEFAULT '{}',
  certifications  JSONB NOT NULL DEFAULT '{}',
  current_load    INT NOT NULL DEFAULT 0,
  active          BOOLEAN NOT NULL DEFAULT TRUE
);

-- 6.7 Twin + RL
CREATE TABLE app.twin_models (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  device_type     app.equipment_type NOT NULL,
  version         TEXT NOT NULL,
  config          JSONB NOT NULL,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE app.twin_calibrations (
  id              BIGSERIAL PRIMARY KEY,
  twin_model_id   TEXT NOT NULL REFERENCES app.twin_models(id),
  device_id       TEXT NOT NULL REFERENCES app.equipment(id),
  params          JSONB NOT NULL,
  mape            DOUBLE PRECISION,
  calibrated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE app.rl_mode AS ENUM ('SHADOW','LIVE','PAUSED');
CREATE TABLE app.rl_agents (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  device_id       TEXT NOT NULL REFERENCES app.equipment(id),
  kpi             TEXT NOT NULL,
  mode            app.rl_mode NOT NULL DEFAULT 'SHADOW',
  reward_config   JSONB NOT NULL,
  safety_bounds   JSONB NOT NULL,
  current_policy  JSONB,
  version         TEXT NOT NULL,
  promoted_at     TIMESTAMPTZ,
  promoted_by     TEXT REFERENCES app.users(id)
);

-- 6.8 Agentic AI
CREATE TYPE app.agent_run_status AS ENUM ('running','succeeded','failed','awaiting_approval','aborted_loop_guard','aborted_budget');
CREATE TABLE app.agent_workflows (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  trigger         TEXT NOT NULL,           -- "alert_created" | "scheduled:0 6 * * *"
  plan_template   JSONB NOT NULL,
  approval_tier   INT NOT NULL DEFAULT 2,
  active          BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE app.agent_runs (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  workflow_id     TEXT REFERENCES app.agent_workflows(id),
  trigger_payload JSONB,
  status          app.agent_run_status NOT NULL DEFAULT 'running',
  result          JSONB,
  tokens_used     INT,
  cost_usd        NUMERIC(8,4),
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at        TIMESTAMPTZ
);
CREATE TABLE app.agent_tool_registry (
  name            TEXT PRIMARY KEY,
  description     TEXT NOT NULL,
  input_schema    JSONB NOT NULL,
  output_schema   JSONB,
  approval_tier   INT NOT NULL DEFAULT 1,
  active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TYPE app.approval_status AS ENUM ('pending','approved','rejected','expired');
CREATE TABLE app.approvals (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  agent_run_id    TEXT REFERENCES app.agent_runs(id),
  tool_name       TEXT NOT NULL REFERENCES app.agent_tool_registry(name),
  tool_args       JSONB NOT NULL,
  requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  requested_by    TEXT NOT NULL,            -- agent identity
  decided_at      TIMESTAMPTZ,
  decided_by      TEXT REFERENCES app.users(id),
  status          app.approval_status NOT NULL DEFAULT 'pending',
  reason          TEXT
);

-- 6.9 Notifications + reports + schedules
CREATE TABLE app.notifications (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  channel         TEXT NOT NULL,            -- email | sms | inapp | webhook
  recipient       TEXT NOT NULL,
  subject         TEXT,
  body            TEXT,
  status          TEXT NOT NULL DEFAULT 'queued',
  related_type    TEXT, related_id TEXT,
  sent_at         TIMESTAMPTZ
);
CREATE TABLE app.reports (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  kind            TEXT NOT NULL,            -- daily | weekly | custom
  generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  range_start     TIMESTAMPTZ NOT NULL,
  range_end       TIMESTAMPTZ NOT NULL,
  storage_path    TEXT NOT NULL,            -- MinIO key
  validator_ok    BOOLEAN NOT NULL DEFAULT FALSE,
  metadata        JSONB
);
CREATE TABLE app.schedules (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  cron            TEXT NOT NULL,
  action          TEXT NOT NULL,            -- "run_workflow:investigate_alert" | "pm_task" | ...
  payload         JSONB,
  active          BOOLEAN NOT NULL DEFAULT TRUE
);

-- 6.10 Users + tenancy plumbing
CREATE TABLE app.users (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  keycloak_id     TEXT UNIQUE NOT NULL,
  display_name    TEXT NOT NULL,
  email           TEXT,
  roles           TEXT[] NOT NULL DEFAULT '{}',
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE app.api_keys (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  name            TEXT NOT NULL,
  hash            TEXT NOT NULL,
  scope           TEXT[] NOT NULL DEFAULT '{}',
  expires_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE app.feature_flags (
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  flag            TEXT NOT NULL,
  enabled         BOOLEAN NOT NULL DEFAULT FALSE,
  payload         JSONB,
  PRIMARY KEY (tenant_id, flag)
);

-- 6.11 Audit (append-only)
CREATE TABLE audit.events (
  id              BIGSERIAL PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  tenant_id       TEXT,
  actor           TEXT NOT NULL,            -- user_id | agent identity | "system"
  action          TEXT NOT NULL,            -- "write_setpoint" | "approve" | …
  target_type     TEXT,
  target_id       TEXT,
  payload         JSONB
);
CREATE INDEX ON audit.events (ts DESC);
CREATE INDEX ON audit.events (actor, ts DESC);
CREATE INDEX ON audit.events (target_type, target_id, ts DESC);

-- 6.12 Embeddings
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE embeddings.knowledge (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL REFERENCES app.tenants(id),
  source          TEXT NOT NULL,
  chunk_text      TEXT NOT NULL,
  embedding       VECTOR(768)               -- nomic-embed-text dim
);
CREATE INDEX ON embeddings.knowledge USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 7 · Multi-tenancy via Row-Level Security

Every business table carries `tenant_id`. RLS policies enforce isolation regardless of which service is making the query.

```sql
ALTER TABLE app.equipment ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_select ON app.equipment
  FOR SELECT USING (tenant_id = current_setting('omnyx.tenant_id', true));
CREATE POLICY tenant_isolation_modify ON app.equipment
  FOR ALL    USING (tenant_id = current_setting('omnyx.tenant_id', true));
-- Repeated for every app.* business table.
```

API layer sets `SET LOCAL omnyx.tenant_id = '<tenant>';` at the start of each request, derived from the JWT. Cross-tenant queries are impossible by construction.

Telemetry hypertables are similarly gated by joining to `app.device_points` (which has `tenant_id`) on the read path — we do not RLS the hypertable itself because it would defeat partition pruning. The repository layer enforces tenant scoping with mandatory `WHERE point_id IN (SELECT id FROM app.device_points WHERE tenant_id = ?)`.

---

## 8 · Database roles

| Role | Privileges | Used by |
|---|---|---|
| `omnyx_app` | `SELECT, INSERT, UPDATE, DELETE` on `app.*`; `SELECT` on `telemetry.*` | api-service |
| `omnyx_writer` | `INSERT` on `telemetry.*`; `SELECT` on `app.device_points` | db-writer, dq-etl (Tier 2 writes results back) |
| `omnyx_reader` | `SELECT` on all schemas | analytics, reports, twin-broker (training reads) |
| `audit_writer` | `INSERT` on `audit.events` only — no `UPDATE`/`DELETE` | any service writing audit rows; enforced at role level so even SQL injection cannot mutate the audit trail |
| `omnyx_admin` | superuser-equivalent within the database | migrations only (Alembic CLI), never via app |

```sql
CREATE ROLE omnyx_app LOGIN PASSWORD '…';
CREATE ROLE omnyx_writer LOGIN PASSWORD '…';
CREATE ROLE omnyx_reader LOGIN PASSWORD '…';
CREATE ROLE audit_writer LOGIN PASSWORD '…';

GRANT USAGE ON SCHEMA app, telemetry, audit, embeddings TO omnyx_app, omnyx_writer, omnyx_reader, audit_writer;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO omnyx_app;
GRANT SELECT                          ON ALL TABLES IN SCHEMA telemetry TO omnyx_app;

GRANT INSERT ON telemetry.readings, telemetry.quality_events, telemetry.twin_states, telemetry.rl_actions TO omnyx_writer;
GRANT SELECT ON app.device_points TO omnyx_writer;

GRANT SELECT ON ALL TABLES IN SCHEMA app, telemetry, embeddings TO omnyx_reader;

GRANT INSERT ON audit.events TO audit_writer;          -- no UPDATE / DELETE
REVOKE UPDATE, DELETE ON audit.events FROM PUBLIC;
```

---

## 9 · Query patterns and the indexes that serve them

| Pattern | Example | Index that serves it |
|---|---|---|
| Latest value per device | "Plant snapshot" | `(device_id, measured_at DESC)` on `telemetry.readings` |
| Trend per point, time range | Device-detail chart | continuous aggregate `readings_1m` keyed on `(bucket, point_id)` |
| Cross-equipment compare | "Chiller 1 vs Chiller 2 kW/TR last 24 h" | `(point_id, measured_at DESC)`; UNION across point_ids |
| Anomaly inbox | "Show me all non-GOOD in last hour" | partial index on `quality_flag <> 'GOOD'` |
| Twin overlay | predicted vs actual | hypertable join on `(device_id, measured_at)` |
| Alert inbox | open critical alerts | `(tenant_id, severity, fired_at DESC) WHERE resolved_at IS NULL` |
| WO board | open work orders by status | `(status, created_at)` |
| Agent run trace | one workflow | PK + index on `workflow_id, started_at` |
| Audit lookup by actor | who did what | `(actor, ts DESC)` |
| Knowledge search | RAG | ivfflat on `embedding vector_cosine_ops` |

---

## 10 · Compression and retention

| Hypertable | Compress after | Retain (raw) | Retain (cagg) |
|---|---|---|---|
| `telemetry.readings` | 7 d | 2 y | 1-min cagg 1 y, 5-min cagg 3 y, 1-h cagg 7 y |
| `telemetry.quality_events` | 7 d | 1 y | n/a |
| `telemetry.twin_states` | 7 d | 1 y | downsample to 5-min cagg @ 3 y |
| `telemetry.rl_actions` | 30 d | 3 y | n/a |

Total at 500-site target ≈ 1.5 TB hot + cold, well within 4-TB NVMe budget.

---

## 11 · Migrations and tooling

| Concern | Tool |
|---|---|
| DDL source of truth | **Alembic** (Python) — single ordered migration tree under `infra/postgres/migrations/` |
| App-service ORM | Prisma in api-service, schema introspected from the live DB (`prisma db pull`), not the other way round — Alembic owns DDL |
| Schema review | Every migration paired with a `down` and a SQL `EXPLAIN` for any new index |
| Re-runnable seeds | `infra/postgres/seeds/*.sql` + `infra/postgres/seeds/*.py` (idempotent `ON CONFLICT DO NOTHING` / `UPSERT`) |
| Local diff vs prod | `pg_dump --schema-only` + `migra` for drift detection |

---

## 12 · Backup, HA, restore

| Concern | POC | Production |
|---|---|---|
| Daily logical backup | `pg_dump` to MinIO | same |
| PITR | not yet | `pgBackRest` continuous WAL archive |
| Replicas | none | 2× synchronous (CloudNativePG operator) |
| Failover | manual | automatic via operator |
| Restore drill | weekly in staging | weekly automated |

---

## 13 · How this aligns to Unicharm (reference only)

| Unicharm shape | OMNYX equivalent |
|---|---|
| 131 per-equipment `*_normalized` tables | One `telemetry.readings` hypertable + dimension rows in `app.device_points` |
| `*_metric`, `*_om_p` raw vendor exports | Replaced by `dal-bacnet` Tier 1 DQ inline — no raw-vendor layer in OMNYX |
| `building`/`floor`/`zone`/`area`/`device` hierarchy | Same hierarchy in `app.*`, plus `tenant_id` on every row |
| `gl_subsystem`, `gl_subsystem_latest_event` | Replaced by `app.equipment` + last-value cache (Redis) + `telemetry.readings_1m` |
| `gl_alarm` | `app.alerts` with strict enum severity and FK to rule / equipment / point |
| `thermynx_app.analysis_audit` / `anomalies` / `agent_runs` | Migrated into `app.agent_runs`, `app.alerts`, `audit.events` |
| `thermynx_app.threads` / `messages` | Stay as is during M1–M3; merged into `app.agent_runs` if useful, otherwise left in their own table |

Cutover plan: [`../migration/UNICHARM_TO_OMNYX.md`](../migration/UNICHARM_TO_OMNYX.md).

---

## 14 · What we are explicitly NOT doing

- **No per-equipment table proliferation.** New equipment types must work zero-DDL.
- **No raw vendor table mirror.** Tier 1 DQ + canonical points is the only path.
- **No second database for analytics.** Continuous aggregates + `omnyx_reader` role on the same cluster.
- **No schema-per-tenant.** Row-level isolation; tenant onboarding is `INSERT INTO app.tenants`.
- **No app-side soft delete via flags everywhere.** `status` enums where it matters (equipment, alerts, WOs, agents); other tables hard-delete with audit log.
- **No MySQL.** Anywhere. Ever. In the OMNYX runtime.
