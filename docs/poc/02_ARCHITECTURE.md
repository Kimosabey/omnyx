# 02 · End-to-End Architecture

## 1 · Layered View

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       FIELD (simulated for POC)                          │
│   gl_pbs/bacnet_name_launcher.py                                         │
│     ├─ 11 × bacnet_name_simulator.py                                     │
│     ├─ DDC01..DDC10 on UDP 2001..2011                                    │
│     └─ Driven by data/eqp_name_handling.csv (363 points, 8 eqp types)    │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ BACnet/IP (UDP, RPM batches of 15)
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       EDGE LAYER (one container)                         │
│   dal-bacnet  (replaces legacy bacnet_reader.py + kafka_bacnet_bridge)   │
│     ├─ Reads INI config (controller map, COV %, intervals)               │
│     ├─ RPM read strategy with single-read fallback (from gl_pbs RCA)     │
│     ├─ COV filter (3 %)                                                  │
│     ├─ DQ TIER 1 inline (completeness, range, frozen, spike, semantic)   │
│     ├─ Quality envelope attached to every point                          │
│     └─ KafkaProducer → raw.bacnet.{device_id}                            │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ Kafka (PLAINTEXT, on-prem)
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      MESSAGE BROKER LAYER                                │
│   Kafka 7.6 (KRaft, single broker for POC)                               │
│   Topics:                                                                │
│     raw.bacnet.{device_id}        DAL  → consumers       (per-device)    │
│     cmd.bacnet.{device_id}        API  → DAL             (write/read)    │
│     reply.bacnet.{request_id}     DAL  → API             (acks)          │
│     dq.events                     DAL+ETL → audit + UI                   │
│     twin.fdd.alerts               twin-broker → API                      │
│     rl.actions                    rl-broker → API + DAL (shadow/live)    │
│     agent.activity                agentic-ai → UI feed                   │
│     health.{service}              all → monitoring                       │
└────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────┘
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
┌──────────┐ ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐
│db-writer │ │ws-bridge   │  │twin-     │  │rl-broker │  │agentic-ai     │
│          │ │            │  │broker    │  │          │  │orchestrator   │
│Timescale-│ │WebSocket   │  │FDD +RUL  │  │shadow+   │  │Planner/Exec/  │
│DB only   │ │snapshot    │  │drift mon │  │live mode │  │Validator      │
└──────────┘ └──────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────┘
                    │             │             │               │
                    └─────────────┴──────┬──────┴───────────────┘
                                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       APPLICATION BACKEND                                │
│   api-service  (Node.js / Fastify, TypeScript)                           │
│     ├─ REST: assets, telemetry, alerts, work_orders, dq, twin, rl, agents│
│     ├─ DUAL DB POOL:                                                     │
│     │     • postgres    — source.* + app.* (RLS, OLTP)                   │
│     │     • timescaledb — telemetry.* (read-only for charts/reports)     │
│     ├─ Rules engine (threshold, offline, anomaly, hold-time)             │
│     ├─ Scheduler (BullMQ on Redis) — PM tasks, scheduled agent workflows │
│     ├─ Agent tool gateway (every tool the agents can call lands here)    │
│     └─ Auth: Keycloak JWT, RBAC                                          │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTP + WSS
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND                                        │
│   React 18 SPA + tablet kiosk views                                      │
│     ├─ Portfolio dashboard, site detail, device detail (twin overlay)    │
│     ├─ Alert inbox + work-order kanban                                   │
│     ├─ Twin diagnostics (RUL, fault tree)                                │
│     ├─ RL dashboard (reward curves, policy view, shadow/live toggle)     │
│     ├─ Agent activity feed (live trace of Planner/Executor/Validator)    │
│     └─ DQ dashboard (per-sensor health, flag distribution)               │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                       CROSS-CUTTING                                      │
│   Keycloak  ·  Prometheus + Grafana  ·  Kafka UI  ·  Loki + Alloy logs   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                       DQ TIER 2 (async)                                  │
│   dq-etl  (Python + APScheduler)                                         │
│     ├─ sensor_drift_estimator   (daily)                                  │
│     ├─ baseline_profiler        (weekly)                                 │
│     ├─ cross_sensor_validator   (hourly)                                 │
│     ├─ gap_reconciler           (hourly)                                 │
│     ├─ quality_score_rollup     (hourly)                                 │
│     ├─ rl_experience_cleaner    (daily)                                  │
│     ├─ twin_calibration_feeder  (daily)                                  │
│     └─ Writes back to data_quality_config → dal-bacnet refreshes q15min  │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2 · Why this shape

