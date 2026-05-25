# 32 · BACnet / PBS / DDC Signal Catalogue

Everything OMNYX needs to understand about the BACnet pipe — object types, properties, services, formats, addressing, error modes. Source-of-truth for `dal-bacnet` implementation.

Source materials:
- [`simulations/gl_pbs/docs/CODEBASE.md`](../../../../simulations/gl_pbs/docs/CODEBASE.md)
- [`simulations/gl_pbs/docs/RCA_RPM_No_Response.md`](../../../../simulations/gl_pbs/docs/RCA_RPM_No_Response.md)
- [`simulations/gl_pbs/docs/HARDWARE_CONTROLLER.md`](../../../../simulations/gl_pbs/docs/HARDWARE_CONTROLLER.md)
- Legacy `graylinx-be/gl_jupiter/hvacBACnetClient.js` (verified BACnet flows)
- Legacy `graylinx-be/gl_jupiter/eqp_name_handling.csv` (point map shape)

---

## 1 · Transport

| Aspect | Value |
|---|---|
| Network layer | **BACnet/IP** (UDP) |
| Default port | **47808 / 0xBAC0** (each gl_pbs simulator DDC also exposes on 2001–2014) |
| Discovery | `Who-Is` / `I-Am` broadcast |
| Routing | UDP broadcast within VLAN, BBMD for cross-subnet (POC: single subnet) |
| MSTP | Supported by `bacpypes` but not used in POC |
| Max APDU | 1024 bytes (per `GLBACpypes.ini`) |
| Segmentation | `segmentedBoth` |

## 2 · BACnet services we use

| Service | Direction | Used in |
|---|---|---|
| `Who-Is` | DAL → device | Discovery |
| `I-Am` | device → DAL | Discovery response |
| `ReadPropertyMultiple` (RPM) | DAL → device | Primary read path (batch of 15 per `rpmBatchSize`) |
| `ReadProperty` | DAL → device | Fallback when device rejects RPM (per RCA fix) |
| `WriteProperty` | api-service → device | RL action / operator command via `cmd.bacnet.*` |
| `SubscribeCOV` (v2) | DAL → device | True CoV instead of polled |
| `ConfirmedCOVNotification` (v2) | device → DAL | CoV push |

## 3 · BACnet object types we encounter

From the legacy `eqp_name_handling.csv` and bacpypes enum:

