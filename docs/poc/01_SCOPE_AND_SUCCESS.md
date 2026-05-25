# 01 · Scope, Goals and Success Criteria

## 1 · POC Definition

POC here = the **production-shaped OMNYX Phase 1 baseline**: same on-prem services, schema,
APIs, deployment model, and product boundaries that go to the first beta customer, but exercised
through a **single-site BACnet/HVAC path** fed by the simulator instead of real DDCs.

This is **not** a throwaway demo. It is also **not** proof that every protocol/vendor path named in
the master PDF is exercised on the dev laptop. The clean way to read the scope is documented in
[38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md):

- **Operational at POC gate** — built and exercised in the 12-week plan
- **Phase 1 contract, not gate-blocking** — onboarding/customer-specific capabilities already in the product boundary
- **Deferred** — explicitly v2/v3

## 2 · Operational at the POC gate

These are the things that must work end-to-end in the simulator-backed gate review.

| Layer | Gate scope |
|---|---|
| Protocol | BACnet/IP via gl_pbs simulator (11 DDCs, 363 points) |
| Edge | BACnet reader + DQ Tier 1 + Kafka producer (replaces `kafka_bacnet_bridge.py`) |
| Pipeline | Kafka 7.6 (KRaft, no zookeeper) with `raw.bacnet.*`, `cmd.bacnet.*`, `health.*` topics |
| Storage | PostgreSQL 16 + TimescaleDB (telemetry hypertable + relational tables for assets, work orders, alerts, DQ config) |
| DQ Tier 2 | ETL jobs in Python (drift, cross-sensor, baseline profiler, gap reconciler, RL experience cleaner) |
| Digital Twin | `twin-broker` hosting at least 1 physics twin (chiller or AHU) + FDD engine + RUL |
| RL | `rl-broker` hosting 1 shadow agent optimising one setpoint |
| Agentic AI | Planner / Executor / Validator on Claude with tool registry; 4 workflows available, 3 exercised in the core demo |
| Backend | Fastify REST + WebSocket plant snapshot + rules engine + scheduler |
| Frontend | React 18 SPA with portfolio dashboard, device detail, twin overlay, agent activity feed, kiosk-mode work order view |
| Auth | Keycloak with `admin / manager / operator / technician / analyst / ai_ops_specialist / readonly` roles |
| Monitoring | Prometheus + Grafana + Kafka UI |
| Deployment | Single-host Docker Compose; everything required for the gate runs on one box |

## 3 · Phase 1 contract that is not gate-blocking

These capabilities are still part of the shipping Phase 1 product boundary, but they are mainly
exercised during onboarding or a customer deployment rather than the six-step laptop demo.

| Area | Phase 1 interpretation |
|---|---|
| Commissioning workflow | Shipped as runbook + admin APIs + bundle apply flow, not as a separate visual commissioning UI yet |
| Source onboarding | Legacy MySQL import, CSV import, and BACnet discovery are all part of the supported commissioning path |
| Device / point mapping | `app.equipment`, `app.device_points`, and config bundles are the shipping mapping layer |
| Live config push | Bundle/API driven; services consume the updated config via their normal refresh paths |
| API contract | REST + OpenAPI + WebSocket are the shipping interfaces |
| HVAC breadth | Gate demo is Unicharm-style chiller plant, but the product boundary is HVAC-first rather than permanently chiller-only |
| BMS / customer integrations | BACnet path is the exercised baseline; customer-specific vendor bridges sit behind the same product boundary and are handled per deployment plan |

See [30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md),
[35_DATA_FLOWS.md](35_DATA_FLOWS.md), and
[38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md).

## 4 · Explicitly deferred to v2 / v3

- Multi-site federation
- Runtime Modbus / OPC-UA / MQTT adapters (the abstraction is preserved; BACnet is the only exercised adapter now)
- CMMS / ERP / MES bi-directional sync
- On-prem LLM as the primary/default path (Claude API is fine for the POC; Ollama remains the fallback)
- Mobile native apps (tablet kiosk view in React is enough)
- Auto-tuning thresholds / federated learning / RL sim-to-real loop
- HA runtime topology (single broker, single DB are fine for the gate; hardened HA topologies are documented separately)
- Factory vertical execution in the 12-week POC

## 5 · API decision

The master PDF mentioned REST + GraphQL. The shipping Phase 1 decision in this repo is:

- **REST + OpenAPI + WebSocket ship**
- **GraphQL does not ship in Phase 1**

This keeps one audited surface for both humans and agents. See
[27_API_REFERENCE.md](27_API_REFERENCE.md) and
[38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md).

## 6 · Success Criteria (PRD-aligned, scaled to the POC gate)

These are the MVP metrics from the PRD §03, restated against what the simulator actually produces
(2.1 msg/s real with CoV at 3%, ~363 points):

| PRD MVP target | POC measurable demonstration |
|---|---|
| 95% uptime of telemetry per site | Edge → Kafka → DB writer runs 24 h with zero gaps > 30 s in the gap registry |
| Multi-site dashboard < 2 s | Portfolio view loads in < 2 s with 1 site of 11 DDCs (we extrapolate; sized to scale) |
| Alert delivery < 30 s | Synthetic threshold breach in simulator fires an Alert Inbox entry < 30 s later |
| Twin FDD detects faults >= 24 h before failure | Scripted slow-drift in simulator → twin RUL prediction matches injected timeline within 10% |
| RL gain >= 10% within 30 days | Shadow agent reduces setpoint deviation cost by >= 10% vs baseline in offline twin replay |
| Agentic AI: 60% autonomous workflows | Of 100 simulated alerts, >= 60 close end-to-end with no human approval (Tier 1 / 2 actions only) |
| Telemetry latency < 5 s | From simulator publish to WebSocket frame in browser, p95 < 5 s |
| Agentic AI wrong actions < 5% | Validator rejection rate <= 5% over the demo run |
| WO creation -> dispatch < 10 min | Twin FDD alert -> auto-created WO appears in technician kiosk view in < 1 min |

## 7 · Demo Storyline (what we show to leadership)

1. Open Portfolio Dashboard (React) — 1 site, 11 DDCs green.
2. Drill into `DDC09` / `chiller_1` — live trend + twin overlay.
3. Inject a sensor freeze on the simulator — within seconds:
   - DQ Tier 1 flags the point `BAD/FROZEN`
   - Alert Inbox shows `SENSOR_FROZEN`
   - Agentic AI Planner -> Executor opens a calibration work order, attaches drift history, notifies the calibration team
   - Validator confirms the WO; agent activity feed shows the full trace
4. Open Twin Diagnostics — replay a slow bearing-wear drift; RUL countdown updates; FDD predicts failure window.
5. Open RL dashboard — shadow agent showing reward curve vs baseline.
6. Open Grafana — Kafka ~1% CPU, telemetry latency p95 < 5 s, DQ flags >= 99% GOOD.

If those six steps run cleanly, the POC is complete for the **gate review**.

The broader Phase 1 boundary that will matter during real customer onboarding is captured in
[30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md) and
[38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md).
