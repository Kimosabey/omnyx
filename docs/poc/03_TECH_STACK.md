# 03 · Tech Stack (pinned, on-prem)

Every component runs locally. No cloud service is required to bring the POC up end-to-end — even the LLM has a documented Ollama fallback path so we can demonstrate air-gap operation.

## 0 · Confirmed stack — at a glance

| Concern | Choice | Note |
|---|---|---|
| **Primary DB** | **PostgreSQL 16 + pgvector** (`pgvector/pgvector:pg16`) | Pure PG16 — source.*, app.*, audit.*, embeddings.* |
| **Time-series DB** | **TimescaleDB on PG16** (`timescale/timescaledb:latest-pg16`) | telemetry.* — hypertables + continuous aggregates + compression |
| **Databases — strategy** | **Two PostgreSQL instances, no MySQL.** | Clean separation: OLTP/source vs high-volume time-series |
| Message bus | Kafka 7.6 (KRaft) | |
| Cache + queue | Redis 7 | |
| Backend | Node.js 20 + Fastify 4 + TypeScript 5 | |
| Edge / DQ Tier 2 / Twin / RL | Python 3.12 | |
| Frontend | React 18 + Vite 5 + TypeScript 5 | |
| Auth | Keycloak 24 | |
| LLM | Anthropic Claude (Opus 4.7 + Sonnet 4.6) · Ollama fallback | |
| Containers | Docker 24 + Compose v2 (POC) / k8s (prod) | |
| Monitoring | Prometheus + Grafana + Loki | |

**No MySQL anywhere in OMNYX.** Unicharm IBMS data is modelled directly in the primary PostgreSQL's `source` schema (DDC registry, point catalog, historical readings, alarms, setpoints). `dal-replay` reads from `source.ibms_readings` and publishes to Kafka — no MySQL connection ever made. The OMNYX runtime has zero MySQL dependencies.

Detailed DB design is in [`08_STORAGE_TIMESCALEDB.md`](08_STORAGE_TIMESCALEDB.md) and the ERD/principles document [`08a_DATABASE_DESIGN.md`](08a_DATABASE_DESIGN.md).

---

## 1 · Languages and Runtimes

| Layer | Choice | Notes |
|---|---|---|
| Edge / DAL | Python 3.12 | Reuses `bacpypes`, `confluent-kafka-python`, `aiokafka`. Keeps continuity with gl_pbs. |
| API + Bridges + Agentic AI | Node.js 20 (TypeScript 5) | Fastify is fastest async framework; tool calling via Anthropic SDK is first-class in TS. |
| DQ Tier 2 + Twin + RL | Python 3.12 | Numerics, scientific libs, RL frameworks. |
| Frontend | React 18 + Vite 5 + TypeScript 5 | |
| Containers | Docker 24 + Docker Compose v2 | k8s for production; documented in §15. |

## 2 · Core platform services

| Service | Image / Library | Version | Role |
|---|---|---|---|
| Kafka | `apache/kafka` | 3.7.0 (KRaft) | Event spine — dual listeners (internal + host-net) |
| Kafka UI | `provectuslabs/kafka-ui` | latest | Topic + consumer-lag visibility |
| **Primary DB** | `pgvector/pgvector:pg16` | PG 16 + pgvector | source + app + audit + embeddings |
| **Time-series DB** | `timescale/timescaledb:latest-pg16` | PG 16 + TimescaleDB | telemetry only (hypertables, compression, retention) |
| Redis | `redis:7-alpine` | 7.2 | BullMQ queues, cache |
| Keycloak | `quay.io/keycloak/keycloak` | 24.0 | SSO, RBAC, agent authorization |
| Prometheus | `prom/prometheus` | 2.51 | Metrics |
| Grafana | `grafana/grafana` | 10.4 | Dashboards |
| Loki | `grafana/loki` | 2.9.8 | Logs |
| Grafana Alloy | `grafana/alloy` | latest | Log pipeline (replaces EOL Promtail) |

## 3 · Backend (api-service)

| Library | Version | Role |
|---|---|---|
| Fastify | 4 | Async HTTP framework |
| `@fastify/websocket` | 10 | WS routes |
| `@fastify/jwt`, `@fastify/cors`, `@fastify/rate-limit` | latest | Standard middleware |
| Zod | 3 | Runtime validation, OpenAPI generation |
| Prisma | 5 | Postgres ORM; reads + writes the relational tables (NOT the telemetry hypertable, that goes through raw SQL) |
| `kafkajs` | 2 | Kafka client |
| `ioredis` | 5 | Redis client |
| `bullmq` | 5 | Job queue (scheduled agent workflows, PM tasks) |
| `pino` + `pino-pretty` | 9 | Structured logging → Loki |

## 4 · Edge (dal-bacnet)

| Library | Version | Role |
|---|---|---|
| `bacpypes` | 0.18 | BACnet/IP (same lib gl_pbs uses; RPM + single-read fallback already in their code) |
| `confluent-kafka` | 2.4 | Kafka producer (higher throughput than `aiokafka`; matches the proven gl_pbs producer) |
| `pydantic` | 2 | Quality envelope and config |
| `prometheus-client` | 0.20 | Edge metrics |

