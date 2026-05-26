import { pool, telemetryPool } from "./db";

/**
 * Alert Rule Engine — periodic evaluator.
 *
 * Reads enabled rules from app.alert_rules and evaluates each against
 * the latest telemetry. Inserts a new alert if a rule fires and there
 * is no open alert for that (rule, point) pair.
 *
 * Rule shape (stored in alert_rules.condition_json):
 *   { type: "threshold", point_id: "GL ...", operator: ">", value: 30 }
 *   { type: "threshold", equipment_id: "equip-ddc01", point_pattern: "%temp%", operator: ">", value: 30 }
 *   { type: "offline",   point_id: "GL ...", stale_seconds: 300 }
 */

interface RuleRow {
  id: string;
  tenant_id: string;
  name: string;
  condition_type: string;
  condition_json: ThresholdCond | OfflineCond;
  severity: string;
  enabled: boolean;
  equipment_filter: string[] | null;
}

interface ThresholdCond {
  type: "threshold";
  point_id?: string;
  equipment_id?: string;
  operator: ">" | "<" | ">=" | "<=" | "==";
  value: number;
}

interface OfflineCond {
  type: "offline";
  point_id?: string;
  equipment_id?: string;
  stale_seconds: number;
}

const EVAL_INTERVAL_MS = 30_000; // every 30s

export function startAlertEvaluator() {
  console.log("[alert-evaluator] starting, interval=30s");
  setInterval(evaluateAll, EVAL_INTERVAL_MS);
  // Run once at startup
  setTimeout(evaluateAll, 5_000);
}

async function evaluateAll() {
  try {
    const rules = await loadEnabledRules();
    if (rules.length === 0) return;

    let fired = 0;
    for (const rule of rules) {
      try {
        const result = await evaluateRule(rule);
        if (result) fired++;
      } catch (e) {
        console.error(`[alert-evaluator] rule ${rule.name} failed:`, (e as Error).message);
      }
    }
    if (fired > 0) console.log(`[alert-evaluator] ${fired} alert(s) fired across ${rules.length} rules`);
  } catch (e) {
    console.error("[alert-evaluator] cycle failed:", (e as Error).message);
  }
}

async function loadEnabledRules(): Promise<RuleRow[]> {
  const client = await pool.connect();
  try {
    const res = await client.query<RuleRow>(
      `SELECT id, tenant_id, name, condition_type, condition_json, severity, enabled, equipment_filter
         FROM app.alert_rules WHERE enabled = true`,
    );
    return res.rows;
  } finally {
    client.release();
  }
}

interface LatestReading { point_id: string; value_num: number | null; measured_at: string; quality_flag: string; }

async function evaluateRule(rule: RuleRow): Promise<boolean> {
  if (rule.condition_type === "threshold") {
    return evaluateThreshold(rule, rule.condition_json as ThresholdCond);
  }
  if (rule.condition_type === "offline") {
    return evaluateOffline(rule, rule.condition_json as OfflineCond);
  }
  return false;
}

async function pointIdsForRule(tenantId: string, cond: ThresholdCond | OfflineCond): Promise<string[]> {
  if (cond.point_id) return [cond.point_id];
  if (cond.equipment_id) {
    const client = await pool.connect();
    try {
      await client.query("SELECT set_config('app.current_tenant_id', $1, true)", [tenantId]);
      const res = await client.query<{ point_id: string }>(
        `SELECT point_id FROM app.device_points WHERE equipment_id=$1 AND is_active=true`,
        [cond.equipment_id],
      );
      return res.rows.map((r) => r.point_id);
    } finally {
      client.release();
    }
  }
  return [];
}

