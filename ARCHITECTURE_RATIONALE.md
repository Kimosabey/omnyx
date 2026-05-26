# OMNYX — Architecture Rationale, Risks & Production Readiness

> **Purpose of this doc:** be brutally honest about *why* OMNYX is built this way, what's **safe** today, what's **risky** today, and exactly what needs to change before each scaling tier. Read this before quoting timelines or signing SLAs.

---

## 1 · The Design — In One Page

```
                            ┌──────────────────────┐
                            │  PRESENTATION        │
                            │  React 18 + Vite     │
                            │  (stateless, ≥1 pod) │
                            └──────────┬───────────┘
                                       │ HTTPS / WSS
                                       ▼
              ┌─────────────────────────────────────────────────────┐
              │  APPLICATION                                         │
              │  api-service (Fastify) ── DUAL DB POOL              │
              │  ws-bridge   (Kafka → WebSocket fan-out)            │
              │  (both stateless, horizontally scalable)            │
              └────┬──────────────────────────────────┬──────────────┘
                   │ writes app data                  │ reads telemetry
                   ▼                                  ▼
        ┌──────────────────────┐       ┌──────────────────────────┐
        │ POSTGRES (PG16)      │       │ TIMESCALEDB (PG16+TS)    │
        │ source.*  ← IBMS     │       │ telemetry.*              │
        │ app.*     ← OLTP     │       │  • hypertables           │
        │ audit.*               │       │  • continuous aggregates │
        │ embeddings.* (vector)│       │  • compression + TTL     │
        └──────────┬───────────┘       └──────────────────────────┘
                   │                              ▲
                   │ source.ibms_readings         │ db-writer (Kafka consumer)
                   ▼                              │
              ┌─────────────┐         ┌──────────────────────────┐
              │ dal-replay  │────────►│  KAFKA  (3.7, KRaft)     │
              │ (one-shot)  │         │  topics:                 │
              └─────────────┘         │   • telemetry.raw        │
                                      │   • dq.events            │
              ┌─────────────┐         │   • twin.fdd.alerts      │
              │ dal-bacnet  │────────►│   • rl.actions           │
              │ (edge)      │         │   • agent.activity       │
              └─────────────┘         └────┬───────────┬─────────┘
                                           │           │
                                           ▼           ▼
                                      twin-broker  rl-broker  agentic-ai
                                      (Gate 3, stubs today)
```

**Five core architectural choices and the reason for each.**

| Choice | Why |
|---|---|
| **Two PostgreSQL instances** (pure PG + TimescaleDB) | OLTP and time-series have different storage, backup, compression, and indexing needs. Mixing them hurts both — TimescaleDB is overkill for app data, plain PG can't handle compressed hypertable workloads at scale. Separating means we can scale each independently and apply different retention policies. |
| **Kafka as the spine** | Multi-consumer fan-out (db-writer, ws-bridge, twin, rl, agentic-ai) without each producer knowing the consumers. 7-day replay window means consumer crashes don't lose data. Proven at the gl_pbs stress test. |
| **Row-Level Security for multi-tenancy** | Tenant isolation enforced at the DB layer, not in app code. App code can't accidentally leak — Postgres refuses the row. |
| **Source schema in PostgreSQL (no MySQL)** | The Unicharm IBMS data we need (DDC registry, point catalog, historical readings) is modelled directly in PostgreSQL. No runtime MySQL dependency means one less DB engine to operate, license, patch, and backup. |
| **Stateless services** (api-service, ws-bridge, db-writer) | Any pod can die; another picks up. Horizontal scaling = add replicas + LB. State lives in postgres, timescaledb, redis, kafka — never in service memory. |

---

## 2 · What's GOOD (the strengths)

