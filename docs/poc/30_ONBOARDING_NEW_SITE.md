# 30 · Onboarding a New Site / Customer

The "day-2" runbook. How a new customer goes from "we want OMNYX" to "operator using it in
production".

In Phase 1, this runbook is also the practical **commissioning tool contract**: onboarding is
delivered through import/discovery flows, admin APIs, and config bundles rather than a separate
visual commissioning builder. See [38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md).

## 1 · Decisions to take before any technical work

| Decision | Default | Notes |
|---|---|---|
| Vertical extension(s) | THERMYNX (HVAC) | FORGYNX etc once shipping |
| Single tenant or multi-tenant install | Single | Multi-tenant only for hosted SaaS later |
| Site count | 1 | Multi-site = v2 |
| Deployment topology | A · Single-host | (A) POC, (B) Two-host, (C) k8s per [15_DEPLOYMENT](15_DEPLOYMENT_ONPREMISE.md) |
| Compliance mode | none | GDPR / SOX / HIPAA-equiv per [23_SECURITY §8](23_SECURITY.md) |
| LLM backend | Claude | Switch to Ollama for air-gap; documented but slower |
| Approval autonomy default | Tier 2 max | Per [19_RISKS R8](19_RISKS.md) |
| Brand surface | OMNYX (+ vertical) | Custom co-brand v2 |

Capture in a one-page onboarding form. Output is committed to `infra/config_bundles/<customer>.yaml`.

## 2 · Infrastructure provisioning

### 2.1 Hardware

Per [15 §A.1 / §D](15_DEPLOYMENT_ONPREMISE.md). Confirm:
- CPU / RAM / disk sized for the number of sites and protocols.
- Network: BACnet UDP reachable from the edge host(s).
- Outbound: only `api.anthropic.com` (or none if Ollama).

### 2.2 OS

Ubuntu 22.04 LTS preferred. Docker 24 + Compose v2. Firewall configured per [23_SECURITY §5](23_SECURITY.md).

### 2.3 Install

```bash
git clone https://internal/git/omnyx.git
cd omnyx
cp infra/compose/.env.example infra/compose/.env
# fill in: POSTGRES_PASSWORD, KEYCLOAK_ADMIN_PASSWORD, ANTHROPIC_API_KEY (or set LLM_BACKEND=ollama)
make build
make up
```

Verify the eight health endpoints from [16 §10](16_POC_RUNBOOK.md).

## 3 · Tenant and users

```bash
# Provision tenant
psql -U omnyx_admin -d omnyx -c \
  "INSERT INTO app.tenants(id,name) VALUES ('<tenant_id>','<Display Name>');"

# Keycloak realm role + first admin
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh create users \
  -r omnyx -s username=<email> -s enabled=true
# (assign admin role, send credential email, force password change)
```

## 4 · Equipment inventory

The single biggest onboarding task. Either:

### Path A — Import from Unicharm-style MySQL (existing customer)

```bash
make seed-from-mysql \
  MYSQL_URL='mysql://ro:<pw>@<host>:3306/<db>' \
  TENANT_ID=<tenant_id> \
  SITE_ID=<site_id>
```

The job introspects `*_normalized` tables, maps them to `app.equipment` and `app.device_points` (using legacy_table/legacy_column back-pointers), and queues `dal-replay` for history backfill.

### Path B — Build from CSV (new customer, no legacy DB)

Use the gl_pbs `eqp_name_handling.csv` shape: `ddc_id, bacnet_object_id, bacnet_property, gl_eqp_type, gl_eqp_instance, gl_param_name, unit`. Provided to the customer as a template.

```bash
make seed-from-csv FILE=infra/seeds/<customer>_equipment.csv TENANT_ID=<tenant_id>
```

### Path C — Discover via BACnet

```bash
make discover BACNET_NET=<cidr>
# Generates a candidate eqp_name_handling.csv from Who-Is + name-resolution
# Engineer reviews / edits / commits.
```

## 5 · Data quality config

