# OMNYX Services — Quick Access & Guide

---

## Frontend
**URL:** [http://localhost](http://localhost)
**Login:** via Keycloak (auto-redirects)

### What to see
- Live dashboard — KPI cards, device telemetry charts, plant snapshot table
- Equipment list — all registered DDCs and sensors
- Alerts — open/acknowledged/resolved alarms
- Work Orders — create and track maintenance jobs
- Agent Activity — AI workflow runs and approval queue
- Reports — historical data exports

### What to add / do
- Create a Keycloak user first (see Keycloak section) to be able to log in
- Navigate to `/agent` to trigger AI workflows manually
- Navigate to `/approvals` to approve or reject pending AI actions

---

## Keycloak — Auth & User Management
**URL:** [http://localhost:8282/admin](http://localhost:8282/admin)
**Username:** `admin` **Password:** `change-me`
**Realm:** [http://localhost:8282/realms/omnyx](http://localhost:8282/realms/omnyx)
**OIDC config:** [http://localhost:8282/realms/omnyx/.well-known/openid-configuration](http://localhost:8282/realms/omnyx/.well-known/openid-configuration)

### What to see
- **Realm Settings** → General, Login, Email, Themes
- **Clients** → `omnyx-frontend` (public PKCE) and `omnyx-api` (confidential)
- **Users** → all registered users and their roles
- **Roles** → realm-level roles (`admin`, `operator`, `viewer`)
- **Sessions** → active login sessions
- **Events** → login history and audit log

### What to add / do
- **Create a test user** → Users → Add user → fill Username → Save → Credentials tab → Set Password (turn off Temporary)
- **Assign roles** → Users → select user → Role Mappings → assign `admin` / `operator` / `viewer`
- **Add a new client** → Clients → Create → for a new service that needs API access
- **Configure email** → Realm Settings → Email → SMTP server (for password reset flows)
- **Check token claims** → Clients → `omnyx-frontend` → Client Scopes → Evaluate → see what JWT payload looks like

---

## API Service
**URL:** [http://localhost:8000](http://localhost:8000)
**Health:** [http://localhost:8000/healthz](http://localhost:8000/healthz)
**Metrics:** [http://localhost:8000/metrics](http://localhost:8000/metrics) *(port 9091 inside Docker)*

### Endpoints (all require `Authorization: Bearer <token>`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/equipment` | List all DDCs / equipment |
| GET | `/api/v1/readings/latest` | Latest sensor readings |
| GET | `/api/v1/readings/history` | Time-range telemetry history |
| GET | `/api/v1/alerts` | All alerts |
| POST | `/api/v1/alerts/:id/acknowledge` | Ack an alert |
| GET | `/api/v1/work-orders` | Work order list |
| POST | `/api/v1/work-orders` | Create new work order |
| GET | `/api/v1/agent/workflows` | AI workflow definitions |
| POST | `/api/v1/agent/workflows/:id/trigger` | Trigger a workflow |
| GET | `/api/v1/agent/runs` | AI run history |
| GET | `/api/v1/approvals` | Pending human-in-loop approvals |
| POST | `/api/v1/approvals/:id/approve` | Approve an AI action |
| POST | `/api/v1/approvals/:id/reject` | Reject an AI action |

### Get a token to test endpoints
```bash
curl -X POST http://localhost:8282/realms/omnyx/protocol/openid-connect/token \
  -d "client_id=omnyx-frontend&grant_type=password&username=<user>&password=<pass>" \
  | grep access_token
```
Paste token as `Authorization: Bearer <token>` in Postman / Insomnia / curl.

---

## Grafana — Dashboards & Visualization
**URL:** [http://localhost:4000](http://localhost:4000)
**Username:** `admin` **Password:** `omnyx2024`

### Dashboards (pre-loaded)
- **OMNYX — Platform Overview** → API metrics, latency, DB write rate, memory, error logs
- **OMNYX — Live Telemetry** → DDC active/offline counts, readings/min, BACnet poll latency, per-service logs

### What to see
- **Dashboards** → Home → browse dashboards
- **Explore** → ad-hoc query Prometheus metrics or Loki logs live
- **Alerting** → alert rules, notification policies, silences
- **Connections** → Prometheus and Loki data sources

### What to add / do
- **Add a panel** → open a dashboard → Edit → Add → Visualization → pick query type
- **Useful Prometheus queries:**
  - `up` — which services are alive (1=up, 0=down)
  - `rate(http_requests_total[5m])` — API request rate
  - `dal_devices_active` — live DDC count
  - `dbwriter_readings_written_total` — total readings in DB
  - `process_resident_memory_bytes` — RAM per service
- **Useful Loki queries in Explore:**
  - `{compose_service="api-service"}` — all API logs
  - `{compose_service="db-writer"} |= "ERROR"` — DB writer errors
  - `{compose_service="dal-bacnet"}` — BACnet reader logs
  - `{job="docker"} |= "ERROR"` — errors across all services
- **Import a community dashboard** → Dashboards → Import → enter ID:
  - `1860` — Node Exporter Full (system metrics)
  - `7589` — Kafka Overview
  - `13639` — Loki logs panel
- **Create alerts** → Alerting → Alert rules → New → set threshold on any metric

---

## Prometheus — Metrics Store
**URL:** [http://localhost:9091](http://localhost:9091)
**Targets:** [http://localhost:9091/targets](http://localhost:9091/targets)
**Alerts:** [http://localhost:9091/alerts](http://localhost:9091/alerts)
**Config:** [http://localhost:9091/config](http://localhost:9091/config)

### Active scrape targets
| Job | Endpoint | Status |
|---|---|---|
| api-service | api-service:9091 | up |
| db-writer | db-writer:8011 | up |
| dal-bacnet | docker-host:8010 | up |
| prometheus | localhost:9090 | up |

### What to add / do
- **Add a new service to scrape** → edit `omnyx/infra/prometheus/prometheus.yml`, add under `scrape_configs`:
  ```yaml
  - job_name: my-service
    static_configs:
      - targets: ["my-service:8080"]
  ```
  Then recreate: `docker compose up -d prometheus`
- **Run PromQL queries** → Graph tab → try `up`, `rate(http_requests_total[1m])`, `dal_devices_active`

---

## Loki — Log Aggregation
**URL:** [http://localhost:3101](http://localhost:3101)
**Ready:** [http://localhost:3101/ready](http://localhost:3101/ready)
**Labels:** [http://localhost:3101/loki/api/v1/labels](http://localhost:3101/loki/api/v1/labels)

### What to see / do
Loki has no UI — use **Grafana Explore** ([http://localhost:4000/explore](http://localhost:4000/explore))

- `{compose_service="api-service"}` — API service logs
- `{compose_service="db-writer"} |= "Flushed"` — DB write confirmations
- `{compose_service="dal-bacnet"}` — BACnet reader logs
- `{compose_service="keycloak"}` — auth events
- `{job="docker"} |= "ERROR" | logfmt` — all errors

---

## Grafana Alloy — Log & Metric Pipeline
**URL:** [http://localhost:12345](http://localhost:12345)
*(Replaces EOL Promtail — Apache 2.0, free)*

### What to see
- **Graph tab** → visual pipeline: `discovery.docker` → `discovery.relabel` → `loki.source.docker` → `loki.write`
- **Components tab** → each pipeline component with live status
- **Debug tab** → component errors and evaluation logs

### What to add / do
- **Add Prometheus scraping via Alloy** → edit `omnyx/infra/prometheus/alloy.river`:
  ```river
  prometheus.scrape "myservice" {
    targets    = [{"__address__" = "myservice:8080"}]
    forward_to = [prometheus.remote_write.prom.receiver]
  }
  ```
- **Hot reload** → `curl -X POST http://localhost:12345/-/reload`

---

## Kafka UI — Message Bus Browser
**URL:** [http://localhost:8080](http://localhost:8080)

### Topics in use
| Topic | Producer | Consumer | Description |
|---|---|---|---|
| `telemetry.raw` | dal-bacnet | db-writer, ws-bridge | Raw BACnet readings |
| `dq.events` | dal-bacnet | dq-etl (Gate 3) | Data quality events |

### What to see / do
- **Topics → `telemetry.raw` → Messages** — browse live DDC readings flowing in
- **Consumers → `db-writer`** — check consumer lag (should be near 0)
- **Produce a test message** → Topics → select → Produce Message → paste JSON:
  ```json
  {"tenant_id":"unicharm","device_id":"DDC01","point_id":"GL 01 00 01 C0 0 003","value":22.5,"quality":"GOOD","ts":"2026-05-26T00:00:00Z"}
  ```
- **Create a topic** → Topics → Add Topic → set name, partitions, retention hours

---

## PostgreSQL / TimescaleDB — Database
**Host:** `localhost:5432` **DB:** `omnyx` **User:** `omnyx` **Password:** `change-me`

### Connect with DBeaver
1. Open DBeaver → New Database Connection → PostgreSQL
2. **Host:** `localhost` **Port:** `5432`
3. **Database:** `omnyx` **Username:** `omnyx` **Password:** `change-me`
4. Click **Test Connection** → Finish
5. In SQL Editor, set tenant context before querying:
   ```sql
   SET app.current_tenant_id = 'unicharm';
   ```

### Connect with psql
```bash
docker exec -it omnyx-postgres-1 psql -U omnyx -d omnyx
# Then set context:
SET app.current_tenant_id = 'unicharm';
```

### Key schemas & tables
| Schema | Table | Description |
|---|---|---|
| `app` | `equipment` | 11 DDCs registered |
| `app` | `device_points` | 363 sensor points |
| `app` | `alerts` | Alert history |
| `app` | `work_orders` | Maintenance jobs |
| `app` | `agent_workflows` | AI workflow definitions |
| `app` | `agent_runs` | AI execution history |
| `app` | `approval_requests` | Human-in-loop queue |
| `telemetry` | `readings` | Time-series sensor data (hypertable) |
| `telemetry` | `rl_decisions` | RL optimization decisions |
| `telemetry` | `twin_predictions` | Digital twin predictions |

### Useful queries
```sql
-- Set tenant context first (required by RLS)
SET app.current_tenant_id = 'unicharm';

-- Latest 20 readings
SELECT device_id, point_id, value_num, quality_flag, measured_at
FROM telemetry.readings ORDER BY measured_at DESC LIMIT 20;

-- Point count per DDC
SELECT device_id, COUNT(*) AS points, MAX(measured_at) AS last_seen
FROM telemetry.readings GROUP BY device_id ORDER BY device_id;

-- Hourly averages (TimescaleDB)
SELECT time_bucket('1 hour', measured_at) AS hour, device_id, AVG(value_num)
FROM telemetry.readings
WHERE measured_at > now() - interval '24 hours'
GROUP BY hour, device_id ORDER BY hour DESC;

-- Equipment list
SELECT name, subtype, building, location FROM app.equipment ORDER BY name;

-- Add new equipment (dynamic — no redeploy needed)
INSERT INTO app.equipment (tenant_id, name, type, subtype, location, building, metadata)
VALUES ('unicharm', 'New AHU — DDC12', 'ddc', 'ahu', 'Level 6', 'Block C',
        '{"bacnet_port":2012,"ip":"127.0.0.1"}');

-- Add new device points for new equipment
INSERT INTO app.device_points (tenant_id, equipment_id, point_id, object_type)
VALUES ('unicharm', '<equipment_id>', 'GL 12 00 01 C0 0 001', 'sensor');
```

### Dynamic scaling — adding new DDCs / equipment
The system is fully dynamic. To add a new device:
1. **Add to BACnet simulator** → edit `simulations/gl_pbs/data/eqp_name_handling.csv` with new DDC rows and points
2. **Register in DB** → run the `INSERT INTO app.equipment` SQL above (no redeploy needed)
3. **Register points** → run `INSERT INTO app.device_points` for each new point
4. Dal-bacnet auto-detects new DDCs from the CSV on next restart
5. Telemetry flows automatically through Kafka → DB-Writer → WebSocket → Frontend

---

## Redis — Cache
**Host:** `localhost:6379` (no auth)

### Connect
```bash
redis-cli -h localhost -p 6379
```

### What to see / do
- `KEYS *` — all cached keys
- `GET <key>` — inspect a value
- `MONITOR` — watch live commands
- `INFO stats` — connection and command stats
- Used by: api-service (rate limiting, sessions), agentic-ai (agent state, Gate 3)

---

## Service Metrics Endpoints
| Service | URL | Key metrics |
|---|---|---|
| DAL-BACnet | [http://localhost:8010/metrics](http://localhost:8010/metrics) | `dal_devices_active`, `dal_read_latency_seconds`, `dal_points_published_total` |
| DB-Writer | [http://localhost:8011/metrics](http://localhost:8011/metrics) | `dbwriter_readings_written_total`, `dbwriter_flush_latency_seconds` |
| API Service | [http://localhost:8000/metrics](http://localhost:8000/metrics) | `http_requests_total`, `http_request_duration_seconds` |

---

## Port Reference

| Port | Service | Notes |
|---|---|---|
| **80** | Frontend (nginx) | Main React UI |
| **8000** | API Service | REST API + health |
| **8080** | Kafka UI | Topic browser |
| **8282** | Keycloak | Admin: `/admin` |
| **8765** | WebSocket Bridge | `ws://localhost:8765/ws?token=` |
| **9091** | Prometheus | Metrics store |
| **9092** | Kafka (internal) | Docker network only |
| **9095** | Kafka (external) | Host-network services |
| **3101** | Loki | Log storage |
| **4000** | Grafana | Dashboards |
| **5432** | PostgreSQL | TimescaleDB |
| **6379** | Redis | Cache |
| **8010** | DAL-BACnet metrics | Prometheus scrape |
| **8011** | DB-Writer metrics | Prometheus scrape |
| **12345** | Grafana Alloy UI | Pipeline inspector |
