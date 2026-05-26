import type { FastifyInstance } from "fastify";
import { readQuery, withTenant } from "../db";
import { getTenantId } from "../auth";

export async function notificationRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  fastify.get<{ Querystring: { unread?: string } }>(
    "/api/v1/notifications", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const userId = (req.user as Record<string, unknown>).sub as string;
      const unread = req.query.unread === "true";
      const rows = await readQuery(
        tid,
        `SELECT * FROM app.notifications
         WHERE tenant_id=$1 AND user_id=$2
           AND ($3 = false OR read_at IS NULL)
         ORDER BY created_at DESC
         LIMIT 50`,
        [tid, userId, unread],
      );
      reply.send({ data: rows });
    },
  );

  fastify.post<{ Params: { id: string } }>(
    "/api/v1/notifications/:id/read", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const userId = (req.user as Record<string, unknown>).sub as string;
      await withTenant(tid, async (client) => {
        await client.query(
          `UPDATE app.notifications SET read_at=now()
           WHERE id=$1 AND user_id=$2 AND read_at IS NULL`,
          [req.params.id, userId],
        );
      });
      reply.send({ ok: true });
    },
  );

  fastify.post("/api/v1/notifications/read-all", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const userId = (req.user as Record<string, unknown>).sub as string;
    await withTenant(tid, async (client) => {
      await client.query(
        `UPDATE app.notifications SET read_at=now()
         WHERE tenant_id=$1 AND user_id=$2 AND read_at IS NULL`,
        [tid, userId],
      );
    });
    reply.send({ ok: true });
  });
}
