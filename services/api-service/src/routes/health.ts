import type { FastifyInstance } from "fastify";
import { pool } from "../db";

export async function healthRoutes(fastify: FastifyInstance) {
  fastify.get("/healthz", { logLevel: "silent" }, async (_req, reply) => {
    try {
      await pool.query("SELECT 1");
      reply.send({ status: "ok", ts: new Date().toISOString() });
    } catch {
      reply.code(503).send({ status: "degraded", db: "unreachable" });
    }
  });
}
