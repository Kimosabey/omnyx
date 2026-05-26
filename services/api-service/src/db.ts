import { Pool, PoolClient } from "pg";
import { config } from "./config";

// ---- App / Primary DB pool ----------------------------------
// Used for source.*, app.*, audit.* read/write operations.
export const pool = new Pool({
  connectionString: config.appDbUrl,
  min: config.dbPoolMin,
  max: config.dbPoolMax,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});
pool.on("error", (err) => {
  console.error("[app-db] idle client error:", err.message);
});

// ---- Telemetry / TimescaleDB pool ---------------------------
// Read-only access for dashboards, charts, reports.
export const telemetryPool = new Pool({
  connectionString: config.telemetryDbUrl,
  min: 1,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});
telemetryPool.on("error", (err) => {
  console.error("[telemetry-db] idle client error:", err.message);
});

/**
 * Execute fn inside a transaction with tenant RLS context set.
 * Every request goes through this so RLS policies fire correctly.
 */
export async function withTenant<T>(
  tenantId: string,
  fn: (client: PoolClient) => Promise<T>
): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('app.current_tenant_id', $1, true)", [tenantId]);
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}

/** Read-only query against the app/primary DB with tenant context. */
export async function readQuery<T>(
  tenantId: string,
  sql: string,
  params: unknown[] = []
): Promise<T[]> {
  const client = await pool.connect();
  try {
    await client.query("SELECT set_config('app.current_tenant_id', $1, true)", [tenantId]);
    const res = await client.query(sql, params);
    return res.rows as T[];
  } finally {
    client.release();
  }
}

/** Read-only query against the telemetry DB (TimescaleDB). No RLS. */
export async function telemetryQuery<T>(
  sql: string,
  params: unknown[] = []
): Promise<T[]> {
  const client = await telemetryPool.connect();
  try {
    const res = await client.query(sql, params);
    return res.rows as T[];
  } finally {
    client.release();
  }
}
