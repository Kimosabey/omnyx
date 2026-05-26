import { buildApp } from "./app";
import { startMetricsServer } from "./metrics";
import { config } from "./config";
import { pool } from "./db";

async function main() {
  startMetricsServer();

  const app = await buildApp();

  try {
    await app.listen({ port: config.port, host: "0.0.0.0" });
    app.log.info(`API service running on :${config.port}`);
  } catch (err) {
    app.log.error(err);
    await pool.end();
    process.exit(1);
  }

  const shutdown = async (signal: string) => {
    app.log.info(`${signal} received, shutting down`);
    await app.close();
    await pool.end();
    process.exit(0);
  };

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT",  () => shutdown("SIGINT"));
}

main();
