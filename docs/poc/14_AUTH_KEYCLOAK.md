# 14 · Auth — Keycloak realm, RBAC, agent authorisation

PRD §05 mandates Keycloak self-hosted, on-prem. POC ships a sealed realm export so you bring it up with one command.

## 1 · Realm

| Item | Value |
|---|---|
| Realm | `omnyx` |
| SSO methods | OIDC, SAML 2.0 (toggle), LDAP/AD federation (toggle) |
| Token TTL | access 5 m, refresh 30 m, idle 30 m |
| MFA | TOTP, optional WebAuthn |

## 2 · Clients

| Client | Type | Used by |
|---|---|---|
| `omnyx-frontend` | public, PKCE | React SPA |
| `omnyx-api` | confidential, service account | api-service (back-channel calls, token introspection) |
| `omnyx-agents` | confidential, service account | agentic-ai (calls tools on behalf of the agent identity) |
| `omnyx-edge` | confidential | dal-bacnet for `cmd.bacnet.*` reply auth |

## 3 · Roles (mirror PRD personas)

| Role | Scope | Capabilities |
|---|---|---|
| `admin` | global | full RBAC, can edit DQ config, twin models, rule definitions, users |
| `manager` | site / org | approve Tier 4–5 actions, see all reports |
| `operator` | site | acknowledge alerts, manage work orders, approve Tier 3 |
| `technician` | per-skill | execute / close work orders on kiosk |
| `analyst` | read | analytics, historical trends |
| `ai_ops_specialist` | global | tune DQ, twin, RL, agent workflows; approve agent promotions |
| `readonly` | scoped | dashboards only |
| `agent_executor` | service-account only | implicit on agentic-ai's token |

Roles map to JWT claims `realm_access.roles[]`. Fastify decorator `requireRole(...)` enforces.

## 4 · Agent authorisation model (PRD §08, Approval Tiers)

Each tool in the gateway declares an `approval_tier`. The api-service decides at request time:

```
allow if:
  user (or service-account) has role X
AND
  approval_tier <= max_tier_for_user (per realm role config)
AND (if tier >= 3):
  request carries a valid Approval token
       (issued by an authorised human via POST /approvals/{id}/decide)
```

Approval token = a short-lived JWT (15 m) signed by api-service with `sub=approval:<id>`, encoding the original tool call hash so it can't be reused.

## 5 · Multi-tenancy hook

`omnyx` realm has groups `tenant:<org_id>`. Every user is in exactly one tenant group; api-service injects `tenant_id` into every query. POC ships with a single tenant `tenant:graylinx_demo` plus a seeded `tenant:unicharm` for the existing HVAC users.

## 6 · Realm export

Lives at `infra/keycloak/realm-export.json`. On `docker compose up` the keycloak container imports it (`KEYCLOAK_IMPORT=/opt/keycloak/data/import/realm-export.json`). Re-export on every realm change with:

```bash
docker exec keycloak /opt/keycloak/bin/kc.sh export --dir /opt/keycloak/data/export --realm omnyx
```

## 7 · Default POC users

| Username | Roles | Use case |
|---|---|---|
| `demo_admin` | admin | bring-up |
| `demo_manager` | manager | approvals demo |
| `demo_operator` | operator | shift use |
| `demo_tech` | technician | tablet kiosk |
| `demo_aiops` | ai_ops_specialist | tune DQ/RL/agents |
| `agent_runner` | agent_executor (service) | agentic-ai daemon |

Passwords are templated in `infra/keycloak/POC_PASSWORDS.md`; replace them during first bring-up and do not reuse them across deployments.