- **Kafka as the spine.** Multiple consumers (DB, WS, Twin, RL, Agentic) all read independently. Removes the HTTP fan-out the legacy `bacnet_reader.py` would otherwise need. Verdict already proven in [KAFKA_VERDICT_AND_REQUIREMENTS.md](../../../../simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md).
- **Tier 1 DQ inline at the edge** so Twins/RL/Alerts never see raw garbage. Tier 2 in ETL closes the loop. Straight from the DQ PRD §02.
- **Twin / RL / Agentic AI as separate brokers**, each a Kafka consumer + REST client. Lets each scale independently and lets us swap implementations.
- **API is the only writer of state.** The agents call API tools, not the DB directly — every action becomes auditable through one place.
- **Snapshot via WebSocket bridge**, not HTTP polling, to hit the < 5 s latency target.

## 3 · Service inventory (everything in one `docker-compose.yml`)

| # | Service | Image / build | Ports (host) | Role |
|---|---|---|---|---|
| 1 | `kafka` | `apache/kafka:3.7.0` | 9092 / 9095 | KRaft single-broker, dual listeners |
| 2 | `kafka-ui` | `provectuslabs/kafka-ui:latest` | 8080 | Topic & lag UI |
| 3 | `postgres` | `pgvector/pgvector:pg16` | 5432 | **Primary DB** — source + app + audit + embeddings |
| 4 | `timescaledb` | `timescale/timescaledb:latest-pg16` | 5434 | **Time-series DB** — telemetry only |
| 5 | `redis` | `redis:7-alpine` | 6379 | BullMQ + caching |
| 6 | `keycloak` | `quay.io/keycloak/keycloak:24.0` | 8282 | SSO/RBAC |
| 7 | `prometheus` | `prom/prometheus:v2.51` | 9091 | Metrics |
| 8 | `grafana` | `grafana/grafana:10.4` | 4000 | Dashboards |
| 9 | `loki` | `grafana/loki:2.9.8` | 3101 | Logs |
| 10 | `alloy` | `grafana/alloy:latest` | 12345 | Log pipeline (replaces EOL Promtail) |
| 11 | `bacnet-sim` | build from gl_pbs | 2001–2011 / 7091–7101 | 11 simulated DDCs |
| 12 | `dal-bacnet` | build (host-net) | — | Edge reader + Tier 1 DQ + Kafka producer |
| 13 | `dal-replay` | build (Python) | — | Replays `source.ibms_readings` → Kafka |
| 14 | `dq-etl` | build (Python) | — | Tier 2 async jobs (Gate 3) |
| 15 | `db-writer` | build (Python) | — | Kafka → TimescaleDB (telemetry only) |
| 16 | `ws-bridge` | build (Node) | 8765 | Kafka → WebSocket snapshot |
| 17 | `twin-broker` | build (Python) | — | Twin FDD + RUL (Gate 3) |
| 18 | `rl-broker` | build (Python) | — | RL agents (Gate 3) |
| 19 | `agentic-ai` | build (Node) | — | Planner/Executor/Validator (Gate 3) |
| 20 | `api-service` | build (Node) | 8000 | REST + tool gateway + dual DB pool |
| 21 | `frontend` | build (nginx static) | 80 | React SPA |

Two PostgreSQL services keep storage cleanly partitioned: relational/OLTP workloads on pure PG16 (with pgvector); high-volume time-series on TimescaleDB (hypertables + continuous aggregates + compression). The api-service is the only consumer that touches both DBs.

See [15_DEPLOYMENT_ONPREMISE.md](15_DEPLOYMENT_ONPREMISE.md) for the compose file, and [`../../SERVICES.md`](../../SERVICES.md) for URLs and credentials.
