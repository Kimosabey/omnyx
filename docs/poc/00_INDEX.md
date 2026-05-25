# OMNYX (by Graylinx) — On-Premise POC Master Index

> **Product name:** OMNYX — *Universal IoT Operations Platform*. Internal PRD codename was "CloudOps"; the customer-facing brand is **OMNYX**. See [`../../BRANDING.md`](../../BRANDING.md).

**Goal:** Stand up the **OMNYX Phase 1 product backbone** (all 8 modules + Data Quality + Digital Twin FDD + RL + Agentic AI) entirely on-premise, fed by the **gl_pbs BACnet simulator** at [D:/Harshan/simulations/gl_pbs](../../../../simulations/gl_pbs/) so we can demonstrate end-to-end behaviour without real DDC hardware. The first vertical extension shipping on top of OMNYX is **THERMYNX** (HVAC, already deployed at Unicharm).

This is **not** a slice / vertical demo. It is the production-shaped product baseline, sized for a single site (11 DDCs, 363 BACnet points) but architected so the same compose stack scales to the 50–500 site target in the PRD. See [38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md) for the exact line between gate-demo scope, Phase 1 contract scope, and v2/v3 deferrals.

---

## Source documents (read these first)

| Source | What it tells us |
|---|---|
| [../source/prd/CloudOps_Core_PRD_v1_0.docx](../source/prd/CloudOps_Core_PRD_v1_0.docx) | v1.1 product scope, 8 modules, Twin/RL/Agentic AI deep-dives, phase split |
| [../source/prd/CloudOps_Data_Quality_Layer.docx](../source/prd/CloudOps_Data_Quality_Layer.docx) | Two-tier DQ (Tier 1 inline, Tier 2 ETL), flag schema, imputation, feedback loop |
| [../source/master/Graylinx_Industrial_Platform_Master.pdf](../source/master/Graylinx_Industrial_Platform_Master.pdf) | Master vision document |
| [simulations/gl_pbs/docs/CODEBASE.md](../../../../simulations/gl_pbs/docs/CODEBASE.md) | BACnet reader, simulator, point flow, CSV format |
| [simulations/gl_pbs/docs/SIMULATION_GUIDE.md](../../../../simulations/gl_pbs/docs/SIMULATION_GUIDE.md) | How the simulator is launched, the controller map, DB schema for legacy stack |
| [simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md](../../../../simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md) | Proven Kafka load model (2.1 msg/s real, 4,913 msg/s ceiling), hardware sizing |
| [simulations/gl_pbs/docs/testing/REAL_STACK_STRESS_TEST_PLAN.md](../../../../simulations/gl_pbs/docs/testing/REAL_STACK_STRESS_TEST_PLAN.md) | Real-stack bridge architecture, the topology we extend |
| [simulations/gl_pbs/docs/testing/EQUIPMENT_ANALYSIS.md](../../../../simulations/gl_pbs/docs/testing/EQUIPMENT_ANALYSIS.md) | Equipment breakdown (DDC09 = 70 % of points), COV behaviour per type |

---

## POC document set

