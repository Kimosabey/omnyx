import type { FastifyInstance } from "fastify";
import { readQuery, withTenant } from "../db";
import { getTenantId } from "../auth";

export async function workOrderRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // List work orders
  fastify.get<{ Querystring: { status?: string; assigned_to?: string } }>(
    "/api/v1/work-orders", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const rows = await readQuery(
        tid,
        `SELECT wo.*, t.name AS technician_name, e.name AS equipment_name
         FROM app.work_orders wo
         LEFT JOIN app.technicians t ON t.id = wo.assigned_to
         LEFT JOIN app.equipment   e ON e.id = wo.alert_id::text
         WHERE wo.tenant_id=$1
           AND ($2::text IS NULL OR wo.status=$2)
           AND ($3::text IS NULL OR wo.assigned_to=$3)
         ORDER BY wo.created_at DESC
         LIMIT 200`,
        [tid, req.query.status || null, req.query.assigned_to || null],
      );
      reply.send({ data: rows });
    },
  );

  // Get single WO
  fastify.get<{ Params: { id: string } }>("/api/v1/work-orders/:id", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const [row] = await readQuery(
      tid,
      `SELECT wo.*, t.name AS technician_name
       FROM app.work_orders wo
       LEFT JOIN app.technicians t ON t.id = wo.assigned_to
       WHERE wo.id=$1`,
      [req.params.id],
    );
    if (!row) return reply.code(404).send({ error: "Not found" });
    reply.send({ data: row });
  });

  // Create WO
  fastify.post<{ Body: Record<string, unknown> }>("/api/v1/work-orders", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const user = (req.user as Record<string, unknown>).sub as string;
    const b = req.body as Record<string, unknown>;
    const [row] = await withTenant(tid, async (client) => {
      const res = await client.query(
        `INSERT INTO app.work_orders
           (tenant_id, alert_id, title, description, priority, assigned_to, created_by, scheduled_at, metadata)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
         RETURNING *`,
        [tid, b.alert_id ?? null, b.title, b.description ?? null,
         b.priority ?? "medium", b.assigned_to ?? null, user,
         b.scheduled_at ?? null, b.metadata ?? {}],
      );
      return res.rows;
    });
    reply.code(201).send({ data: row });
  });

  // Update WO status
  fastify.patch<{ Params: { id: string }; Body: Record<string, unknown> }>(
    "/api/v1/work-orders/:id", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const b = req.body as Record<string, unknown>;
      const [row] = await withTenant(tid, async (client) => {
        const res = await client.query(
          `UPDATE app.work_orders
           SET status=$2, assigned_to=coalesce($3, assigned_to),
               resolution_notes=coalesce($4, resolution_notes),
               completed_at=CASE WHEN $2='completed' THEN now() ELSE completed_at END,
               actual_hours=coalesce($5, actual_hours),
               updated_at=now()
           WHERE id=$1
           RETURNING *`,
          [req.params.id, b.status, b.assigned_to ?? null,
           b.resolution_notes ?? null, b.actual_hours ?? null],
        );
        return res.rows;
      });
      if (!row) return reply.code(404).send({ error: "Not found" });
      reply.send({ data: row });
    },
  );

  // Technician list (for assignment UI)
  fastify.get("/api/v1/technicians", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const rows = await readQuery(
      tid,
      `SELECT t.*, coalesce(json_agg(ts) FILTER (WHERE ts.technician_id IS NOT NULL), '[]') AS skills
       FROM app.technicians t
       LEFT JOIN app.technician_skills ts ON ts.technician_id = t.id
       WHERE t.tenant_id=$1
       GROUP BY t.id
       ORDER BY t.name`,
      [tid],
    );
    reply.send({ data: rows });
  });
}
