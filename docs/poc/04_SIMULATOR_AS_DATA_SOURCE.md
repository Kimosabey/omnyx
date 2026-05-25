# 04 · Simulator + Legacy DB as Data Sources

The POC has **two data paths** so demos cover both the live operational story and the historical analytics story.

## 1 · Path A — Live: gl_pbs BACnet simulator

The whole [gl_pbs](../../../../simulations/gl_pbs/) project becomes the field for our POC. We do not modify it; we run it as-is and consume its BACnet UDP stream from our new edge service.

### 1.1 How the simulator is launched

From [SIMULATION_GUIDE.md](../../../../simulations/gl_pbs/docs/SIMULATION_GUIDE.md):

```powershell
cd D:\Harshan\simulations\gl_pbs
python bacnet_name_launcher.py
```

This:
1. Reads `data/eqp_name_handling.csv` (363 real points, 11 DDC identifiers).
2. Spawns one `bacnet_name_simulator.py` subprocess per DDC.
3. Assigns BACnet UDP ports starting at 2001 and per-simulator HTTP web ports at 7091.
4. Writes the controller map back into `config/GLBACpypes.ini`.

### 1.2 Controller and port map (POC default)

| DDC | BACnet UDP | Sim Web UI | Equipment families |
|---|---|---|---|
| DDC01 | 2001 | 7091 | C0 (chiller cooling) |
| DDC01_01 | 2002 | 7092 | B0 (chiller) |
| DDC02 | 2003 | 7093 | B0 |
| DDC03 | 2004 | 7094 | B1 (pump) |
| DDC04 | 2005 | 7095 | CB (breaker) |
| DDC05 | 2006 | 7096 | B4 (AHU fan) |
| DDC06 | 2007 | 7097 | B7 (cooling tower) |
| DDC07 | 2008 | 7098 | B7 + C0 |
| DDC07_01 | 2009 | 7099 | B7 |
| **DDC09** | **2010** | **7100** | 0, B0, B1, B3, B4, C0, CB — **254 of 363 pts** |
| DDC10 | 2011 | 7101 | 0 + B7 |

Equipment distribution from [EQUIPMENT_ANALYSIS.md](../../../../simulations/gl_pbs/docs/testing/EQUIPMENT_ANALYSIS.md):

| Code | Equipment | Points | Expected COV behaviour |
|---|---|---|---|
| `0` | Energy meters | 135 | HIGH — every poll |
| `B7` | Cooling towers / AHU | 51 | MEDIUM |
| `B0` | Chillers | 48 | MEDIUM |
| `B3` | Power panels | 48 | HIGH |
| `B1` | Pumps | 30 | MEDIUM |
| `B4` | AHU fans | 30 | MEDIUM |
| `C0` | Chiller cooling sys | 17 | LOW-MEDIUM |
| `CB` | Circuit breakers | 4 | LOW |

### 1.3 `eqp_name_handling.csv` format

Each row maps **(DDC, BACnet object) → (GL equipment, GL parameter)**. The new edge service uses this same CSV for name resolution on first cycle, exactly like `bacnet_reader.py` does today (`USE_OBJECT_NAME_HANDLER = True` in the INI). Sample columns (verify via `head data/eqp_name_handling.csv`):

```
ddc_id, bacnet_object_id, bacnet_property, gl_eqp_type, gl_eqp_instance, gl_param_name, unit, ...
```

### 1.4 How the new edge service consumes it

`dal-bacnet` (the service that replaces `bacnet_reader.py` + `kafka_bacnet_bridge.py`) does this each cycle:

1. RPM read per device (batch size 15, exactly as the proven path).
2. Single-read fallback for non-RPM devices (the [RCA fix](../../../../simulations/gl_pbs/docs/RCA_RPM_No_Response.md) is preserved verbatim — we copy `bacnet/read_strategy.py` and `bacnet/read_thread.py` into `dal-bacnet/bacnet/`).
3. COV filter at 3 % (config: `COV_THRESHOLD_PCT`).
4. **DQ Tier 1 inline** on every reading (see §06).
5. Quality envelope attached.
6. Kafka publish to `raw.bacnet.{device_id}`.

### 1.5 Stress / scale modes for the simulator

From [STRESS_TEST_GUIDE.md](../../../../simulations/gl_pbs/docs/testing/STRESS_TEST_GUIDE.md), the simulator supports synthetic scaling. POC defaults:

| Demo mode | Command | Rate | Purpose |
|---|---|---|---|
| Real-stack live | `bacnet_name_launcher.py` | ~2 msg/s (COV-filtered) | Live UI + Twin + Agentic story |
| 10× scale | `stress_test_kafka.py --mode real --rate 500 --scale 10` | ~500 msg/s | Sizing demo |
| 100× scale | `stress_test_kafka.py --mode real --rate 5000 --scale 100` | ~5 kmsg/s | Ceiling demo |

These bypass DAL (they speak Kafka directly), so they only validate the broker + DB tier, not the BACnet → DQ → twin paths.

## 2 · Path B — Historical: replay Unicharm MySQL

