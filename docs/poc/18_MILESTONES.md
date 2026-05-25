# 18 · Milestones — 12 weeks to a demoable end-product

A focused critical path. One engineer can run this; two cuts it ~30 %. Targets align with PRD §11 Phase 1 (MVP Core).

| Week | Theme | Concrete deliverables | Demo at end of week |
|---|---|---|---|
| W1 | Foundation | `omnyx/` repo skeleton (done), compose stack up: Kafka + Postgres + Redis + Keycloak + Prometheus + Grafana. Realm + seed scripts. | `docker compose up`, login at frontend stub, Kafka UI green. |
| W2 | Storage & migrations | Postgres migrations (telemetry + app + audit + embeddings). Seed scripts: equipment, points, DQ config from Unicharm DDL. `dal-replay` skeleton. | `make seed-unicharm`; SELECT from `app.equipment` returns the Unicharm tree. |
| W3 | Edge + Kafka | `dal-bacnet` reads simulator (port the gl_pbs read strategy verbatim), publishes `PointBatch` JSON. `db-writer` persists to `telemetry.readings`. | Live BACnet → Kafka → Postgres; rows visible in `telemetry.readings`. |
| W4 | DQ Tier 1 | Inline pipeline (8 checks), `QualityEnvelope`, `dq.events`. Config-driven from `data_quality_config`. Fault-injection script. | `--freeze` demo flips a flag end-to-end. |
| W5 | WS bridge + Frontend shell | `ws-bridge`. React shell with Keycloak auth, Portfolio + Device pages, live snapshot. | Login → portfolio dashboard pulses in real time. |
| W6 | Rules engine + Alerts | Rule evaluation in api-service, alert inbox UI, ack/resolve. Notifications stub. | Threshold trip in simulator → alert visible in UI in < 30 s. |
| W7 | Work orders + Approvals | `app.work_orders` model + UI (Kanban + kiosk). Approval API + UI. | Manual WO flow end-to-end on tablet. |
| W8 | Twin (1 model) | `twin-broker` w/ `chiller_v1` physics twin. Calibrate from replayed data. FDD engine, RUL extrapolator. `twin.fdd.alerts`. UI twin overlay on Device page. | `--drift` demo produces a twin alert with RUL prediction. |
| W9 | RL (1 agent) | `rl-broker` w/ `chiller_efficiency_v1` agent. Offline train on replay, deploy SHADOW. Reward dashboard. | RL dashboard shows reward curve vs baseline. |
| W10 | Agentic AI | `agentic-ai` with Planner/Executor/Validator on Claude. Tool gateway in api-service. Workflows A (alert), B (daily report), C (drift). Activity feed UI. | Twin FDD critical → autonomous WO creation visible in agent activity feed. |
| W11 | DQ Tier 2 + Sensor health | `dq-etl` jobs: drift, baseline, cross-sensor, gap reconciler, score rollup. Feedback loop to DAL. DQ dashboard. | Drift detected by ETL → coefficient pushed → DAL applies it within 15 m. |
| W12 | Hardening + Demo | Tests from `17_TEST_PLAN.md`, Grafana OMNYX overview dashboard, runbook polish, demo dry-runs. | Six-step demo storyline ([01 §5](01_SCOPE_AND_SUCCESS.md)) runs cleanly twice in a row. |

## Buffers and parallelism notes

- Weeks 4 ↔ 5 ↔ 6 are partially parallel (DQ inline + frontend shell + rules engine touch different files).
- Twin and RL bootstrap (W8/W9) can be sped up if there's a second engineer — they're isolated services.
- Auth/Keycloak realm is built in W1 but only fully wired into routes from W5 onward.
- `dal-replay` (W2) is required for W8/W9 because both twin and RL need historical context to be useful.

## Done means

- All 17 tests in [17_TEST_PLAN.md](17_TEST_PLAN.md) pass twice in a row.
- The six-step demo runs without engineer intervention.
- Compose `docker compose up -d` from a fresh clone reaches green in < 5 min after `make seed-*`.
- The repo includes a recorded demo video (10–15 min) and a one-page leadership brief.
