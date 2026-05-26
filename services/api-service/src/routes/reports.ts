import type { FastifyInstance } from "fastify";
import { readQuery, telemetryQuery } from "../db";
import { getTenantId } from "../auth";

export async function reportRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // Daily operations report (mixes app DB and telemetry DB)
  fastify.get<{ Querystring: { date?: string } }>(
    "/api/v1/reports/daily", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const date = req.query.date ?? new Date().toISOString().slice(0, 10);
      const from = `${date}T00:00:00Z`;
      const to   = `${date}T23:59:59Z`;

      const [alerts, workOrders, dqEvents] = await Promise.all([
        readQuery(
          tid,
          `SELECT severity, status, count(*) AS count
           FROM app.alerts
           WHERE tenant_id=$1 AND created_at BETWEEN $2 AND $3
           GROUP BY severity, status`,
          [tid, from, to],
        ),
        readQuery(
          tid,
          `SELECT status, priority, count(*) AS count
           FROM app.work_orders
           WHERE tenant_id=$1 AND created_at BETWEEN $2 AND $3
           GROUP BY status, priority`,
          [tid, from, to],
        ),
        telemetryQuery(
          `SELECT quality_flag, count(*) AS count
           FROM telemetry.readings
           WHERE tenant_id=$1 AND measured_at BETWEEN $2 AND $3
           GROUP BY quality_flag`,
          [tid, from, to],
        ),
      ]);

      reply.send({
        data: { date, alerts, work_orders: workOrders, data_quality: dqEvents },
      });
    },
  );

  // Custom range report (resolves equipment → points in app DB, then queries telemetry)
  fastify.get<{ Querystring: { from: string; to: string; equipment_id?: string } }>(
    "/api/v1/reports/custom", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const { from, to, equipment_id } = req.query;

      let pointIds: string[] | null = null;
      if (equipment_id) {
        const rows = await readQuery<{ point_id: string }>(
          tid,
          `SELECT point_id FROM app.device_points WHERE equipment_id=$1 AND is_active=true`,
          [equipment_id],
        );
        pointIds = rows.map((r) => r.point_id);
        if (pointIds.length === 0) return reply.send({ data: { from, to, readings: [] } });
      }

      const sql = pointIds
        ? `SELECT point_id, bucket, avg, high, low, sample_count
           FROM telemetry.readings_1h
           WHERE tenant_id=$1 AND bucket BETWEEN $2 AND $3 AND point_id = ANY($4::text[])
           ORDER BY point_id, bucket LIMIT 10000`
        : `SELECT point_id, bucket, avg, high, low, sample_count
           FROM telemetry.readings_1h
           WHERE tenant_id=$1 AND bucket BETWEEN $2 AND $3
           ORDER BY point_id, bucket LIMIT 10000`;
      const params: unknown[] = pointIds ? [tid, from, to, pointIds] : [tid, from, to];

      const readings = await telemetryQuery(sql, params);
      reply.send({ data: { from, to, readings } });
    },
  );

  // Audit log
  fastify.get<{ Querystring: { limit?: string } }>(
    "/api/v1/audit", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const limit = Math.min(parseInt(req.query.limit ?? "100"), 1000);
      const rows = await readQuery(
        tid,
        `SELECT * FROM audit.events WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT $2`,
        [tid, limit],
      );
      reply.send({ data: rows });
    },
  );
}
