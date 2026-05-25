# 06 · Data Quality Layer (Tier 1 inline + Tier 2 ETL)

Implements the two-tier design from [CloudOps_Data_Quality_Layer.docx](../source/prd/CloudOps_Data_Quality_Layer.docx) verbatim. This is what protects Twin / RL / Alerts from garbage in.

## 1 · Why both tiers are needed

| Subsystem | Consumes data from | Protected by ETL alone? |
|---|---|---|
| Digital Twin FDD | Raw telemetry stream | ❌ No |
| RL Agent | Live state observation | ❌ No |
| Alerting Engine | Pre-storage telemetry | ❌ No |
| DWH reporting | ETL-cleaned warehouse tables | ✅ Yes |

The legacy HVAC platform leans entirely on Unicharm's upstream ETL (`*_metric` / `*_om_p` → `*_normalized`). For real-time twin / RL / agentic this is too late — we need inline cleaning.

## 2 · Tier 1 — inline at the DAL (target < 50 ms / point)

Lives in `dal-bacnet/dq/`. Runs between BACnet read and Kafka publish.

```
BACnet read
   └─ COV filter (3 %)
        └─ Tier 1 pipeline
              ├─ 1. Completeness check (null, NaN, parse-fail)
              ├─ 2. Timestamp normalize (UTC, drift, latency)
              ├─ 3. Range check (hard physical limits)
              ├─ 4. Frozen detection (rolling window std-dev)
              ├─ 5. Spike filter (z-score against rolling mean)
              ├─ 6. Rate-of-change check
              ├─ 7. Semantic / cross-sensor check (equipment-type rules)
              ├─ 8. Flag attach + imputation routing
              └─ Kafka publish PointBatch (with QualityEnvelope on every reading)
```

Every check is **configurable per `point_id`** via the `data_quality_config` table. DAL refreshes the config every 15 minutes (or on Kafka `dq.config.changed` event).

### 2.1 Each check, in detail

| # | Check | Detection | What we set |
|---|---|---|---|
| 1 | Completeness | Value is `None`, NaN, or unparseable | `flag=MISSING`, route per `on_missing` |
| 2 | Timestamp | `received_at - measured_at > max_latency` (default 60 s) | `flag=STALE`, store with historical timestamp, do not push to live twin |
| 3 | Range | Outside `[hard_min, hard_max]` for the point type | `flag=BAD`, `detail={"type":"RANGE","val":...}` |
| 4 | Frozen | `std(window_samples) < std_dev_threshold` for N samples | `flag=BAD`, `detail={"type":"FROZEN","samples":N}` |
| 5 | Spike | `|val − rolling_mean| > z_score_threshold * rolling_std` | `flag=SUSPECT`, median filter applied |
| 6 | Rate-of-change | `|dv/dt| > max_delta_per_minute` | `flag=SUSPECT`, rate-limited for twin input |
| 7 | Semantic | Per-equipment rule (e.g. chiller inlet ≤ outlet) | `flag=SUSPECT` on both contributors |
| 8 | Imputation routing | Apply per `on_bad` / `on_missing` strategy | `flag=IMPUTED`, `imputation_method` set |

### 2.2 Per-point config table (`data_quality_config`)

```yaml
# Stored as one row in Postgres data_quality_config, JSON for clarity
point_id: "chiller_1.evap_leaving_temp"
expected_poll_interval_seconds: 60
gap_tolerance_multiplier: 2.0
max_gap_before_missing_seconds: 300
range:
  hard_min: -10
  hard_max: 30
  unit: "C"
rate_of_change:
  max_delta_per_minute: 5.0
frozen_detection:
  window_samples: 10
  std_dev_threshold: 0.01
spike_filter:
  enabled: true
  z_score_threshold: 4.0
  window_samples: 20
semantic_rules:
  - id: "chiller_evap_supply_lt_return"
    pair: ["chiller_1.evap_entering_temp", "chiller_1.evap_leaving_temp"]
    rule: "lhs > rhs"   # entering must be higher than leaving when cooling
on_bad: IMPUTE_TWIN
on_missing: IMPUTE_LKG
on_suspect: PASS_WITH_FLAG
max_imputation_chain: 10
twin_protected: true
rl_observation: true
alert_on_bad_sensor: true
suppress_threshold_alerts_when: ["BAD","MISSING"]
# Pushed by Tier 2 jobs
drift_coefficient: 0.0
bias_offset: 0.0
updated_at: "2026-05-25T11:00:00Z"
```

Seeded at deployment from `data_quality_config_seed.yaml` (a known-good baseline for the 363 simulator points + the legacy unicharm equipment).

### 2.3 Imputation strategies

| Strategy | Best for | Behaviour |
|---|---|---|
| `LKG` (Last Known Good) | Short gaps, slow signals | Hold last GOOD/IMPUTED value, increment gap counter |
| `LINEAR` | Reporting gap fill | Interpolated post-hoc by Tier 2 |
| `IMPUTE_TWIN` | Twin-protected critical sensors | Ask `twin-broker` for predicted value via Kafka `cmd.twin.predict` |
| `REGRESSION` | Correlated sensor pairs | Built nightly by Tier 2 |
| `PROFILE` | Daily/weekly profiles | Built weekly by Tier 2 |
| `ZERO` | Binary safety signals | Conservative fallback |
| `REJECT` | Critical control / interlocks | No value sent; downstream must handle null explicitly |

