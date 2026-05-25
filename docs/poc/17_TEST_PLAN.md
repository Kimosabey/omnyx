# 17 · Test Plan

Each PRD MVP success metric gets one or more concrete tests. Pass = the metric is demonstrated on the POC stack with the simulator + replayed Unicharm data.

## 1 · Pipeline reliability

| Test | How | Pass criterion |
|---|---|---|
| T1.1 Telemetry uptime ≥ 95 % | Run dal-bacnet + simulator for 24 h; count gaps via `telemetry.quality_events WHERE event_type='MISSING'` | `total_gap_seconds / 86400 < 0.05` |
| T1.2 Kafka lag bound | `kafka-consumer-groups --describe` for db-writer, ws-bridge | lag < 1 000 for db-writer, < 100 for ws-bridge sustained |
| T1.3 Backpressure recovery | Pause db-writer for 5 min, resume | DAL queue drains within 2 × pause; no in-memory overflow |

## 2 · Data quality (Tier 1 + Tier 2)

| Test | How | Pass criterion |
|---|---|---|
| T2.1 Frozen detection | `inject_dq_fault.py --freeze` for 10 min | `FROZEN/BAD` flag within `window_samples` × poll_interval; `SENSOR_FROZEN` alert raised |
| T2.2 Spike filter | `--spike --magnitude 50` | Single spike is SUSPECT, no threshold alert fires |
| T2.3 Range check | Submit -300°C via simulator HTTP | Flagged BAD immediately, twin pauses FDD for that param |
| T2.4 Drift correction round-trip | Run Tier 2 `sensor_drift_estimator` against rigged data | `data_quality_config.drift_coefficient` updates within run; DAL refreshes within 15 min; subsequent readings carry `drift_corrected=true` |
| T2.5 Imputation LKG | Silence DDC for 3 min | Flag MISSING, LKG values pass; no spurious threshold alerts |
| T2.6 Widespread event | Silence > 30 % of devices | `WIDESPREAD_QUALITY_EVENT`, twin + RL pause |

## 3 · Latency & UI

| Test | How | Pass criterion |
|---|---|---|
| T3.1 Telemetry to WS | Inject value via simulator; observe browser timestamp | p95 < 5 s |
| T3.2 Dashboard cold load | Hard refresh `/` with 1 site | < 2 s to first interactive |
| T3.3 Alert delivery | Threshold-trip via simulator | UI alert appears < 30 s |
| T3.4 WO create-to-dispatch | Twin FDD critical alert → auto-WO → tech kiosk | < 1 min end-to-end |

## 4 · Digital Twin FDD

| Test | How | Pass criterion |
|---|---|---|
| T4.1 Detection lead time | `--drift kw_per_tr --slope 0.005 --hours 24` | Critical FDD alert fires ≥ 24 h before injected fault threshold |
| T4.2 Root cause string | Same test | Alert `payload.fault_code` matches injected mode; `payload.root_cause` non-empty |
| T4.3 RUL accuracy | Same test | RUL prediction within 10 % of injected timeline at T-24h |
| T4.4 Twin pause on BAD input | Freeze a twin-input sensor | Twin marks `fdd_active=false` for that parameter; no false FDD alerts during the freeze |

## 5 · Reinforcement Learning

| Test | How | Pass criterion |
|---|---|---|
| T5.1 Shadow training | Train on 90 d replay buffer | Validation reward > baseline by ≥ 5 % on held-out 14 d |
| T5.2 Reward curve | Run 24 h shadow on live stream | Reward improves and stays above baseline; no safety violations |
| T5.3 RL pause on widespread DQ event | Run T2.6 alongside | `mode` flips to `PAUSED`, no actions emitted |
| T5.4 KPI ≥ 10 % improvement | Replay simulation comparing baseline period vs RL period | `mean(kw_per_tr_baseline) − mean(kw_per_tr_rl) ≥ 10 % * baseline` |

## 6 · Agentic AI

| Test | How | Pass criterion |
|---|---|---|
| T6.1 Workflow A autonomy | 100 simulated alerts (mix of severities) | ≥ 60 % close end-to-end without human approval (Tier 1–2 only) |
| T6.2 Validator catches errors | Inject a fake "WO created" by corrupting a tool reply | Validator rejects, requests replan |
| T6.3 Wrong actions < 5 % | Same 100-alert run | ≤ 5 alerts mis-handled (wrong WO or wrong tech) |
| T6.4 Approval gating | Tier 3 tool called by agent | Workflow pauses, `/approvals` shows pending; resumes on `approve`, aborts on `reject` |
| T6.5 Loop guard | Construct a workflow that calls the same tool 6× | Aborts at 5, emits escalation event |
| T6.6 Cost ceiling | Run T6.1 | Total Anthropic cost reported by `agent_runs` aggregates within configured monthly budget |

## 7 · Replay / Migration

| Test | How | Pass criterion |
|---|---|---|
| T7.1 Row parity | After dal-replay, run queries in [08_STORAGE §5.3](08_STORAGE_TIMESCALEDB.md) | Counts match per equipment |
| T7.2 Timestamp parity | Same | `MAX(measured_at)` in new = `MAX(slot_time)` in unicharm ± 1 min |
| T7.3 Twin can train on replay | Run twin calibration job | Model fit R² ≥ 0.9 on chiller_v1 outputs |
| T7.4 Agentic AI can query history | Tool `query_historical_trends` for 30-day window | Returns rows that match a direct SQL query |

## 8 · Auth & RBAC

| Test | How | Pass criterion |
|---|---|---|
| T8.1 Role gating | Log in as `demo_operator`, hit `/api/v1/admin/users` | 403 |
| T8.2 Approval token | Try Tier-3 tool without approval | 403 |
| T8.3 Service-account flow | `omnyx-agents` token exchanges and calls a Tier-2 tool | 200 with `audit.events` row |

## 9 · Resilience

| Test | How | Pass criterion |
|---|---|---|
| T9.1 Restart any container | `docker compose restart <svc>` | Service rejoins, no data loss in Kafka, UI recovers within 15 s |
| T9.2 Network blip simulate | `iptables` drop UDP for 30 s | DAL recovers, MISSING flags fired, network_watchdog resumes BACnet |
| T9.3 Kafka broker down 60 s | Stop kafka container | DAL buffers in memory; on resume, no readings lost |

## 10 · Reporting / Compliance

| Test | How | Pass criterion |
|---|---|---|
| T10.1 Daily report generated | Wait until 06:00 trigger | PDF saved + emailed; Validator approved; numbers match a direct SQL query |
| T10.2 Audit trail | Run any Tier-3 action | `audit.events` row with actor, action, target, payload |
| T10.3 Immutable audit | Try to `UPDATE` an audit row | DB role permissions prevent (only `audit_writer` can `INSERT`) |

## 11 · Performance ceilings (informational)

| Test | How | Reference |
|---|---|---|
| P1 100 msg/s | `stress_test_kafka.py --rate 100 --duration 30` | Already proven: 99 msg/s, 9.2 % host CPU |
| P2 500 msg/s, 10x | `--rate 500 --scale 10` | 494 msg/s, 11.3 % host CPU |
| P3 5 000 msg/s synthetic | `--mode synthetic --rate 5000` | 4 931 msg/s, 42 % host CPU |

These re-validate the [KAFKA_VERDICT](../../../../simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md) numbers on the same hardware OMNYX runs on.
