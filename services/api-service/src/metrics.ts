import { Registry, Counter, Histogram, collectDefaultMetrics } from "prom-client";
import http from "http";
import { config } from "./config";

export const registry = new Registry();
collectDefaultMetrics({ register: registry });

export const httpRequests = new Counter({
  name: "api_http_requests_total",
  help: "Total HTTP requests",
  labelNames: ["method", "route", "status"],
  registers: [registry],
});

export const httpDuration = new Histogram({
  name: "api_http_duration_seconds",
  help: "HTTP request duration",
  labelNames: ["method", "route"],
  buckets: [0.005, 0.01, 0.05, 0.1, 0.5, 1, 5],
  registers: [registry],
});

export const dbQueryDuration = new Histogram({
  name: "api_db_query_duration_seconds",
  help: "DB query duration",
  labelNames: ["query"],
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
  registers: [registry],
});

export function startMetricsServer(): void {
  const server = http.createServer(async (_req, res) => {
    res.setHeader("Content-Type", registry.contentType);
    res.end(await registry.metrics());
  });
  server.listen(config.metricsPort, () => {
    console.log(`[metrics] listening on :${config.metricsPort}`);
  });
}