| BACnet object type | Type code | Common use in PBS |
|---|---|---|
| `analogInput` (AI) | 0 | Read-only sensor (temperature, pressure, flow) |
| `analogOutput` (AO) | 1 | Writeable setpoint, valve, damper |
| `analogValue` (AV) | 2 | Calculated / virtual values (kW/TR, derived metrics) — heaviest in DDC09 |
| `binaryInput` (BI) | 3 | Read-only binary (running, fault, dry contact) |
| `binaryOutput` (BO) | 4 | Writeable binary (start/stop, enable) |
| `binaryValue` (BV) | 5 | Calculated / virtual binary (computed state) — used for circuit breakers |
| `multiStateInput` (MSI) | 13 | Read-only enum (mode, status code) |
| `multiStateOutput` (MSO) | 14 | Writeable enum (mode select) |
| `multiStateValue` (MSV) | 19 | Virtual enum |
| `device` | 8 | Device object itself (Who-Is target) |
| `schedule` | 17 | BACnet-side schedules (we don't use these; OMNYX owns scheduling) |

## 4 · BACnet properties we read

| Property | Code | Per-object behavior |
|---|---|---|
| `presentValue` | 85 | The actual reading — primary target |
| `units` | 117 | Engineering units enum |
| `objectName` | 77 | DDC-side name; resolved on first cycle (`USE_OBJECT_NAME_HANDLER`) |
| `description` | 28 | Free-text label |
| `statusFlags` | 111 | `[in_alarm, fault, overridden, out_of_service]` — feeds DQ |
| `reliability` | 103 | enum: `no_fault_detected`, `unreliable_other`, `over_range`, … — feeds DQ |
| `outOfService` | 81 | Maintenance flag |
| `eventState` | 36 | `normal | fault | offnormal | high_limit | low_limit` |
| `covIncrement` | 22 | For SubscribeCOV (v2) |
| `priorityArray` | 87 | For writes — priority 16 default |
| `relinquishDefault` | 104 | Default when priority array is released |

## 5 · BACnet engineering units (the ones we actually see in PBS)

From `bacstack`/`bacpypes` `EngineeringUnits` enum:

| Unit code | Name | OMNYX canonical `unit` string |
|---|---|---|
| 0 | square-meters | `m2` |
| 47 | degrees-celsius | `C` |
| 48 | degrees-Kelvin | `K` |
| 49 | degrees-Fahrenheit | `F` |
| 53 | percent-relative-humidity | `%RH` |
| 55 | parts-per-million | `ppm` |
| 64 | percent | `%` |
| 65 | percent-per-second | `%/s` |
| 71 | meters-per-second | `m/s` |
| 73 | liters-per-second | `L/s` |
| 75 | gallons-per-minute | `gpm` |
| 80 | kilopascals | `kPa` |
| 89 | revolutions-per-minute | `RPM` |
| 90 | currency1 | (ignore) |
| 95 | counts | `count` |
| 137 | kilowatts | `kW` |
| 138 | kilowatt-hours | `kWh` |
| 187 | tons-refrigeration | `TR` |

`dal-bacnet` carries a unit-code → canonical-string table and warns on any unmapped code (UI shows it raw and DQ flags SUSPECT until mapped).

## 6 · Point map (`eqp_name_handling.csv`) format

One row per BACnet point. Shape used by both gl_pbs simulator and the new DAL:

| Column | Meaning | Example |
|---|---|---|
| `ddc_id` | Controller identifier | `DDC09` |
| `device_instance` | BACnet device instance number | `8623` |
| `address` | IP:port of the DDC | `10.10.20.85:2010` |
| `bacnet_object_type` | Symbolic object type | `analogValue` |
| `bacnet_object_id` | `<type>:<instance>` | `analogValue:42` |
| `bacnet_property` | Property to read | `presentValue` |
| `gl_eqp_type` | OMNYX equipment family code | `B0` (chiller) |
| `gl_eqp_instance` | Equipment instance | `chiller_1` |
| `gl_param_name` | Canonical parameter | `kw_per_tr` |
| `unit` | Engineering unit | `kW/TR` |
| `point_type` | measurement / setpoint / command / state | `measurement` |
| `cov_threshold_pct` | per-point COV % (optional override) | `3.0` |
| `expected_poll_seconds` | per-point cadence (optional) | `60` |
| `value_kind` | numeric / boolean / text | `numeric` |
| `notes` | free text | |

`dal-bacnet` consumes this exactly like `bacnet_reader.py` does today. The two-phase resolution (`_name_list` first cycle → `_rpm_list` thereafter) is preserved.

## 7 · OMNYX equipment-type codes (from gl_pbs CSV legend)

| Code | OMNYX `equipment.type` | Typical points |
|---|---|---|
| `0` | `meter` | Energy: V, A, kW, kWh, PF |
| `B0` | `chiller` | kW, TR, kW/TR, evap/cond temps, status |
| `B1` | `pump` | kW, run-status, hours |
| `B3` | `meter` (power-panel) | V, A, kW, kVAR, PF |
| `B4` | `ahu` (fan path) | kW, speed, status |
| `B7` | `cooling_tower` | fan kW, status, run hours |
| `C0` | `chiller` (cooling-system aux) | aux temps |
| `CB` | `breaker` | binary state |

Mapping table seeded into `app.feature_flags.equipment_type_map` so we can extend without code change.

## 8 · Read cycle behaviour (carried over from gl_pbs verbatim)

```
1. GLProcessLoop fires every `interBatchInterval` minutes (default 0.1 min = 6 s)
2. For each device:
   a. Build RPM request, max 15 objects per request (rpmBatchSize)
   b. Send RPM
      • if SUCCESS  → parse values, attach quality, publish
      • if RejectPDU(unrecognized-service) or AbortPDU(buffer-overflow|segmentation-not-supported|unrecognized-service)
        → fall back to per-object ReadProperty for *this device*, cache the fact
      • if timeout → ThreadSupervisor retries with 2× timeout up to `dataAcquisitionMaximumRetryAttempts`
3. COV filter (3 % default, per `CoVThresholdPercent`)
4. DQ Tier 1 (see 06)
5. Publish PointBatch to `raw.bacnet.{device_id}`
6. Heartbeat → `heartbeat.txt` + Prometheus
```

Heartbeat behaviour (force-write every `dataAcquisitionHeartbeatMinutes`, default 15) is preserved — the legacy `ddc_watchdog.py` becomes a sidecar container that monitors `heartbeat.txt` and restarts the DAL if stale.

## 9 · Error modes the DAL must classify

| BACnet error | Tier-1 DQ flag | Tier-1 detail |
|---|---|---|
| `RejectPDU(unrecognized-service)` | (handled at strategy layer — fall back to single-read) | n/a |
| `AbortPDU(buffer-overflow)` | (same) | n/a |
| `AbortPDU(segmentation-not-supported)` | (same) | n/a |
| `Timeout` after retries | `BAD` | `{type:"PROTOCOL_TIMEOUT",retries:n}` |
| `Error(unknown-object)` | `BAD` | `{type:"UNKNOWN_OBJECT"}` |
| `Error(unknown-property)` | `BAD` | `{type:"UNKNOWN_PROPERTY"}` |
| `statusFlags.fault = 1` | `BAD` | `{type:"DEVICE_REPORTED_FAULT"}` |
| `statusFlags.in_alarm = 1` | `SUSPECT` | `{type:"DEVICE_IN_ALARM"}` |
| `statusFlags.overridden = 1` | `SUSPECT` | `{type:"OVERRIDDEN"}` |
| `statusFlags.out_of_service = 1` | `MISSING` | `{type:"OUT_OF_SERVICE"}` |
| `reliability != no_fault_detected` | `BAD` | `{type:"UNRELIABLE",reason:<enum>}` |
| `presentValue = NaN/null` | `MISSING` | `{type:"NULL_VALUE"}` |

These are checked **before** the range/frozen/spike rules; a device-reported fault always wins over a value-based rule.

## 10 · WriteProperty semantics

```
api-service tool `write_setpoint`
  → publishes BacnetCommand to cmd.bacnet.{device_id} with {object_id, property, value, priority=16}
  → dal-bacnet consumes, issues WriteProperty
  → on SimpleAck:
       publishes reply.bacnet.{request_id} {result: ok}
       audit.events row inserted with actor, target, payload
  → on Error:
       publishes reply with error code
       agentic AI sees the failure, replans or escalates
```

Writes always use priority 16 (lowest manual) unless the workflow explicitly requests higher. Priority array release is a Tier-4 operation.

## 11 · COV (Change of Value) details

Two flavours:

| Flavour | When | Behaviour |
|---|---|---|
| Polled COV (POC) | DAL polls at `interBatchInterval`, compares to last published value | Publishes only when `|new − old| / scale > cov_threshold_pct` — same as gl_pbs |
| Subscribed COV (v2) | DAL subscribes to device via `SubscribeCOV` | Device pushes notifications; DAL still runs Tier 1 on each |

Polled COV is conservative: missed pushes don't matter, but small steady drift can be averaged away. `dataAcquisitionHeartbeatMinutes` (default 15) forces a publish regardless of COV so the DB and twin always have fresh values.

## 12 · Configuration knobs

Every legacy `GLBACpypes.ini` setting is preserved in OMNYX, surfaced via env vars or `app.feature_flags`:

| Legacy INI key | OMNYX equivalent | Default |
|---|---|---|
| `defaultIPAddress` | `BACNET_LOCAL_IP` | host IP |
| `address` | `BACNET_LOCAL_CIDR` | `<ip>/24` |
| `myBACnetPort` | `BACNET_LOCAL_PORT` | 47808 |
| `objectIdentifier` | `BACNET_LOCAL_DEVICE_INSTANCE` | 8623 |
| `objectName` | `BACNET_LOCAL_NAME` | `OMNYX_DAL` |
| `maxApduLengthAccepted` | `BACNET_APDU_LEN` | 1024 |
| `segmentationSupported` | `BACNET_SEGMENTATION` | `segmentedBoth` |
| `vendorIdentifier` | `BACNET_VENDOR_ID` | 15 |
| `useReadPropertyMultiple` | `BACNET_USE_RPM` | true |
| `rpmBatchSize` | `BACNET_RPM_BATCH_SIZE` | 15 |
| `interBatchInterval` (minutes) | `BACNET_CYCLE_MINUTES` | 0.1 |
| `recurringDataLoad` | `BACNET_RECURRING` | true |
| `USE_OBJECT_NAME_HANDLER` | `BACNET_NAME_RESOLUTION` | true |
| `allowMultipleSamplingRates` | `BACNET_PER_DEVICE_INTERVAL` | false |
| `checkCoV` | `COV_ENABLED` | true |
| `CoVThresholdPercent` | `COV_THRESHOLD_PCT` | 3 |
| `dataAcquisitionHeartbeatMinutes` | `BACNET_HEARTBEAT_MINUTES` | 15 |
| `dataAcquisitionTimeoutSecs` | `BACNET_IOCB_TIMEOUT` | 15 |
| `dataAcquisitionMaximumRetryAttempts` | `BACNET_MAX_RETRIES` | 3 |
| `controllermap` | seeded from `app.device_points.address` | n/a |

## 13 · Network watchdog + heartbeat

Same dual mechanism as gl_pbs:
- `network_watchdog` pings `BACNET_WATCH_IP` (gateway by default) every N seconds; on link loss it stops the BACnet event loop, waits for recovery, recreates `BIPSimpleApplication`.
- `heartbeat.txt` is touched each cycle; a sidecar restarts `dal-bacnet` if stale.

In compose this looks like:
```yaml
dal-bacnet:
  healthcheck:
    test: ["CMD","python","-c","import time,os,sys; sys.exit(0 if (time.time()-os.path.getmtime('/app/heartbeat.txt'))<300 else 1)"]
    interval: 30s
    timeout: 5s
    retries: 3
```

## 14 · Object-name handling (and naming gotcha)

The first cycle reads `objectName` for every object on every device and builds the map `{device_id: {bacnet_object_id: param_name}}`. Subsequent cycles read `presentValue` only. This is the two-phase `_name_list` / `_rpm_list` flip in `point_list_store.py`.

Naming pitfalls observed in production:
- Some DDC vendors put trailing whitespace in `objectName` — normalised by stripping.
- Some use Unicode middle-dots that look like ASCII dots — normalised by NFKC.
- Some return the device's own name on every object (mis-configuration) — DAL detects ≥ 3 objects with identical names and falls back to the CSV's `gl_param_name`.

## 15 · "What might come" — checklist of edge cases DAL handles

- BACnet device reboot mid-cycle → next cycle `unknown-object` → `BAD`, alert raised
- Time drift on the controller (some PLCs don't have RTC) → `STALE` if `received_at - measured_at > 60s` per [06](06_DATA_QUALITY_LAYER.md)
- Wrap-around on counters (uint16 / uint32 KWh meter) → detected by a negative delta vs LKG → DQ marks `SUSPECT` and the counter normaliser corrects in Tier 2
- Negative readings on unsigned points (sensor fault returns 0xFFFF / -1) → range check → `BAD`
- Mixed-VLAN routing via BBMD → POC single-subnet; v2 documents the BBMD config
- DDC firmware that double-encodes RPM responses → handled by the bacpypes fix already in gl_pbs
- Setpoint write rejected (read-only priority array slot) → reply.bacnet error → audit + agent retry with higher priority gated on approval

## 16 · References to legacy code we are *not* importing wholesale

We **copy** the read strategy + fallback fix verbatim (`bacnet/read_strategy.py`, `bacnet/read_thread.py`).

We **don't** import:
- The legacy Node BACnet client (`graylinx-be/gl_jupiter/hvacBACnetClient.js`) — Node `bacstack` is less mature than `bacpypes`; Python at the edge is the right call.
- The legacy CPM (control process module) in raw form — we adopt the *concepts* (start/stop sequence, setpoint authority, manual/auto modes) in the RL broker + agent tools, not the code (see [33_LEGACY_REFERENCE_PATTERNS](33_LEGACY_REFERENCE_PATTERNS.md)).
