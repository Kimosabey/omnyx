# OMNYX Services — Access, Credentials & Guide

> **Architecture:** 2-DB split for clean separation —
> `postgres` (Primary App + Source) · `timescaledb` (Time-Series only)

---

## Frontend
**URL:** [http://localhost](http://localhost)
**Login:** via Keycloak (auto-redirects on first hit)

### What to see
- Dashboard — KPI cards, ECharts live telemetry, plant snapshot
- Equipment list — 11 DDCs registered (Unicharm THERMYNX)
- Alerts, Work Orders, Agent Activity, Approvals, Reports

### What to do
- Create Keycloak user first (see Keycloak section below)
- Toggle dark/light theme (top-right, persisted)
- Visit `/agent` to trigger AI workflows manually
- Visit `/approvals` to approve/reject pending agent actions

---

## Keycloak — Auth & User Management
**URL:** [http://localhost:8282/admin](http://localhost:8282/admin)
**Username:** `admin` **Password:** `change-me`

| Resource | URL |
|---|---|
| Realm public info | [http://localhost:8282/realms/omnyx](http://localhost:8282/realms/omnyx) |
| OIDC discovery   | [http://localhost:8282/realms/omnyx/.well-known/openid-configuration](http://localhost:8282/realms/omnyx/.well-known/openid-configuration) |
| Account console  | [http://localhost:8282/realms/omnyx/account](http://localhost:8282/realms/omnyx/account) |

### What to see
- **Realm Settings** → General, Login, Email, Themes
- **Clients** → `omnyx-frontend` (PKCE) and `omnyx-api` (confidential)
- **Users** → registered users + their roles
- **Roles** → `admin`, `operator`, `viewer`
- **Sessions** → active logins
- **Events** → login history + audit log

### What to add / do
- **Create test user** → Users → Add user → Username → Save → Credentials → Set Password (turn off Temporary)
- **Assign roles** → Users → select → Role Mappings → assign `admin` / `operator` / `viewer`
- **New OIDC client** → Clients → Create → for a new service
- **Email SMTP config** → Realm Settings → Email
- **Test token claims** → Clients → omnyx-frontend → Client Scopes → Evaluate

---

## API Service (Fastify)
**URL:** [http://localhost:8000](http://localhost:8000)
**Health:** [http://localhost:8000/healthz](http://localhost:8000/healthz)
**Metrics (internal):** port 9091

Connects to **two databases:** `postgres` (CRUD) + `timescaledb` (read-only telemetry).

### Endpoints (all require `Authorization: Bearer <token>`)

| Method | Endpoint | DB used | Purpose |
|---|---|---|---|
| GET | `/api/v1/equipment` | postgres | List all equipment |
| GET | `/api/v1/equipment/:id/readings/latest` | both | Latest snapshot for equipment |
| GET | `/api/v1/equipment/:id/readings?from=&to=&resolution=` | both | Time-range telemetry (`raw`/`1m`/`5m`/`1h`) |
| GET | `/api/v1/alerts` | postgres | All alerts |
| POST | `/api/v1/alerts/:id/acknowledge` | postgres | Ack an alert |
| GET | `/api/v1/work-orders` | postgres | Work order list |
| POST | `/api/v1/work-orders` | postgres | Create work order |
| GET | `/api/v1/agent/workflows` | postgres | AI workflows |
| POST | `/api/v1/agent/workflows/:id/trigger` | postgres | Trigger workflow |
| GET | `/api/v1/agent/runs` | postgres | AI run history |
| GET | `/api/v1/approvals` | postgres | Pending approvals |
| POST | `/api/v1/approvals/:id/approve` | postgres | Approve action |
| GET | `/api/v1/reports/daily?date=` | both | Daily ops report |
| GET | `/api/v1/audit` | postgres | Audit log |

### Get a token to test
```bash
curl -X POST http://localhost:8282/realms/omnyx/protocol/openid-connect/token \
  -d "client_id=omnyx-frontend&grant_type=password&username=<user>&password=<pass>" \
  | jq -r .access_token
```

---

## Grafana — Dashboards
**URL:** [http://localhost:4000](http://localhost:4000)
**Username:** `admin` **Password:** `omnyx2024`

### Dashboards (pre-loaded)
- **OMNYX — Platform Overview** → API rate, latency, memory, error logs
- **OMNYX — Live Telemetry** → DDC counts, readings/min, BACnet poll latency

### Useful PromQL
| Query | Meaning |
|---|---|
| `up` | Services alive (1=up, 0=down) |
| `sum(rate(http_requests_total[1m]))` | API req/s |
| `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` | p95 latency |
| `dal_devices_active` | Live DDC count |
| `rate(dbwriter_readings_written_total[1m])*60` | Readings written/min |
| `process_resident_memory_bytes` | RAM per service |

### Useful LogQL (Loki via Explore)
- `{compose_service="api-service"}` — API logs
- `{compose_service="db-writer"} |= "Flushed"` — DB write confirmations
- `{compose_service="dal-bacnet"} |= "ERROR"` — BACnet errors
- `{compose_service="keycloak"} |= "LOGIN"` — auth events
- `{job="docker"} |= "ERROR" | logfmt` — all errors

### What to add
- Import community dashboards → Dashboards → Import → enter ID `1860` (Node), `7589` (Kafka), `13639` (Loki)
- Create alerts → Alerting → Alert rules → New
- Add panel → Dashboard → Edit → Add → Visualization

---

## Prometheus
**URL:** [http://localhost:9091](http://localhost:9091)
**Targets:** [http://localhost:9091/targets](http://localhost:9091/targets) (all up)
**Config:** [http://localhost:9091/config](http://localhost:9091/config)
**Alerts:** [http://localhost:9091/alerts](http://localhost:9091/alerts)

### Active scrape targets
| Job | Endpoint | Status |
|---|---|---|
| api-service | api-service:9091 | up |
| db-writer | db-writer:8011 | up |
| dal-bacnet | docker-host:8010 (host-net via gateway) | up |
| prometheus | localhost:9090 | up |

### Add a scrape target
Edit `omnyx/infra/prometheus/prometheus.yml`:
```yaml
- job_name: my-service
  static_configs:
    - targets: ["my-service:8080"]
```
Then `docker compose up -d prometheus`.

---

## Loki + Grafana Alloy
**Loki URL:** [http://localhost:3101](http://localhost:3101) (no UI — use Grafana Explore)
**Alloy UI:** [http://localhost:12345](http://localhost:12345)

Alloy replaces EOL Promtail (Apache 2.0, free). Pipeline: Docker discovery → relabel → Loki write.

### Modify the pipeline
Edit `omnyx/infra/prometheus/alloy.river`, then hot reload:
```bash
curl -X POST http://localhost:12345/-/reload
```

---

## Kafka UI — Message Bus
**URL:** [http://localhost:8080](http://localhost:8080)

### Topics in use
| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `telemetry.raw` | dal-bacnet | db-writer, ws-bridge | Live BACnet readings |
| `dq.events` | dal-bacnet | dq-etl (Gate 3) | DQ events |

### What to do
- **Topics → `telemetry.raw` → Messages** — browse live data
- **Consumers → `db-writer`** — check lag (should be near 0)
- **Produce a test message** → Topics → select → Produce Message → paste JSON

---

## 🗄️ Primary DB — PostgreSQL 16 (Source + App)
**Host:** `localhost:5432` **DB:** `omnyx` **User:** `omnyx` **Password:** `change-me`
**Image:** `pgvector/pgvector:pg16` (PostgreSQL 16 + pgvector — no TimescaleDB)

### Schemas
| Schema | Purpose | Tables |
|---|---|---|
| `source` | **Unicharm IBMS mirror** (source of truth) | `ddc_registry`, `point_catalog`, `ibms_readings`, `ibms_alarms`, `setpoints` |
| `app` | **OMNYX operational** (multi-tenant via RLS) | `tenants`, `equipment`, `device_points`, `alerts`, `work_orders`, `technicians`, `agent_workflows`, `agent_runs`, `approval_requests`, `notifications`, `twin_models`, `rl_agents` |
| `audit` | Append-only audit trail | `events` |
| `embeddings` | pgvector for AI RAG | `knowledge_chunks` |

### Connect with DBeaver
1. New Database Connection → **PostgreSQL**
2. **Host:** `localhost` **Port:** `5432` **DB:** `omnyx` **User:** `omnyx` **Pass:** `change-me`
3. Test → Finish
4. In SQL Editor: `SET app.current_tenant_id = 'unicharm';` (required by RLS)

### Connect with psql
```bash
docker exec -it omnyx-postgres-1 psql -U omnyx -d omnyx
SET app.current_tenant_id = 'unicharm';
```

### Seeded data
- **11 DDCs** in `source.ddc_registry` — DDC01 through DDC10 + sub-controllers
- **363 BACnet points** in `source.point_catalog` (auto-loaded from CSV)
- **11 equipment** in `app.equipment` linked to source DDCs
- **363 device_points** in `app.device_points` linked to source points
- **1 tenant** — `unicharm`

### Useful queries
```sql
SET app.current_tenant_id = 'unicharm';

-- Equipment overview
SELECT name, subtype, building, location FROM app.equipment ORDER BY name;

-- Point counts per DDC (with source-of-truth catalog)
SELECT d.ddc_id, d.name, COUNT(p.id) AS points
FROM source.ddc_registry d
LEFT JOIN source.point_catalog p USING (ddc_id)
GROUP BY d.ddc_id, d.name ORDER BY d.ddc_id;

-- Writable points (setpoints/commands)
SELECT gl_code, display_name, unit FROM source.point_catalog
WHERE is_writable = true LIMIT 20;

-- Active alerts
SELECT severity, title, equipment_id, created_at
FROM app.alerts WHERE status = 'open' ORDER BY created_at DESC;

-- Add new DDC (dynamic, no redeploy)
INSERT INTO source.ddc_registry (ddc_id, name, ip_address, bacnet_port, building, location)
VALUES ('DDC11', 'New AHU Block C', '127.0.0.1', 2012, 'Block C', 'Level 1');

INSERT INTO app.equipment (tenant_id, source_ddc_id, name, type, subtype, building, location, metadata)
VALUES ('unicharm', 'DDC11', 'New AHU Block C', 'ddc', 'ahu', 'Block C', 'Level 1', '{}');
```

### Default roles
- `omnyx_writer` — INSERT/UPDATE on app.*, INSERT on audit.events
- `omnyx_reader` — SELECT only

---

## 🗄️ Time-Series DB — TimescaleDB (PG16 + TimescaleDB)
**Host:** `localhost:5434` **DB:** `omnyx_ts` **User:** `omnyx` **Password:** `change-me`
**Image:** `timescale/timescaledb:latest-pg16`

### Schema: `telemetry` only
| Table | Type | Purpose |
|---|---|---|
| `readings` | hypertable | Raw sensor readings (1d chunks) |
| `twin_predictions` | hypertable | Digital twin outputs (1d chunks) |
| `rl_decisions` | hypertable | RL agent decisions (1d chunks) |
| `readings_1m` | continuous agg | 1-minute OHLC roll-up |
| `readings_5m` | continuous agg | 5-minute OHLC roll-up |
| `readings_1h` | continuous agg | 1-hour OHLC roll-up |
| `readings_1d` | continuous agg | 1-day OHLC roll-up |

### Compression & retention (auto)
| Table | Compress after | Drop after |
|---|---|---|
| `readings` | 7 days | 90 days |
| `twin_predictions` | 7 days | 180 days |
| `rl_decisions` | 7 days | 1 year |

Continuous aggregates **survive raw data retention** — keep 1h roll-ups for 1 year, 1d for 5 years.

### Connect with DBeaver
1. New PostgreSQL Connection
2. **Host:** `localhost` **Port:** `5434` **DB:** `omnyx_ts` **User:** `omnyx` **Pass:** `change-me`

### Connect with psql
```bash
docker exec -it omnyx-timescaledb-1 psql -U omnyx -d omnyx_ts
```

### Useful queries
```sql
-- Recent readings (raw)
SELECT measured_at, device_id, point_id, value_num, quality_flag
FROM telemetry.readings ORDER BY measured_at DESC LIMIT 20;

-- Hourly average for one point (continuous aggregate)
SELECT bucket, avg, high, low
FROM telemetry.readings_1h
WHERE point_id = 'GL 01 00 01 C0 0 003'
  AND bucket > now() - INTERVAL '24 hours'
ORDER BY bucket DESC;

-- Hypertable storage info
SELECT hypertable_name,
       pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS size,
       (SELECT count(*) FROM timescaledb_information.chunks
        WHERE chunks.hypertable_name = h.hypertable_name) AS chunks
FROM timescaledb_information.hypertables h;

-- Compression status
SELECT hypertable_name,
       pg_size_pretty(before_compression_total_bytes) AS before,
       pg_size_pretty(after_compression_total_bytes)  AS after,
       round(100 - (after_compression_total_bytes::numeric / before_compression_total_bytes * 100), 1) AS pct_saved
FROM hypertable_compression_stats('telemetry.readings');
```

---

## Redis
**Host:** `localhost:6379` (no auth)

```bash
redis-cli -h localhost -p 6379
KEYS *
MONITOR
INFO stats
```

Used by api-service (rate limiting, sessions), agentic-ai (agent state — Gate 3).

---

## Service Metrics Endpoints
| Service | URL | Key metrics |
|---|---|---|
| dal-bacnet | [:8010/metrics](http://localhost:8010/metrics) | `dal_devices_active`, `dal_read_latency_seconds`, `dal_points_published_total` |
| db-writer | [:8011/metrics](http://localhost:8011/metrics) | `dbwriter_readings_written_total`, `dbwriter_flush_latency_seconds` |
| api-service (internal) | port 9091 (scraped by Prometheus) | `http_requests_total`, `http_request_duration_seconds_bucket` |

---

## Adding equipment dynamically (no redeploy)
1. Insert into `source.ddc_registry` (if from Unicharm IBMS) or skip
2. Insert into `app.equipment` linked via `source_ddc_id`
3. Add CSV row in `simulations/gl_pbs/data/eqp_name_handling.csv` if you want simulator to publish for it
4. Restart `dal-bacnet` to pick up the new CSV
5. New telemetry flows automatically: Kafka → db-writer → TimescaleDB → ws-bridge → frontend

---

## Full Port Reference

| Port | Service | Notes |
|---|---|---|
| **80** | Frontend (nginx) | React UI |
| **3101** | Loki | Log storage |
| **4000** | Grafana | Dashboards |
| **5432** | PostgreSQL (primary) | source + app schemas |
| **5434** | TimescaleDB | telemetry schema |
| **6379** | Redis | Cache |
| **8000** | API Service | REST API |
| **8010** | DAL-BACnet metrics | Host-net |
| **8011** | DB-Writer metrics | Prometheus scrape |
| **8080** | Kafka UI | Topic browser |
| **8282** | Keycloak | `/admin` for console |
| **8765** | WebSocket Bridge | `ws://localhost:8765/ws?token=` |
| **9091** | Prometheus | Metrics store (internal 9090 → external 9091) |
| **9092** | Kafka (internal) | Docker network only |
| **9095** | Kafka (external) | Host-network services |
| **12345** | Grafana Alloy UI | Pipeline graph |