Apply a starting bundle:

```bash
make apply-bundle BUNDLE=infra/config_bundles/<customer>.yaml
# bundles contain: rules, dq_config, twin_models, rl_agents, agent_workflows, pm_templates
```

If unsure, start with `generic_hvac.yaml` and tune over the first 2 weeks via [19_RISKS R6](19_RISKS.md) noise-tuning loop.

## 6 · Twin model selection

For each equipment of supported type, attach the appropriate twin model:

```sql
UPDATE app.equipment SET twin_model_id = 'chiller_v1' WHERE type = 'chiller' AND tenant_id = '<t>';
UPDATE app.equipment SET twin_model_id = 'cooling_tower_v1' WHERE type = 'cooling_tower' AND tenant_id = '<t>';
```

If history exists, run twin calibration:

```bash
docker compose exec twin-broker python -m calibrate --tenant=<t> --device=<id>
# Reports MAPE; if > 5 %, ops engineer reviews twin parameters.
```

## 7 · RL agent (optional at onboarding)

Don't enable on day 1. After 14 days of historic shadow data:

```bash
docker compose exec rl-broker python -m bootstrap_agent \
  --tenant <t> --device chiller_1 \
  --reward kw_per_tr --safety-bounds '{"chw_setpoint":[5.5,10]}'
```

This trains offline on the replay buffer and creates a SHADOW agent.

## 8 · Agentic workflows

Workflows A (Investigate Alert), B (Daily Report), C (Drift Handling), D (Widespread Quality) ship in the bundle. Verify each fires:

```bash
make e2e-workflows TENANT=<t>
# 1. simulate an alert and observe Workflow A
# 2. cron-trigger Workflow B at on-demand path
# 3. mock a drift event for Workflow C
# 4. mass-silence for Workflow D
```

Set the customer's monthly LLM budget cap in `app.feature_flags`:

```sql
INSERT INTO app.feature_flags(tenant_id, flag, payload)
VALUES ('<t>','agent_budget','{"usd_per_month": 500, "warn_pct": 80}');
```

## 9 · Notifications

```bash
# Email
psql -c "UPDATE app.tenants SET metadata=jsonb_set(metadata,'{smtp}','{\"host\":\"...\",\"from\":\"omnyx@<customer>\"}') WHERE id='<t>';"

# SMS (Twilio) and Webhook (CMMS) per same pattern; documented in infra/operations/NOTIFICATIONS.md
```

## 10 · Operator training

- 30-minute walkthrough using the [29_DEMO_SCRIPT](29_DEMO_SCRIPT.md).
- Tablet kiosk handover for technicians.
- Document the customer's runbook: who acks Tier-3 approvals, escalation contacts.

## 11 · Go-live checklist

- [ ] All eight health endpoints green for 24 h.
- [ ] DQ Tier-1 inline duration p95 < 50 ms.
- [ ] Telemetry-to-WS p95 < 5 s.
- [ ] At least one twin model attached with MAPE < 5 %.
- [ ] Agent run cost vs budget under 80 %.
- [ ] Approval inbox covered by named on-call.
- [ ] Backups verified (`make backup-pg` + restore drill).
- [ ] Audit table writable, append-only role verified.
- [ ] Knowledge corpus ingested.
- [ ] Tenant feature flags set.

## 12 · First 30 days

Track and review with the customer weekly:

| Week | Focus |
|---|---|
| 1 | Noise-tune DQ thresholds + alert rules — expected high false-positive rate at first |
| 2 | Confirm twin MAPE stable, calibrate if needed |
| 3 | Start RL shadow training |
| 4 | Review agent autonomy %, validator rejection rate; promote workflows from Tier 2 to higher as trust builds |

## 13 · Decommission of legacy systems

If migrating from a legacy stack (e.g., Unicharm THERMYNX path), follow [`../migration/UNICHARM_TO_OMNYX.md`](../migration/UNICHARM_TO_OMNYX.md) phases M1 → M2 → M3 → M4.
