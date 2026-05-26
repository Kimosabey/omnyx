import type { FastifyInstance } from "fastify";
import { readQuery, withTenant } from "../db";
import { getTenantId } from "../auth";

export async function equipmentRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // List all equipment
  fastify.get("/api/v1/equipment", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const rows = await readQuery(
      tid,
      `SELECT id, name, type, subtype, location, floor, building, is_active, metadata, created_at
       FROM app.equipment
       WHERE is_active = true
       ORDER BY name`,
    );
    reply.send({ data: rows });
  });

  // Get single equipment + its points
  fastify.get<{ Params: { id: string } }>("/api/v1/equipment/:id", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const [eq] = await readQuery(
      tid,
      `SELECT e.*,
        coalesce(json_agg(dp ORDER BY dp.point_id) FILTER (WHERE dp.id IS NOT NULL), '[]') AS points
       FROM app.equipment e
       LEFT JOIN app.device_points dp ON dp.equipment_id = e.id
       WHERE e.id = $1
       GROUP BY e.id`,
      [req.params.id],
    );
    if (!eq) return reply.code(404).send({ error: "Not found" });
    reply.send({ data: eq });
  });

  // Create equipment
  fastify.post<{ Body: Record<string, unknown> }>("/api/v1/equipment", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const b = req.body as Record<string, unknown>;
    const [row] = await withTenant(tid, async (client) => {
      const res = await client.query(
        `INSERT INTO app.equipment (tenant_id, name, type, subtype, location, floor, building, metadata)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
         RETURNING *`,
        [tid, b.name, b.type, b.subtype ?? null, b.location ?? null, b.floor ?? null, b.building ?? null, b.metadata ?? {}],
      );
      return res.rows;
    });
    reply.code(201).send({ data: row });
  });

  // Update equipment
  fastify.patch<{ Params: { id: string }; Body: Record<string, unknown> }>(
    "/api/v1/equipment/:id", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const b = req.body as Record<string, unknown>;
      const [row] = await withTenant(tid, async (client) => {
        const res = await client.query(
          `UPDATE app.equipment
           SET name=$2, type=$3, location=$4, is_active=$5, updated_at=now()
           WHERE id=$1
           RETURNING *`,
          [req.params.id, b.name, b.type, b.location, b.is_active ?? true],
        );
        return res.rows;
      });
      if (!row) return reply.code(404).send({ error: "Not found" });
      reply.send({ data: row });
    },
  );
}
