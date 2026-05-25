# 27 · API Reference Overview

The **authoritative API reference is auto-generated** from Fastify route schemas via `@fastify/swagger` and served at:

- Dev / POC: http://localhost:8000/docs (Swagger UI) and http://localhost:8000/openapi.json

This document gives the **route catalogue** so reviewers can see the surface without running the service. Detailed shapes live in the OpenAPI spec.

## 1 · Conventions

| Convention | Value |
|---|---|
| Base path | `/api/v1` |
| Auth | `Authorization: Bearer <JWT>` (Keycloak) for users; `x-api-key` for service accounts (in `app.api_keys`) |
| Tenant scoping | Derived from JWT; cross-tenant impossible (RLS) |
| Pagination | Cursor-based: `?cursor=...&limit=...`, response `next_cursor` |
| Time params | ISO-8601 UTC; `from`/`to` inclusive/exclusive documented per route |
| Errors | RFC-7807 problem+json |
| Idempotency | `Idempotency-Key` header on all `POST` that create state |
| Rate limiting | Per-route, per-user; default 60 req/min for read, 30 req/min for write |

### 1.1 API stance for Phase 1

The master PDF mentioned REST + GraphQL. The shipping contract in this repo is intentionally:

- **REST + OpenAPI** for request/response APIs
- **WebSocket** for live push channels
- **No GraphQL in Phase 1**

Reason: one audited API surface for both humans and agents, one auth path, one codegen source for
SDKs, and one approval/audit story. If GraphQL is ever added later it will be additive, not the
primary contract.

## 2 · Catalogue by group

### Equipment & sites
- `GET /equipment` — tree (sites → buildings → equipment)
- `GET /equipment/{id}` — detail
- `GET /equipment/{id}/points` — points + DQ config
- `GET /sites/{id}/snapshot` — same shape as the WS `PlantSnapshot`
- `GET /sites/{id}/health` — quality + alert + WO rollup

### Telemetry
- `GET /telemetry` — `?point_id=&from=&to=&res=raw|1m|5m|1h` (cursor-pageable)
- `GET /telemetry/latest` — last GOOD per point for one device
- `GET /telemetry/compare` — multi-point aligned
- `POST /telemetry/export` — async export (`format=csv|parquet|json`); response has `job_id` + signed URL when ready

### Alerts
- `GET /alerts` — `?status=&severity=&device_id=&source=`
- `GET /alerts/{id}`
- `POST /alerts/{id}/ack` `{ note? }`
- `POST /alerts/{id}/resolve` `{ note?, resolution_code }`

### Rules
- `GET /rules`, `POST /rules`, `PATCH /rules/{id}`, `DELETE /rules/{id}`
- `POST /rules/test` — dry-run a rule against historical data

### Work orders
- `GET /work-orders` — `?status=&technician_id=&device_id=`
- `POST /work-orders`
- `PATCH /work-orders/{id}` — state transitions enforced server-side
- `POST /work-orders/{id}/parts` — add/remove parts
- `POST /work-orders/{id}/close` — requires diagnosis confirmation block

### Technicians
- `GET /technicians`
- `POST /technicians/suggest` `{ work_order_id }` — returns ranked list (see [20 §M6.1](20_MODULE_COVERAGE.md))

### Data quality
- `GET /dq/config/{point_id}` / `PUT /dq/config/{point_id}`
- `GET /dq/events` — `?point_id=&from=&to=`
- `GET /dq/scores` — sensor health scores
- `POST /dq/run-tier2` — trigger Tier-2 job ad-hoc (admin)

### Digital Twin
- `GET /twin/models`
- `GET /twin/{device_id}` — latest state + RUL
- `POST /twin/{device_id}/simulate` `{ inputs, horizon_minutes }`
- `GET /twin/{device_id}/calibration-history`

### Reinforcement Learning
- `GET /rl/agents`
- `GET /rl/agents/{id}` / `GET /rl/agents/{id}/performance`
- `POST /rl/agents/{id}/promote` — Tier-4 protected
- `POST /rl/agents/{id}/pause` / `POST /rl/agents/{id}/resume`

### Agentic AI
- `GET /agents/workflows`
- `POST /agents/workflows` / `PATCH /agents/workflows/{id}`
- `POST /agents/run` `{ workflow_id, payload }`
- `GET /agents/runs/{id}` (returns steps)
- `POST /agents/runs/{id}/cancel`

### Approvals
- `GET /approvals` — `?status=pending` for inbox
- `POST /approvals/{id}/decide` `{ status: approved|rejected, reason? }`

### Tools (agent gateway)
- `POST /tools/{name}` — every tool from [11 §3](11_AGENTIC_AI.md); only callable by the agentic-ai service account or by users with the appropriate tier permission

### Reports
- `GET /reports` — list
- `GET /reports/{id}` — metadata + signed URL
- `POST /reports/custom` — see [20 §M5.3](20_MODULE_COVERAGE.md)

### Admin & commissioning
- `GET/POST/PATCH /admin/users`
- `GET/POST/PATCH /admin/equipment`
- `GET/POST/PATCH /admin/device-points`
- `POST /admin/bundles/apply` — config bundle import [20 §M7.1](20_MODULE_COVERAGE.md)
- `POST /admin/knowledge` — corpus upload

These are also the Phase 1 commissioning endpoints. Combined with the import/discovery flows in
[30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md), they cover source onboarding, mapping,
bundle apply, and live activation without a separate commissioning GUI.

### Auth
- handled by `@fastify/jwt` middleware; no app-level login endpoint (Keycloak is the IdP)

### Health & metrics
- `GET /healthz`
- `GET /metrics` — Prometheus exposition

## 3 · WebSocket

Connect `wss://<host>:8765/?token=<JWT>`. Control frames are JSON:

```json
// client → server
{ "type":"subscribe", "channels":["plant.snapshot.unicharm_chennai","alerts.unicharm_chennai","agent.activity.<workflow_id>"] }
{ "type":"unsubscribe", "channels":[ ... ] }
{ "type":"ping" }

// server → client
{ "type":"snapshot", "data": PlantSnapshot }
{ "type":"alert",    "data": Alert }
{ "type":"agent",    "data": AgentEvent }
{ "type":"pong" }
{ "type":"error",    "code":"...", "msg":"..." }
```

## 4 · Versioning

- Breaking changes go behind a new path prefix (`/api/v2`).
- Additive changes (new fields, new endpoints) ship under `/api/v1`.
- Deprecation header `Sunset: <date>` on routes scheduled for removal.

## 5 · Client SDKs

| SDK | Status |
|---|---|
| TypeScript | Auto-generated from `openapi.json` via `openapi-typescript-codegen`; lives in `shared/clients/ts/` |
| Python | Auto-generated via `openapi-python-client`; lives in `shared/clients/py/` |

Both are published as private packages (`@omnyx/api-client` and `omnyx-api-client`) in v2; POC uses them directly from the repo via path imports.

## 6 · OpenAPI spec location

`infra/openapi/openapi.yaml` is the committed spec, dumped from a running api-service via `make export-openapi`. CI fails if the committed spec drifts from what Fastify emits — keeps doc-as-code honest.