async function evaluateThreshold(rule: RuleRow, cond: ThresholdCond): Promise<boolean> {
  const points = await pointIdsForRule(rule.tenant_id, cond);
  if (points.length === 0) return false;

  // Get latest reading for each point
  const latest = await telemetryPool.query<LatestReading>(
    `SELECT DISTINCT ON (point_id) point_id, value_num, measured_at, quality_flag
       FROM telemetry.readings
      WHERE tenant_id=$1 AND point_id = ANY($2::text[]) AND value_num IS NOT NULL
      ORDER BY point_id, measured_at DESC`,
    [rule.tenant_id, points],
  );

  let fired = false;
  for (const r of latest.rows) {
    if (r.quality_flag !== "GOOD") continue; // skip bad data
    const v = r.value_num;
    if (v === null) continue;
    const breach =
      (cond.operator === ">"  && v >  cond.value) ||
      (cond.operator === ">=" && v >= cond.value) ||
      (cond.operator === "<"  && v <  cond.value) ||
      (cond.operator === "<=" && v <= cond.value) ||
      (cond.operator === "==" && v === cond.value);
    if (!breach) continue;

    const inserted = await openAlertIfNew(rule, r.point_id, {
      reason: "threshold_breach",
      value: v,
      operator: cond.operator,
      threshold: cond.value,
      measured_at: r.measured_at,
    });
    if (inserted) fired = true;
  }
  return fired;
}

async function evaluateOffline(rule: RuleRow, cond: OfflineCond): Promise<boolean> {
  const points = await pointIdsForRule(rule.tenant_id, cond);
  if (points.length === 0) return false;

  const cutoff = new Date(Date.now() - cond.stale_seconds * 1000).toISOString();
  const stale = await telemetryPool.query<{ point_id: string; last_seen: string | null }>(
    `WITH last_seen AS (
       SELECT point_id, MAX(measured_at) AS last_seen
         FROM telemetry.readings
        WHERE tenant_id=$1 AND point_id = ANY($2::text[])
        GROUP BY point_id
     )
     SELECT p AS point_id, ls.last_seen
       FROM unnest($2::text[]) p
       LEFT JOIN last_seen ls ON ls.point_id = p
      WHERE ls.last_seen IS NULL OR ls.last_seen < $3`,
    [rule.tenant_id, points, cutoff],
  );

  let fired = false;
  for (const s of stale.rows) {
    const inserted = await openAlertIfNew(rule, s.point_id, {
      reason: "offline",
      last_seen: s.last_seen,
      stale_seconds: cond.stale_seconds,
    });
    if (inserted) fired = true;
  }
  return fired;
}

async function openAlertIfNew(
  rule: RuleRow,
  pointId: string,
  payload: Record<string, unknown>,
): Promise<boolean> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('app.current_tenant_id', $1, true)", [rule.tenant_id]);

    // Find equipment_id from device_points
    const eqRes = await client.query<{ equipment_id: string }>(
      `SELECT equipment_id FROM app.device_points WHERE tenant_id=$1 AND point_id=$2 LIMIT 1`,
      [rule.tenant_id, pointId],
    );
    const equipmentId = eqRes.rows[0]?.equipment_id ?? null;

    // Dedup: skip if there is already an open alert for this rule+point
    const dup = await client.query(
      `SELECT 1 FROM app.alerts
        WHERE tenant_id=$1 AND rule_id=$2 AND point_id=$3 AND status IN ('open','acknowledged')
        LIMIT 1`,
      [rule.tenant_id, rule.id, pointId],
    );
    if ((dup.rowCount ?? 0) > 0) {
      await client.query("COMMIT");
      return false;
    }

    await client.query(
      `INSERT INTO app.alerts
         (tenant_id, equipment_id, point_id, rule_id, severity, status, title, detail, payload)
       VALUES ($1,$2,$3,$4,$5,'open',$6,$7,$8::jsonb)`,
      [
        rule.tenant_id,
        equipmentId,
        pointId,
        rule.id,
        rule.severity,
        rule.name,
        `Rule "${rule.name}" fired on ${pointId}`,
        JSON.stringify(payload),
      ],
    );
    await client.query("COMMIT");
    return true;
  } catch (e) {
    await client.query("ROLLBACK");
    throw e;
  } finally {
    client.release();
  }
}
