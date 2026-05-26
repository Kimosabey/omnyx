import type { FastifyInstance } from "fastify";
import { readQuery, withTenant } from "../db";
import { getTenantId } from "../auth";

export async function alertsRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // List alerts (filterable)
  fastify.get<{ Querystring: { status?: string; severity?: string; limit?: string } }>(
    "/api/v1/alerts", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const status   = req.query.status   ?? "open";
      const severity = req.query.severity;
      const limit    = Math.min(parseInt(req.query.limit ?? "100"), 500);

      const rows = await readQuery(
        tid,
        `SELECT a.*, e.name AS equipment_name
         FROM app.alerts a
         LEFT JOIN app.equipment e ON e.id = a.equipment_id
         WHERE a.tenant_id=$1
           AND ($2::text IS NULL OR a.status=$2)
           AND ($3::text IS NULL OR a.severity=$3)
         ORDER BY a.created_at DESC
         LIMIT $4`,
        [tid, status || null, severity || null, limit],
      );
      reply.send({ data: rows });
    },
  );

  // Get single alert
  fastify.get<{ Params: { id: string } }>("/api/v1/alerts/:id", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const [row] = await readQuery(
      tid,
      `SELECT a.*, e.name AS equipment_name
       FROM app.alerts a
       LEFT JOIN app.equipment e ON e.id = a.equipment_id
       WHERE a.id=$1`,
      [req.params.id],
    );
    if (!row) return reply.code(404).send({ error: "Not found" });
    reply.send({ data: row });
  });

  // Acknowledge alert
  fastify.post<{ Params: { id: string } }>("/api/v1/alerts/:id/acknowledge", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const user = (req.user as Record<string, unknown>).sub as string;
    const [row] = await withTenant(tid, async (client) => {
      const res = await client.query(
        `UPDATE app.alerts
         SET status='acknowledged', acknowledged_at=now(), acknowledged_by=$2, updated_at=now()
         WHERE id=$1 AND status='open'
         RETURNING *`,
        [req.params.id, user],
      );
      return res.rows;
    });
    if (!row) return reply.code(404).send({ error: "Not found or already acknowledged" });
    reply.send({ data: row });
  });

  // Resolve alert
  fastify.post<{ Params: { id: string }; Body: { notes?: string } }>(
    "/api/v1/alerts/:id/resolve", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const [row] = await withTenant(tid, async (client) => {
        const res = await client.query(
          `UPDATE app.alerts
           SET status='resolved', resolved_at=now(), updated_at=now(),
               payload = payload || $2::jsonb
           WHERE id=$1 AND status IN ('open','acknowledged')
           RETURNING *`,
          [req.params.id, JSON.stringify({ resolution_notes: req.body?.notes })],
        );
        return res.rows;
      });
      if (!row) return reply.code(404).send({ error: "Not found or already resolved" });
      reply.send({ data: row });
    },
  );

  // Alert rules
  fastify.get("/api/v1/rules", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const rows = await readQuery(tid,
      `SELECT * FROM app.alert_rules WHERE tenant_id=$1 ORDER BY name`, [tid]);
    reply.send({ data: rows });
  });

  fastify.post<{ Body: Record<string, unknown> }>("/api/v1/rules", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const b = req.body as Record<string, unknown>;
    const [row] = await withTenant(tid, async (client) => {
      const res = await client.query(
        `INSERT INTO app.alert_rules
           (tenant_id, name, description, condition_type, condition_json, severity, enabled, notify_roles)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
         RETURNING *`,
        [tid, b.name, b.description, b.condition_type, b.condition_json,
         b.severity ?? "warning", b.enabled ?? true, b.notify_roles ?? []],
      );
      return res.rows;
    });
    reply.code(201).send({ data: row });
  });
}
