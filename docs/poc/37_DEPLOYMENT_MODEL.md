# 37 · Deployment Model — One Customer, One Install, Their Hardware

The single most important sentence in this entire plan:

> **Each customer runs their own OMNYX install on their own hardware. Graylinx never hosts a customer's data.**

Every architectural choice in OMNYX follows from this. This doc fixes the rule and walks through what it implies for code, sales, support, ops.

## 1 · The rule

| Concern | Rule |
|---|---|
| Where OMNYX runs | On the **customer's** hardware, inside the **customer's** network |
| Who owns the data | The customer |
| Who hosts the LLM | Either Anthropic (cloud, if customer allows) or the customer (on-site GPU) — never Graylinx |
| Who hosts the database | The customer |
| Who hosts Kafka | The customer |
| Who hosts Keycloak | The customer |
| What Graylinx hosts | Internal dev bench + image registry + customer support tools. **Never** customer-runtime data. |

This is **single-tenant per install** in every customer-facing sense. The RLS multi-tenancy in the DB schema is a future option, not the shipping product.

## 2 · Why this is the rule

- Customers in the industrial / facility / government space require data sovereignty.
- "We host it for you" makes us a data processor, which is a different regulatory posture (GDPR, sectoral regulations) we don't want to take on at this stage.
- One install per customer means a security incident at one customer cannot touch another. No blast radius.
- It also means Graylinx is a software vendor, not a SaaS provider. Cleaner business model for now; SaaS option opens later if we want.

## 3 · What this means concretely

### 3.1 No shared anything

| Component | Per customer? |
|---|---|
| PostgreSQL cluster | One per customer install |
| Kafka cluster | One per customer install |
| Keycloak realm | One per customer install (the realm is named `omnyx` either way, but the instance is theirs) |
| Redis | One per customer install |
| MinIO (backups) | One per customer install |
| Prometheus + Grafana + Loki | One per customer install |
| Ollama (if Topology A) | One per customer install, on their hardware |
| Anthropic API key (if Topology C) | **One per customer** — they bring their own, or we provide one **billed to them** |

No "Graylinx central" anything in the customer plane.

### 3.2 The Graylinx internal server (Dell Pro Max Tower T2 with RTX 4000 Ada)

What it actually does:

| Use | Detail |
|---|---|
| Internal dev environment | The team builds and tests OMNYX images here |
| Model bench | Try new Ollama models before recommending them to a customer |
| Image registry mirror | Pull customer images from here when their site has no internet |
| Reference machine | "We built and tested this on hardware similar to what you're getting" |
| **Never** | Hosts a customer's database, agents, telemetry, or LLM calls |

A customer site **never** routes anything to this server.

### 3.3 Multi-tenant schema columns — what they are for

The `tenant_id` columns and RLS policies in [`08a_DATABASE_DESIGN`](08a_DATABASE_DESIGN.md) §7 are kept because:

| Reason | Detail |
|---|---|
| Future SaaS option | If Graylinx ever decides to host a SaaS edition, the schema is already correct |
| Logical scoping within a customer | A single customer with several legal entities may want `tenant_id` to model that |
| Audit clarity | Every business row has a `tenant_id` so cross-row joins are unambiguous |

For the shipping product: every customer install has **one** row in `app.tenants` (e.g. `unicharm`, `aiims_madurai`, `varanasi_airport`). All data carries that one tenant id. RLS still works, but it's degenerate.

## 4 · Topologies that follow

Re-stating from [`36_HARDWARE_REQUIREMENTS`](36_HARDWARE_REQUIREMENTS.md):

| Topology | LLM | Site GPU? | Net needed? |
|---|---|---|---|
| **A** — On-site Ollama | customer's GPU | yes | air-gap ok |
| **C** — Claude API | Anthropic | no | yes (outbound) |

There is no Topology B in the customer-facing product. The earlier draft included "central Graylinx LLM via Tailscale" — that was wrong for the customer plane and has been removed.

## 5 · Customer scenarios

### 5.1 One-site customer (Varanasi Airport)

- One physical box at the airport.
- OMNYX docker-compose stack on that box.
- Local BACnet UDP → DAL → Kafka → DB on the same box.
- Operators use the web UI on the same LAN.
- LLM: Topology C (Claude) if internet allowed; Topology A (RTX 4000 Ada SFF on the same box) otherwise.

### 5.2 Single-site customer with separate edge + server (Unicharm Chennai)

- Edge gateway near the BACnet network — runs `dal-bacnet` only.
- Server in the data centre — runs everything else.
- Edge and server linked by the customer's LAN.
- One install, two boxes, one customer's network.

### 5.3 Multi-site one customer (a hypothetical chain of buildings under one owner)

- One OMNYX server in the customer's central data centre.
- Thin DAL agents at each site (one container per site, BACnet-local).
- All DALs publish to the central Kafka.
- Operators see all sites in one portfolio dashboard.
- Still **one customer = one install**.

### 5.4 Multi-customer (Graylinx with 5 different customers)

- **Five separate installs**, each on the respective customer's hardware.
- Each is independent. No data crosses.
- Each customer holds their own Anthropic key (if Topology C) or runs their own Ollama (if Topology A).
- Graylinx supports each install through the support runbook, not by reaching into a shared database.

## 6 · Support model implications

| Need | Mechanism |
|---|---|
| We need logs to debug an issue | Customer ships sanitised log bundle (`make support-bundle`) or grants short-lived screen-share |
| We need to push a fix | New image version pulled from the customer's local registry mirror |
| We need to inspect their DB | We don't. We provide read-only queries the customer's ops runs |
| We monitor uptime | Customer's own Prometheus + Grafana; we get alerts only via their explicit forward, not by reach-in |

No "phone home" of customer data. Period.

## 7 · Billing implications

| Item | Who pays |
|---|---|
| OMNYX software licence | Customer pays Graylinx |
| Site hardware | Customer's capex |
| Internet bandwidth | Customer |
| Anthropic API tokens (Topology C) | Customer's billing account — or pass-through with markup, by contract |
| Customer's Tailscale / WireGuard for ops support | Customer |
| Graylinx engineering hours | Per support contract |

The financial model matches the deployment model: customer owns the runtime, Graylinx sells the software + expertise.

## 8 · What changes in the docs (already applied)

The earlier hardware doc included a "Topology B — central Graylinx LLM via Tailscale" option. That was incorrect for the customer-facing product and has been removed from [`36_HARDWARE_REQUIREMENTS.md`](36_HARDWARE_REQUIREMENTS.md). Customer topologies are now only A and C.

[`14_AUTH_KEYCLOAK §5`](14_AUTH_KEYCLOAK.md) (multi-tenancy hook) is preserved as schema-level future-proofing but is **not** the shipping operational story. Each install has one tenant in practice.

[`23_SECURITY §5`](23_SECURITY.md) network plane no longer references a Graylinx-hosted LLM endpoint. Outbound allowlist for Topology C is **Anthropic only**; for Topology A there is no outbound.

## 9 · The one-sentence test

If anyone asks "where does this customer's data go?" the answer is:

> "Nowhere. It stays on their hardware, in their network. The LLM either runs on their hardware too, or talks to Anthropic over the customer's own internet connection. Graylinx is not in the data path."

If you can't say that about a feature, it doesn't ship.
