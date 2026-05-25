# Migration — Unicharm MySQL → OMNYX TimescaleDB

How the existing THERMYNX deployment at Unicharm lands in the new OMNYX schema **without breaking the live HVAC product**.

## 1 · Current state (verified)

| Source | Shape | Volume |
|---|---|---|
| MySQL `unicharm` (Tailscale, port 3307) | Per-equipment `*_normalized` tables: `chiller_1_normalized`, `chiller_2_normalized`, `cooling_tower_1_normalized`, `cooling_tower_2_normalized`, `condenser_pump_0102_normalized`, `condenser_pump_03_normalized`, `primary_pump_{1,2,3}_normalized`, `plant_normalized` | ~131 tables, ~18.9 M rows total |
| Raw vendor exports | `*_metric`, `*_om_p` (do not query, ETL'd upstream into `_normalized`) | Many |
| Facility tables | `building`, `floor`, `zone`, `area`, `device`, `campus`, … | Few thousand rows |
| THERMYNX app state | Postgres `thermynx_app` — `analysis_audit`, `anomalies`, `agent_runs`, `threads`, `messages`, `embeddings` | Small |

Verified DDL in [DATABASE_SCHEMA_REFERENCE.md](../../../../HVAC%20AI%20Operations%20Intelligence%20Platform/docs/reference/DATABASE_SCHEMA_REFERENCE.md). Full DDL export at [unicharm_db_ddl.md](../../../../HVAC%20AI%20Operations%20Intelligence%20Platform/unicharm_db_ddl.md).

## 2 · Target state in OMNYX

One Postgres database with TimescaleDB. See [`../poc/08_STORAGE_TIMESCALEDB.md`](../poc/08_STORAGE_TIMESCALEDB.md):

- `telemetry.readings` (hypertable) — replaces every `*_normalized` table.
- `app.equipment`, `app.device_points` — dimension model with `legacy_table` / `legacy_column` back-pointers.
- `app.alerts`, `app.work_orders`, `app.agent_runs` — replace `thermynx_app` equivalents.
- `embeddings.knowledge` — pgvector, replaces `thermynx_app.embeddings`.

## 3 · Migration phases

### Phase M1 — Shadow read (read both)

| What | Why |
|---|---|
| OMNYX comes up next to existing Unicharm + THERMYNX | Zero risk to live operations |
| `dal-replay` back-fills `telemetry.readings` from `*_normalized` (read-only) | OMNYX has full history for twin + RL + agentic |
| OMNYX REST is up; Frontend shows OMNYX dashboard | Demo to leadership in parallel with current product |

Verification queries from [`08_STORAGE_TIMESCALEDB.md §5.3`](../poc/08_STORAGE_TIMESCALEDB.md).

### Phase M2 — Live tap (still no writes to Unicharm)

| What | Why |
|---|---|
| `dal-bacnet` deployed at Unicharm site, in parallel with their existing BACnet reader | Live BACnet feed lands in OMNYX without disturbing existing ETL |
| Both paths populate; we compare per-minute aggregates | Build confidence that OMNYX numbers match THERMYNX |

Comparison job runs nightly:

```sql
-- For each chiller, for each metric, compare yesterday's avg between systems.
SELECT
  o.point_id,
  AVG(o.value_num)              AS omnyx_avg,
  u.unicharm_avg,
  ABS(AVG(o.value_num) - u.unicharm_avg) / NULLIF(u.unicharm_avg,0) AS pct_diff
FROM telemetry.readings o
JOIN (
  SELECT 'chiller_1.kw_per_tr' AS point_id, AVG(kw_per_tr) AS unicharm_avg
  FROM unicharm.chiller_1_normalized
  WHERE slot_time >= NOW() - INTERVAL 1 DAY
) u USING (point_id)
WHERE o.measured_at >= NOW() - INTERVAL '1 day'
  AND o.source = 'bacnet'
GROUP BY o.point_id, u.unicharm_avg;
```

Pass criterion: `pct_diff < 0.5 %` per point for 7 consecutive days.

### Phase M3 — Cutover

| What | Why |
|---|---|
| THERMYNX UI re-points to OMNYX API (federated routes) | Users see the same screens with the new pipes |
| Existing Unicharm ETL is paused | OMNYX is the source of truth |
| `*_normalized` tables kept read-only for 90 days | Roll-back safety |
| THERMYNX app state migrated: `thermynx_app.threads` → `app.threads` (or kept; THERMYNX namespace) | Conversation history preserved |

### Phase M4 — Decommission

| What | When |
|---|---|
| Unicharm MySQL retained read-only | M3 + 90 d |
| Final archive snapshot to MinIO | M3 + 90 d |
| Old MySQL shut down | M3 + 120 d |

## 4 · THERMYNX continuity

THERMYNX's screens and prompts already work — we don't rewrite them. Three changes only:

1. **Datasource** — its repository layer points at `telemetry.readings` instead of `chiller_*_normalized`. Same SQL columns become rows; the existing `CHILLER_COLS` list maps to `point_id IN ('chiller_1.kw','chiller_1.kw_per_tr',...)`. A thin compatibility view ships if needed:

   ```sql
   CREATE VIEW unicharm_compat.chiller_1_normalized AS
   SELECT
     measured_at AS slot_time,
     MAX(value_num) FILTER (WHERE point_id='chiller_1.kw')            AS kw,
     MAX(value_num) FILTER (WHERE point_id='chiller_1.tr')            AS tr,
     MAX(value_num) FILTER (WHERE point_id='chiller_1.kw_per_tr')     AS kw_per_tr,
     ...
   FROM telemetry.readings_1m
   WHERE point_id LIKE 'chiller_1.%'
   GROUP BY measured_at;
   ```

   Lets the existing FastAPI code keep its queries unchanged during cut-over.

2. **App state** — `thermynx_app.analysis_audit` / `anomalies` / `agent_runs` data migrate into the matching `app.*` tables; existing THERMYNX FastAPI uses a small DAO shim to keep writing.

3. **LLM** — THERMYNX keeps Ollama qwen2.5:14b for its own analyzer; OMNYX agentic AI uses Claude. They don't share an LLM client.

## 5 · Cutover risks (linked to [19_RISKS.md](../poc/19_RISKS.md))

- R4: Unicharm RO credential — coordinate with Unicharm DBA, document refresh path.
- R10: bundle bloat — module-federate THERMYNX routes (`/extensions/thermynx/*`).
- Specific to migration:
  - **Clock skew**: ensure OMNYX, dal-bacnet, Unicharm MySQL all use UTC; convert any local-timestamp columns at the boundary.
  - **Unit drift**: legacy columns are sometimes in non-SI units; the seed table includes explicit `unit` per point so consumers don't guess.
  - **`is_running` semantics**: replay materialises `is_running` as a separate boolean point `chiller_1.is_running` rather than dropping it — preserves the `WHERE is_running = 1` filter the existing analytics rely on.

## 6 · Rollback plan

At any point during M1–M3, OMNYX can be turned off without affecting Unicharm:

```bash
cd /d/Harshan/graylinx-v2/omnyx/infra/compose
docker compose down                 # keeps Postgres volume
# THERMYNX + Unicharm continue running, untouched.
```

To re-enable: `docker compose up -d`. M3 cutover is the first reversible-with-effort point; before that it's trivially reversible.