| # | Strength | Evidence / Why |
|---|---|---|
| 1 | **Clean separation of concerns** | OLTP in `postgres`, time-series in `timescaledb`, events in Kafka, cache in Redis, auth in Keycloak — each tool doing exactly what it's good at. No "Postgres for everything" anti-pattern. |
| 2 | **Multi-tenant isolation enforced by DB engine** | RLS policies on every `app.*` table use `current_setting('app.current_tenant_id')`. App code can't bypass — Postgres returns 0 rows if context not set. Cross-tenant leak is structurally impossible at the data layer. |
| 3 | **Time-series scale path is real** | TimescaleDB compression delivers 90%+ savings after 7d. Continuous aggregates (1m/5m/1h/1d) make dashboards 10× faster than scanning raw. Retention policies auto-drop old chunks. We can hold 5 years of aggregated data per tenant on commodity hardware. |
| 4 | **Replay-friendly event spine** | Kafka retention (7d default, tunable) means consumer crashes don't lose data. db-writer down for 6 hours? It catches up automatically when restarted. No data loss in transit. |
| 5 | **Stateless application services** | api-service and ws-bridge hold no state. Adding capacity = adding replicas. Each replica owns its own DB pool, so connection limits scale linearly. |
| 6 | **Source-of-truth traceability** | Every `app.device_point` row links to `source.point_catalog` via FK. Every alert references the rule that fired and the point that breached. Every agent action lands in `audit.events`. Forensics work. |
| 7 | **No MySQL runtime dependency** | One fewer DB engine to operate. Unicharm IBMS data is one-time imported into `source.ibms_readings`. After that, OMNYX runs entirely on PostgreSQL + Kafka + Redis + Keycloak. |
| 8 | **Open-source, on-premise viable** | Every component is Apache 2.0 / BSD / MIT licensed (see [`docs/poc/31_OPENSOURCE_LICENSING.md`](docs/poc/31_OPENSOURCE_LICENSING.md)). No vendor lock-in. Air-gapped deployments work. |
| 9 | **Observability built-in from day 0** | Prometheus + Grafana + Loki + Alloy. Every service exposes `/metrics`. Every log gets shipped. We can answer "why is p95 latency up?" without redeploying. |
| 10 | **Modern dev tooling** | TypeScript everywhere on the Node side, Pydantic on Python side, Zod at API boundaries. Strong types = fewer runtime surprises. |

---

## 3 · What's INCOMPLETE for production (the honest cons)

> Every item below is a **known risk that exists today** if you ran this stack against real customers. None are insurmountable; all need explicit planning before launch.

### 3.1 — High-Availability Gaps (P0 — must fix before any paying customer)

| Risk | What can happen | Today | Mitigation needed |
|---|---|---|---|
| **Single Kafka broker** | Broker dies → all event flow stops. If it dies during a write, the in-flight messages are lost (replication_factor=1) | 1 broker, RF=1 | 3-broker cluster, RF=3, `min.insync.replicas=2` |
| **Single postgres instance** | Disk fails or process crashes → entire app DB unavailable. No replica to fail over to. | 1 instance, no replica | Streaming replica + Patroni/Stolon for automated failover |
| **Single timescaledb instance** | Same as above for time-series | 1 instance | Read replica (TimescaleDB supports streaming replication) |
| **No backups configured** | Zero recovery story. Volume corruption = full data loss. | No backup automation | pgBackRest with daily full + WAL archive, off-site copy |
| **No PITR (point-in-time recovery)** | Can't restore to "5 minutes before the incident" | No WAL archive | WAL archiving to S3/MinIO, retention 30 days |
| **Single Redis** | Loss of session cache, BullMQ jobs in-flight | 1 instance, no AOF persistence yet | Redis Sentinel (HA) or Cluster, enable AOF for queue durability |
| **Single Keycloak** | Auth outage = no logins possible. Existing tokens still valid until expiry. | 1 node, file-based H2 cache | Keycloak cluster (2+ nodes) with Infinispan replicated cache, external postgres backing store |
| **No connection pooler** | Beyond ~50 concurrent users, postgres connection slots exhaust | api-service holds direct connections | PgBouncer in transaction-pooling mode in front of both DBs |
| **No graceful shutdown drills** | SIGTERM may interrupt in-flight writes | Not tested | Add shutdown handlers (db-writer flushes, api-service drains) + test |

### 3.2 — Multi-Site Gaps (P1 — must fix before 2nd site)

| Risk | What can happen | Today | Mitigation needed |
|---|---|---|---|
| **No edge buffering** | If WAN to central goes down, telemetry is lost | dal-bacnet publishes direct to central Kafka | Per-site local Kafka, MirrorMaker 2 → central |
| **No site failure isolation** | One site's runaway producer can fill central Kafka | Shared Kafka | Per-tenant Kafka client quotas; topic-per-tenant or partition-per-tenant strategy |
| **No DR site** | Datacenter outage = full platform down | Single DC | Cross-region async replica, RPO ~5min target |
| **Latency-sensitive paths assume colocation** | ws-bridge → frontend across WAN will degrade | Not yet measured | CDN for frontend, edge ws-bridge per region |

