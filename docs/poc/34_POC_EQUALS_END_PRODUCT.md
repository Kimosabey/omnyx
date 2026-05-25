# 34 · "POC = End Product" — What That Really Means

Short answer: **yes**, but read it precisely.

The POC is not a demo throwaway. It is the same on-prem architecture, same codebase, same
containers, same database schema, and same deployment model that go to the first paying customer.

What it does **not** mean is "every protocol, vendor connector, and future vertical from the master
PDF is exercised on the dev laptop." The POC proves the **production backbone and the HVAC-first
Phase 1 deployment path**. Customer-specific onboarding and integration paths sit on top of that
same backbone.

See [01_SCOPE_AND_SUCCESS.md](01_SCOPE_AND_SUCCESS.md) and
[38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md).

## 1 · What stays the same

| Layer | POC | First beta customer |
|---|---|---|
| Languages | Python 3.12 + Node 20 + React 18 | same |
| Database | PostgreSQL 16 + TimescaleDB + pgvector | same |
| Event bus | Kafka 7.6 KRaft | same |
| Cache + queue | Redis 7.2 | same |
| Auth | Keycloak 24 | same |
| LLM mode | Claude API or Ollama fallback | same |
| Container runtime | Docker 24 + Compose v2 | Compose v2 or k8s |
| Monitoring | Prometheus + Grafana + Loki | same |
| DB schema | exact DDL in [08a](08a_DATABASE_DESIGN.md) | same |
| Service set | 18 containers in [02 §3](02_ARCHITECTURE.md) | same |
| API contract | `/api/v1` + OpenAPI + WebSocket | same |
| Tool registry model | Planner / Executor / Validator calling API tools | same |
| Deployment rule | customer-owned hardware, customer-owned data | same |

Graylinx's internal server and dev laptop stay **internal-only**. Each customer site is a
self-contained OMNYX install on the customer's own hardware
([37_DEPLOYMENT_MODEL.md](37_DEPLOYMENT_MODEL.md)).

## 2 · What changes between POC and beta

| Concern | POC | Beta |
|---|---|---|
| Data source | `gl_pbs` simulator + replayed Unicharm history | Real DDCs / customer sources |
| Deployment | Single-host Docker Compose | Single-host or two-host customer topology; k8s only where needed |
| Kafka brokers | 1 | 1 or 3 depending on hardening target |
| Postgres | Single instance | Single instance or HA topology depending on customer hardening |
| TLS / PKI | self-signed or local-only | customer CA / hardened network posture |
| Backups | local/nightly | customer backup target + restore drill |
| Notifications | demo/test routing | customer SMTP / SMS / webhook endpoints |
| Inventory and mapping | simulator / replay seed data | customer BACnet discovery, CSV import, or legacy import |

Those changes are deployment, onboarding, and hardening work. They do **not** require a rewrite of
the product backbone.

## 3 · What the gate review actually proves

When the POC passes, we have proven:

- real-time monitoring, alerts, work orders, reporting, DQ, twin, RL, and agent workflows
- the on-prem service topology and data model
- the shipping REST/OpenAPI/WebSocket contract
- the approval, audit, auth, and observability model
- the HVAC-first operational path that the first customer deployment will use

That is the core meaning of "POC = end product".

## 4 · Phase 1 capabilities that exist but are not fully exercised in the gate demo

These are still part of the Phase 1 product boundary:

| Capability | How Phase 1 ships it |
|---|---|
| Commissioning tool | Runbook + admin APIs + import/discovery/bundle workflow, not a standalone GUI yet |
| Device / point mapping | Tenant/site/equipment/device-point records + bundle-managed config |
| Live config push | `admin/bundles/apply` + service refresh paths |
| Customer onboarding | CSV import, BACnet discovery, legacy MySQL import, twin/RL binding |
| HVAC breadth beyond the demo plant | Preserved in schema, taxonomy, and rollout path, even if the gate demo stays Unicharm-style |
| Vendor integrations | Supported through the product boundary and deployment plan, but exercised only when a real customer needs them |

The important point is: **same artefacts, different day-0 inputs**.

## 5 · What is genuinely deferred

| Deferred | Why this does not break "POC = product" |
|---|---|
| Multi-site federation | One site is already a complete deployment; federation is scale-out, not a new core architecture |
| Runtime Modbus / OPC-UA / MQTT adapters | Adapter framework exists; BACnet is the exercised path today |
| CMMS / ERP / MES bi-directional sync | Export / notification / webhook seams are preserved; full sync lands with v2/customer work |
| Custom workflow builder UI | Workflows already run; YAML authoring is enough for Phase 1 |
| Plant-level RL coordination | Single-agent shadow proves the runtime and safety path |
| Autonomous Tier-3+ mode | Approval model already exists; autonomy ceiling increases later |
| On-prem LLM as the primary/default path | Ollama fallback already exists; making it default is a later packaging decision |
| Factory vertical execution | Roadmap and architecture remain in place, but executable factory deliverables are not part of the 12-week POC |

These are scope decisions, not evidence that the POC needs to be rebuilt before a customer can use
it.

## 6 · Acceptance rule

The bring-up runbook ([16_POC_RUNBOOK.md](16_POC_RUNBOOK.md)) and the 17 tests in
[17_TEST_PLAN.md](17_TEST_PLAN.md) prove the **executable POC gate scope** and the product backbone
required for the first customer deployment.

Replacing the simulator with real DDCs is an onboarding step, not a restart-from-scratch step.

## 7 · One-paragraph summary

POC = the same OMNYX product backbone the customer installs: same services, same schema, same API,
same auth/audit model, same deployment rule, same HVAC-first operating path. The laptop demo proves
the executable gate scope; customer onboarding then swaps in real inventory, real mappings, real
credentials, and real plant data on top of those same artefacts. No throwaway, but also no false
claim that the simulator demo alone exhausts every Phase 1 path in the master PDF.
