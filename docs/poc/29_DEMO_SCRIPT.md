# 29 · Demo Script (15-minute leadership walk-through)

Tight, scripted run that proves every PRD claim end-to-end. Designed to be rehearsed twice and recorded once.

## 0 · Pre-checks (5 min before demo, no audience)

- All terminals open and pre-titled.
- Browsers logged in as: `demo_admin`, `demo_operator`, `demo_tech` (kiosk).
- Grafana "OMNYX overview" dashboard open in last tab.
- `make smoke` returned green within the last hour.
- Simulator launcher already running with 11 DDCs.
- DAL running, db-writer caught up (Kafka lag = 0).
- Kafka UI shows healthy partitions.

If any of those is red, **don't start** — fix first.

---

## Act 1 — "What is OMNYX?" (1.5 min)

Open the landing screen, login.

> "OMNYX is the universal IoT operations platform from Graylinx. One on-premise install, every site, every equipment type. Today I'll show you the HVAC vertical — THERMYNX — running on top of OMNYX, fed by a simulated Unicharm-style plant. Everything you'll see runs on this laptop. No cloud."

Show the sidebar: `OMNYX · by Graylinx`. Click `/` Portfolio.

> "One site, 21 devices, 500 telemetry points. Health score 100, no critical alerts. Live telemetry from BACnet at 5-second WebSocket cadence."

Hover a tile — show the metric strip update in real time.

---

## Act 2 — "Real-time monitoring + digital twin" (2 min)

Click into `chiller_1` device.

> "This is the device detail page. Solid line is the actual reading. Dashed line is the digital twin's prediction running in parallel — physics-based, calibrated from Unicharm's last 90 days of operation."

Point at the residual heat strip.

> "Twin and reality are tracking. If they diverge beyond tolerance, the Twin FDD engine raises a fault with a root cause and a remaining-useful-life estimate."

---

## Act 3 — "Inject a sensor fault" (2 min)

Switch terminal to fault injector.

```bash
python scripts/inject_dq_fault.py --freeze chiller_1.evap_leaving_temp --seconds 600
```

> "I just froze the evaporator leaving-temperature sensor on the simulator."

Switch to `/dq` page. Within ~60 s, the sensor flips amber, flag distribution shows `BAD`.

Switch to `/alerts`. New alert appears: `SENSOR_FROZEN` on `chiller_1.evap_leaving_temp`, severity critical.

> "Tier 1 data quality caught the freeze in seconds — before it ever reached the twin or RL or the rule engine. Twin paused FDD on that parameter so we don't get a cascade of false diagnoses."

---

## Act 4 — "Agentic AI responds" (3 min)

Switch to `/agents`. The "Investigate Alert" workflow has already fired.

> "We don't ask a human to investigate this. Workflow A — Planner, Executor, Validator — already started."

Walk the activity feed:

> "Planner read the alert, decided to: gather context, validate it's a real sensor fault, open a calibration WO, notify the calibration team."
> "Executor called `get_sensor_drift_history`, `get_last_calibration_date`, `create_work_order`, `assign_technician`, `send_notification`."
> "Validator re-fetched the work order, confirmed it matches the diagnosis, marked the run done."

Switch to `/work-orders`. New WO open. Click into it.

> "Auto-assigned to a technician with `mechanical-l1` skill, lowest current load. Diagnosis populated, recommended parts attached. From sensor freeze to dispatched WO: under 60 seconds, fully autonomous."

Switch to tech kiosk browser. WO is in their inbox.

---

## Act 5 — "Twin RUL + RL" (3 min)

Back to demo terminal:

```bash
python scripts/inject_dq_fault.py --drift chiller_1.kw_per_tr --slope 0.005 --hours 24 &
```

> "Now I'm injecting a slow performance drift — kW/TR creeping up. That's how bearing wear looks before it becomes a failure."

Switch to `/twin/chiller_1`. RUL countdown visible, fault tree highlights `BEARING_WEAR`.

> "Twin caught it. Predicted failure window: 14 days. Plenty of time for planned PM instead of emergency repair."

Switch to `/rl`. Reward curve for `chiller_efficiency_v1` in shadow mode.

> "Reinforcement Learning agent has been shadow-running for 14 days. Reward is consistently above the baseline — about 7 % better setpoint policy. Zero safety violations. One more week of shadow data and we promote to live, with the AI Ops Specialist's sign-off."

---

## Act 6 — "It scales" (2 min)

Switch to Grafana "OMNYX overview".

> "Kafka: 1 % CPU. Postgres: 2 % CPU. End-to-end latency p95 under 5 seconds. Data quality 99.8 % GOOD. Validator rejection 0 %."

Switch to Kafka UI, point at throughput.

> "Right now we're at 10 messages a second. In stress testing on this same laptop we've hit 5,000 — enough for 100 sites on this hardware. The PRD's target is 50–500 sites; we have headroom even on commodity edge gateways."

---

## Act 7 — "What you're seeing in numbers" (1 min)

Switch to one slide / `/admin/status`.

> "Eight PRD modules, all running:
> — Real-time monitoring ✅
> — Alerting + Twin FDD ✅
> — RL optimisation (shadow) ✅
> — Agentic AI with Planner/Executor/Validator ✅
> — Analytics + reports ✅
> — Work orders with smart dispatch ✅
> — Portfolio + multi-site + RBAC ✅
> — Integration: BACnet today, OPC-UA / Modbus / MQTT slot in via the same adapter interface."

> "Everything on premises. The customer's data never leaves their network. The LLM has an Ollama fallback for air-gap demands."

---

## Act 8 — "What's next" (0.5 min)

> "POC is the MVP. v2 adds factory/water verticals, plant-level RL coordination, custom workflow builder UI, CMMS integration. v3 adds federated learning across sites and fully autonomous mode."

End screen: `OMNYX · by Graylinx · Universal IoT Operations Platform`.

---

## Recovery scripts (if anything fails mid-demo)

| Symptom | Quick fix |
|---|---|
| `/alerts` doesn't show new alert | `docker compose logs --tail=50 api-service` and `dq-etl` — usually a missed COV; retry inject |
| Agent activity feed stuck | `docker compose restart agentic-ai`; the run restarts |
| Twin chart blank | `docker compose restart twin-broker`; chart catches up within 30 s |
| Kafka UI showing high lag | Open Grafana, point at panel and continue talking; the system always catches up within the demo |

If something is irrecoverable, end the storyline at Act 4 — the autonomy demo is the strongest beat and is independent of Acts 5+.