### 3.3 — Multi-Tenant Gaps (P1 for >5 tenants, P0 if any tenant is regulated)

| Risk | What can happen | Today | Mitigation needed |
|---|---|---|---|
| **Noisy neighbour at Kafka level** | One tenant's burst saturates broker | Shared topics | Kafka client quotas per producer, partition strategy by tenant_id |
| **Noisy neighbour at DB level** | Big query from tenant A slows tenant B | Shared postgres + timescaledb | `statement_timeout` (already set), connection pool quotas per tenant via PgBouncer, ultimately schema-per-tenant or DB-per-tenant for premium |
| **RLS misconfiguration** | Forgotten `SET app.current_tenant_id` returns 0 rows (safe-failure) but a *missing* RLS policy on a new table would leak | RLS enabled on all current `app.*` tables, but new tables must be added explicitly | Add a CI test that checks every table in `app.*` has RLS enabled; alembic migration template includes RLS step |
| **No per-tenant audit trail isolation** | Tenant A's admin can see audit logs structurally, RLS protects but is one bug away | RLS-protected | Same fix as above + immutable audit log writer role |

### 3.4 — Operational Gaps (P1)

| Risk | Today | Mitigation needed |
|---|---|---|
| **Secrets in `.env` files** | `change-me` defaults present | Vault / Docker secrets, rotation policy |
| **No CI/CD** | Manual `docker compose build` | GitHub Actions: build → unit → integration → push to registry → deploy |
| **No SLO / SLI** | "It feels fast" | Define: p99 < 500ms, ingestion lag < 30s, uptime 99.9%, then alert on burn rate |
| **No runbook for common incidents** | Tribal knowledge | One markdown per scenario: Kafka broker down, postgres replica lag, OOM kill, certificate expiry |
| **No load testing** | We don't know the breaking point | k6/Locust scripts with realistic tenant + reading rates |
| **No chaos testing** | We don't know what breaks first | Kill a service, fill a disk, sever the network, observe |

### 3.5 — Phase 1 Feature Gaps (Gate 3 work, in progress)

| Gap | Impact |
|---|---|
| `agentic-ai` is a stub | No AI workflows fire — Workflow A/B/C from PRD not yet wired |
| `dq-etl` is a stub | No Tier 2 DQ — no drift detection, no baseline profiling |
| `twin-broker` is a stub | No FDD, no RUL — predictive maintenance promise unfulfilled |
| `rl-broker` is a stub | No optimization — efficiency gains promise unfulfilled |
| `dal-replay` has no implementation | Can't bulk-import Unicharm history yet |

---

## 4 · "Are we risking data loss?"

**Today, on this POC stack: YES if a broker, postgres, or timescaledb instance dies hard.**

Specifically:
- **Kafka broker dies hard** (kernel panic, disk corruption) → messages that haven't been flushed to disk are lost. With RF=1 there is no replica to recover from. Window: typically <5 seconds of data depending on `flush.ms` settings.
- **postgres dies hard** → app DB unavailable until restored from… nothing yet, since no backups are scheduled.
- **timescaledb dies hard** → telemetry DB unavailable; raw readings since last db-writer commit may be in Kafka and recoverable on restart.

**Risk windows by scenario (current POC stack):**

| Scenario | Data loss window | Recovery time | Acceptable for? |
|---|---|---|---|
| api-service crash | 0s (stateless) | <30s | Production |
| ws-bridge crash | 0s (state held in Kafka) | <30s | Production |
| db-writer crash | 0s (Kafka retains 7d) | Auto-catchup | Production |
| dal-bacnet crash | 0s if BACnet device buffers; few seconds if not | <60s | Production with caveat |
| Kafka broker crash | ~5s of in-flight messages, possibly more without RF | Manual restart 1–5min | **POC only** |
| postgres process crash | Active transactions rolled back; no data loss if disk intact | <60s restart | **POC only** |
| postgres disk failure | **Total app DB loss without backup** | **Unrecoverable today** | **NOT acceptable** |
| timescaledb disk failure | Last few hours of compressed chunks + everything since last Kafka commit window | Partially recoverable from Kafka if within 7d | **NOT acceptable** |
| Datacenter outage | **Total platform loss** | **Unrecoverable today** | **NOT acceptable** |

