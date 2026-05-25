# 16 · POC Runbook — Bring-up, Demo, Tear-down

Step-by-step for an engineer who has not seen the project before. Times shown are wall-clock on the dev laptop.

## 0 · Pre-flight (one-time)

```bash
# Repo
cd D:\Harshan\graylinx-v2\omnyx

# Secrets
cp infra/compose/.env.example infra/compose/.env
# Edit infra/compose/.env:
#   POSTGRES_PASSWORD=...
#   KEYCLOAK_ADMIN_PASSWORD=...
#   ANTHROPIC_API_KEY=sk-ant-...
#   UNICHARM_HOST=... (Tailscale IP of Unicharm MySQL)
#   UNICHARM_RO_PW=...

# Python venv for fault-injection scripts
python -m venv .venv && source .venv/Scripts/activate
pip install -r scripts/requirements.txt
```

## 1 · Bring-up — core stack (~3 min)

```bash
cd infra/compose
docker compose up -d kafka kafka-init kafka-ui postgres redis keycloak prometheus grafana loki promtail

# Wait for healthchecks
docker compose ps
```

Verify:
- Kafka UI on http://localhost:8080
- Keycloak admin on http://localhost:8081 (admin / $KEYCLOAK_ADMIN_PASSWORD)
- Postgres `omnyx` database exists; `\dn` shows schemas `app`, `telemetry`, `audit`, `embeddings`
- Grafana on http://localhost:3000 (admin / admin)

## 2 · Seed the database (~30 s)

```bash
make seed-unicharm          # populates app.organization, .campus, .building, .site, .equipment, .device_points
make seed-dq-config         # writes data_quality_config for every point
make seed-rules             # threshold/offline/anomaly rules baseline
make seed-twin-models       # registers chiller_v1, cooling_tower_v1
make seed-rl-agents         # registers chiller_efficiency_v1 in SHADOW
make seed-workflows         # Workflow A,B,C from 11_AGENTIC_AI.md
```

## 3 · Optional — replay Unicharm history (~30 min for 90 d)

```bash
docker compose --profile replay up dal-replay
# Watches: progress per equipment, throughput, lag
# Stops itself when MAX(measured_at) >= NOW() - 5min for every replayed device
```

Verify with the queries in [08_STORAGE_TIMESCALEDB.md §5.3](08_STORAGE_TIMESCALEDB.md).

## 4 · Bring up application services (~1 min)

```bash
docker compose up -d db-writer dq-etl twin-broker rl-broker api-service ws-bridge agentic-ai frontend
```

Verify:
- `curl http://localhost:8000/healthz` — every dependency `ok`
- Login at http://localhost — `demo_admin` / password from `infra/keycloak/POC_PASSWORDS.md`
- Empty Portfolio dashboard renders (no live data yet)

## 5 · Start the field — gl_pbs simulator

```bash
# In a separate terminal (BACnet needs host network)
cd /d/Harshan/simulations/gl_pbs
python bacnet_name_launcher.py
# Wait for 11 DDCs to print READY
```

Then start the DAL:

```bash
cd /d/Harshan/graylinx-v2/omnyx/infra/compose
docker compose up -d dal-bacnet
```

Within 30 s:
- Kafka UI: `raw.bacnet.DDC09` and friends should show inbound messages.
- Frontend Portfolio: 1 site shows GREEN, 11 devices online.
- DQ score 100 %, all flags GOOD.

## 6 · Smoke tests

```bash
make smoke
```

Runs:
1. POST to api `/equipment` returns the tree.
2. GET `/telemetry/latest?device_id=DDC09` returns < 60 s old GOOD readings.
3. Open WS `wss://localhost:8765` with a demo JWT, expect a PlantSnapshot frame within 6 s.
4. Trigger Agentic AI Workflow A manually:
   `POST /agents/run {"workflow_id":"investigate_alert","payload":{"alert_id":"<seeded>"}}` — expect completion within 30 s with `validator_verdict=approved`.

## 7 · Demo storyline — six steps

Run these live to mirror [01_SCOPE_AND_SUCCESS.md §5](01_SCOPE_AND_SUCCESS.md):

```bash
# Step 1+2 — show dashboard, drill into DDC09 / chiller_1
# (UI work, no terminal needed)

# Step 3 — inject a sensor freeze on the simulator
python scripts/inject_dq_fault.py --freeze chiller_1.evap_leaving_temp --seconds 600
# Watch:
#  - DQ events stream in /dq
#  - SENSOR_FROZEN alert in /alerts within 60 s
#  - Agent activity feed begins: Planner → Executor → Validator
#  - New WO appears in /work-orders within ~30 s after the alert

# Step 4 — twin diagnostics + RUL
python scripts/inject_dq_fault.py --drift chiller_1.kw_per_tr --slope 0.005 --hours 24 &
# Open /twin/chiller_1 — RUL countdown trending down

# Step 5 — RL dashboard
# Open /rl — reward curve, shadow vs baseline, action distribution

# Step 6 — Grafana
# Open http://localhost:3000 → Dashboard "OMNYX overview"
#   - Kafka CPU < 5 %
#   - DQ GOOD% > 99
#   - Latency p95 < 5 s
#   - Agent runs / hour
```

## 8 · Tear-down

```bash
cd infra/compose
docker compose down                 # keep volumes
docker compose down -v              # nuke volumes (full reset)
```

## 9 · Common operations

| Task | Command |
|---|---|
| Tail logs of one service | `docker compose logs -f api-service` |
| Restart a service | `docker compose restart twin-broker` |
| Run Tier-2 ETL manually | `docker compose exec dq-etl python -m jobs.run_all` |
| Run a one-off SQL | `docker compose exec postgres psql -U omnyx -d omnyx -f /tmp/q.sql` |
| Re-seed | `make reseed` (drops + re-runs all seeds) |
| Switch LLM backend | edit `.env`: `LLM_BACKEND=ollama`; `docker compose restart agentic-ai` |
| Snapshot Postgres | `make backup-pg` (writes to `backups/`) |

## 10 · Health-check matrix (what should be green)

| Source | Endpoint | OK |
|---|---|---|
| api-service | `GET /healthz` | every dep `ok` |
| db-writer | logs | `consumer lag < 1000` |
| ws-bridge | `GET /healthz` | `ok`, connected clients ≥ 1 in demo |
| twin-broker | `GET /healthz/{device_id}` | `synced=true` |
| rl-broker | `GET /agents/{id}/status` | `mode=SHADOW`, last action < 60s |
| agentic-ai | logs | no `loop_guard_tripped` |
| Kafka UI | http://localhost:8080 | partitions healthy, no under-replicated |
| Grafana | OMNYX overview | all panels green |
