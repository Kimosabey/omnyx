# 05 · Canonical Data Model

Single set of types every service uses. Lives in `shared/models.py` (Python) and `shared/models.ts` (TypeScript, generated from the Python source via `datamodel-codegen` + `quicktype`). Anything crossing a Kafka topic or REST boundary must use these — no plain dicts.

## 1 · `PointReading` — the atom

Every BACnet point, after Tier 1 DQ, becomes one of these.

```python
@dataclass
class PointReading:
    # identity
    device_id: str           # e.g. "DDC09" or "chiller_1"
    point_id: str            # e.g. "chiller_1.kw_per_tr"
    site_id: str             # e.g. "unicharm_chennai"
    # value
    value: float | bool | str | None
    unit: str                # "C", "kW", "kW/TR", "boolean", "%"
    # time
    measured_at: datetime    # UTC, when sensor read happened
    received_at: datetime    # UTC, when DAL received the value
    # quality (see §06)
    quality: QualityEnvelope
    # context
    bacnet_object_id: str | None    # "analogValue:42" — for BACnet sources only
    source: Literal["bacnet", "replay", "synthetic"]
```

`point_id` is always `<device_id>.<param_name>` (snake_case). Maps cleanly from the legacy `gl_param_name` column.

## 2 · `QualityEnvelope`

```python
class QualityFlag(str, Enum):
    GOOD = "GOOD"
    SUSPECT = "SUSPECT"
    IMPUTED = "IMPUTED"
    BAD = "BAD"
    MISSING = "MISSING"
    STALE = "STALE"

@dataclass
class QualityEnvelope:
    flag: QualityFlag
    detail: dict | None = None          # {"type":"FROZEN","samples":15}
    original_value: float | None = None # populated only if imputation applied
    imputation_method: str | None = None  # LKG | LINEAR | TWIN | REGRESSION | PROFILE | ZERO
    drift_corrected: bool = False
    tier2_validated: bool = False
```

Every downstream consumer (Twin, RL, Alert engine) keys its behaviour off `flag` — the rules table is in [06_DATA_QUALITY_LAYER.md §5](06_DATA_QUALITY_LAYER.md).

## 3 · `PointBatch` — Kafka message wrapper

To amortize Kafka overhead and group per-device, the DAL produces batches, not individual readings.

```python
@dataclass
class PointBatch:
    site_id: str
    device_id: str
    cycle_id: str           # UUID per read cycle, used for tracing
    cycle_started_at: datetime
    cycle_ended_at: datetime
    readings: list[PointReading]
    cov_filter_applied: bool
    raw_count: int          # how many were read before COV filter
```

Published to topic `raw.bacnet.{device_id}` partition-keyed by `device_id` (preserves ordering per device while still allowing fan-out).

## 4 · `PlantSnapshot` — the WebSocket frame

The `ws-bridge` aggregates the latest `PointReading` for every point on every device into a single JSON blob, broadcast every 5 s (configurable). This mirrors `plant_snapshot.py` in gl_pbs.

```python
@dataclass
class PlantSnapshot:
    snapshot_at: datetime
    site_id: str
    sites: dict[str, SiteState]

@dataclass
class SiteState:
    site_id: str
    name: str
    health: HealthRollup
    devices: dict[str, DeviceState]

@dataclass
class DeviceState:
    device_id: str
    name: str
    device_type: str         # chiller | cooling_tower | pump | ahu | meter | breaker
    online: bool
    last_seen: datetime
    twin_status: TwinStatus  # synced | drifting | paused | none
    quality_score: float     # 0..100 from sensor_health_scores
    metrics: dict[str, MetricLatest]  # latest GOOD value per param
    active_alerts: int

@dataclass
class MetricLatest:
    value: float | bool | str | None
    unit: str
    measured_at: datetime
    quality: QualityFlag
```

## 5 · `EquipmentMeta` / `DevicePoint` — dimension model

