# 21 · Personas & UX Goals

PRD §04 personas, restated with concrete OMNYX touchpoints. Every UI screen and agent workflow ties back to one of these.

## 1 · Portfolio Manager (primary)

| Attribute | Value |
|---|---|
| Scope | 50–500 sites; cross-domain |
| Primary device | Desktop browser, occasional tablet |
| Cares about | Uptime, SLA, cost, team productivity |
| KPIs they watch | Portfolio quality score, open critical alerts, cost trend, RL gain, agent autonomy % |
| OMNYX touchpoints | `/` portfolio dashboard · `/reports` weekly executive report · `/approvals` for Tier 4–5 |
| Agent autonomy reviewed via | Daily Operations Report (Workflow B) + Agent Activity Feed summary |

## 2 · Site Operator (primary)

| Attribute | Value |
|---|---|
| Scope | One site, on-site shift |
| Primary device | Tablet kiosk + occasional desktop |
| Cares about | What to do right now |
| KPIs they watch | Open alerts on their site, devices online, twin sync, pending approvals |
| OMNYX touchpoints | `/sites/:id` · `/alerts` · `/work-orders` · `/approvals` for Tier 3 |
| Voice expectation | Calm, declarative, "Scan now", no marketing words |

## 3 · Operations Engineer (secondary)

| Attribute | Value |
|---|---|
| Scope | One or more sites; deep technical |
| Primary device | Desktop |
| Cares about | Tuning twin/RL/DQ, audit of agent decisions, historical analytics |
| KPIs they watch | Twin MAPE, DQ flag distribution, RL safety violations, rule false-positive rate |
| OMNYX touchpoints | `/dq` · `/twin/:id` · `/rl` · `/admin/rules` · `/admin/equipment` |
| Agent override authority | High — can pause / replay workflows |

## 4 · Maintenance Technician (secondary)

| Attribute | Value |
|---|---|
| Scope | Assigned WOs |
| Primary device | Tablet kiosk |
| Cares about | Next job, diagnosis, parts, time |
| OMNYX touchpoints | `/work-orders/kiosk` (big-tap mode) |
| Confirms / overrides | Twin diagnosis on WO close — feeds twin accuracy KPI |

## 5 · AI Operations Specialist (NEW in v1.1)

| Attribute | Value |
|---|---|
| Scope | All AI subsystems (DQ, twin, RL, agentic) |
| Primary device | Desktop |
| Cares about | Agent decision quality, model drift, cost ceiling |
| KPIs they watch | Validator rejection rate, agent token spend vs budget, RL agent reward vs baseline, twin prediction MAPE |
| OMNYX touchpoints | `/agents` · `/agents/workflows` (YAML editor) · `/rl` · `/twin` · `/dq` |
| Promotion authority | RL agent shadow→live, twin model deployment, agent workflow activation |

## 6 · Domain Specialists (tertiary)

For the POC only HVAC (Energy Manager / Quality Manager / Production Scheduler in the PRD) — these are served by **THERMYNX** routes under `/extensions/thermynx/*`, role-gated by `thermynx_hvac`.

---

## 7 · UX goals tied back to personas

| UX goal | Which persona | How OMNYX delivers |
|---|---|---|
| One-glance health | Portfolio Mgr | Portfolio dashboard heatmap; daily Workflow-B summary |
| Next-action clarity | Site Operator | Alert inbox sorted by severity + twin diagnosis preview |
| Tablet ergonomics | Technician | Kiosk WO view; large-tap targets; offline-capable form |
| Auditability | Ops Engineer, AI Ops, Mgr | Agent activity feed, audit.events table, exportable |
| Trust building | All | Default everything to Tier 2 max; shadow-first RL; Validator gates |
| Calm voice | All | THERMYNX design system rules in [`../../BRANDING.md`](../../BRANDING.md) |
