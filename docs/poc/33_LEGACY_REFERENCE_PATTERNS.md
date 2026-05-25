# 33 · Useful Patterns from Legacy Graylinx (Jupiter) Backend & Frontend

Findings from a scan of `D:\Harshan\graylinx-be\gl_jupiter\` (Node.js + Express + MySQL "iBMS" backend) and `D:\Harshan\graylinx-fe\jupiter_ui\` (React + Material-UI legacy SPA). **We are not importing this code.** We are extracting domain knowledge that should shape OMNYX behaviour so the new product matches what Graylinx already does well.

## 1 · CPM — Control Process Module (worth absorbing)

Legacy `CPM/` + `CPM_modular/` runs continuous decision loops over plant state. Key constructs to bring into OMNYX:

| Legacy concept | OMNYX home |
|---|---|
| `decision_engine.js` — rule-driven start/stop logic for chillers, pumps, towers | RL agents + rules engine. Where the legacy used hard-coded heuristics, OMNYX uses safety-bounded RL with the same effect |
| `CPM_Data_Handler.js` — gathers inputs, normalises, dispatches | `dal-bacnet` Tier 1 DQ + `api-service` snapshot |
| Sequence of Operations (SoO) | Will become an Agentic AI workflow set per equipment combination (chiller-pump-tower start sequence) in v2 |
| Auto / Manual mode toggle | OMNYX exposes via `change_mode` Tier-3 tool + the `equipment.state.mode` field; matches operator's mental model |
| 15-second control tick | Mirrored by `interBatchInterval = 0.1 min` (6 s) on the DAL; RL agent decisions every 60 s by default |

We make the CPM **explicit** in OMNYX: every control action shows up as an `rl_action` row or an `audit.events` row from an agent tool call. The legacy CPM was a black box; OMNYX's version is auditable.

## 2 · Alarm module (already aligned)

Legacy `alarm_module.js` runs every 5 seconds; categorises Critical / Non-Critical; tracks acknowledgement + restoration. Already in OMNYX:

| Legacy | OMNYX |
|---|---|
| Critical / Non-Critical | `app.alert_severity` enum (`info | warning | critical`) |
| Ack / Restore | `app.alerts.acknowledged_at`, `resolved_at`, `resolved_by` |
| 5 s check loop | Rules engine evaluates on every Kafka batch (∼1 s tick) |
| Alarm history | `audit.events` + `app.alerts` |

## 3 · iKW/TR and run-hour accounting (carried into OMNYX)

Legacy provided real-time efficiency (iKW/TR) and run-hour KPIs. OMNYX surfaces both natively:

| Legacy KPI | OMNYX surface |
|---|---|
| `iKW/TR` per chiller | First-class `chiller_*.kw_per_tr` point; chart on device detail; THERMYNX efficiency band view |
| Plant aggregate kW/TR | `plant.kw_per_tr` computed in Tier 2 + continuous aggregate |
| Run hours per equipment | `<device>.run_hours` point, integrated by Tier 2 `quality_score_rollup` job into `app.equipment.metadata.run_hours` snapshot |
| Heatmaps | THERMYNX vertical retains heat-map components in `/extensions/thermynx/*` |

## 4 · Schedule engine (legacy → OMNYX)

| Legacy | OMNYX |
|---|---|
| `Gl_Schedules` service + `schedules.js` | `app.schedules` table + BullMQ worker (api-service scheduler) |
| BMS-resident schedules | Documented as **out** of OMNYX — we own scheduling at the platform layer |
| One-off + recurring | Same cron string in `app.schedules.cron` |

## 5 · Energy analytics module (legacy → THERMYNX extension)

`Gl_IBMS_Analytics`, `Energy_analytics`, `gl_analytics_schema.js` — the analytics that fed dashboards. OMNYX core stays domain-agnostic; the energy-specific KPIs live in the **THERMYNX** vertical, fed from the canonical `telemetry.readings` hypertable.

Specifically:
- Daily / weekly / monthly energy rollups → continuous aggregates + Tier-2 jobs.
- BTU/TR-h cumulative counters → derived KPIs computed on read or as cagg expressions.
- Cost analysis (tariff × kWh) → THERMYNX-only feature, with tariff table per tenant.

## 6 · Frontend (legacy `jupiter_ui/`)

| Legacy choice | OMNYX choice | Why we change |
|---|---|---|
| Material-UI v3/v4 era | Chakra UI 2 (continues THERMYNX line) | Already proven in the THERMYNX product; consistent feel |
| Chartist + jQuery in places | Recharts only | Modern, React-native, one chart lib |
| Webpack + Gulp | Vite 5 | Faster dev loop, smaller bundles |
| Server-rendered EJS for some pages | All SPA, REST + WS | One front-end paradigm |

Legacy frontend's strongest pages worth re-creating in OMNYX:
- Live SLD (single-line diagram) for chiller plant — becomes a Site view widget in v2.
- Alarm console with critical/non-critical split — already in OMNYX `/alerts`.
- Run-hour cards per equipment — adopted on device detail page.

## 7 · Database lessons (what to avoid)

Legacy MySQL had:
- `gl_subsystem`, `gl_subsystem_latest_event` — the "latest value" pattern. **OMNYX replaces with Redis cache + WS snapshot**, never reads a "latest" table on the hot path.
- Mixed-schema timeseries tables. **OMNYX replaces with one generic hypertable**.
- Composite keys with varchar(36) UUIDs. **OMNYX keeps text PKs for stable readable IDs** (`chiller_1` not `9ada01f6-…`) and uses UUIDs only where uniqueness across customers matters.

## 8 · API surface (what carried over and what didn't)

Legacy `Routes/v1/*` + `Services/*` had ~30 resource groups. OMNYX consolidates:

| Legacy area | OMNYX |
|---|---|
| `Gl_user`, `Auth`, `Auth2` | Keycloak |
| `Gl_Device`, `Bacnet`, `Building`, `Floor`, `Area`, `Campus`, `GlZone` | `app.equipment` + hierarchy in [08a](08a_DATABASE_DESIGN.md) |
| `Gl_Alerts`, `Alerts` | `app.alerts` |
| `Gl_Schedules` | `app.schedules` |
| `Cpm`, `Control` | RL broker + tool gateway |
| `Energy_analytics`, `Gl_IBMS_Analytics`, `Gl_analytics`, `Gl_reports`, `Gl_reports1` | Continuous aggregates + reports service + agent-generated reports |
| `Gl_calc_engine` | Tier-2 ETL jobs |
| `DataUpload` | `POST /admin/knowledge` + `POST /admin/bundles/apply` |
| `Backup` | `make backup-pg` + ops runbook |
| `Coworking`, `CustomerApi` | Out of POC; integration framework in [20 §M8.2](20_MODULE_COVERAGE.md) |

## 9 · BACnet integration (already noted)

`hvacBACnetClient.js` and `myBACnetUtils.js` are skipped — we use Python `bacpypes` at the edge per [32 §16](32_BACNET_SIGNAL_CATALOGUE.md).

## 10 · Things NOT to copy

- The 15-second polling using `setInterval` driving everything. Brittle. OMNYX uses event-driven Kafka consumers.
- Direct DB writes from BACnet handler. OMNYX always goes Kafka → db-writer.
- HTTPS termination inside `app.js`. OMNYX terminates at the reverse proxy.
- MAC-address licence verification. Replaced by Keycloak service-account model.
- `sql_mode` resets on startup. Postgres doesn't need this.

## 11 · One-time scan & migrate plan

Combined for Unicharm + Jupiter legacy:

1. Inventory legacy DB tables → OMNYX `app.*` mapping (see [`../migration/UNICHARM_TO_OMNYX.md`](../migration/UNICHARM_TO_OMNYX.md)).
2. Catalogue alarms in `gl_alarm` → seed `app.rules` with equivalent rules.
3. Catalogue CPM decision rules → seed initial `app.rl_agents.safety_bounds` and `app.rules` of kind `state`.
4. Catalogue schedules in `gl_schedule` → seed `app.schedules`.
5. Read SoO documents (`Doc/`) → seed `app.agent_workflows` for plant start-up.

After cutover, the Jupiter backend gets the same 90-day read-only retention + decommission timeline as the Unicharm MySQL.