The legacy `unicharm` MySQL (already documented in [DATABASE_SCHEMA_REFERENCE.md](../../../../HVAC%20AI%20Operations%20Intelligence%20Platform/docs/reference/DATABASE_SCHEMA_REFERENCE.md)) holds **per-minute normalized HVAC history** for two chillers, two cooling towers, multiple pumps. We need that data in the new platform for three reasons:

1. **Twin training / calibration** — physics twins need months of operating data to fit.
2. **RL replay buffer** — RL agents bootstrap from historical state/action pairs.
3. **Agent context** — analytics agents must answer "how did chiller_1 perform last month?".

### 2.1 Source tables (read-only, MySQL CLI)

```bash
# Connection string for the read-only credential
mysql -h <host> -P 3307 -u ro_user -p<pw> -D unicharm

# Inventory we replay
SHOW TABLES LIKE '%_normalized';
# → chiller_1_normalized
#   chiller_2_normalized
#   cooling_tower_1_normalized
#   cooling_tower_2_normalized
#   condenser_pump_0102_normalized
#   condenser_pump_03_normalized
#   primary_pump_1_normalized
#   primary_pump_2_normalized
#   primary_pump_3_normalized
#   plant_normalized
```

Per the existing DATA_DICTIONARY.md we **never** touch `*_metric` or `*_om_p` — those are raw vendor exports that ETL feeds the `_normalized` tables. We accept the same contract.

### 2.2 Replay job — `dal-replay`

A one-shot Python container that we run during POC setup:

```
dal-replay
  ├── reads unicharm.{equipment}_normalized in time order
  ├── projects each row into N PointReading messages (one per metric column)
  ├── attaches quality_flag = GOOD (already cleaned by upstream ETL)
  ├── publishes to raw.bacnet.{device_id}
  └── progress tracked in replay_progress table so it's resumable
```

Mapping from legacy → canonical:

| Legacy table | Canonical `device_id` | Canonical `device_type` | Point map |
|---|---|---|---|
| `chiller_1_normalized` | `chiller_1` | `chiller` | one row → ~14 `PointReading` (kw, tr, kw_per_tr, evap_entering_temp, ...) |
| `chiller_2_normalized` | `chiller_2` | `chiller` | same |
| `cooling_tower_1_normalized` | `cooling_tower_1` | `cooling_tower` | fan1_kw, fan2_kw, fan3_kw, kw, kwh, run_hours |
| `cooling_tower_2_normalized` | `cooling_tower_2` | `cooling_tower` | same |
| `condenser_pump_0102_normalized` | `condenser_pump_1` | `pump` | kw, kwh, cumulative_kwh, run_hours |
| `condenser_pump_03_normalized` | `condenser_pump_3` | `pump` | same |
| `primary_pump_{1,2,3}_normalized` | `primary_pump_{1,2,3}` | `pump` | same |
| `plant_normalized` | `plant` | `plant_rollup` | total_kw, total_kwh, total_tr, total_trh, aux_kw, aux_kwh |

Equipment metadata (display name, type, site, parent) lives in the existing `building`, `floor`, `zone`, `area`, `device` facility tables. The replay job seeds the new `device_points` and `equipment` dimension tables from those.

### 2.3 Bulk-load mode vs continuous catch-up mode

| Mode | When | Behaviour |
|---|---|---|
| Bulk-load | One-time during POC bring-up | Reads from `MIN(slot_time)` to `NOW()` in 1-day batches, throttled to ~5 k msg/s to not saturate Kafka |
| Catch-up | Optional ongoing | Polls for new rows every minute; useful if Unicharm ETL is still upstream of the new system during cutover |

For the POC demo we do bulk-load once and then the **simulator becomes the live source**. In a real cutover at Unicharm itself, the old ETL stops, the new `dal-bacnet` reads the field directly, and Unicharm's MySQL is decommissioned.

## 3 · How to scale the simulator for capacity-planning demos

Per [CAPACITY_PLANNING.md](../../../../simulations/gl_pbs/docs/planning/CAPACITY_PLANNING.md), the formula is:

```
target_msg_per_sec = total_bacnet_points / poll_interval_seconds
```

For 50 sites × 363 points / 5 s = 3,630 msg/s. Already proven on a single i7 laptop (Scenario 5–7 in [STRESS_TEST_GUIDE.md](../../../../simulations/gl_pbs/docs/testing/STRESS_TEST_GUIDE.md)).

## 4 · What the simulator does *not* do (and how we cover it)

| Gap | Mitigation |
|---|---|
| Doesn't inject sensor faults | We add `simulator/fault_injector.py` (tiny script that POSTs to per-DDC web UI on 7091+ to freeze, drift, spike, or set ranges on chosen points). Used for demo Step 3 in [01_SCOPE_AND_SUCCESS.md](01_SCOPE_AND_SUCCESS.md). |
| Doesn't have a twin baseline | We seed the twin from Path B (Unicharm history) for `chiller_1` and `cooling_tower_1`. The simulator's DDC01_01 / DDC06 ports are mapped to those `device_id`s. |
| Doesn't support writes | The simulator does support `WriteProperty` (see `simulator/objects/writable_objects.py`); we use it for RL agent action demos. |