## 5 · DQ Tier 2, Twin, RL

| Library | Role |
|---|---|
| `APScheduler` | Scheduled ETL jobs (drift, baseline, gap reconciler, etc.) |
| `pandas`, `numpy`, `scipy` | Numerical heavy-lifting |
| `scikit-learn` | Regression for drift / cross-sensor models |
| `psycopg[binary]` + `asyncpg` | Postgres access |
| `pydantic` | Shared models |
| `simpy` or custom | Discrete-event simulation for digital twins (chiller, AHU) |
| `stable-baselines3` (optional v2) | RL backbone |

## 6 · Agentic AI

| Choice | Notes |
|---|---|
| Anthropic Claude API | Planner = Opus 4.7 or Sonnet 4.6, Executor = Sonnet 4.6, Validator = Sonnet 4.6 (separate context so it audits independently) |
| `@anthropic-ai/sdk` | TypeScript SDK, tool-use + prompt caching |
| Local fallback | Ollama (`qwen2.5:14b`) via `httpx` for air-gap demos; behind a `LLM_BACKEND=claude\|ollama` env flag |
| Tool gateway | All tools are Fastify routes the SDK calls back via `tool_use` blocks |
| Prompt cache | Claude prompt caching enabled on the static system prompt + tool definitions |

## 7 · Frontend

| Library | Role |
|---|---|
| React 18 + TypeScript 5 + Vite 5 | App shell |
| `react-router-dom` 6 | Routing |
| Chakra UI 2 or Mantine 7 | Component primitives (Chakra to match the HVAC platform's design language) |
| TanStack Query 5 | Server state, caching |
| `recharts` 3 | Charts (matches Unicharm dashboards already) |
| `socket.io-client` or native WS | Plant snapshot WS |
| `react-markdown` + `remark-gfm` | Agent activity feed, AI report rendering |

## 8 · Deltas vs the legacy HVAC AI Operations stack

| Concern | Legacy (`HVAC AI Operations Intelligence Platform`) | New CloudOps POC | Why we switch |
|---|---|---|---|
| Telemetry store | MySQL `unicharm` read-only, per-equipment normalized tables (`chiller_1_normalized`, ...) | **PostgreSQL 16 + TimescaleDB hypertable** `telemetry`, plus `device_points` dimension | Generic schema scales to any equipment type; hypertable handles 50–500 site target without per-equipment DDL |
| App state | Postgres `thermynx_app` separate from telemetry | **Same Postgres database** with `app` schema and `telemetry` schema | One backup, one HA story, joins across telemetry + app state |
| Vector store | pgvector in `thermynx_app` | pgvector in same DB | Same |
| Backend framework | FastAPI (Python) | **Fastify (Node.js, TypeScript)** | Matches PRD §06 tech stack; sharper tool-calling story for Agentic AI in TS; async I/O still fine |
| LLM | Ollama, qwen2.5:14b | **Claude API (primary)** with Ollama fallback | Multi-agent Planner/Executor/Validator needs the long context + reliable tool use; Ollama is the air-gap escape hatch |
| Agent loop | Custom ReAct loop, MAX_STEPS=8 | **Planner / Executor / Validator** as separate agents on Kafka topic `agent.activity` | Matches PRD §08; better auditability and reliability |
| Event bus | None (single-plant POC) | **Kafka 7.6 KRaft** | Multi-consumer fan-out — DB, WS, Twin, RL, Agent all subscribe |
| Edge data ingest | None — reads ETL'd MySQL only | **dal-bacnet** with Tier 1 DQ inline | Real-time field path for live operations |
| Auth | None (LAN POC) | **Keycloak** with RBAC + agent authorization model | PRD requirement; production-ready from day 1 |
| Job queue | arq (Python) | **BullMQ (Redis)** | Node-native; same Redis instance does cache + queue |
| Monitoring | Prometheus + Loki + Grafana (`obs` profile) | **Same** | Already proven; we keep it |

## 9 · Bridge to existing Unicharm telemetry

We **do not throw away** the existing `chiller_*_normalized` / `cooling_tower_*_normalized` / `condenser_pump_*_normalized` history. The POC includes a one-time **back-fill job** that streams those rows through Kafka into the new `telemetry` hypertable, mapping each legacy table to canonical `device_id` + `point_id` (see §08 storage migration). After back-fill, the new platform has full historical context for analytics, twin training and RL replay.

`mysql cli` is the canonical inspection tool — every DDL question in this POC plan should be verified against the live unicharm DB using:

```bash
mysql -h <host> -P 3307 -u ro_user -p -D unicharm -e "DESCRIBE chiller_1_normalized;"
```

The full DDL export is preserved at [`d:\Harshan\HVAC AI Operations Intelligence Platform\unicharm_db_ddl.md`](../../../../HVAC AI Operations Intelligence Platform/unicharm_db_ddl.md).