These live in Postgres relational tables (`equipment`, `device_points`) and are served by REST `/api/v1/equipment`. They map 1-to-1 to what the React UI needs to render the device tree.

```python
@dataclass
class EquipmentMeta:
    id: str                    # "chiller_1"
    name: str
    type: str                  # chiller | cooling_tower | pump | ahu | meter | breaker | plant
    site_id: str
    parent_id: str | None      # "plant" for plant rollup
    twin_model_id: str | None  # FK to twin_models
    rl_agent_id: str | None
    metadata: dict             # vendor, model, serial, install_date, etc.

@dataclass
class DevicePoint:
    id: str                    # "chiller_1.kw_per_tr"
    device_id: str
    name: str                  # "kw_per_tr"
    display_name: str          # "Efficiency (kW/TR)"
    unit: str
    point_type: str            # measurement | setpoint | command | state
    bacnet_object_id: str | None
    bacnet_property: str | None
    legacy_table: str | None   # "chiller_1_normalized" — back-pointer for replay
    legacy_column: str | None  # "kw_per_tr"
    dq_config_id: str          # FK to data_quality_config
    twin_protected: bool
    rl_observation: bool
    expected_poll_seconds: int
```

`legacy_table` + `legacy_column` are how we round-trip historical analytics — the API can fall through to the original `unicharm` MySQL when needed during transition.

## 6 · Alert / WorkOrder / AgentEvent

Mirroring the PRD §07 modules. Just the headline shape; full Postgres DDL is in [08_STORAGE_TIMESCALEDB.md](08_STORAGE_TIMESCALEDB.md).

```python
@dataclass
class Alert:
    id: str
    source: Literal["rule", "twin_fdd", "dq", "system"]
    severity: Literal["info", "warning", "critical"]
    fault_code: str | None
    device_id: str | None
    point_id: str | None
    fired_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    payload: dict     # twin_diagnosis, RUL, recommended_action, etc.

@dataclass
class WorkOrder:
    id: str
    title: str
    status: Literal["open","assigned","in_progress","resolved","closed"]
    severity: str
    device_id: str | None
    created_by: Literal["user","twin_fdd","agentic_ai","schedule"]
    diagnosis: dict | None
    recommended_parts: list[str]
    technician_id: str | None
    created_at: datetime
    sla_due_at: datetime | None

@dataclass
class AgentEvent:
    workflow_id: str
    step: int
    agent: Literal["planner","executor","validator"]
    timestamp: datetime
    kind: Literal["thought","tool_call","tool_result","approval_request","done","error"]
    payload: dict
```

`AgentEvent` is what the frontend consumes from topic `agent.activity` to render the live agent trace.

## 7 · Topic ↔ schema map

| Topic | Schema | Partition key |
|---|---|---|
| `raw.bacnet.{device_id}` | `PointBatch` | `device_id` |
| `cmd.bacnet.{device_id}` | `BacnetCommand` (write_setpoint, read, change_mode) | `device_id` |
| `reply.bacnet.{request_id}` | `BacnetReply` | `request_id` |
| `dq.events` | `QualityEvent` (FROZEN, SPIKE, DRIFT, MISSING, …) | `device_id` |
| `twin.fdd.alerts` | `Alert(source="twin_fdd")` | `device_id` |
| `rl.actions` | `RlAction` | `device_id` |
| `agent.activity` | `AgentEvent` | `workflow_id` |
| `health.{service}` | `HealthBeat` | `service` |

Everything is serialised as JSON for the POC (matches the legacy stress-test bridge). v2 path is to switch to **Avro + Schema Registry** without changing any consumer code, since the dataclasses already have stable shapes.

## 8 · Why we keep both `measured_at` and `received_at`

DQ Tier 1 needs `received_at - measured_at` to fire `STALE`. Twin needs `measured_at` for state alignment. Loss of either is a debugging hole — we always carry both.
