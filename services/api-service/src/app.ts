import Fastify from "fastify";
import cors from "@fastify/cors";
import { authPlugin } from "./auth";
import { healthRoutes } from "./routes/health";
import { equipmentRoutes } from "./routes/equipment";
import { readingsRoutes } from "./routes/readings";
import { alertsRoutes } from "./routes/alerts";
import { workOrderRoutes } from "./routes/work-orders";
import { agentRoutes } from "./routes/agent";
import { reportRoutes } from "./routes/reports";
import { notificationRoutes } from "./routes/notifications";
import { httpRequests, httpDuration } from "./metrics";

export async function buildApp() {
  const fastify = Fastify({
    logger: {
      level: process.env.LOG_LEVEL ?? "info",
      transport: process.env.NODE_ENV === "development"
        ? { target: "pino-pretty" }
        : undefined,
    },
  });

  // CORS
  await fastify.register(cors, { origin: true });

  // Auth (Keycloak JWKS)
  await fastify.register(authPlugin);

  // Prometheus request metrics hook
  fastify.addHook("onResponse", (req, reply, done) => {
    const route = req.routerPath ?? req.url;
    httpRequests.labels(req.method, route, String(reply.statusCode)).inc();
    httpDuration.labels(req.method, route).observe(reply.elapsedTime / 1000);
    done();
  });

  // Routes
  await fastify.register(healthRoutes);
  await fastify.register(equipmentRoutes);
  await fastify.register(readingsRoutes);
  await fastify.register(alertsRoutes);
  await fastify.register(workOrderRoutes);
  await fastify.register(agentRoutes);
  await fastify.register(reportRoutes);
  await fastify.register(notificationRoutes);

  // 404 handler
  fastify.setNotFoundHandler((_req, reply) => {
    reply.code(404).send({ error: "Not found" });
  });

  // Error handler
  fastify.setErrorHandler((err, _req, reply) => {
    fastify.log.error(err);
    reply.code(err.statusCode ?? 500).send({ error: err.message });
  });

  return fastify;
}
