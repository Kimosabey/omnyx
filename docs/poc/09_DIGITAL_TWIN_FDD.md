# 09 · Digital Twin + FDD

Implements PRD §09. The `twin-broker` service hosts one or more physics twins, drives FDD continuously, emits diagnoses to Kafka.

## 1 · Service shape (`twin-broker`)

```
twin-broker (Python)
  ├── kafka consumer on raw.bacnet.{device_id} for every twin-protected device
  ├── twin runtime
  │     ├── loads twin model from app.twin_models
  │     ├── steps simulation in lockstep with incoming readings
  │     ├── FDD engine compares predicted vs actual
  │     └── RUL extrapolator
  ├── kafka producer
  │     ├── twin.fdd.alerts   on deviation > threshold
  │     └── telemetry.twin_states (via db-writer) every step
  ├── REST endpoints (called by api-service tool gateway)
  │     ├── POST /predict  {device_id, inputs}    → twin output (used by DQ IMPUTE_TWIN)
  │     ├── POST /simulate {device_id, scenario}  → forward-roll for RL sim-to-real
  │     └── GET  /health/{device_id}
  └── Tier-2 fed calibration coefficients (twin_calibration_feeder ETL)
```

## 2 · POC twin scope

Two physics twins ship in the POC, both seeded from the Unicharm history we replay (see §08.5):

| Twin model id | Device type | Reasonable physics | Inputs | Outputs | FDD targets |
|---|---|---|---|---|---|
| `chiller_v1` | chiller | Carnot-shifted COP + heat-exchanger ε-NTU + part-load curve | `evap_entering_temp`, `cond_entering_temp`, `chiller_load`, `evap_flow`, `cond_flow`, `ambient_temp`, `wet_bulb_temp` | `kw_predicted`, `tr_predicted`, `kw_per_tr_predicted`, `evap_leaving_temp_predicted`, `cond_leaving_temp_predicted` | bearing wear (kW drift up at constant load), fouling (low ΔT), refrigerant low-charge (cap loss), sensor drift |
| `cooling_tower_v1` | cooling_tower | wet-bulb approach + fan-affinity laws | `wet_bulb_temp`, `cond_entering_temp`, fan_kw vector | `cond_leaving_temp_predicted`, `approach_predicted` | fan imbalance, fouling, fill degradation |

Each twin model is one Python class implementing:

```python
class PhysicsTwin(Protocol):
    twin_model_id: str
    def step(self, inputs: dict[str, float], dt: timedelta) -> TwinStep: ...
    def diagnose(self, predicted: TwinStep, actual: dict[str, float]) -> Diagnosis | None: ...
    def estimate_rul(self, history: list[Diagnosis]) -> dict[str, float]: ...  # {component: days}
    def calibrate(self, history: pd.DataFrame) -> None: ...  # called by twin_calibration_feeder
```

## 3 · FDD engine

Per step the engine computes per-output residuals:

```
residual = actual − predicted
z = residual / sigma(point, hour, load_band)    # sigma from baseline_profiles
```

Decision table:

| Condition | Action |
|---|---|
| `|z| < 2` | nothing |
| `2 ≤ |z| < 3`, persistent ≥ N | emit `Alert(severity=warning, source=twin_fdd, fault_code=Z2)`, increment degradation counter |
| `|z| ≥ 3`, persistent ≥ N | emit `Alert(severity=critical, source=twin_fdd)`, populate `payload.fault_code`, `payload.root_cause`, `payload.rul_days` |
| Multiple parameters off simultaneously | run `correlate_faults()`; cascading failure vs independent |
| Input quality flag != GOOD | pause FDD for that parameter (rules from [06_DATA_QUALITY_LAYER.md §4](06_DATA_QUALITY_LAYER.md)) |

Fault library lives in `services/twin-broker/fault_codes.yaml`. Each code maps to recommended action, parts list, technician skill — fed straight into the auto-created WorkOrder.

## 4 · RUL — remaining useful life

For each named degradation mode the twin keeps a rolling fit of:

```
degradation_index(t) = exponential_smoothing(z_residual)
slope = linear_fit_last_30d(degradation_index)
days_to_fault_threshold = (fault_threshold - degradation_index(now)) / slope
```

`rul_estimates` is a JSONB column on `telemetry.twin_states` so we can chart its history per equipment.

## 5 · POC demo — scripted slow drift

Used in the demo storyline (see [01_SCOPE_AND_SUCCESS.md §5](01_SCOPE_AND_SUCCESS.md)):

```bash
python scripts/inject_dq_fault.py --drift chiller_1.kw_per_tr --slope 0.005 --hours 24
```

Expected:
- Day 0: twin residual within band.
- Day 0.5: `z` climbs above 2 → warning alert, agentic AI investigates, opens watch WO.
- Day 1: `z` ≥ 3 → critical alert, RUL ≈ 14 days, agent escalates to maintenance lead.

## 6 · Twin health monitoring (model drift, not equipment drift)

The twin itself can drift. We track `twin_prediction_error` rolling 7-d MAPE per output and:
- alert `TWIN_INPUT_QUALITY_DEGRADED` when GOOD-flag inputs < 97 %
- alert `TWIN_MODEL_DRIFTING` when MAPE > 2× the original calibration MAPE
- the `twin_calibration_feeder` Tier-2 job pushes refreshed coefficients daily

## 7 · Sim-to-Real for RL

The same `POST /simulate` endpoint that the DQ layer uses for `IMPUTE_TWIN` is what `rl-broker` uses to train new policies safely — see [10_RL_OPTIMIZER.md §4](10_RL_OPTIMIZER.md).
