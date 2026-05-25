# OMNYX — Universal IoT Operations Platform by Graylinx

> **OMNYX** is the universal IoT operations platform from Graylinx. Real-time monitoring, predictive maintenance, and intelligent automation across industrial and operational domains — on customer premises, with no data leaving the network perimeter.

| Brand element | Value |
|---|---|
| Parent brand | **Graylinx** |
| Product wordmark | **OMNYX** |
| Tagline | *Universal IoT Operations Platform* |
| Footer signature | `OMNYX · by Graylinx` |
| HVAC vertical (already shipping) | **THERMYNX** — see [`extensions/thermynx-hvac/`](./extensions/thermynx-hvac/) |

OMNYX delivers the v1.1 product described in [`docs/source/prd/CloudOps_Core_PRD_v1_0.docx`](./docs/source/prd/CloudOps_Core_PRD_v1_0.docx): eight domain-agnostic modules, Digital Twin FDD, Reinforcement Learning optimisation, and an Agentic AI framework (Planner / Executor / Validator) on top of a Kafka + PostgreSQL/TimescaleDB on-prem core.

---

## What's In This Repository

```text
omnyx/
├── README.md                ← you are here
├── BRANDING.md              ← name, logo, voice, casing rules
├── docs/
│   ├── poc/                 ← End-to-end POC plan (see docs/poc/00_INDEX.md)
│   ├── source/
│   │   ├── master/          ← master PDF and source-of-truth artifacts
│   │   ├── prd/             ← PRD / DQ source documents
│   │   └── references/      ← supporting reference captures
│   ├── migration/           ← Plan to migrate Unicharm MySQL into the OMNYX schema
│   └── site-evaluations/    ← site-specific hardware evaluations
├── assets/
│   └── brand/               ← palette / typography assets copied from THERMYNX kit
├── services/
│   ├── dal-bacnet/          ← Edge: BACnet reader + DQ Tier 1 + Kafka producer
│   ├── dal-replay/          ← One-shot: replays Unicharm MySQL into Kafka
│   ├── api-service/         ← Fastify REST + WebSocket + agent tool gateway
│   ├── ws-bridge/           ← Kafka → WebSocket plant snapshot
│   ├── db-writer/           ← Kafka → TimescaleDB
│   ├── dq-etl/              ← Tier 2 scheduled jobs (Python + APScheduler)
│   ├── twin-broker/         ← Digital Twin FDD + RUL engine
│   ├── rl-broker/           ← RL agent registry, shadow/live modes
│   ├── agentic-ai/          ← Planner / Executor / Validator on Claude
│   └── frontend/            ← React 18 SPA + tablet kiosk views
├── extensions/
│   └── thermynx-hvac/       ← HVAC vertical (Unicharm deployment lives here)
├── shared/                  ← Canonical models (Python + TS), Kafka schemas
├── infra/
│   ├── compose/             ← docker-compose.yml for the on-prem POC
│   ├── kafka/               ← Topic creation init job
│   ├── postgres/migrations/ ← Schema migrations (TimescaleDB + relational)
│   ├── keycloak/            ← Realm export + agent authorization model
│   ├── prometheus/          ← Scrape configs
│   └── grafana/             ← Dashboards (DQ, Kafka, latency, twin/RL/agents)
└── scripts/                 ← bring-up, fault-injection, smoke tests, demo script
```

---

## Start Here

1. **Product spec** — [`docs/poc/00_INDEX.md`](./docs/poc/00_INDEX.md)
2. **Scope and success criteria** — [`docs/poc/01_SCOPE_AND_SUCCESS.md`](./docs/poc/01_SCOPE_AND_SUCCESS.md)
3. **Phase 1 scope contract** — [`docs/poc/38_PHASE1_SCOPE_CONTRACT.md`](./docs/poc/38_PHASE1_SCOPE_CONTRACT.md)
4. **Architecture diagram** — [`docs/poc/02_ARCHITECTURE.md`](./docs/poc/02_ARCHITECTURE.md)
5. **POC runbook** — [`docs/poc/16_POC_RUNBOOK.md`](./docs/poc/16_POC_RUNBOOK.md)

## Existing Assets Being Absorbed

| Source | Role in OMNYX |
|---|---|
| [`D:\Harshan\simulations\gl_pbs`](../../simulations/gl_pbs/) | Field data source for the POC (BACnet simulator, 11 DDCs, 363 points). Reused as-is. |
| [`D:\Harshan\HVAC AI Operations Intelligence Platform`](../../HVAC%20AI%20Operations%20Intelligence%20Platform/) | The current THERMYNX deployment at Unicharm. Becomes the first vertical extension; its MySQL `unicharm` history is replayed into the new TimescaleDB hypertable via `services/dal-replay`. |
| [`docs/source/`](./docs/source/) | Original PRD documents, master PDF, and supporting references. Kept as the authoritative source-of-truth for product requirements. |

---

## Status

- **Phase 0 (Foundation)** — in progress. Documentation is organized under a single project root; code scaffolds are ready to be populated.
- See [`docs/poc/18_MILESTONES.md`](./docs/poc/18_MILESTONES.md) for the week-by-week plan to a demoable end product.
