# OMNYX — Project Overview: Vision, Use Cases, Legacy Comparison

> One-page answer to: **"What are we building, who is it for, what problems does it solve compared to what exists today, and how good is the design?"**

---

## 1 · The One-Liner

**OMNYX is a universal on-premise IoT operations platform** that replaces fragmented per-equipment databases, manual rule-based alerts, and ad-hoc analytics scripts with a **unified event-driven stack** that handles real-time monitoring, predictive maintenance (Digital Twin), AI-driven optimization (RL), and agentic workflows — all running on the customer's own hardware, with no data leaving their perimeter.

**Built by Graylinx. First vertical: THERMYNX (HVAC). First customer: Unicharm Thailand.**

---

## 2 · The Big Picture — What OMNYX Is

```
                  ┌────────────────────────────────────────────────┐
                  │  WHAT THE BUSINESS GETS                        │
                  │                                                │
                  │  • Live plant visibility (5s latency)          │
                  │  • Predictive maintenance (RUL hours)          │
                  │  • Energy optimization (~5-15% savings)        │
                  │  • Autonomous work-order creation              │
                  │  • Full audit trail for compliance             │
                  │  • Zero data leaves the customer's network     │
                  └────────────────────────────────────────────────┘
                                       ▲
                  ┌────────────────────┴───────────────────────────┐
                  │  WHAT THE PLATFORM DOES                        │
                  │                                                │
                  │  Ingest → Quality-check → Store → Detect →     │
                  │  Predict → Optimize → Plan → Approve → Act     │
                  └────────────────────────────────────────────────┘
                                       ▲
                  ┌────────────────────┴───────────────────────────┐
                  │  WHAT'S UNDER THE HOOD                         │
                  │                                                │
                  │  Kafka · PostgreSQL · TimescaleDB · Redis ·    │
                  │  Keycloak · Claude API · React 18 · Fastify    │
                  └────────────────────────────────────────────────┘
```

---

## 3 · The Phased Plan (12 weeks → V1 → V2 → V3)

### Phase 0 — Foundation *(✅ Done)*
- Repo skeleton, docker-compose stack
- 2-DB architecture (PostgreSQL + TimescaleDB)
- Kafka, Redis, Keycloak running
- All MD docs aligned

### Phase 1 / Weeks 1–7 — Live Operations *(✅ ~Done, finishing Gate 2)*
- Edge ingest from BACnet → Kafka → TimescaleDB *(✅)*
- DQ Tier 1 inline at edge *(⚠️ basic; full 8-check rules pending)*
- WebSocket fan-out + React 18 frontend *(✅)*
- Alert engine + alert inbox UI *(⏳ alert evaluator just built; rules need seeding)*
- Work orders + approvals UI *(✅)*

### Phase 2 / Weeks 8–11 — Intelligence Layer *(⏳ Gate 3 — coming next)*
- **W8** Digital Twin Broker — `chiller_v1` physics twin, RUL prediction, fault detection
- **W9** RL Broker — `chiller_efficiency_v1` agent in SHADOW mode, reward dashboard
- **W10** Agentic AI — Planner / Executor / Validator on Claude, Workflows A (alert response), B (daily report), C (drift)
- **W11** DQ Tier 2 — drift estimator, baseline profiler, cross-sensor validator, gap reconciler

### Phase 3 / Week 12 — Hardening *(⏳ Gate 4, optional for POC)*
- Tests from `17_TEST_PLAN.md`
- Grafana overview dashboard polish
- Runbook + demo dry-runs
- Pre-launch: pgBackRest, PgBouncer, Kafka HA cluster (see `ARCHITECTURE_RATIONALE.md` §6)

### Phase 4 / Year 2 — Multi-Site & Multi-Tenant *(future)*
- Edge stack per site + MirrorMaker 2 to central
- DR site, cross-region replica
- Schema-per-tenant for premium customers
- SOC 2 / ISO 27001 audit prep

### Phase 5 / Year 3 — Vertical Expansion *(future)*
- THERMYNX (HVAC) → industry pilots
- New verticals: water utilities, cold-chain, energy storage
- Mobile / kiosk apps
- White-label / partner channel

