import type { FastifyInstance } from "fastify";
import { readQuery, telemetryQuery } from "../db";
import { getTenantId } from "../auth";

export async function readingsRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // Helper: resolve equipment_id → list of point_ids (from app DB)
  async function pointsForEquipment(tenantId: string, equipmentId: string): Promise<string[]> {
    const rows = await readQuery<{ point_id: string }>(
      tenantId,
      `SELECT point_id FROM app.device_points WHERE equipment_id=$1 AND is_active=true`,
      [equipmentId],
    );
    return rows.map((r) => r.point_id);
  }

  // Time-range telemetry for one equipment (cross-DB: app → timescaledb)
  fastify.get<{ Params: { id: string }; Querystring: { from?: string; to?: string; resolution?: string } }>(
    "/api/v1/equipment/:id/readings", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const { from, to, resolution = "raw" } = req.query;
      const fromTs = from ?? new Date(Date.now() - 3_600_000).toISOString();
      const toTs   = to   ?? new Date().toISOString();

      const pointIds = await pointsForEquipment(tid, req.params.id);
      if (pointIds.length === 0) return reply.send({ data: [], resolution, from: fromTs, to: toTs });

      let sql: string;
      if (resolution === "1m") {
        sql = `SELECT bucket AS ts, point_id, avg AS value, sample_count
               FROM telemetry.readings_1m
               WHERE tenant_id=$1 AND point_id = ANY($2::text[])
                 AND bucket BETWEEN $3 AND $4
               ORDER BY point_id, ts`;
      } else if (resolution === "5m") {
        sql = `SELECT bucket AS ts, point_id, avg AS value, sample_count
               FROM telemetry.readings_5m
               WHERE tenant_id=$1 AND point_id = ANY($2::text[])
                 AND bucket BETWEEN $3 AND $4
               ORDER BY point_id, ts`;
      } else if (resolution === "1h") {
        sql = `SELECT bucket AS ts, point_id, avg AS value, sample_count
               FROM telemetry.readings_1h
               WHERE tenant_id=$1 AND point_id = ANY($2::text[])
                 AND bucket BETWEEN $3 AND $4
               ORDER BY point_id, ts`;
      } else {
        sql = `SELECT measured_at AS ts, point_id, value_num AS value, quality_flag, dq_flags
               FROM telemetry.readings
               WHERE tenant_id=$1 AND point_id = ANY($2::text[])
                 AND measured_at BETWEEN $3 AND $4
               ORDER BY point_id, ts
               LIMIT 5000`;
      }

      const rows = await telemetryQuery(sql, [tid, pointIds, fromTs, toTs]);
      reply.send({ data: rows, resolution, from: fromTs, to: toTs });
    },
  );

  // Latest snapshot — one value per point for one equipment
  fastify.get<{ Params: { id: string } }>(
    "/api/v1/equipment/:id/readings/latest", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const pointIds = await pointsForEquipment(tid, req.params.id);
      if (pointIds.length === 0) return reply.send({ data: [] });

      const rows = await telemetryQuery(
        `SELECT DISTINCT ON (point_id)
           point_id, measured_at AS ts, value_num AS value,
           quality_flag, dq_flags
         FROM telemetry.readings
         WHERE tenant_id=$1 AND point_id = ANY($2::text[])
         ORDER BY point_id, measured_at DESC`,
        [tid, pointIds],
      );
      reply.send({ data: rows });
    },
  );
}
