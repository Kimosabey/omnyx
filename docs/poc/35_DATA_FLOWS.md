# 35 · Data Flows (every scenario, end-to-end)

Companion to [02_ARCHITECTURE.md](02_ARCHITECTURE.md). That doc shows what exists; this doc shows **how data moves** through it. Read each section as one scenario, top to bottom.

Conventions
- `═══>` synchronous (HTTP)
- `── >` asynchronous (Kafka)
- `<<-->>` WebSocket
- numbers in `①②③` mark order

---

## Flow 1 — Live telemetry: BACnet device → user's screen

```
①  DDC controller (real or simulator)
       │ BACnet/IP UDP
       │ presentValue + statusFlags + reliability
       ▼
②  dal-bacnet                                         (Python, host net)
   ├─ RPM (15 objects/batch); single-read fallback   [from RCA fix]
   ├─ COV filter (3 %, override per point)
   ├─ DQ Tier 1 inline (8 checks, <50 ms)
   │     completeness · timestamp · range · frozen ·
   │     spike · rate · semantic · imputation route
   ├─ attach QualityEnvelope
   └─ batch into PointBatch
       │
       │ ── > Kafka topic  raw.bacnet.{device_id}     [partition by device_id]
       │
   ┌───┴───────────┬──────────────┬──────────────┬──────────────┐
   ▼               ▼              ▼              ▼              ▼
③ db-writer    ws-bridge     twin-broker    rl-broker     agentic-ai
   │               │              │              │              │
   │ ───>          │              │              │              │
   ▼               │              ▼              ▼              │
④ TimescaleDB   ⑤ keep state    twin step     observation     planner gets
   telemetry.   for snapshot    + FDD         update            triggered only
   readings     every 5 s       + RUL                            on alerts
   (hypertable,
    compressed
    after 7d)
                   │
                   │ <<-->> WebSocket
                   ▼
⑥  React client    PlantSnapshot received, UI repaints
                   p95 latency from ① to ⑥ < 5 s
```

Notes
- Every consumer reads independently from Kafka. db-writer can lag without blocking the WS bridge.
- The same `PointReading` JSON shape is consumed in five places; no per-consumer adapter code.
- If db-writer crashes, Kafka retains 7 days — replay catches it up.

---

## Flow 2 — Write-back (operator or RL agent → device)

```
①  user clicks "Set chiller_1 chw_setpoint = 7.5 °C"   (or RL agent decides)
       │
       │ ═══>  POST /api/v1/tools/write_setpoint  { device, point, value }
       ▼
② api-service tool gateway
   ├─ Auth (Keycloak JWT, role check)
   ├─ Tier-3 approval gate
   │     if not auto-approved → POST /approvals/request → wait for verdict
   ├─ Safety bounds check vs app.rl_safety_bounds
   ├─ audit.events INSERT (actor, tool, args, approval_id)
   └─ produce BacnetCommand
       │
       │ ── > Kafka topic  cmd.bacnet.{device_id}
       ▼
③ dal-bacnet consumes
   ├─ BACnet WriteProperty (priority 16)
   ├─ wait for SimpleAck or Error
   └─ produce reply
       │
       │ ── > Kafka topic  reply.bacnet.{request_id}
       ▼
④ api-service consumes reply
   ├─ resolves the original HTTP request
   ├─ audit.events INSERT (result)
   ▼
⑤ HTTP response  { status: ok | error, value_after: 7.5 }
   │
   │ also: next read cycle re-reads presentValue; UI sees the new value live
```

Notes
- Writes are **never** in the synchronous HTTP path beyond the queue submit; user / agent gets an ack within ms, the real BACnet write completes async.
- Approval gate is enforced server-side; client cannot bypass.

---

## Flow 3 — Rule-based alert (threshold breach)

