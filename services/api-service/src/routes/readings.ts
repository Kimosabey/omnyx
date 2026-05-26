import type { FastifyInstance } from "fastify";
import { readQuery } from "../db";
import { getTenantId } from "../auth";

export async function readingsRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // Latest reading per point for one equipment
  fastify.get<{ Params: { id: string }; Querystring: { from?: string; to?: string; resolution?: string } }>(
    "/api/v1/equipment/:id/readings", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const { from, to, resolution = "raw" } = req.query;
      const fromTs = from ?? new Date(Date.now() - 3_600_000).toISOString();
      const toTs   = to   ?? new Date().toISOString();

      let sql: string;
      if (resolution === "1m") {
        sql = `SELECT bucket AS ts, point_id, avg AS value, sample_count
               FROM telemetry.readings_1m
               WHERE tenant_id=$1 AND point_id IN (
                 SELECT point_id FROM app.device_points WHERE equipment_id=$2)
               AND bucket BETWEEN $3 AND $4
               ORDER BY point_id, ts`;
      } else if (resolution === "5m") {
        sql = `SELECT bucket AS ts, point_id, avg AS value, sample_count
               FROM telemetry.readings_5m
               WHERE tenant_id=$1 AND point_id IN (
                 SELECT point_id FROM app.device_points WHERE equipment_id=$2)
               AND bucket BETWEEN $3 AND $4
               ORDER BY point_id, ts`;
      } else {
        sql = `SELECT measured_at AS ts, point_id, value_num AS value, quality_flag, dq_flags
               FROM telemetry.readings
               WHERE tenant_id=$1 AND point_id IN (
                 SELECT point_id FROM app.device_points WHERE equipment_id=$2)
               AND measured_at BETWEEN $3 AND $4
               ORDER BY point_id, ts
               LIMIT 5000`;
      }

      const rows = await readQuery(tid, sql, [tid, req.params.id, fromTs, toTs]);
      reply.send({ data: rows, resolution, from: fromTs, to: toTs });
    },
  );

  // Latest snapshot — one value per point for one equipment
  fastify.get<{ Params: { id: string } }>(
    "/api/v1/equipment/:id/readings/latest", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const rows = await readQuery(
        tid,
        `SELECT DISTINCT ON (r.point_id)
           r.point_id, r.measured_at AS ts, r.value_num AS value,
           r.quality_flag, r.dq_flags
         FROM telemetry.readings r
         JOIN app.device_points dp ON dp.point_id = r.point_id
         WHERE r.tenant_id=$1 AND dp.equipment_id=$2
         ORDER BY r.point_id, r.measured_at DESC`,
        [tid, req.params.id],
      );
      reply.send({ data: rows });
    },
  );
}