| # | File | Purpose |
|---|---|---|
| 01 | [01_SCOPE_AND_SUCCESS.md](01_SCOPE_AND_SUCCESS.md) | What is in / out, MVP success metrics mapped to gl_pbs reality |
| 02 | [02_ARCHITECTURE.md](02_ARCHITECTURE.md) | Layered diagram from BACnet → UI, every container in the stack |
| 03 | [03_TECH_STACK.md](03_TECH_STACK.md) | Pinned versions of every component on-prem |
| 04 | [04_SIMULATOR_AS_DATA_SOURCE.md](04_SIMULATOR_AS_DATA_SOURCE.md) | How gl_pbs simulator feeds the platform; controller map; CSV format; how to replay or scale |
| 05 | [05_CANONICAL_DATA_MODEL.md](05_CANONICAL_DATA_MODEL.md) | `PointReading`, `PointBatch`, `PlantSnapshot`, quality envelope, Kafka topic schema |
| 06 | [06_DATA_QUALITY_LAYER.md](06_DATA_QUALITY_LAYER.md) | Tier 1 inline + Tier 2 ETL, all rules from the DQ PRD, config table, feedback loop |
| 07 | [07_KAFKA_PIPELINE.md](07_KAFKA_PIPELINE.md) | Brokers, topics, consumer groups, retention, sizing |
| 08 | [08_STORAGE_TIMESCALEDB.md](08_STORAGE_TIMESCALEDB.md) | PostgreSQL + TimescaleDB schema (telemetry, alerts, work_orders, dq tables) |
| 08a | [08a_DATABASE_DESIGN.md](08a_DATABASE_DESIGN.md) | Comprehensive DB design — principles, ERD, full DDL, RLS, roles, indexes, compression, migrations |
| 09 | [09_DIGITAL_TWIN_FDD.md](09_DIGITAL_TWIN_FDD.md) | twin-broker service, fault classification, RUL, drift monitoring |
| 10 | [10_RL_OPTIMIZER.md](10_RL_OPTIMIZER.md) | RL agent registry, shadow mode, reward config, safety bounds |
| 11 | [11_AGENTIC_AI.md](11_AGENTIC_AI.md) | Planner / Executor / Validator, tool library, approval tiers, demo workflows |
| 12 | [12_BACKEND_API_WS.md](12_BACKEND_API_WS.md) | Fastify REST, WebSocket plant snapshot, rules engine, scheduler |
| 13 | [13_FRONTEND.md](13_FRONTEND.md) | React 18 SPA + tablet kiosk routes, twin overlay, agent activity feed |
| 14 | [14_AUTH_KEYCLOAK.md](14_AUTH_KEYCLOAK.md) | Realm, roles, agent authorization model |
| 15 | [15_DEPLOYMENT_ONPREMISE.md](15_DEPLOYMENT_ONPREMISE.md) | Docker Compose for POC, k8s notes for production, networking, GPU |
| 16 | [16_POC_RUNBOOK.md](16_POC_RUNBOOK.md) | Step-by-step bring-up, every terminal, every health check, demo script |
| 17 | [17_TEST_PLAN.md](17_TEST_PLAN.md) | What we verify and how; ties back to MVP success metrics |
| 18 | [18_MILESTONES.md](18_MILESTONES.md) | Week-by-week plan to reach a demoable end product |
| 19 | [19_RISKS.md](19_RISKS.md) | Risks, open questions, mitigations |
| 20 | [20_MODULE_COVERAGE.md](20_MODULE_COVERAGE.md) | **Strict audit:** every PRD feature → plan location. Gaps filled inline. |
| 21 | [21_PERSONAS.md](21_PERSONAS.md) | PRD personas + concrete OMNYX touchpoints per role |
| 22 | [22_ROADMAP_V2_V3.md](22_ROADMAP_V2_V3.md) | Beyond MVP — v2 Intelligence (Month 6–9) and v3 Scale & Autonomy (Month 10–24) |
| 23 | [23_SECURITY.md](23_SECURITY.md) | Defence-in-depth: data-at-rest, in-transit, secrets, network, agentic-specific, audit |
| 24 | [24_OBSERVABILITY.md](24_OBSERVABILITY.md) | Metrics catalogue per service, log structure, Grafana dashboards, Prometheus alerts |
| 25 | [25_KNOWLEDGE_BASE_RAG.md](25_KNOWLEDGE_BASE_RAG.md) | Knowledge corpus structure, ingest pipeline, retrieval, hallucination control |
| 26 | [26_CI_CD.md](26_CI_CD.md) | Make targets, CI pipeline, image tags, releases, rollback |
| 27 | [27_API_REFERENCE.md](27_API_REFERENCE.md) | Route catalogue + OpenAPI auto-gen pointer |
| 28 | [28_GLOSSARY.md](28_GLOSSARY.md) | Canonical terms, acronyms |
| 29 | [29_DEMO_SCRIPT.md](29_DEMO_SCRIPT.md) | 15-minute leadership walk-through, scripted |
| 30 | [30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md) | Customer onboarding runbook (hardware → users → equipment → go-live) |
| 31 | [31_OPENSOURCE_LICENSING.md](31_OPENSOURCE_LICENSING.md) | Every dependency with its license; air-gap deployment posture |
| 32 | [32_BACNET_SIGNAL_CATALOGUE.md](32_BACNET_SIGNAL_CATALOGUE.md) | All BACnet object types, properties, services, units, error modes, error-handling matrix |
| 33 | [33_LEGACY_REFERENCE_PATTERNS.md](33_LEGACY_REFERENCE_PATTERNS.md) | Useful patterns from legacy graylinx-be (CPM, alarm module, iKW/TR, schedules) and what NOT to copy |
| 34 | [34_POC_EQUALS_END_PRODUCT.md](34_POC_EQUALS_END_PRODUCT.md) | Explicit: POC = the end product on-premise. What stays same / what changes for beta |
| 35 | [35_DATA_FLOWS.md](35_DATA_FLOWS.md) | **12 end-to-end data flows** (telemetry read, write-back, alerts, twin→WO, DQ loop, agent workflow, RL, Unicharm replay, auth, approvals, bundle apply, backup) + service-interaction matrix |
| 36 | [36_HARDWARE_REQUIREMENTS.md](36_HARDWARE_REQUIREMENTS.md) | Per-customer hardware tiers (min + recommended), two valid topologies (A site-local LLM / C Claude API), re-eval of AIIMS Madurai + Varanasi Airport |
| 37 | [37_DEPLOYMENT_MODEL.md](37_DEPLOYMENT_MODEL.md) | **One customer = one install on their own hardware.** Graylinx never hosts customer data. Multi-tenancy in schema is future-SaaS optionality only |
| 38 | [38_PHASE1_SCOPE_CONTRACT.md](38_PHASE1_SCOPE_CONTRACT.md) | Clarifies what the POC gate proves vs what is Phase 1 contract scope vs what is truly deferred |
| M | [../migration/UNICHARM_TO_OMNYX.md](../migration/UNICHARM_TO_OMNYX.md) | Phased cutover from the existing Unicharm MySQL into the OMNYX TimescaleDB without breaking THERMYNX |

---

## One-paragraph summary for leadership

The POC reuses the **gl_pbs BACnet simulator** (11 DDC controllers, 363 real points from `eqp_name_handling.csv`) as the field data source. A new edge service replaces the legacy HTTP-POST path with a **BACnet → DQ Tier 1 → Kafka** producer. Kafka fans out to four on-prem consumers: **TimescaleDB writer**, **WebSocket bridge** for the React UI, **Twin FDD engine**, and **RL observer**. A separate **Agentic AI orchestrator** (Planner / Executor / Validator on Claude) coordinates workflows over a tool library that calls the same REST API the UI uses. **Keycloak** provides SSO + RBAC. **Prometheus + Grafana** monitors the stack. Everything runs in **Docker Compose** on a single Intel Core i5+ / 16 GB box for the POC, with a documented Kubernetes path for production. Hardware envelope is proven: at our 2.1 msg/s real load, Kafka uses 1 % CPU and ~470 MB RAM — the box is over-provisioned by ~50×.
