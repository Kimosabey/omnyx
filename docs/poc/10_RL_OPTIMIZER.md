# 10 · Reinforcement Learning Optimiser

Implements PRD §07 Module 3. The `rl-broker` service is the runtime; the POC ships one toy agent in **shadow mode** to demonstrate the end-to-end loop without changing production setpoints.

## 1 · Service shape

```
rl-broker (Python)
  ├── agent registry  (app.rl_agents)
  ├── observation collector: consumes raw.bacnet.* + telemetry.twin_states
  │     • drops non-GOOD points per DQ rules
  ├── policy runtime: stable-baselines3 or custom
  ├── action emitter:
  │     SHADOW → telemetry.rl_actions (applied=false)
  │     LIVE   → cmd.bacnet.{device_id}  (via api-service tool, with approval if Tier 3+)
  ├── reward engine: pulls from telemetry.readings_1m + reward_config
  └── retraining loop: nightly, uses cleaned replay buffer from rl_experience_cleaner
```

## 2 · POC agent — `chiller_efficiency_v1`

| Field | Value |
|---|---|
| Device | `chiller_1` |
| Mode | SHADOW (read-only for POC; flip to LIVE after sign-off) |
| Observation | `evap_entering_temp`, `evap_leaving_temp`, `cond_entering_temp`, `ambient_temp`, `chiller_load`, `kw_per_tr` — all must be `GOOD` |
| Action | `chiller_1.chw_setpoint` ∈ `[6 °C, 9 °C]` in 0.5 °C steps |
| Reward | `−(kw_per_tr - 0.55)² − λ·comfort_violation` where comfort_violation = `max(0, supply_temp − comfort_band_high)` |
| Safety bounds | hard `[5.5, 10] °C`; never write more often than 5 min |
| Cadence | new action every 60 s |

## 3 · Shadow → Live promotion

| Tier | Required before promotion |
|---|---|
| Shadow days | ≥ 14 days running |
| KPI gain in shadow | ≥ 5 % vs baseline on `kw_per_tr` |
| Safety violations | 0 |
| Human review | AI Ops Specialist sign-off recorded in `audit.events` |
| Mode change | API call `POST /rl/agents/{id}/promote` (Tier 4 approval, dual auth) |

The PRD's 10 % KPI MVP target ([01_SCOPE_AND_SUCCESS.md §4](01_SCOPE_AND_SUCCESS.md)) is measured on the shadow-mode replay, not on the simulator, so we don't need 30 days of physical operation to show the metric.

## 4 · Twin-based training (sim-to-real)

Bootstrap step done once per agent:

```
1. Pull last 90 d of Unicharm history for chiller_1 → DataFrame.
2. Train an initial policy via offline RL (CQL) on this history.
3. Validate on a held-out 14 d slice; reject if reward < baseline.
4. Wrap policy as 'shadow' agent on the live stream.
5. After 14 d shadow, re-evaluate, promote if criteria met.
```

The twin's `POST /simulate` endpoint lets the trainer roll the chiller forward under a candidate policy for ad-hoc what-if scenarios.

## 5 · Reward dashboard (frontend)

`/rl/agents/chiller_efficiency_v1` page shows:
- live reward curve (last 24 h, 7 d, 30 d)
- baseline reward curve (the period before agent went shadow)
- action distribution histogram
- top features per recent decision (SHAP or simple gradient)
- safety violation counter (must remain at zero)
- shadow/live toggle (Tier 4 protected)

## 6 · Multi-objective (v2 onward)

Reward config is a list, not a single scalar — same agent can optimise `(energy, comfort, lifecycle)` with configurable weights. POC ships the energy-only objective; UI surfaces the weights so it's visible the framework is multi-objective.
