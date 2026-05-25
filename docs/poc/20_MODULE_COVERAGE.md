# 20 · PRD Module Coverage Audit

Every feature in **`docs/source/prd/CloudOps_Core_PRD_v1_0.docx` §07–§09** and **`docs/source/prd/CloudOps_Data_Quality_Layer.docx`** is mapped to its OMNYX plan location. Anything not covered elsewhere gets a full spec inline below.

Legend
- ✅ **POC** — built in the 12-week MVP plan
- 🅥 **v2** — deferred to Phase 2 per PRD §10
- 🅦 **v3** — deferred to Phase 3 per PRD §10
- 🆕 **Gap filled here** — wasn't in another doc, now is

---

## A · Module-by-module audit

### Module 1 — Real-Time Monitoring & Control

| Feature | Status | Plan location |
|---|---|---|
| Portfolio Dashboard | ✅ POC | [13_FRONTEND §2](13_FRONTEND.md) |
| Site-Level Device Dashboard | ✅ POC | [13_FRONTEND §2](13_FRONTEND.md) |
| Live Telemetry Streaming (WS) | ✅ POC | [12_BACKEND_API_WS §5](12_BACKEND_API_WS.md) |
| Device Detail View w/ Twin Overlay | ✅ POC | [13_FRONTEND §4](13_FRONTEND.md) |
| Device Registry & Asset Mgmt | ✅ POC | [08a_DATABASE_DESIGN §6.3](08a_DATABASE_DESIGN.md) |
| Parameter Control & Write-Back | ✅ POC | [11_AGENTIC_AI §3](11_AGENTIC_AI.md) tools + [12_BACKEND §2](12_BACKEND_API_WS.md) |
| Historical Trending | ✅ POC | [08_STORAGE §2.2 cont-aggs](08_STORAGE_TIMESCALEDB.md) |

### Module 2 — Alerting & Predictive Maintenance