**Bottom line:** the current stack is **safe for the Unicharm POC and demos**. It is **not safe for paying customers** until P0 items in §3.1 are done. That work is documented in detail in [`Gate 4` of `SERVICES.md`](SERVICES.md) and tracked as Phase 4 / Production Hardening.

---

## 5 · Scaling Tiers — pick the tier, then the architecture

| Tier | Customer profile | What stack looks like | Effort to reach |
|---|---|---|---|
| **T0 — POC / Demo** *(today)* | 1 site, ~100 devices, ~363 points, 1 tenant, <5 concurrent users | Single-replica everything, no backups, single DC | **Done** |
| **T1 — Small Prod** | 1 site, 100–500 devices, 1 tenant, ~50 users, 99.5% uptime | + pgBackRest backups + PgBouncer + 3-broker Kafka + Redis Sentinel + Keycloak HA pair + WAL archive + monitoring alerts | **~3 weeks** focused work |
| **T2 — Multi-Site Prod** | 10 sites, ~5k devices, 1–5 tenants, 200 users, 99.9% uptime | T1 + per-site edge Kafka with MirrorMaker 2 + postgres streaming replica + timescaledb replica + DR site + per-tenant quotas | **~6 weeks** after T1 |
| **T3 — Multi-Tenant SaaS** | 50+ tenants, 50+ sites, regulated industries, 99.95% uptime | T2 + schema-per-tenant for premium + Kafka topic-per-tenant + per-tenant DB instances optional + SOC 2 audit prep + RBAC review | **~3 months** after T2 |
| **T4 — Enterprise / Sovereign** | Per-customer dedicated deployment, air-gapped, mandatory data residency | T3 + Kubernetes operator + Helm charts + dedicated VPC per tenant + cross-region DR + 24/7 NOC | **~6 months** after T3 |

**Where we are: T0. Where Unicharm needs us: T1. Where the product roadmap aims: T3.**

---

## 6 · Recommended sequence to de-risk

### Now (this week, parallel to Gate 2/3 work)
1. **Schedule pgBackRest** for both postgres and timescaledb — daily full, hourly incremental, 30-day retention. Without this we cannot recover from disk failure. Cost: ~3 hours.
2. **Document a restore drill** — "from a fresh server with only the backup, how do we get back?" Run it. Time it. Cost: ~1 day.
3. **Enable PgBouncer** in front of postgres (transaction pool, default_pool_size=20). Without this we will hit `max_connections` at ~50 users. Cost: ~half a day.
4. **Turn on Kafka producer acks=all** (currently default=1). This costs ~5ms per message but prevents the "broker accepted but didn't fsync" data loss window. Cost: ~1 hour.

### Before Unicharm production (Gate 4 hardening — Tier T1)
5. **3-broker Kafka cluster** with RF=3 — single-broker is the biggest risk.
6. **Postgres streaming replica + Patroni** for automated failover.
7. **TimescaleDB streaming replica** (read-only, can also serve dashboards).
8. **Redis Sentinel** for cache + BullMQ durability.
9. **Keycloak HA pair** with Infinispan shared cache, postgres backing.
10. **Monitoring alerts**: broker down, replica lag, disk >80%, p99 latency >1s, certificate expiry, error rate >1%.

### Before second customer / second site (Tier T2)
11. **Edge Kafka per site** + MirrorMaker 2 → central — survives WAN outage.
12. **Per-tenant Kafka topic partitioning** — `telemetry.raw.<tenant_id>` to isolate noisy neighbours.
13. **Cross-region DR** — postgres async replica in a second region, RPO 5min.
14. **Disaster Recovery drill** — fail over to DR, prove it works.

### Before multi-tenant SaaS (Tier T3)
15. **Schema-per-tenant** option for premium customers (requires migration tooling change).
16. **Per-tenant connection pool quotas** via PgBouncer.
17. **CI-enforced RLS check** — every new table in `app.*` must have RLS or build fails.
18. **SOC 2 / ISO 27001 evidence collection** — audit logging, access reviews.

---

## 7 · What WON'T scale — anti-patterns we are explicitly avoiding