```
②  point lands in api-service via Kafka raw.bacnet.* consumer (rules engine)
   │
   ├─ evaluate every rule for that point_id
   │     threshold | offline | anomaly | delta | semantic
   │
   ├─ if rule fires (and hold-time satisfied):
   │     INSERT app.alerts
   │     │
   │     │ ── > Kafka topic  alerts.changed
   │     ▼
   ws-bridge picks up
   │     ▼
   ⑤ React inbox shows new alert toast within 1 s
   │
   │ also fan-out to:
   │
   ├─ agentic-ai (if rule has linked workflow)
   ├─ notifications worker (email / SMS / inapp)
   └─ escalation_runner (schedules step-2..N timers per config)
```

Within 30 s of the breach the operator sees the alert — see [17 T3.3](17_TEST_PLAN.md).

---

## Flow 4 — Digital twin FDD → autonomous WO

```
①  raw.bacnet.* lands in twin-broker
   │
② twin-broker
   ├─ step twin physics with incoming inputs
   ├─ compute residual; z-score vs baseline_profiles
   ├─ if  z >= 3  persistent ≥ N samples:
   │     diagnose fault (lookup app.fault_codes)
   │     estimate RUL
   │     │
   │     │ ── > Kafka topic  twin.fdd.alerts
   │     ▼
③ db-writer       INSERT app.alerts (source='twin_fdd', payload={...})
③ ws-bridge       PlantSnapshot now shows twin_status='alert'
③ agentic-ai      Workflow A "Investigate Alert" triggers
                     │
                     ▼
④  Planner ─► Executor ─► Validator
       (calls get_twin_diagnosis, get_history,
        create_work_order, assign_technician, send_notification)
       │
       ▼
⑤ app.work_orders new row appears in technician kiosk within ~30 s of step ②.
```

Total ① → ⑤ under 1 minute. Matches PRD MVP target "WO creation-to-dispatch < 10 min".

---

## Flow 5 — Data Quality two-tier loop

```
Tier 1 inline (DAL)                                Tier 2 async (dq-etl)
═══════════════════════════                         ════════════════════════════

every reading:                                      hourly / daily jobs:

  PointReading                                       sensor_drift_estimator
       │                                              baseline_profiler
       ▼                                              cross_sensor_validator
  Tier 1 checks                                      gap_reconciler
       │                                              quality_score_rollup
       ├─ flag = GOOD/SUSPECT/IMPUTED/BAD/MISSING    rl_experience_cleaner
       ├─ emit QualityEvent to dq.events            twin_calibration_feeder
       └─ publish PointBatch                        sampling_irregularity_report
                                                                │
                       ┌─── feedback loop ────────────────────┐ │
                       │                                       ▼ ▼
                       └──── data_quality_config (DB) ◄── writes drift_coefficient,
                                                            bias_offset, baselines

DAL refreshes config every 15 min → new readings drift-corrected automatically
```

Twin and RL receive flag-aware readings (see [06 §4](06_DATA_QUALITY_LAYER.md) matrix). No bad value reaches FDD or RL.

---

## Flow 6 — Agentic AI workflow (e.g. "Investigate Alert")

```
⓪ Trigger
   alert created (twin_fdd or rule)  ── > Kafka topic alerts.changed
                                           or scheduler tick (BullMQ)
                                           or POST /agents/run (operator)
   │
   ▼
① agentic-ai orchestrator                                  app.agent_runs row created (status=running)
   │
   ├─ Planner (Claude Opus)
   │     reads alert + tools registry + recent precedent (RAG + agent_runs)
   │     emits AgentEvent(kind="thought") ── > agent.activity
   │     produces plan: [step1: get_twin_diagnosis, step2: ..., approval_tier:2]
   │
   ├─ Executor (Claude Sonnet)
   │     for each step:
   │        emits AgentEvent(kind="tool_call")  ──>
   │        ═══> POST /api/v1/tools/{name} ............... api-service
   │                 │
   │                 ├─ RBAC + tier check
   │                 ├─ if tier >= 3: approval gate (pause + emit "approval_request")
   │                 ├─ execute (DB / Kafka / external)
   │                 └─ audit.events row
   │        ←═══ result
   │        emits AgentEvent(kind="tool_result")
   │
   ├─ Validator (Claude Sonnet, separate context)
   │     re-fetches the artifacts (WO, alert, etc.)
   │     verifies match plan expectation
   │     emits AgentEvent(kind="done" or kind="replan")
   │
   └─ orchestrator finalises
       update app.agent_runs.status, tokens_used, cost_usd
       audit.events summary row

UI: agent activity feed shows every step in <1 s, live, via WS.
```