| Feature | Status | Plan location |
|---|---|---|
| Rule-Based Alerting | ✅ POC | [12_BACKEND §3](12_BACKEND_API_WS.md) |
| Digital Twin FDD Engine | ✅ POC | [09_DIGITAL_TWIN](09_DIGITAL_TWIN_FDD.md) |
| Twin-Based Fault Classification | ✅ POC | [09 §3 + §B below (Fault Code Library)](#b--fault-code-library-spec) |
| Time-to-Failure (RUL) | ✅ POC | [09 §4](09_DIGITAL_TWIN_FDD.md) |
| Root-Cause Localisation | ✅ POC | [09 §3](09_DIGITAL_TWIN_FDD.md) |
| Multi-Symptom Correlation | ✅ POC | [09 §3 decision table](09_DIGITAL_TWIN_FDD.md) |
| Alert Inbox & Management | ✅ POC | [13_FRONTEND §2 /alerts](13_FRONTEND.md) |
| **Alert Escalation chains** | 🆕 POC | §A1 below |
| **Fault Code Library** | 🆕 POC | §B below |
| Alert History & Audit | ✅ POC | [08a §6.5 + audit.events](08a_DATABASE_DESIGN.md) |
| Notifications (email/SMS/in-app) | ✅ POC | [08a §6.9 app.notifications](08a_DATABASE_DESIGN.md) — channels wired §C1 |
| Twin Model Health Monitoring | ✅ POC | [09 §6](09_DIGITAL_TWIN_FDD.md) |

#### A1 · Alert Escalation chains (filling gap)

Stored per rule and per fault-code on the rule/alert row. Evaluated by a BullMQ worker every 30 s.

```yaml
# config example — lives on the rule, copied to alert on fire
escalation:
  steps:
    - after_seconds: 0
      notify: ["operator_on_shift"]
      channels: ["inapp"]
    - after_seconds: 300        # 5 min unack
      notify: ["site_supervisor"]
      channels: ["inapp","email"]
    - after_seconds: 900        # 15 min unack
      notify: ["portfolio_manager"]
      channels: ["inapp","email","sms"]
    - after_seconds: 1800
      action: "open_incident_work_order"   # auto-create WO if still unacked
```

Critical twin alerts skip steps 1–2 and fire steps 3–4 immediately. Implementation:
- Worker `escalation_runner` reads open alerts where `last_step_at + step.after_seconds <= now()` and the previous step's notify count has not been acked.
- Each escalation tick writes an `audit.events` row + appends to `alerts.payload.escalation_history`.

#### B · Fault Code Library spec (filling gap)

```yaml
# services/twin-broker/fault_codes.yaml — versioned, per equipment_type
chiller:
  BEARING_WEAR:
    description: "Compressor bearing degradation"
    affected_component: "compressor.bearing"
    twin_signal: ["kw_residual_high_at_constant_load"]
    typical_lead_time_days: 21
    recommended_action: "Schedule bearing inspection; lubricate if not done in 90 days"
    parts: ["BRG-COMP-7320", "GREASE-NLGI2"]
    skill_required: "mechanical-l2"
    severity_default: "warning"
    rul_threshold_days: 14            # downgrade to critical if RUL crosses
  REFRIGERANT_LOW_CHARGE:
    description: "Refrigerant charge below spec"
    affected_component: "refrigeration_loop"
    twin_signal: ["superheat_high","capacity_loss"]
    typical_lead_time_days: 7
    recommended_action: "Leak check + recharge"
    parts: ["R-134A-1KG"]
    skill_required: "refrigeration-cert"
    severity_default: "critical"
  FOULING_EVAPORATOR:
    description: "Evaporator heat-exchange fouling"
    affected_component: "evaporator"
    twin_signal: ["chw_delta_t_low"]
    typical_lead_time_days: 45
    recommended_action: "Chemical clean evaporator tubes"
    parts: ["CHEM-CLEAN-EVAP"]
    skill_required: "mechanical-l1"
    severity_default: "warning"
cooling_tower:
  FAN_IMBALANCE:
    ...
  FILL_DEGRADATION:
    ...
```

Loaded into `app.fault_codes` at startup (table added inline below; lives in `08a §6` for v1.1 deployments):

```sql
CREATE TABLE app.fault_codes (
  code               TEXT PRIMARY KEY,
  equipment_type     app.equipment_type NOT NULL,
  description        TEXT NOT NULL,
  affected_component TEXT,
  twin_signals       TEXT[],
  typical_lead_time_days INT,
  recommended_action TEXT,
  parts              TEXT[],
  skill_required     TEXT,
  severity_default   app.alert_severity NOT NULL DEFAULT 'warning',
  rul_threshold_days INT
);
```

Twin-broker emits `Alert.payload.fault_code` + a `recommended_action` lifted straight from this table; agent Workflow A reads it when creating the WO.

#### C1 · Notification gateway wiring (filling gap)

```
notifications outbound paths (POC)
  ├── email     → SMTP relay (local Postfix container)
  ├── sms       → Twilio HTTP API (env-gated; falls back to logged-only)
  ├── inapp     → Kafka topic `notifications.inapp` → ws-bridge → toast in React
  └── webhook   → POST to customer URL (for CMMS bridge, v2)
```

`services/api-service/src/services/notifier.ts` polls `app.notifications WHERE status='queued'` and dispatches per channel. Retries 3× with exponential back-off. Status transitions: `queued → sending → sent | failed`.

---

### Module 3 — Optimisation & RL

| Feature | Status | Plan location |
|---|---|---|
| RL Agent Registry | ✅ POC | [08a §6.7 app.rl_agents](08a_DATABASE_DESIGN.md) |
| Setpoint Optimisation | ✅ POC | [10_RL §2](10_RL_OPTIMIZER.md) |
| **Schedule Optimisation** | 🅥 v2 | §A2 below (POC stub + v2 plan) |
| Multi-Objective Optimisation | ✅ POC (framework) / 🅥 v2 (full weights UI) | [10 §6](10_RL_OPTIMIZER.md) |
| Reward Function Configuration | ✅ POC | [10 §2 + 08a app.rl_agents.reward_config](10_RL_OPTIMIZER.md) |
| Safety Bounds & Constraints | ✅ POC | [10 §2 + 08a.app.rl_agents.safety_bounds](10_RL_OPTIMIZER.md) |
| Human-in-the-Loop Mode | ✅ POC | [10 §3 promotion gating](10_RL_OPTIMIZER.md) |
| Shadow Mode Deployment | ✅ POC | [10 §1 + §3](10_RL_OPTIMIZER.md) |
| **A/B Testing Framework** | 🅥 v2 | §A3 below |
| Reward Curves & Performance | ✅ POC | [10 §5](10_RL_OPTIMIZER.md) |
| Policy Visualisation | ✅ POC | [10 §5](10_RL_OPTIMIZER.md) |
| Continuous Retraining | ✅ POC | [10 §1 + dq-etl rl_experience_cleaner](10_RL_OPTIMIZER.md) |
| Twin-Based Training (sim-to-real) | ✅ POC | [10 §4](10_RL_OPTIMIZER.md) |
| Multi-Equipment Coordination | 🅥 v2 | PRD §10 row |

#### A2 · Schedule Optimisation stub

POC ships a manual schedules editor in the admin UI writing to `app.schedules`. The RL agent has access to `schedule_advisor` Tier-2 tool that suggests changes; suggestions land as draft schedule entries gated on operator approval. Full RL-driven scheduling is v2.

#### A3 · A/B Testing Framework (v2 design, scoped now)

Each RL agent gets a sibling `<agent>_baseline` row in `app.rl_agents` of mode `BASELINE` representing the policy in production before promotion. The reward engine logs both timelines so a clean A vs B comparison renders on the UI. Statistical significance (Welch's t over hourly buckets) is a v2 add.

---

### Module 4 — Agentic AI Framework

| Feature | Status | Plan location |
|---|---|---|
| Planner Agent | ✅ POC | [11_AGENTIC_AI §2](11_AGENTIC_AI.md) |
| Executor Agent | ✅ POC | [11 §2](11_AGENTIC_AI.md) |
| Validator Agent | ✅ POC | [11 §2](11_AGENTIC_AI.md) |
| Orchestration Engine | ✅ POC | [11 §1](11_AGENTIC_AI.md) |
| Tool-Use Framework | ✅ POC | [11 §3 + 08a app.agent_tool_registry](11_AGENTIC_AI.md) |
| Approval Gates | ✅ POC | [14_AUTH §4 + 08a app.approvals](14_AUTH_KEYCLOAK.md) |
| Agent Activity Feed | ✅ POC | [13_FRONTEND §5](13_FRONTEND.md) |
| Workflow Templates | ✅ POC | [11 §4 three workflows](11_AGENTIC_AI.md) |
| **Custom Workflow Builder UI** | 🅥 v2 | YAML editing in admin UI for POC; visual builder is v2 |
| Agent Memory & Context | ✅ POC | [08a §6.12 embeddings.knowledge + agent_runs](08a_DATABASE_DESIGN.md) |
| Multi-Step Reasoning | ✅ POC | [11 §4 Workflow A example](11_AGENTIC_AI.md) |
| Error Handling & Recovery | ✅ POC | [11 §7 loop guard + replan](11_AGENTIC_AI.md) |
| Agent Performance Metrics | ✅ POC | [08a app.agent_runs.tokens_used/cost_usd](08a_DATABASE_DESIGN.md) |
| Human Override & Takeover | ✅ POC | [13 §5 + 11 §5](11_AGENTIC_AI.md) |
| Audit & Compliance Logs | ✅ POC | [08a §6.11 audit.events](08a_DATABASE_DESIGN.md) |

---

### Module 5 — Operations Analytics & Reporting  🆕 filled-in section

| Feature | Status | Plan location |
|---|---|---|
| Agent-Generated Reports | ✅ POC | [11_AGENTIC_AI Workflow B](11_AGENTIC_AI.md) |
| **Twin Diagnostic Reports** | 🆕 POC | §M5.1 below |
| **RL Performance Reports** | 🆕 POC | §M5.2 below |
| **Custom Reports & Export** | 🆕 POC | §M5.3 below |
| **Comparative Analysis** | 🆕 POC | §M5.4 below |
| Data Visualisation | ✅ POC | [13_FRONTEND](13_FRONTEND.md) |

#### M5.1 · Twin Diagnostic Report

Per-equipment PDF/HTML generated on demand or on alert resolution. Sections:
1. Equipment header (id, type, site, install date)
2. Twin health (prediction MAPE last 7/30 d, calibration date)
3. RUL countdown(s) per modelled fault mode
4. Residual chart (predicted vs actual, last 30 d)
5. Fault history (alerts of source `twin_fdd` last 90 d) with resolution outcome
6. Recommended next actions (PM schedule, parts list)

Generated by `services/api-service/src/services/reports/twin_diagnostic.ts` → renders MJML/HTML → wkhtmltopdf → MinIO → row in `app.reports`. Validator agent verifies numbers match.

#### M5.2 · RL Performance Report

Per-agent, weekly. Sections: reward curve (agent vs baseline), KPI delta, action distribution, safety violation count (target zero), shadow vs live status, retrain history.

#### M5.3 · Custom Reports & Export

Endpoint `POST /api/v1/reports/custom { metrics, equipment_ids, range, format }` builds a report from a YAML template at `infra/reports/templates/`. Output formats: PDF, HTML, CSV, JSON, Parquet. CSV/Parquet land in MinIO with signed URL.

POC ships three templates: `daily_brief.yaml`, `weekly_efficiency.yaml`, `monthly_executive.yaml`. THERMYNX's existing daily-brief prompt becomes the seed for `daily_brief.yaml`.

#### M5.4 · Comparative Analysis

REST: `GET /api/v1/telemetry/compare?points=a,b,c&from=...&to=...&res=1h` returns aligned time-bucketed values. Frontend renders multi-line + delta heat strip. The agent tool `compare_periods` already maps onto this endpoint (one tool, one HTTP route).

---

### Module 6 — Work Order & Task Management  🆕 filled-in section

| Feature | Status | Plan location |
|---|---|---|
| Work Order Lifecycle | ✅ POC | [08a §6.6 wo_status enum](08a_DATABASE_DESIGN.md) |
| Twin-Triggered WOs | ✅ POC | [11 Workflow A](11_AGENTIC_AI.md) |
| Agent-Generated WOs | ✅ POC | [11 Workflow A](11_AGENTIC_AI.md) |
| **Smart Technician Assignment** | 🆕 POC | §M6.1 below |
| Mobile WO UI | ✅ POC | [13 /work-orders/kiosk](13_FRONTEND.md) |
| **WO Analytics** | 🆕 POC | §M6.2 below |
| **Task Scheduling (PM)** | 🆕 POC | §M6.3 below |
| CMMS Integration | 🅥 v2 | scope-out in [01](01_SCOPE_AND_SUCCESS.md) |

#### M6.1 · Smart Technician Assignment

Scoring at WO creation time. Tool `assign_technician` ranks `app.technicians WHERE active AND tenant_id=...` by:

```
score =  w_skill_match     * skills_overlap(required_skills, tech.skills)
       + w_certification   * has_cert(required_cert, tech.certifications)
       + w_familiarity     * count(closed_WOs_same_device_last_180d, tech.id)
       - w_load            * tech.current_load
       - w_distance        * distance_to_site(tech, equipment.site_id)
```

Weights configurable in `app.feature_flags` under `wo_assignment.weights`. Output: top-3 ranked list; Agent picks #1 unless approval policy says present-to-human.

#### M6.2 · Work Order Analytics

Dashboards at `/work-orders/analytics`:
- MTTR per equipment type / per technician
- SLA compliance % per severity
- Re-open rate (any WO closed and reopened within 30 d)
- Twin-diagnosed WO accuracy: % of twin-created WOs that the technician confirmed the diagnosis on close (logged via WO close form)
- Parts consumption trend

Built off `app.work_orders` (already has all the columns), plus a small `app.work_order_events` log table:

```sql
CREATE TABLE app.work_order_events (
  id              BIGSERIAL PRIMARY KEY,
  work_order_id   TEXT NOT NULL REFERENCES app.work_orders(id) ON DELETE CASCADE,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor           TEXT NOT NULL,
  event_type      TEXT NOT NULL,            -- created | assigned | started | resolved | reopened | parts_added | diagnosis_confirmed | diagnosis_overridden
  payload         JSONB
);
```

#### M6.3 · Task Scheduling (PM)

Cron-style entries in `app.schedules` with `action = 'pm_task'` and payload `{ template_id }`. Templates in `infra/pm_templates/*.yaml`:

```yaml
id: chiller_quarterly_inspection
applies_to: { type: chiller }
interval: P3M           # ISO-8601
title: "Quarterly chiller inspection"
checklist:
  - Verify oil level
  - Tighten compressor mounts
  - Check refrigerant pressures
  - Calibrate temp sensors
estimated_minutes: 90
required_skills: [mechanical-l1]
```

`pm_task_runner` worker materialises templates into actual `work_orders` rows N days before due, using twin RUL as an early-bird hint (PRD §07 Module 6: "Twin RUL estimates inform PM timing").

---

### Module 7 — Portfolio & Multi-Site Management  🆕 filled-in section

| Feature | Status | Plan location |
|---|---|---|
| Site Hierarchy | ✅ POC | [08a §6.2](08a_DATABASE_DESIGN.md) |
| User Management & RBAC | ✅ POC | [14_AUTH](14_AUTH_KEYCLOAK.md) |
| Agent Authorisation Model | ✅ POC | [14_AUTH §4](14_AUTH_KEYCLOAK.md) |
| Multi-Tenancy | ✅ POC | [08a §7 RLS](08a_DATABASE_DESIGN.md) |
| **Configuration Templates** | 🆕 POC | §M7.1 below |
| Audit Logging | ✅ POC | [08a §6.11](08a_DATABASE_DESIGN.md) |
| Data Governance (retention, encryption) | ✅ POC | [08a §10 + 15 backups](15_DEPLOYMENT_ONPREMISE.md) |

#### M7.1 · Configuration Templates

A "config bundle" defines: rules, DQ thresholds, twin model bindings, RL agents, agent workflows, PM templates. Stored as a versioned YAML bundle in `infra/config_bundles/` and importable via `POST /api/v1/admin/bundles/apply`.

Apply flow:
1. Validate bundle (schema check, tenant scope).
2. Diff against current state of the target site.
3. Show diff to admin; apply on confirm.
4. Audit row per row changed.

POC ships three bundles:
- `unicharm_hvac.yaml` — full Unicharm site config (rules + DQ + twin bindings + RL agents).
- `generic_hvac.yaml` — minimal HVAC baseline.
- `demo_synthetic.yaml` — what the gl_pbs simulator uses.

---

### Module 8 — Integration & Extensions  🆕 filled-in section

| Feature | Status | Plan location |
|---|---|---|
| **Protocol Adapter Framework** | 🆕 POC framework, BACnet shipping; Modbus/OPC-UA/MQTT in v2 | §M8.1 below |
| Domain Extension Framework | ✅ POC | [13 §7 federated extensions](13_FRONTEND.md) + `extensions/thermynx-hvac/` |
| Digital Twin Integration | ✅ POC | [09](09_DIGITAL_TWIN_FDD.md) |
| RL Agent Integration | ✅ POC | [10](10_RL_OPTIMIZER.md) |
| Agentic AI Tool Registry | ✅ POC | [11 §3 + 08a app.agent_tool_registry](11_AGENTIC_AI.md) |
| External System Integration (BMS/MES/CMMS/ERP) | 🅥 v2 | webhook path stubbed §M8.2 |
| REST API & SDK | ✅ POC (REST) / 🅥 v2 (SDK) | [12 §2 OpenAPI](12_BACKEND_API_WS.md) |
| Data Export & BI | ✅ POC (CSV/JSON/Parquet on demand) | §M5.3 |
| Notification Gateway | ✅ POC | §C1 above |

#### M8.1 · Protocol Adapter Framework

POC ships only BACnet but the abstraction is real so v2 adapters drop in.

```python
# shared/protocols/base.py
class ProtocolAdapter(ABC):
    name: str  # "bacnet" | "modbus" | "opcua" | "mqtt" | "rest"

    @abstractmethod
    def discover(self) -> list[DiscoveredDevice]: ...

    @abstractmethod
    def poll(self, device: ConfiguredDevice) -> list[PointReading]: ...

    @abstractmethod
    def write(self, device: ConfiguredDevice, point_id: str, value: Any) -> WriteResult: ...

    @abstractmethod
    def subscribe(self, device: ConfiguredDevice, on_event: Callable[[PointReading], None]) -> None: ...
```

`dal-bacnet` implements this. v2 adds `dal-modbus`, `dal-opcua`, `dal-mqtt`, each a sibling Docker service that publishes to the same `raw.bacnet.*` topic family (topic name is a misnomer post-v2; renamed `raw.points.*` then).

Each adapter declares its capabilities in `protocol_capabilities.yaml` so the UI can render correct write/read affordances per device.

#### M8.2 · External system bridge (v2 webhook path stubbed)

`POST /api/v1/integrations/inbound/{provider}` — generic inbound webhook. Verified by signing secret, parsed to internal events. Outbound to CMMS uses `notifications.webhook` channel. v2 fills the provider list (Maximo, ServiceNow, UpKeep, SAP PM).

---

### Module 8B — Commissioning Tool / Activation Flow  🆕 filled-in section

The master spec includes a commissioning workflow. In Phase 1, OMNYX ships that workflow as a
runbook + admin API + bundle flow, not as a separate visual builder. See
[38_PHASE1_SCOPE_CONTRACT](38_PHASE1_SCOPE_CONTRACT.md).

| Feature | Status | Plan location |
|---|---|---|
| Source inventory import (legacy DB / CSV) | ✅ POC | [30 §4 Path A/B](30_ONBOARDING_NEW_SITE.md) |
| BACnet discovery -> candidate mapping file | ✅ POC | [30 §4 Path C](30_ONBOARDING_NEW_SITE.md) |
| Device / point mapping | ✅ POC | [30 §4](30_ONBOARDING_NEW_SITE.md) + [27 Admin & commissioning](27_API_REFERENCE.md) |
| Site / hierarchy definition | ✅ POC | [30 §3](30_ONBOARDING_NEW_SITE.md) + [08a §6.2](08a_DATABASE_DESIGN.md) |
| Config bundle apply (rules, DQ, twin, RL, workflows, PM) | ✅ POC | [30 §5](30_ONBOARDING_NEW_SITE.md) + [M7.1 above](#m71--configuration-templates) |
| Twin / RL binding | ✅ POC | [30 §6-§7](30_ONBOARDING_NEW_SITE.md) |
| Validation / go-live checklist | ✅ POC | [30 §11](30_ONBOARDING_NEW_SITE.md) |
| Live config push | ✅ POC | [38 §3.4](38_PHASE1_SCOPE_CONTRACT.md) |
| Rollback via prior bundle / config state | ✅ POC | [38 §3.4](38_PHASE1_SCOPE_CONTRACT.md) |
| Separate visual commissioning UI | 🅥 v2 | [38 §3.5](38_PHASE1_SCOPE_CONTRACT.md) |

### Phase 1 API / integration stance  🆕 explicit guardrail

| Topic from master spec | Status | Plan location |
|---|---|---|
| REST API | ✅ POC | [27](27_API_REFERENCE.md) |
| WebSocket live channels | ✅ POC | [27 §3](27_API_REFERENCE.md) |
| GraphQL surface | 🆕 Not shipping in Phase 1 | [27 §1.1](27_API_REFERENCE.md) + [38 §4](38_PHASE1_SCOPE_CONTRACT.md) |
| BACnet runtime adapter | ✅ POC | [32](32_BACNET_SIGNAL_CATALOGUE.md) |
| Modbus / OPC-UA / MQTT runtime adapters | 🅥 v2 | [M8.1 above](#m81--protocol-adapter-framework) |
| BMS / CMMS / ERP sync | 🅥 v2 for bi-directional sync; outbound seams preserved | [M8.2 above](#m82--external-system-bridge-v2-webhook-path-stubbed) + [38 §5](38_PHASE1_SCOPE_CONTRACT.md) |

### Vertical boundary note  🆕 explicit guardrail

| Topic from master spec | Status | Plan location |
|---|---|---|
| HVAC-first executable path | ✅ POC | [13 §7](13_FRONTEND.md) + [38 §6](38_PHASE1_SCOPE_CONTRACT.md) |
| Wider HVAC families beyond simulator-backed chiller plant | ✅ Phase 1 boundary, customer-specific rollout | [38 §6](38_PHASE1_SCOPE_CONTRACT.md) |
| Factory extension execution | 🅥 v2 | [22 §v2.4](22_ROADMAP_V2_V3.md) + [38 §7](38_PHASE1_SCOPE_CONTRACT.md) |

---

## B · Data Quality PRD coverage

| DQ PRD feature | Status | Plan location |
|---|---|---|
| Two-tier architecture | ✅ POC | [06_DATA_QUALITY](06_DATA_QUALITY_LAYER.md) |
| Quality Flag schema (GOOD/SUSPECT/IMPUTED/BAD/MISSING/STALE) | ✅ POC | [05 §2](05_CANONICAL_DATA_MODEL.md) |
| Sensor-level issue catalogue (drift, bias, frozen, spike, noise, range, calibration) | ✅ POC | [06 §2.1](06_DATA_QUALITY_LAYER.md) |
| System-level issues (gaps, late, dup, irregular, protocol errors, ts, partial, register mis-config) | ✅ POC | [06 §2.1](06_DATA_QUALITY_LAYER.md) |
| Semantic issues (impossible, cross-sensor contradiction, context-impossible, unit, rate, seasonal, location) | ✅ POC | [06 §2.1 + cross_sensor_rules](06_DATA_QUALITY_LAYER.md) |
| Imputation strategies (LKG, Linear, Twin, Regression, Profile, Zero, Reject) | ✅ POC | [06 §2.3](06_DATA_QUALITY_LAYER.md) |
| Per-point DQ config JSON | ✅ POC | [06 §2.2 + 08a app.data_quality_config](06_DATA_QUALITY_LAYER.md) |
| Subsystem-response matrix (twin/RL/alert reactions) | ✅ POC | [06 §4](06_DATA_QUALITY_LAYER.md) |
| Tier 2 ETL jobs (drift, baseline, cross-sensor, gap, score, RL cleaner, twin calibration, sampling) | ✅ POC | [06 §3](06_DATA_QUALITY_LAYER.md) |
| Tier 2 → Tier 1 feedback loop | ✅ POC | [06 §3.2](06_DATA_QUALITY_LAYER.md) |
| DQ data model (config, events, scores, gaps, baselines, cross-sensor rules) | ✅ POC | [08a §6.4](08a_DATABASE_DESIGN.md) |
| Telemetry quality columns | ✅ POC | [08 §2 + 08a](08_STORAGE_TIMESCALEDB.md) |
| Portfolio DQ dashboard KPIs | ✅ POC | [13 §6](13_FRONTEND.md) |
| Sensor health view per device | ✅ POC | [13 §6](13_FRONTEND.md) |
| DQ alert types (drift/frozen/bias/quality-degraded/cross-sensor/widespread/RL-quality/twin-quality) | ✅ POC | §A4 below 🆕 |
| Agentic AI DQ workflows (drift handling, widespread event) | ✅ POC | [11 Workflow C](11_AGENTIC_AI.md) + new "Widespread event" workflow §A5 🆕 |

#### A4 · DQ alert types — explicit list seeded into `app.rules`

```yaml
- id: dq_sensor_drift
  kind: anomaly
  source: dq_tier2
  fires_on: SENSOR_DRIFT_DETECTED
  severity: warning
  routing: ["calibration_team","ai_ops"]
- id: dq_sensor_frozen
  kind: state
  source: dq_tier1
  fires_on: FROZEN
  severity: critical
  routing: ["maintenance"]
- id: dq_sensor_bias
  kind: anomaly
  source: dq_tier2
  fires_on: BIAS_SUSPECTED
  severity: warning
- id: dq_device_degraded
  kind: composite
  fires_on: quality_score < 80
  severity: warning
- id: dq_cross_sensor
  kind: semantic
  fires_on: CROSS_SENSOR_CONTRADICTION
  severity: warning
- id: dq_widespread
  kind: composite
  fires_on: pct_bad_or_missing > 30
  severity: critical
- id: dq_rl_quality
  kind: composite
  fires_on: rl_observation_good_pct < 95
  severity: warning
- id: dq_twin_quality
  kind: composite
  fires_on: twin_input_good_pct < 97
  severity: warning
```

#### A5 · "Widespread quality event" workflow (Workflow D)

Added to [11_AGENTIC_AI](11_AGENTIC_AI.md) workflow set:

```
Trigger: WIDESPREAD_QUALITY_EVENT alert
Planner: scope is network / adapter / power / device?
Executor: check_adapter_status, check_network_connectivity, check_device_ping, get_protocol_error_logs
        → pause_rl_agents(site_id), pause_twin_fdd(site_id)
        → notify_portfolio_manager + IT + create_incident_work_order
Validator: monitor recovery; resume rl + twin when good_pct ≥ 95 % for 5 min consecutive.
```

---

## C · PRD §08 (Agentic AI deep-dive) coverage

| PRD §08 item | Status | Plan location |
|---|---|---|
| Why multi-agent (separation, reliability, audit, scale, safety) | ✅ POC | [11 §1](11_AGENTIC_AI.md) |
| Planner / Executor / Validator responsibilities & models | ✅ POC | [11 §2](11_AGENTIC_AI.md) |
| Tool Library initial set | ✅ POC | [11 §3 (18 tools)](11_AGENTIC_AI.md) |
| Approval Tiers (1–5) | ✅ POC | [14 §4 + 11 §3](14_AUTH_KEYCLOAK.md) |
| Cost model | ✅ POC | [11 §7](11_AGENTIC_AI.md) |
| Example workflows (Investigate, Daily Report, Optimisation Recommendation) | ✅ POC (3 + DQ workflows added) | [11 §4](11_AGENTIC_AI.md) + A5 above |

---

## D · PRD §09 (Digital Twin FDD deep-dive) coverage

| PRD §09 item | Status | Plan location |
|---|---|---|
| How it works (real → twin → FDD → fault → output) | ✅ POC | [09 §3](09_DIGITAL_TWIN_FDD.md) |
| Early Detection, Root Cause, RUL, Cascading, Calibration Drift | ✅ POC | [09 §2 + §3 + §4 + §6](09_DIGITAL_TWIN_FDD.md) |
| Twin Model Lifecycle (onboarding/operation/health/retrain/retire) | ✅ POC | [09 §6 + 08a app.twin_calibrations](09_DIGITAL_TWIN_FDD.md) |

---

## E · PRD §10–§13 coverage

| PRD section | Status | Plan location |
|---|---|---|
| §10 Phase Split (MVP / v2 / v3) | ✅ POC scope set | [01 §3](01_SCOPE_AND_SUCCESS.md), [18_MILESTONES](18_MILESTONES.md) |
| §11 24-month roadmap | ✅ POC = Phase 1 covered week-by-week | [18_MILESTONES](18_MILESTONES.md); Phase 2/3 deferred-doc here |
| §12 Deployment model | ✅ POC | [15_DEPLOYMENT](15_DEPLOYMENT_ONPREMISE.md) |
| §13 Open Questions & Risks | ✅ POC | [19_RISKS](19_RISKS.md) |

---

## F · Cross-cutting MVP success metrics (PRD §03)

| Metric | Status | Plan location |
|---|---|---|
| 95 % telemetry uptime | ✅ POC | [17_TEST T1.1](17_TEST_PLAN.md) |
| Dashboard < 2 s | ✅ POC | [17 T3.2](17_TEST_PLAN.md) |
| Alert delivery < 30 s | ✅ POC | [17 T3.3](17_TEST_PLAN.md) |
| Twin FDD ≥ 24 h pre-failure on 80 %+ | ✅ POC | [17 T4.1](17_TEST_PLAN.md) |
| RL ≥ 10 % gain in 30 d | ✅ POC | [17 T5.4](17_TEST_PLAN.md) |
| Agentic AI ≥ 60 % autonomous | ✅ POC | [17 T6.1](17_TEST_PLAN.md) |
| Telemetry latency < 5 s | ✅ POC | [17 T3.1](17_TEST_PLAN.md) |
| WO create-to-dispatch < 10 min | ✅ POC | [17 T3.4](17_TEST_PLAN.md) |
| Agentic AI wrong actions < 5 % | ✅ POC | [17 T6.3](17_TEST_PLAN.md) |

---

## G · Verdict

Every PRD §07–§09 feature has a plan location. Items that were thin (Module 5/6/7/8, alert escalation, fault code library, notification gateway wiring, DQ alert types, widespread quality workflow) are filled in this doc above and now have a concrete spec. v2/v3 items are explicitly tagged so we don't accidentally promise them in the POC.

If anything in the PRD is *not* on the list above, it isn't in the PRD §07–§09 / DQ PRD scope — flag it and we'll add it.