### 2.4 Emitting `QualityEvent` for audit

Every non-`GOOD` decision becomes a `QualityEvent` on Kafka topic `dq.events`:

```json
{
  "time": "2026-05-25T11:23:01Z",
  "device_id": "chiller_1",
  "point_id": "chiller_1.evap_leaving_temp",
  "event_type": "FROZEN",
  "original_value": 7.42,
  "corrected_value": null,
  "flag_applied": "BAD",
  "source": "TIER1",
  "imputation_method": null
}
```

The `db-writer` consumer persists these to the `quality_events` hypertable (audit + Tier 2 input).

## 3 · Tier 2 — async ETL (`dq-etl` container)

Python + APScheduler. Reads from the same Postgres + hits Unicharm MySQL when it needs cross-validation against the legacy ground truth.

### 3.1 Jobs

| Job | Schedule | Output | Feedback |
|---|---|---|---|
| `sensor_drift_estimator` | daily | rolling 7/30-day drift coefficient per sensor → `data_quality_config.drift_coefficient` | yes, Tier 1 picks up in ≤ 15 min |
| `baseline_profiler` | weekly | `baseline_profiles` (mean/sigma per hour/dow/month) | indirect — used by Tier 1 context-aware range checks v2 |
| `cross_sensor_validator` | hourly | `quality_events` of type `CROSS_SENSOR_CONTRADICTION` | routed to calibration team |
| `gap_reconciler` | hourly | Retroactively fills gaps in `telemetry` hypertable via linear interpolation | does NOT affect live twin/RL |
| `quality_score_rollup` | hourly | `sensor_health_scores` (0-100) | dashboard KPI |
| `rl_experience_cleaner` | daily | Removes IMPUTED/BAD rows from RL replay buffer | feeds rl-broker retraining |
| `twin_calibration_feeder` | daily | Updates per-twin calibration params | pushed to `twin-broker` |
| `sampling_irregularity_report` | daily | `sampling_health_report` table | dashboard + adapter alerts |

### 3.2 Feedback loop diagram

```
                   ┌──────────────────────────────┐
                   │  Tier 2 ETL  (daily/hourly)  │
                   └───────────────┬──────────────┘
                                   │ writes
                                   ▼
                   ┌──────────────────────────────┐
                   │ data_quality_config (Postgres)│
                   │ sensor_health_scores         │
                   │ baseline_profiles            │
                   └───────┬──────────────┬───────┘
                           │              │
        ┌──────────────────┘              └────────────────────┐
        ▼                                                       ▼
  Tier 1 DAL                                              Frontend DQ
  refresh q15min                                          dashboard
        │
        ▼
  Drift corrections applied
  to every new reading
```

## 4 · How each subsystem reacts to each flag (rule matrix)

This is the **single source of truth** for downstream behaviour. Coded into the consumer libraries.

| Flag | Twin | RL | Alert engine |
|---|---|---|---|
| GOOD | Normal update + FDD | Normal observation, full weight | Evaluate rules normally |
| SUSPECT | Update + widen uncertainty ×2 | Observation, weight 0.5, no reward use | Require N persistent breaches before firing |
| IMPUTED | Use, mark state estimated | Use, reduced exploration, replay-tagged | No threshold alerts; offline/state alerts ok |
| BAD | Hold last GOOD, pause FDD on that param | Substitute last GOOD, increment counter | Suppress threshold; fire `SENSOR_FAULT` |
| MISSING | Hold, grow uncertainty; freeze after `max_gap` | Hold last action / safe default | Offline counter, fire `DEVICE_OFFLINE` after N misses |
| STALE | Insert at history slot; don't update live | Discard | Evaluate with caveat |

Mass-event rules:
- If `>30 %` of a device's points are BAD/MISSING simultaneously → `WIDESPREAD_QUALITY_EVENT` alert, twin and RL pause.

## 5 · POC fault-injection script

`scripts/inject_dq_fault.py` — used in demos to deliberately trigger each branch.

| Mode | Effect | Expected pipeline reaction |
|---|---|---|
| `--freeze <point> --seconds 600` | Pin value via simulator HTTP API | Tier 1 fires FROZEN → BAD, agent opens calibration WO |
| `--drift <point> --slope 0.01` | Slowly bias the reading | Tier 2 catches drift next day → coefficient pushed → agent workflow |
| `--spike <point> --magnitude 50` | Inject large outlier | Tier 1 spike filter → SUSPECT, no alert noise |
| `--silence <ddc>` | Block UDP from a DDC | Tier 1 MISSING → DEVICE_OFFLINE alert |
| `--swap-units <point>` | Send °F instead of °C | Cross-sensor rule catches it (entering > leaving inverted) |

## 6 · Metrics

DAL exposes Prometheus counters per check:
- `dq_tier1_checks_total{check="frozen",result="bad"}`
- `dq_tier1_duration_seconds` histogram (SLO ≤ 50 ms p95)
- `dq_flag_distribution{flag="GOOD|SUSPECT|...",device_id}`
- `dq_imputations_total{method="LKG|TWIN|..."}`

Grafana panel: per-site quality score, per-sensor flag distribution, drift heat map. See [12_BACKEND_API_WS.md](12_BACKEND_API_WS.md) for the API surface.