If anything fails: loop guard, budget cap, validator rejection → workflow aborts or replans. All in [11_AGENTIC_AI](11_AGENTIC_AI.md).

---

## Flow 7 — Reinforcement Learning shadow / live

```
   raw.bacnet.* ──> rl-broker
                      │
                      ├─ assemble observation vector (only GOOD-flag points)
                      ├─ pass through policy network
                      ├─ action proposal
                      │
                      ├─ if SHADOW:
                      │     INSERT telemetry.rl_actions (applied=false)
                      │     ── > Kafka rl.actions
                      │     UI shows action on the reward dashboard
                      │
                      ├─ if LIVE:
                      │     check safety bounds
                      │     if Tier 3+: route via approval
                      │     ═══> POST /tools/write_setpoint (or change_mode)
                      │     INSERT telemetry.rl_actions (applied=true, approved_by)
                      │     ── > Kafka rl.actions
                      │
                      └─ reward computation
                            pull next-step readings (already in DB)
                            compute reward per reward_config
                            INSERT rl_actions.reward
                            feeds nightly retraining

Nightly:
   dq-etl rl_experience_cleaner removes IMPUTED/BAD experience rows
   rl-broker retrainer fits new policy, version bumped, gated by safety check
```

---

## Flow 8 — Unicharm history replay

```
ONE-TIME during cutover

unicharm MySQL                                       dal-replay (Python)
═══════════════                                       ════════════════════
chiller_1_normalized       ─── SELECT (1-day batches)
chiller_2_normalized       ─── SELECT
cooling_tower_*_normalized ─── SELECT
condenser_pump_*_normalized─── SELECT
primary_pump_*_normalized  ─── SELECT
plant_normalized           ─── SELECT
                              │
                              ├─ map each row → N PointReading
                              │   (using app.device_points.legacy_table/_column)
                              ├─ flag = GOOD, tier2_validated = true
                              ├─ source = "replay"
                              │
                              │ ── > Kafka raw.bacnet.{device_id}
                              ▼
                          (same db-writer / twin-broker / rl-broker consumers)
                              │
                              ▼
                          telemetry.readings hypertable

Progress kept in `replay_progress`; resumable.
After completion: MAX(measured_at) == Unicharm MAX(slot_time)
```

Twin calibration and RL bootstrap then read from `telemetry.readings` with `source='replay' OR source='bacnet'` indistinguishably — see [08a §13](08a_DATABASE_DESIGN.md).

---

## Flow 9 — User login (auth)

```
① browser → frontend                ② frontend redirects to Keycloak
③ Keycloak login form (Realm: omnyx) → JWT
④ frontend stores access token + refresh token (httpOnly cookies)
⑤ every API call attaches Authorization: Bearer <JWT>
⑥ api-service @fastify/jwt verifies against JWKS endpoint (cached)
⑦ req.user.roles populated; RBAC + ABAC enforced
⑧ DB session: SET LOCAL omnyx.tenant_id = ... (for RLS)
⑨ refresh every 5 min in background; force re-login at 30-min idle
```

Service-to-service calls use a separate confidential client (`omnyx-agents`) — see [14_AUTH §2](14_AUTH_KEYCLOAK.md).

---

## Flow 10 — Approval gate (Tier 3+)