| Anti-pattern (don't do this) | Why we say no | What we do instead |
|---|---|---|
| One Postgres for everything (telemetry + app) | Hypertable compression interferes with OLTP indexing, backup windows balloon | 2-DB split |
| Per-equipment tables (`chiller_1_normalized`, `chiller_2_normalized`, …) — the Unicharm legacy shape | DDL change on every new device, impossible at 1000+ devices | Generic `telemetry.readings` hypertable, dimension model in `app.equipment` |
| MySQL anywhere in the runtime | Second DB engine to license, patch, back up, train ops on; no native time-series partitioning; no pgvector | All PostgreSQL |
| Schema-per-tenant from day 1 | 100 tenants = 100 schemas to migrate every time we ship DDL | RLS first; schema-per-tenant only for premium customers when justified |
| HTTP polling from frontend | At 1000 devices × 5s polling = 200 req/s per user, melts the API | WebSocket snapshot + delta |
| Direct DB writes from agents | Bypasses audit log, breaks RBAC, no rollback | Every agent action goes through api-service tool gateway |
| Vendor-specific time-series DB (InfluxDB, kdb+) | Lock-in, separate query language, no SQL joins | TimescaleDB — it's just PostgreSQL |
| Per-site cloud rendering | Customer data leaves the perimeter | On-prem first, cloud as opt-in extension |

---

## 8 · The Verdict

**Is this design reliable and scalable? Yes — *for the tier it's targeted at*.**

- **For T0 (POC):** Yes, with the caveat that we shouldn't promise SLAs.
- **For T1 (small production):** Yes, after the 4 "now" items + 5 "before Unicharm prod" items in §6 are done. ~3 weeks of focused work.
- **For T2 (multi-site):** Yes, after T1 plus the multi-site items. ~6 more weeks.
- **For T3 (multi-tenant SaaS):** Yes, after T2 plus schema isolation work. ~3 more months.

**Are we risking data loss right now?** Only if we put paying customers on the current POC stack without doing the §6 "Now" items first.

**Should we keep building features (Gate 2 → Gate 3) before hardening?** Yes for POC — features prove the product. **No after the demo lands** — hardening must precede the first paying customer.

> **The plan is sound. The execution sequence matters more than any individual technical choice. Don't ship to production until Tier T1 items are checked off.**

---

## 9 · Assumed On-Site Usage Scenarios — What Actually Happens In The Field

> These are the **real-world scenarios** we are designing for. Every architectural choice in §1 maps back to at least one of these. If a future scenario isn't in this list, we may have built the wrong thing.

### Site Profile — Unicharm Thailand (POC, today)

| Attribute | Value |
|---|---|
| Sector | Personal hygiene manufacturing — diapers, sanitary products |
| Site | Single factory, Chennai, India |
| Footprint | ~1 building, 5 floors, plant room + production block A/B |
| HVAC scale | 11 DDC controllers (`DDC01..DDC10` + 2 sub-controllers), 363 BACnet points |
| Equipment types | 2× chillers, 1× cooling tower, 3× AHUs, 1× FCU controller, 2× pumps, primary + secondary plant |
| Data volume | ~363 points × 1 sample / 5 sec = ~73 readings/sec ≈ 6.3M readings/day ≈ 2.3B/year (raw, uncompressed) |
| Concurrent users | 5–20 (plant ops + AI engineers + managers) |
| Uptime expectation | 99.5% (POC); 99.9% post-cutover |
| Network | On-prem; office WiFi to field BACnet via Ethernet; Tailscale VPN for remote ops |

### Scenario 1 — Daily Morning Operations (08:00 plant supervisor login)

**Actors:** Plant Supervisor, Maintenance Engineer
**Frequency:** Every weekday, 08:00 IST

1. Supervisor opens [http://omnyx.unicharm.local](http://omnyx.unicharm.local) on the plant terminal.
2. Logs in via Keycloak (`unicharm-admin`).
3. Lands on **Dashboard** — sees:
   - Live KPI cards: active devices (should show 11), open alerts (target: <5), open work orders (target: <10), readings/min
   - **ECharts** live telemetry: chiller supply/return temps, cooling tower water levels, plant kW
   - Device snapshot table — 11 DDCs, green status indicators
4. Reviews overnight alerts (`/alerts`) — 2 high-priority alerts from 03:00–06:00 window need ack.
5. Acknowledges both, creates a work order from alert #1, assigns to maintenance engineer.
6. Closes browser by 08:15.

**What the architecture must do:**
- Dashboard renders < 2s (continuous aggregates `readings_1m` from TimescaleDB, not raw scan)
- Live telemetry chart updates every 5s via WebSocket (ws-bridge → frontend)
- Alert list query < 200ms (indexed on `tenant_id, status, created_at DESC`)
- Work-order create writes atomically to `app.work_orders` + `audit.events` in one transaction

**Failure modes & how we handle them:**
- ws-bridge dies during view → frontend reconnects with exponential backoff, no manual refresh needed
- TimescaleDB slow → dashboard falls back to "last cached value" via Redis (after Gate 4 caching layer)
- Network blip → frontend shows offline banner, queues acks locally (after Gate 4 PWA)

### Scenario 2 — Critical Alert at 02:30 (chiller approaching trip)

**Actors:** On-call maintenance engineer (phone), Plant Supervisor (informed)
**Frequency:** Expected 1–3 times/month

1. Chiller-1 condenser pressure exceeds threshold for 5 minutes.
2. `dal-bacnet` reads the BACnet point at COV (3% change).
3. Reading flows: BACnet → dal-bacnet → Kafka (`telemetry.raw`) → db-writer → TimescaleDB.
4. **Alert evaluator** (in api-service, runs every 30s) reads `app.alert_rules`, sees rule "Chiller-1 high condenser pressure", queries TimescaleDB latest reading, detects breach, inserts row into `app.alerts` (severity=critical).
5. Notification pipeline: alert → `app.notifications` → email/SMS webhook (Gate 4) → on-call engineer's phone.
6. Engineer opens mobile-friendly frontend, sees the alert, looks at the chart (last 30 min trend), acknowledges.
7. **Agentic AI** (Gate 3) workflow "B — Critical Alert Response" triggers: queries the digital twin for RUL prediction, generates a draft work order with recommended actions, files an **approval request** (`app.approval_requests`, tier 2).
8. Engineer approves the work order in the app → work order created, assigned to himself.
9. Engineer arrives on-site by 03:00, performs maintenance.
10. Updates work order status to `completed`, alert auto-resolves.

**What the architecture must do:**
- End-to-end latency from BACnet read to alert in DB: **< 30 seconds** (5s BACnet poll + 5s Kafka + 5s db-writer + 15s evaluator interval)
- Alert evaluator must not miss breaches even if it runs late — dedup logic in `openAlertIfNew()`
- Notification webhook must retry on failure (idempotent — same alert ID won't double-notify)
- Agentic workflow must be auditable — `app.agent_runs.trigger_payload` records the firing alert; `audit.events` records every tool call

**Failure modes & how we handle them:**
- Alert evaluator down → alerts fire late but still fire on next cycle (gap detected in `audit.events`, on-call paged)
- Kafka broker down → dal-bacnet buffers locally up to 1 hour (Gate 4); after that, samples lost
- Agentic AI off / Claude API down → tier-2+ approvals queue up, engineers handle manually; system degrades gracefully

### Scenario 3 — Weekend Plant Watchdog (Saturday/Sunday, unattended)

**Actors:** None on-site; plant runs autonomously
**Frequency:** Continuous, every weekend

1. Plant runs unattended for 48 hours.
2. ~50,000 readings/hour flow through Kafka → TimescaleDB.
3. **DQ Tier 1** (in dal-bacnet, today): every reading gets `quality_flag` and `dq_flags`.
4. **DQ Tier 2** (in dq-etl, Gate 3): runs nightly drift detection, baseline profiling, gap reconciliation. Updates `app.data_quality_config`.
5. **Digital Twin** (twin-broker, Gate 3): runs every 15 minutes against chiller/cooling tower models, writes residuals + RUL predictions to `telemetry.twin_predictions`.
6. **RL Broker** (Gate 3, shadow mode): suggests setpoint changes; writes to `telemetry.rl_decisions` without acting.
7. If a critical event fires, the alert flow from Scenario 2 kicks in.
8. Monday 08:00 — supervisor returns to a dashboard showing weekend summary, any alerts/work orders that fired, RL suggestions to review.

**What the architecture must do:**
- Survive 48 hours unattended without human intervention.
- Auto-compress TimescaleDB chunks older than 7 days (so disk doesn't fill).
- Auto-drop raw readings older than 90 days (retention policy).
- All scheduled jobs (dq-etl, twin-broker, rl-broker) must self-recover from crashes — restart policies + watchdog.

**Failure modes & how we handle them:**
- Power outage on Saturday → UPS holds for 15 min; if longer, all services come up cleanly on restart, telemetry resumes (Kafka retains 7d, no data loss for the gap that the UPS covered).
- Disk fills up → Prometheus alert fires Saturday morning, ops gets paged Sunday remotely.
- BACnet device disconnects → dal-bacnet's `dal_devices_offline` metric goes >0, alert fires.

### Scenario 4 — Maintenance Window Migration (DDC firmware upgrade)

**Actors:** Maintenance engineer + OMNYX engineer
**Frequency:** Quarterly per DDC

1. Maintenance engineer schedules a 30-minute window, notifies operations.
2. OMNYX engineer marks `DDC03` as `is_active=false` in `source.ddc_registry` (so alerts are suppressed during expected downtime).
3. Engineer physically updates DDC firmware.
4. During the window, dal-bacnet logs `Device offline: DDC03`. No alerts fire (RLS-aware suppression).
5. Engineer powers DDC back on; dal-bacnet auto-reconnects.
6. OMNYX engineer flips `is_active=true`; alerts resume.
7. Continuous aggregates show a gap — Tier 2 `gap_reconciler` (Gate 3) interpolates or marks the window.

**What the architecture must do:**
- Provide an "in-maintenance" status without re-deploying services.
- Audit log every flip of `is_active` in `audit.events`.
- Backfill gaps cleanly when possible.

### Scenario 5 — New Equipment Onboarding (factory expansion adds DDC11)

**Actors:** Operations engineer, plant supervisor
**Frequency:** A few times/year per site

1. Plant adds a new chiller + DDC controller (`DDC11`) in Block C.
2. Operations engineer adds a row to `simulations/gl_pbs/data/eqp_name_handling.csv` listing the new DDC's points (or in production: reads the BACnet device discovery and writes to `source.point_catalog`).
3. Engineer inserts row into `source.ddc_registry`:
   ```sql
   INSERT INTO source.ddc_registry (ddc_id, name, ip_address, bacnet_port, building, location)
   VALUES ('DDC11', 'New AHU Block C', '10.0.1.211', 2012, 'Block C', 'Level 1');
   ```
4. Engineer inserts equipment row in `app.equipment`:
   ```sql
   INSERT INTO app.equipment (tenant_id, source_ddc_id, name, type, subtype, building, location, metadata)
   VALUES ('unicharm', 'DDC11', 'New AHU Block C', 'ddc', 'ahu', 'Block C', 'Level 1', '{}');
   ```
5. Inserts the new points into `source.point_catalog` + `app.device_points`.
6. Restarts `dal-bacnet` (or hot-reload after Gate 4).
7. Telemetry from DDC11 begins flowing into Kafka → TimescaleDB.
8. New equipment appears on the frontend equipment page automatically (no frontend deploy needed).

**What the architecture must do:**
- Add equipment without code changes or redeploys.
- Foreign keys keep data consistent (`device_points.equipment_id` references `equipment.id`).
- TimescaleDB hypertable accepts new `point_id` automatically — no DDL needed.

### Scenario 6 — Multi-Site Rollout (Year 2)

**Actors:** OMNYX deployment team, customer ops
**Frequency:** 5–10 sites/quarter at peak

1. New factory in another city/country needs OMNYX.
2. Customer deploys an "edge stack" on-site: dal-bacnet + local Kafka buffer + MirrorMaker 2.
3. Central OMNYX adds the new site to `app.tenants` (or a sub-tenant model) + `source.ddc_registry` rows for the new site's DDCs.
4. MirrorMaker 2 streams local Kafka → central Kafka.
5. Central db-writer ingests, ws-bridge fans out, dashboards include the new site.
6. Site-level dashboards available locally even if WAN goes down (edge stack has its own ws-bridge).

**What the architecture must do:**
- **Edge stack** — dal-bacnet + local Kafka + local cache must survive WAN outages.
- **Tenant routing** — every event carries `tenant_id` from the start, never inferred at the central side.
- **Site isolation** — a runaway producer at site B can't saturate central Kafka (per-site quotas).
- **Central consolidation** — analytics across sites possible via timescaledb central instance.

**Requires Tier T2 architecture (see §5).**

### Scenario 7 — Auditor / Compliance Review (annual)

**Actors:** External auditor, internal compliance officer
**Frequency:** Annually, plus ad-hoc

1. Auditor asks: "show me every setpoint change to Chiller-1 in the last 12 months and who made it."
2. Compliance officer logs in, navigates to `/audit` page (or queries `audit.events` directly with read-only role).
3. Query returns immutable log entries for every API call that touched the chiller setpoint — actor (user or agent), timestamp, before/after values, work order link if any.
4. Auditor asks: "show me every Tier 3+ AI action and the human who approved it."
5. Query joins `app.agent_runs` + `app.approval_requests` + `app.users` to produce the report.
6. Auditor verifies that every Tier 3+ action has an approver and that the chain is intact.

**What the architecture must do:**
- **Append-only audit log** — `audit.events` has no UPDATE/DELETE permissions on the writer role.
- **Every state-changing API call writes to audit** — enforced in api-service middleware.
- **Agentic AI actions are first-class auditable** — every tool call lands in audit, every approval has a paper trail.
- **Retention** — audit data kept for 7 years (compliance norm). Pure PG table, partitioned by year for performance.

### Scenario 8 — Disaster Recovery Drill

**Actors:** OMNYX ops team
**Frequency:** Quarterly (mandatory at Tier T2+)

1. Ops chooses a maintenance window.
2. Simulates a full datacenter loss — kills the primary DC's services.
3. **DR site** (Tier T2+) takes over: postgres replica promotes to primary, timescaledb replica promotes, Kafka MirrorMaker 2 inverts direction.
4. Frontend DNS flips to DR site.
5. Customers see ~5 min outage; new connections route to DR.
6. After validation, ops fails back to primary.

**What the architecture must do:**
- Replica with **defined RPO (~5 min)** and **RTO (~10 min)**.
- Automated promotion via Patroni — no manual SQL.
- Customers don't need to know which site is serving them (DNS routing).
- Audit log captures the failover event.

**Requires Tier T2 architecture (see §5). Not in scope for POC.**

---

## 10 · Capacity Planning — Real Numbers For The Unicharm Site

| Metric | Today (POC) | T1 (Unicharm prod) | T2 (10 sites) |
|---|---|---|---|
| DDC controllers | 11 | 11 | 110 |
| BACnet points | 363 | 363 | 3,630 |
| Readings/sec | ~73 | ~73 | ~730 |
| Readings/day | 6.3M | 6.3M | 63M |
| Raw storage/year | ~140 GB | ~140 GB | ~1.4 TB |
| Compressed storage/year (TimescaleDB compression after 7d) | ~14 GB | ~14 GB | ~140 GB |
| Kafka throughput | ~30 KB/sec | ~30 KB/sec | ~300 KB/sec |
| Concurrent users (peak) | ~5 | ~20 | ~100 |
| Concurrent DB connections (api-service) | ~10 | ~50 (needs PgBouncer) | ~200 |
| Dashboard p95 latency target | <2s | <1s | <1s |
| Alert evaluation latency | <30s | <30s | <30s |
| End-to-end ingestion lag (BACnet → DB) | <15s | <10s | <10s |

**TimescaleDB on commodity hardware** (8 cores, 32GB RAM, 1TB NVMe SSD) easily handles all three tiers. Postgres primary DB is much smaller (config + alerts + work orders + audit ≈ <10 GB/year for one tenant).

**Conclusion:** the bottleneck is **not** the database. It's **availability** (replicas + backups) and **operations** (monitoring + runbooks + on-call). That's where the Gate 4 work goes.

---

## 11 · References

- Architecture overview — [`docs/poc/02_ARCHITECTURE.md`](docs/poc/02_ARCHITECTURE.md)
- Database design — [`docs/poc/08a_DATABASE_DESIGN.md`](docs/poc/08a_DATABASE_DESIGN.md)
- Tech stack — [`docs/poc/03_TECH_STACK.md`](docs/poc/03_TECH_STACK.md)
- Service access & ops — [`SERVICES.md`](SERVICES.md)
- Test plan — [`docs/poc/17_TEST_PLAN.md`](docs/poc/17_TEST_PLAN.md)
- Open-source licensing — [`docs/poc/31_OPENSOURCE_LICENSING.md`](docs/poc/31_OPENSOURCE_LICENSING.md)
- Hardware requirements — [`docs/poc/36_HARDWARE_REQUIREMENTS.md`](docs/poc/36_HARDWARE_REQUIREMENTS.md)

---

*This document is opinionated by design. If you disagree with a tradeoff, open a PR — but justify the change against the §5 scaling tiers.*
