import { Pool, PoolClient } from "pg";
import { config } from "./config";

export const pool = new Pool({
  connectionString: config.postgresUrl,
  min: config.dbPoolMin,
  max: config.dbPoolMax,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

pool.on("error", (err) => {
  console.error("[db] idle client error:", err.message);
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

/** Run a read-only query without transaction overhead. */
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
