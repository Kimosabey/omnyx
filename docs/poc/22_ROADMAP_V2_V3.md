# 22 · Roadmap — v2 (Month 6–9) and v3 (Month 10–24)

PRD §10 (Phase Split) and §11 (Phased Roadmap), translated into concrete OMNYX work items beyond the POC.

The POC ([18_MILESTONES](18_MILESTONES.md)) is **Phase 1 (MVP Core)**. v2 = Phase 2 (Intelligence), v3 = Phase 3 (Scale & Autonomy).

---

## v2 — Intelligence (Months 6–9)

### v2.1 · Alerting / Predictive Maintenance

- **Escalation chain editor** — visual UI to author escalations (POC ships YAML).
- **Auto-tuning thresholds** — bandit-style refinement of rule thresholds from operator ack/dismiss feedback.
- **Multi-equipment twin correlation** — cross-asset FDD (e.g., chiller-tower pair, pump-array imbalance).
- **Twin drift detection** automated retraining trigger (POC has manual `twin_calibration_feeder`).

### v2.2 · Reinforcement Learning

- **Plant-level RL coordination** — agent-of-agents controlling chiller sequencing + tower staging together.
- **Multi-objective UI** — sliders for energy ↔ comfort ↔ lifecycle weights.
- **A/B testing framework** — statistically rigorous compare (Welch's t on hourly buckets).
- **Continuous retraining policy** with rollback (POC has nightly retrain; needs change-monitoring + safety abort).

### v2.3 · Agentic AI

- **Custom Workflow Builder UI** — drag-and-drop instead of YAML.
- **Expanded tool library** — 18 POC tools → ~50 (BMS bridges, MES, CMMS, ERP, BI export).
- **Agent-to-agent collaboration** — Planner dispatches sub-workflows to specialised agents.
- **Approval policies as code** — declarative routing rules.

### v2.4 · Domain Extensions

- **OPC-UA adapter** (`dal-opcua` service implementing `ProtocolAdapter`).
- **Modbus TCP / RTU adapter**.
- **MQTT adapter**.
- **FORGYNX (Factory)** — first non-HVAC vertical: MES connector, production analytics, defect tracking twin.

### v2.5 · Integration

- **CMMS bi-directional sync** — Maximo / ServiceNow / UpKeep.
- **BMS bridge** for non-BACnet sites.
- **BI export** to Tableau / Power BI (Parquet → MinIO).

### v2.6 · Reporting

- **Multi-language reports** (i18n).
- **Custom dashboard builder** for portfolio-level metrics.
- **Comparative analytics** across sites / time periods.

### v2.7 · Data Quality

- **Tier-2 ML-based subtle drift detection** (Isolation Forest / Prophet residuals).
- **Predictive sensor failure scoring** — score sensors before they go bad.
- **Auto-calibration recommendations** flowing into PM scheduler.

---

## v3 — Scale & Autonomy (Months 10–24)

### v3.1 · Multi-Site Federation

- Site-local "edge brokers" with cross-site Kafka replication (MirrorMaker2).
- Per-site offline mode with eventual reconciliation.
- Cross-site analytics rollups.

### v3.2 · Twin auto-calibration & federated learning

- Twin models self-recalibrate from drift signal without ops engineer.
- Federated twin learning across customer sites (privacy-preserving).

### v3.3 · Sim-to-real RL continuous loop

- Policies trained in twin → deployed shadow → live, automatically with safety gates.
- Federated RL across customer sites.

### v3.4 · Fully autonomous agent mode

- Tier 3 actions go autonomous for "trusted" workflows after configurable confidence threshold.
- Operator only intervenes on Tier 4–5 or anomalies.
- Fine-tuned agent models per customer's vocabulary and equipment quirks.

### v3.5 · On-prem LLM

- Replace Anthropic API with self-hosted LLM (Llama-3-70B class or Claude on-prem when available).
- Ollama integration already present (POC fallback); v3 makes it the primary path for customers requiring air-gap.

### v3.6 · Advanced analytics & forecasting

- Foundation time-series models (Chronos / TimeGPT) for load forecasting.
- What-if simulators using the twin layer.

### v3.7 · Domain extensions complete

- THERMYNX v3 (HVAC), FORGYNX v3 (Factory), AQUYNX (Water), VOLTYNX (Power), Manufacturing.

### v3.8 · API gateway for 3rd-party

- OAuth client-credentials flow for partner integrations.
- Public SDKs: TypeScript, Python.

---

## Capability evolution table (PRD §10 restated)

| Capability | POC (MVP) | v2 | v3 |
|---|---|---|---|
| Real-Time Monitoring | Portfolio + device dashboards, twin overlay | Device compare, floor-plan overlay | Custom dashboard builder |
| Rule-Based Alerting | Threshold + offline + anomaly, inbox, ack | Escalation chains UI, advanced rules | Auto-tuning thresholds |
| Twin FDD | Integration + FDD + classification + RUL | Multi-equipment correlation, drift detection | Auto-calibration, federated twin learning |
| RL | 1 shadow agent + reward dashboards | Multi-objective UI, plant coordination, A/B | Sim-to-real continuous, federated RL |
| Agentic AI | Planner/Executor/Validator, 4 workflows | Custom workflow builder, advanced approvals, more tools | Autonomous mode, agent-to-agent, fine-tuned |
| Reporting | Daily / weekly agent-generated | Twin diagnostic + RL perf + custom workflows | Multi-language, advanced analytics |
| Work Orders | Twin + agent generated, basic dispatch | Smart assignment via agents, CMMS sync | Predictive PM via twin RUL |
| Scheduling | Basic + agent-driven | Conflict resolution | RL-optimised schedules |
| Protocols | BACnet/IP | + OPC-UA, MQTT, Modbus | Custom protocols |
| Deployment | Single-host Compose | Two-host with HA Postgres | k8s multi-site, GPU pool |
| LLM | Claude API + Ollama fallback | Same | On-prem LLM primary |

---

## Exit gates between phases

| Gate | Required to start the next phase |
|---|---|
| POC → v2 | All 17 POC tests pass twice; beta customer signed; 30 d of live shadow-mode data |
| v2 → v3 | At least one customer running v2 in production for 90 d; agent autonomy ≥ 60 % sustained; zero RL safety violations in audit |