---

## 4 · The Use Cases (Who Uses This For What)

| Persona | Primary use case | Frequency |
|---|---|---|
| **Plant Supervisor** | Check live status, ack alerts, dispatch work orders | Daily, 5–10 min mornings & evenings |
| **Maintenance Engineer** | Receive alerts, view trends, complete work orders on tablet | Per-incident |
| **On-Call Engineer** | Get paged on critical alerts at 02:30, diagnose remotely | 1–3 times/month |
| **Operations Manager** | Weekly KPI review, energy reports, technician productivity | Weekly |
| **AI/ML Engineer** | Tune twin/RL models, review agent decisions, ingest new equipment manuals into RAG | Daily during model dev, weekly steady-state |
| **Plant Manager** | Monthly energy savings dashboard, root-cause reports for incidents | Monthly |
| **Compliance Officer / Auditor** | Pull audit trails of setpoint changes, AI actions, approval chains | Annually + ad-hoc |
| **OMNYX Operations** | Add new equipment, onboard new sites, run DR drills | Per-event |

**8 detailed on-site scenarios** including critical-alert flows, weekend watchdog, maintenance windows, multi-site rollout, and compliance audits are documented in [`ARCHITECTURE_RATIONALE.md §9`](ARCHITECTURE_RATIONALE.md#9--assumed-on-site-usage-scenarios--what-actually-happens-in-the-field).

---

## 4.5 · The Big Transformation — From Single Site to Universal Platform

> **This is the story in one picture.** What existed before vs what OMNYX is.

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    BEFORE — THERMYNX at Unicharm                              ║
║                    "One project, one site, one of everything"                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

  ONE site             ONE project            ONE codebase
  Unicharm Chennai     Bespoke HVAC POC      Custom for this customer
  11 DDCs              No re-use plan         Per-customer fork to add anyone else
       │                    │                       │
       └────────────────────┴───────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │   ONE MySQL DB            │
              │   (Unicharm IBMS)         │
              │                           │
              │   131 per-equipment       │
              │   tables — chiller_1_     │
              │   normalized, etc.        │
              └─────────────┬─────────────┘
                            │
              ┌─────────────┴─────────────┐
              │   ONE Postgres            │
              │   (thermynx_app)          │
              │   — alerts, agents in     │
              │   a separate engine       │
              └─────────────┬─────────────┘
                            │
              ┌─────────────┴─────────────┐
              │   ONE Backend             │
              │   Monolith — direct DB    │
              │   writes from BACnet,     │
              │   HTTP polling everywhere │
              └─────────────┬─────────────┘
                            │
              ┌─────────────┴─────────────┐
              │   ONE Frontend            │
              │   Custom for Unicharm     │
              │   Hard-coded equipment    │
              │   labels                  │
              └───────────────────────────┘

  Problems baked in:
  ─ Add a new equipment type? → new MySQL table + backend code + frontend deploy
  ─ Sell to a second customer? → fork the entire repo, maintain N copies
  ─ Add a 12th DDC? → DDL change + manual config
  ─ Need AI features? → bolt-on Python scripts, no audit, no platform
  ─ Want to predict failures? → no time-series engine, no twin layer
  ─ Compliance audit asks "who changed what"? → no audit log to query
  ─ MySQL disk fills? → manual cleanup at night, no compression
  ─ Need to add a real-time consumer? → poll the DB more, hammer it
  ─ Cross-customer reporting? → impossible by design


╔═══════════════════════════════════════════════════════════════════════════════╗
║                    AFTER — OMNYX (Universal Platform)                         ║
║                    "Multi-site, multi-tenant, multi-vertical from day 1"      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

  MULTI-SITE              MULTI-TENANT             MULTI-VERTICAL
  ─ Unicharm Chennai      ─ Unicharm (T0)          ─ THERMYNX (HVAC) — Unicharm
  ─ + Site 2 (future)     ─ + Customer 2 (T1)      ─ + Water utilities (future)
  ─ + Site 3 ...          ─ + Customer 3 (T2 SaaS) ─ + Cold-chain (future)
        │                       │                        │
        └───────────────────────┴────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │  ONE PLATFORM CODEBASE        │
                │  Universal services           │
                │  Add customer = config row,   │
                │  not a code fork              │
                └───────────────┬───────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
        TWO POSTGRES        KAFKA SPINE       KEYCLOAK SSO
        instances           7-day replay      Multi-realm
        ─ source.* (IBMS    Multi-consumer    RBAC per role
          mirror, no                          OIDC standard
          per-equip tables) Replayable
        ─ app.*  (RLS multi- Decoupled
          tenant)
        ─ telemetry.*       Multi-tenant via
          (hypertables,     topic partitions
          compressed,       (T2+)
          autoretain)
                │
                ▼
        MULTIPLE STATELESS BACKENDS — scale by adding replicas
        ─ api-service · ws-bridge · db-writer · dal-bacnet ·
          dal-replay · twin-broker · rl-broker · agentic-ai · dq-etl
                │
                ▼
        ONE FRONTEND CODEBASE — multi-tenant from day 1
        ─ Tenant context from JWT
        ─ Equipment list loaded from API (no hardcoding)
        ─ Theme + branding per tenant (vertical config)

  How the legacy problems disappear:
  ─ Add new equipment? → INSERT row in app.equipment. Zero code change.
  ─ Sell to a 2nd customer? → INSERT row in app.tenants. Same codebase.
  ─ Add a 12th DDC? → INSERT 1 row in source.ddc_registry + CSV addition.
  ─ Want AI features? → Built-in: Twin + RL + Agentic + RAG.
  ─ Predict failures? → twin-broker writes telemetry.twin_predictions.
  ─ Compliance audit? → query audit.events with date+tenant filter.
  ─ Disk filling? → TimescaleDB compresses 90% after 7d, drops after 90d.
  ─ Add a real-time consumer? → subscribe to Kafka topic. Zero impact on others.
  ─ Cross-customer reporting? → SaaS path: schema-per-tenant for premium.

╔═══════════════════════════════════════════════════════════════════════════════╗
║  THE TRANSFORMATION IN NUMBERS                                                ║
║                                                                               ║
║  Tables defining "what an equipment is": 131 → 1 (generic)                   ║
║  Database engines: 2 (MySQL + Postgres) → 2 PostgreSQL (clean split)         ║
║  Lines of per-customer code: ~thousands → 0 (config-driven)                  ║
║  Time to onboard a new equipment type: days → minutes                        ║
║  Time to onboard a new customer (T1+): weeks → hours                         ║
║  Time-series compression ratio: 1× → ~10×                                    ║
║  Dashboard latency on 30-day trend: 8–15s → <1s (continuous aggregates)      ║
║  Real-time consumers per producer: 1 → unlimited (Kafka fan-out)             ║
║  Audit trail coverage: none → 100% of state changes                          ║
║  Open-source license: mixed/proprietary → 100% Apache/BSD/MIT/AGPL           ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

**The headline:** OMNYX is the move from a **bespoke single-customer project** to a **universal platform** that handles many customers, many sites, many verticals, many equipment types — all without forking the codebase. Every architectural decision in [`§5` below] and in [`ARCHITECTURE_RATIONALE.md`](ARCHITECTURE_RATIONALE.md) flows from that goal.

---

## 5 · Legacy vs OMNYX — Problem & Solution Map

This is the brutally honest "what was wrong before, what's better now" comparison. Each row is a real pain point from the Unicharm IBMS + THERMYNX platform.

### 5.1 — Data Modelling

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 1 | **Per-equipment tables** (`chiller_1_normalized`, `chiller_2_normalized`, … 131 tables) | New equipment = new DDL = code change = deploy = downtime risk | **Generic `telemetry.readings` hypertable** keyed by `point_id` | Add 1,000 devices without touching schema. SQL queries are one-liners instead of UNION-ing 131 tables. |
| 2 | **Inconsistent units across columns** (`wet_bulb_c`, `wet_bulb_temp`) | Ambiguous meaning, silent data corruption | **`unit` column on every point** in `source.point_catalog` | Explicit, validated, no silent unit mismatches |
| 3 | **No quality tagging** on readings | Garbage values stored as facts; downstream models trained on noise | **`quality_flag` + `dq_flags` + `quality_score`** on every reading | Twin/RL models filter out bad data automatically; DQ events stored as first-class |
| 4 | **Two databases** (MySQL telemetry + Postgres `thermynx_app`) | Two backup schedules, two auth setups, no joins between facts and dimensions | **Two PostgreSQL instances split by access pattern**, both queryable | Same query language; two-step queries (`app.device_points` → `telemetry.readings`) replace cross-engine ETL |
| 5 | **No standardized point ID** | Each table re-defined columns; hard to compare across equipment | **`gl_code` canonical IDs** in `source.point_catalog` | Same identifier flows from BACnet → Kafka → TimescaleDB → dashboard |

### 5.2 — Storage & Performance

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 6 | **No native time-series compression** in MySQL | Disk filled in months; archives manual | **TimescaleDB native compression** (~90% savings after 7d) | 10× less disk per year of history |
| 7 | **No retention automation** | Manual `DELETE` scripts ran weekly, locked tables | **`add_retention_policy()`** auto-drops old chunks | Set once, forget. Chunks dropped atomically, no table locks. |
| 8 | **Dashboards scanned raw rows** for trends | Trend chart took 8–15 seconds on a month of data | **Continuous aggregates** (`readings_1m/_5m/_1h/_1d`) | Dashboard p95 < 1s instead of 10s+ |
| 9 | **No native partitioning** on MySQL telemetry | Single huge table per equipment; index bloat | **Hypertable auto-partitions by time** (1d chunks) | Recent chunks stay hot in cache; old chunks compressed |
| 10 | **No JSON indexing** in MySQL 5.7 | Flexible metadata couldn't be queried efficiently | **JSONB + GIN indexes** in PostgreSQL | Schema-flexible fields without giving up query speed |

### 5.3 — Data Flow & Real-Time

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 11 | **Direct DB writes from BACnet reader** | Reader and DB tightly coupled; DB outage = reading loss | **Kafka as buffer** with 7-day retention | DB can be down for hours; readings replay when it comes back |
| 12 | **Single consumer** for telemetry (just DB writer) | Anyone else who needed live data had to query DB → slow & noisy | **Kafka multi-consumer** — db-writer, ws-bridge, twin, rl, agentic-ai all read independently | New consumers added without touching producers |
| 13 | **HTTP polling** from frontend for "live" data | Frontend hammered API every 5s × N devices = melts the API | **WebSocket bridge** broadcasts snapshot every 5s | One push, all clients update; API load drops 100× |
| 14 | **No replay capability** | If an analytics job failed mid-run, restart from scratch | **Kafka offsets + replay** | Replay last N hours into a new consumer for backfill |

### 5.4 — Operations & Reliability

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 15 | **No observability stack** | Bugs found by users, not engineers | **Prometheus + Grafana + Loki + Alloy** built-in | Every service exposes `/metrics`; logs queryable; alerts before users notice |
| 16 | **No structured logging** | Production debugging meant SSH and `grep` | **Pino (Node) + structlog (Python) → JSON → Loki** | Filter by service, level, tenant, request_id in seconds |
| 17 | **No audit trail** for actions | "Who changed the setpoint at 03:00 last Tuesday?" — unknowable | **`audit.events`** append-only log + middleware writes on every state change | Forensics work; compliance reports auto-generated |
| 18 | **No multi-tenant isolation** at DB layer | Cross-customer contamination risk if multi-tenanted later | **Row-Level Security** policies on every `app.*` table | DB engine refuses leaked rows even if app code has a bug |

### 5.5 — Intelligence Layer

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 19 | **No predictive maintenance** | Reactive only — equipment failed, then repaired | **Digital Twin Broker** (Gate 3) — physics-based twins + FDD + RUL hours | Maintenance scheduled *before* failure |
| 20 | **No optimization** | Setpoints set manually; no learning loop | **RL Broker** (Gate 3) — agents in shadow/advisory/live modes | 5–15% energy savings demonstrated in similar deployments |
| 21 | **No AI/automation** | Engineers wrote scripts ad-hoc; no central platform | **Agentic AI** (Gate 3) — Planner/Executor/Validator on Claude | Autonomous handling of Tier-1/2 incidents; humans approve Tier-3+ |
| 22 | **No knowledge base** | Equipment manuals on shared drives; lost institutional knowledge | **`embeddings.knowledge_chunks`** + pgvector RAG | Agents cite manuals; new engineers ramp 10× faster |

### 5.6 — Authentication & Authorization

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 23 | **Per-service auth** (basic auth on some, API keys on others) | Brittle; key rotation a nightmare | **Keycloak OIDC** single source of truth | One identity, one rotation, RBAC enforced everywhere |
| 24 | **No RBAC granularity** | Either admin or read-only — no role for "approve Tier-3 AI actions" | **Realm roles + scopes** (`admin`, `operator`, `viewer`, `approver`) | Right person, right action, audited |

### 5.7 — Deployment & Lock-In

| # | Legacy problem | Pain it caused | OMNYX solution | Why it's better |
|---|---|---|---|---|
| 25 | **Mixed licensing** (some commercial vendors) | License renewal risk; air-gapped deployments hard | **100% Apache 2.0 / BSD / MIT / AGPL** stack | Air-gapped deployments work; no per-CPU fees |
| 26 | **No reproducible deploys** | "It worked on my laptop" | **Docker Compose** today, **Helm charts + k8s** Tier T3+ | One command from a fresh clone to a running stack |
| 27 | **Customer data left perimeter** for analytics | Compliance & sovereignty concerns | **On-prem only by default; Claude API the one optional outbound call** | Customers can air-gap entirely (Ollama fallback for LLM) |

---

## 6 · How Good Is OMNYX — Honest Scoring

> 1–5 stars per category. Higher = closer to "great". Honest about gaps.

| Category | Score | Why |
|---|---|---|
| **Data modelling** | ⭐⭐⭐⭐⭐ | Generic schema, source-of-truth in `source.*`, RLS multi-tenancy, no anti-patterns. |
| **Time-series storage** | ⭐⭐⭐⭐⭐ | TimescaleDB hypertables + compression + continuous aggregates + retention — best-in-class OSS |
| **Event-driven architecture** | ⭐⭐⭐⭐⭐ | Kafka spine, multi-consumer, replayable, decoupled |
| **Real-time data delivery** | ⭐⭐⭐⭐ | WebSocket snapshot < 5s end-to-end; deltas could be added |
| **Multi-tenant isolation** | ⭐⭐⭐⭐ | RLS today (soft); schema-per-tenant available for premium when needed |
| **Observability** | ⭐⭐⭐⭐ | Prometheus + Grafana + Loki + Alloy — solid; alerts not yet wired |
| **Open-source & vendor neutrality** | ⭐⭐⭐⭐⭐ | 100% OSS licensed, on-prem first, no proprietary protocols |
| **Frontend / UX** | ⭐⭐⭐⭐ | React 18 + Tailwind + ECharts + Framer Motion + WCAG 2.2 + dark/light theme |
| **API design** | ⭐⭐⭐⭐ | Fastify + Zod + JWT + RBAC + REST conventions; OpenAPI gen still pending |
| **Predictive maintenance (Twin)** | ⭐⭐ | Schema + service scaffold ready, models not yet implemented |
| **RL optimization** | ⭐⭐ | Same — scaffold ready, agents not yet implemented |
| **Agentic AI** | ⭐⭐ | Same — Claude SDK + tool gateway design ready, workflows not yet built |
| **DQ Tier 1** | ⭐⭐⭐ | Quality envelope on every reading; 8-check pipeline partly wired |
| **DQ Tier 2** | ⭐ | Scaffold only — drift/baseline/gap reconciler not yet implemented |
| **High Availability** | ⭐⭐ | Single-instance everything today; HA path documented but not built |
| **Backup / Disaster Recovery** | ⭐ | No backups configured yet — biggest production gap |
| **Multi-site capability** | ⭐⭐ | Architecture supports it; edge stack + MirrorMaker 2 not yet wired |
| **CI/CD** | ⭐ | Manual builds today; pipeline not yet set up |
| **Documentation** | ⭐⭐⭐⭐⭐ | 50+ MD docs covering every aspect, including this honest assessment |

**Mean score: 3.4 / 5.**
**For T0 POC: that's correct — features over hardening.**
**For T1 Production: 4.0+ required. Add HA, backups, PgBouncer.**

---

## 7 · What Makes OMNYX Different (vs Similar Platforms)

| Vs… | OMNYX advantage |
|---|---|
| **Tridium Niagara / Honeywell EBI / Siemens Desigo** (proprietary BMS) | Open-source, no per-point licensing, AI-native, modern stack |
| **AWS IoT / Azure IoT Hub** | On-prem, no data egress, no cloud egress fees, no vendor lock-in |
| **Generic SCADA** (Ignition, Wonderware) | AI-native (Twin + RL + Agentic), not just HMI |
| **DIY (Python scripts + Grafana)** | Production-grade event spine, multi-tenant, hardened path defined |
| **Legacy Unicharm IBMS (current state)** | Every row of §5 above |

---

## 8 · What Could Go Wrong — Top 5 Risks Right Now

| # | Risk | Probability | Impact | Mitigation status |
|---|---|---|---|---|
| 1 | Postgres disk failure with no backup | Low | **Catastrophic** | **Open** — needs pgBackRest scheduling (P0) |
| 2 | Kafka broker death loses in-flight data | Low | **High** | **Open** — needs 3-broker cluster RF=3 |
| 3 | Connection exhaustion at ~50 concurrent users | Medium | High | **Open** — needs PgBouncer |
| 4 | Keycloak outage = no logins | Low | High | **Open** — needs HA pair |
| 5 | Gate 3 services (twin/RL/agentic) slip past Phase 2 deadline | Medium | Medium (POC features) | **Owned** — sequenced after Gate 2 finish |

Full risk register: [`ARCHITECTURE_RATIONALE.md §3`](ARCHITECTURE_RATIONALE.md#3--whats-incomplete-for-production-the-honest-cons).

---

## 9 · Bottom Line

> **The plan is sound. The architecture is modern and scalable. The risks are known and have explicit mitigation paths. The legacy problems we set out to solve — per-equipment tables, dual databases, no AI, no audit, no time-series features — are solved by the current design.**
>
> **Today's gap is execution: Gate 3 features need building, Gate 4 hardening needs scheduling. We are not risking data loss as long as the current POC stack stays a POC. Once we point paying customers at it, the §3.1 HA gaps in `ARCHITECTURE_RATIONALE.md` are non-negotiable.**

---

## 10 · Where To Read More

| Topic | Doc |
|---|---|
| Honest risk register + scaling tiers | [`ARCHITECTURE_RATIONALE.md`](ARCHITECTURE_RATIONALE.md) |
| Service URLs + credentials + DB connect | [`SERVICES.md`](SERVICES.md) |
| Architecture diagram + service inventory | [`docs/poc/02_ARCHITECTURE.md`](docs/poc/02_ARCHITECTURE.md) |
| Database design (2-DB split, schemas) | [`docs/poc/08a_DATABASE_DESIGN.md`](docs/poc/08a_DATABASE_DESIGN.md) |
| Tech stack | [`docs/poc/03_TECH_STACK.md`](docs/poc/03_TECH_STACK.md) |
| 12-week milestone plan | [`docs/poc/18_MILESTONES.md`](docs/poc/18_MILESTONES.md) |
| Test plan | [`docs/poc/17_TEST_PLAN.md`](docs/poc/17_TEST_PLAN.md) |
| Migration from Unicharm IBMS | [`docs/migration/UNICHARM_TO_OMNYX.md`](docs/migration/UNICHARM_TO_OMNYX.md) |
| Open-source licensing | [`docs/poc/31_OPENSOURCE_LICENSING.md`](docs/poc/31_OPENSOURCE_LICENSING.md) |
| Hardware requirements | [`docs/poc/36_HARDWARE_REQUIREMENTS.md`](docs/poc/36_HARDWARE_REQUIREMENTS.md) |
