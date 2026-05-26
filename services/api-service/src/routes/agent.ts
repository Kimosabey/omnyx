import type { FastifyInstance } from "fastify";
import { readQuery, withTenant } from "../db";
import { getTenantId } from "../auth";

export async function agentRoutes(fastify: FastifyInstance) {
  const pre = { preHandler: [fastify.authenticate] };

  // List agent workflows
  fastify.get("/api/v1/agent/workflows", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const rows = await readQuery(
      tid,
      `SELECT * FROM app.agent_workflows WHERE tenant_id=$1 ORDER BY name`,
      [tid],
    );
    reply.send({ data: rows });
  });

  // Trigger a workflow manually
  fastify.post<{ Params: { id: string }; Body: Record<string, unknown> }>(
    "/api/v1/agent/workflows/:id/trigger", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const [run] = await withTenant(tid, async (client) => {
        const res = await client.query(
          `INSERT INTO app.agent_runs (tenant_id, workflow_id, trigger_payload, status)
           VALUES ($1,$2,$3,'running')
           RETURNING *`,
          [tid, req.params.id, req.body ?? {}],
        );
        return res.rows;
      });
      // Actual execution is handled by agentic-ai service consuming from Kafka
      reply.code(202).send({ data: run, message: "Workflow queued" });
    },
  );

  // List agent runs
  fastify.get<{ Querystring: { workflow_id?: string; status?: string; limit?: string } }>(
    "/api/v1/agent/runs", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const limit = Math.min(parseInt(req.query.limit ?? "50"), 200);
      const rows = await readQuery(
        tid,
        `SELECT ar.*, aw.name AS workflow_name
         FROM app.agent_runs ar
         LEFT JOIN app.agent_workflows aw ON aw.id = ar.workflow_id
         WHERE ar.tenant_id=$1
           AND ($2::text IS NULL OR ar.workflow_id=$2)
           AND ($3::text IS NULL OR ar.status=$3)
         ORDER BY ar.started_at DESC
         LIMIT $4`,
        [tid, req.query.workflow_id || null, req.query.status || null, limit],
      );
      reply.send({ data: rows });
    },
  );

  // Get single run with full result
  fastify.get<{ Params: { id: string } }>("/api/v1/agent/runs/:id", pre, async (req, reply) => {
    const tid = getTenantId(req);
    const [row] = await readQuery(
      tid,
      `SELECT ar.*, aw.name AS workflow_name
       FROM app.agent_runs ar
       LEFT JOIN app.agent_workflows aw ON aw.id = ar.workflow_id
       WHERE ar.id=$1`,
      [req.params.id],
    );
    if (!row) return reply.code(404).send({ error: "Not found" });
    reply.send({ data: row });
  });

  // Approval requests
  fastify.get<{ Querystring: { status?: string } }>(
    "/api/v1/approvals", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const rows = await readQuery(
        tid,
        `SELECT * FROM app.approval_requests
         WHERE tenant_id=$1
           AND ($2::text IS NULL OR status=$2)
           AND (status != 'expired' OR expires_at > now())
         ORDER BY created_at DESC
         LIMIT 100`,
        [tid, req.query.status || null],
      );
      reply.send({ data: rows });
    },
  );

  // Approve / reject
  fastify.post<{ Params: { id: string; action: string }; Body: { note?: string } }>(
    "/api/v1/approvals/:id/:action", pre, async (req, reply) => {
      const tid = getTenantId(req);
      const user = (req.user as Record<string, unknown>).sub as string;
      const action = req.params.action === "approve" ? "approved" : "rejected";
      const [row] = await withTenant(tid, async (client) => {
        const res = await client.query(
          `UPDATE app.approval_requests
           SET status=$2, approved_by=$3, resolved_at=now()
           WHERE id=$1 AND status='pending' AND expires_at > now()
           RETURNING *`,
          [req.params.id, action, user],
        );
        return res.rows;
      });
      if (!row) return reply.code(404).send({ error: "Not found, already resolved, or expired" });
      reply.send({ data: row });
    },
  );
}
