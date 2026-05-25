# 28 · Glossary

Single source of truth for terminology. If a word here, use it; if a word isn't here, propose it via PR.

## Product & brand

| Term | Meaning |
|---|---|
| **Graylinx** | Parent company / brand |
| **OMNYX** | The universal IoT operations platform product (this repo) |
| **THERMYNX** | HVAC vertical extension on top of OMNYX (already deployed at Unicharm) |
| **FORGYNX**, **AQUYNX**, **VOLTYNX** | Reserved vertical-extension names (Factory / Water / Power) |
| **CloudOps** | Internal PRD codename, **not** the external product name. Use OMNYX externally. |

## Architecture & components

| Term | Meaning |
|---|---|
| **DAL** | Data Acquisition Layer (`dal-bacnet`, `dal-replay`) — the edge ingestion services |
| **Tier 1 DQ** | Inline data quality at the DAL, < 50 ms per point |
| **Tier 2 DQ** | Asynchronous ETL data quality, runs hourly/daily, feeds back to Tier 1 |
| **Twin Broker** | Service that hosts digital twin models and runs FDD |
| **RL Broker** | Service that hosts RL agents in shadow or live mode |
| **Agentic AI** | The Planner/Executor/Validator service |
| **WS Bridge** | Kafka → WebSocket plant snapshot broadcaster |
| **Tool Gateway** | Fastify routes under `/api/v1/tools/*` that agentic AI calls |

## Data model

| Term | Meaning |
|---|---|
| **PointReading** | One value of one point at one moment, including its quality envelope |
| **PointBatch** | Group of `PointReading`s from one device in one read cycle |
| **PlantSnapshot** | Aggregated latest-state JSON broadcast over WS |
| **DevicePoint** | The schema row defining what a point is (`<device_id>.<param>`) |
| **device_id** | Stable identifier (`chiller_1`, `DDC09`) |
| **point_id** | `<device_id>.<param>` — always |
| **Equipment** | Synonym for device in this product, sometimes "asset" |
| **Hypertable** | TimescaleDB time-partitioned table |
| **Continuous Aggregate** (cagg) | Auto-refreshing materialised view on a hypertable |

## Data quality

| Term | Meaning |
|---|---|
| **Quality Envelope** | The `flag + detail + original + imputation` block on every reading |
| **GOOD / SUSPECT / IMPUTED / BAD / MISSING / STALE** | The six quality flags |
| **LKG** | Last Known Good (imputation strategy) |
| **Drift coefficient** | Per-sensor scalar correction computed by Tier 2, applied at Tier 1 |
| **Bias offset** | Per-sensor constant correction |
| **Sensor health score** | 0–100, computed hourly by Tier 2 |
| **Widespread quality event** | > 30 % of a device's points BAD/MISSING simultaneously |

## Alerts & faults

| Term | Meaning |
|---|---|
| **Rule-based alert** | Threshold / offline / anomaly / delta / semantic — fires from the rules engine |
| **Twin FDD alert** | Comes from twin residual exceeding configured z-threshold |
| **Fault code** | Library entry (e.g., `BEARING_WEAR`) with recommended action & parts |
| **RUL** | Remaining Useful Life (twin-estimated days to fault threshold) |
| **Escalation chain** | Time-ordered notify/action steps if an alert is unacked |

## RL

| Term | Meaning |
|---|---|
| **Shadow mode** | RL agent runs but never writes back |
| **Live mode** | RL agent writes setpoints subject to safety bounds and approvals |
| **Reward function** | The scalar (or vector) the agent maximises |
| **Safety bound** | Hard limit the agent's action cannot violate; enforced at the broker |
| **Sim-to-real** | Train against the digital twin, then deploy to real equipment |

## Agentic AI

| Term | Meaning |
|---|---|
| **Planner** | Agent that decomposes goal into steps |
| **Executor** | Agent that runs tool calls per plan |
| **Validator** | Independent agent that verifies execution |
| **Tool** | A callable function the agents can invoke; one tool = one Fastify route |
| **Approval Tier** | 1 read, 2 low-risk write, 3 operational write, 4 significant, 5 critical (PRD §08) |
| **Workflow** | A named recipe (trigger + plan template + approval tier) |
| **Run** | One execution instance of a workflow |
| **Loop guard** | Aborts a run if the same tool is called > 5 times |

## Auth

| Term | Meaning |
|---|---|
| **Tenant** | A customer organisation; isolated by Row-Level Security |
| **RBAC** | Role-Based Access Control (the role list in [14_AUTH](14_AUTH_KEYCLOAK.md)) |
| **ABAC** | Attribute-Based scoping — "which site can this user see" |
| **Approval token** | 15-min single-use JWT proving a human approved a Tier-3+ tool call |

## Legacy / reference

| Term | Meaning |
|---|---|
| **Unicharm** | The customer with the existing THERMYNX deployment; its MySQL is the reference history we replay |
| **gl_pbs** | The BACnet simulator project at `D:\Harshan\simulations\gl_pbs` |
| **`*_normalized`** | Per-equipment tables in Unicharm MySQL — the **anti-pattern** OMNYX replaces |
| **`_metric`, `_om_p`** | Raw vendor exports in Unicharm — never queried by OMNYX |
| **Bennu / c10003490** | The physical Raspberry-Pi-based controller documented in `gl_pbs/docs/HARDWARE_CONTROLLER.md` |

## Acronyms

| Acronym | Expansion |
|---|---|
| AHU | Air Handling Unit |
| BACnet | Building Automation and Control networks protocol |
| BAS / BMS | Building Automation / Management System |
| CMMS | Computerised Maintenance Management System |
| COV | Change Of Value |
| DDC | Direct Digital Controller |
| ERD | Entity-Relationship Diagram |
| FDD | Fault Detection & Diagnostics |
| HA | High Availability |
| HVAC | Heating, Ventilation, Air Conditioning |
| IoT | Internet of Things |
| KPI | Key Performance Indicator |
| kW/TR | kilowatts per ton of refrigeration (chiller efficiency) |
| MES | Manufacturing Execution System |
| MAPE | Mean Absolute Percentage Error |
| MQTT | Message Queuing Telemetry Transport |
| OPC-UA | Open Platform Communications — Unified Architecture |
| PITR | Point-In-Time Recovery |
| PM | Preventive Maintenance |
| RBAC / ABAC | Role / Attribute-Based Access Control |
| RL | Reinforcement Learning |
| RPM | ReadPropertyMultiple (BACnet service) |
| RUL | Remaining Useful Life |
| SLA | Service Level Agreement |
| SOP | Standard Operating Procedure |
| WO | Work Order |