```
agent or user attempts a Tier-3 tool call
        │
        ▼
api-service                                              app.approvals INSERT (status=pending)
        │
        ├─ if user has direct Tier-3 role → continue immediately
        └─ else
              │
              │ ── > Kafka approvals.requested
              ▼
         operator inbox /approvals shows it (WS push)
              │
              │ operator clicks Approve / Reject
              │ ═══> POST /approvals/{id}/decide
              ▼
api-service
   ├─ verify decider has manager role (Tier 4) or operator (Tier 3)
   ├─ UPDATE app.approvals (status=approved/rejected, decided_by)
   ├─ audit.events row
   ├─ emit approval token (15-min JWT, single-use, hash-bound to original args)
   └─ resume the queued tool call → execute
              │
              ▼
        original caller (agent or operator) gets a delayed 200 OK or 403
```

---

## Flow 11 — Configuration bundle apply (new site onboarding)

```
admin runs:
   POST /api/v1/admin/bundles/apply { yaml-payload }
        │
        ▼
api-service
   ├─ validate schema (Zod)
   ├─ diff against current state per tenant
   ├─ show diff to admin → confirm
   ├─ apply in a transaction:
   │     INSERT rules, dq_config, twin_models, rl_agents, agent_workflows, pm_templates
   │     UPDATE equipment.twin_model_id / rl_agent_id where applicable
   ├─ audit.events row per change
   ├─ notify dq-etl to refresh
   └─ notify rl-broker to reload agents
```

POC ships three bundles (`unicharm_hvac`, `generic_hvac`, `demo_synthetic`).

---

## Flow 12 — Backup + restore (operational)

```
Nightly cron (host or k8s CronJob)
   make backup-pg
        │
        ├─ pg_dump --format=custom omnyx → ./backups/omnyx-YYYY-MM-DD.dump
        ├─ encrypt with customer-supplied key
        └─ rclone copy ./backups/ to minio://omnyx-backups/

Restore drill (weekly):
   spin up scratch Postgres
   pg_restore latest dump
   run smoke queries (row counts, MAX(measured_at) etc.)
   record drill outcome in audit.events
```

---

## Master service-interaction matrix

| From ↓ To → | dal-bacnet | api-service | ws-bridge | db-writer | twin-broker | rl-broker | agentic-ai | dq-etl | postgres | kafka | redis | keycloak | LLM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dal-bacnet | — | — | — | — | — | — | — | — | — | producer | — | — | — |
| api-service | — | — | — | — | REST | REST | — | — | RW | producer+consumer | RW | JWKS | — |
| ws-bridge | — | — | — | — | — | — | — | — | — | consumer | — | JWKS | — |
| db-writer | — | — | — | — | — | — | — | — | writer | consumer | — | — | — |
| twin-broker | — | REST | — | — | — | — | — | — | reader | consumer+producer | — | — | — |
| rl-broker | — | REST | — | — | REST (simulate) | — | — | — | RW | consumer+producer | — | — | — |
| agentic-ai | — | REST (tools) | — | — | — | — | — | — | reader | producer | — | token | yes |
| dq-etl | — | — | — | — | — | — | — | — | RW | producer | — | — | — |
| frontend (browser) | — | REST | WSS | — | — | — | — | — | — | — | — | OIDC | — |

(`RW` = read-write; `JWKS` = verifies token via Keycloak JWKS endpoint; `token` = uses service-account client.)

---

## How to read this with the rest of the docs

- For *what* exists → [02_ARCHITECTURE](02_ARCHITECTURE.md)
- For *how it moves* → this doc (you're here)
- For *what to call* → [27_API_REFERENCE](27_API_REFERENCE.md) + [11_AGENTIC_AI §3](11_AGENTIC_AI.md)
- For *what it looks like in storage* → [08a_DATABASE_DESIGN](08a_DATABASE_DESIGN.md)
- For *how it fails and recovers* → [19_RISKS](19_RISKS.md) + [23_SECURITY §10](23_SECURITY.md)
