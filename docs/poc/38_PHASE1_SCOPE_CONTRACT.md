# 38 · Phase 1 Scope Contract and Commissioning Boundary

The master PDF is the strategic product specification. This document says what that means for the
**shipping Phase 1 / POC artefacts in this repo**, so reviewers do not confuse:

- what is exercised in the 12-week gate demo,
- what is already part of the Phase 1 product contract but is customer-specific or onboarding-time,
- and what is genuinely deferred to v2/v3.

Use this doc alongside [01_SCOPE_AND_SUCCESS.md](01_SCOPE_AND_SUCCESS.md),
[30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md), and
[34_POC_EQUALS_END_PRODUCT.md](34_POC_EQUALS_END_PRODUCT.md).

## 1 · Three scope classes

| Class | Meaning |
|---|---|
| **Operational at POC gate** | Built and exercised in the 12-week plan, demo storyline, and [17_TEST_PLAN](17_TEST_PLAN.md). |
| **Phase 1 contract, not gate-blocking** | Part of the customer-facing product boundary in Phase 1, but typically exercised during onboarding or a real deployment rather than on the laptop demo. |
| **Deferred** | Explicitly moved to v2/v3. Framework hooks may exist, but the runtime capability is not promised in the POC gate. |

This is the key distinction behind "POC = end product": **same architecture and artefacts**, but
not every customer-specific integration path is exercised in the simulator-based gate review.

## 2 · Scope matrix for the main disputed areas

| Area | Phase 1 status | What actually ships |
|---|---|---|
| Commissioning tool | **Phase 1 contract, not gate-blocking** | Delivered as a runbook + admin APIs + seed/discovery/bundle workflows, not as a separate visual builder yet. |
| API surface | **Operational at POC gate** | REST + OpenAPI + WebSocket. GraphQL is intentionally **not** a shipping Phase 1 contract. |
| BACnet path | **Operational at POC gate** | Full read, DQ Tier 1, write-back, Kafka fan-out, UI, alerts, twin, RL, agent flows. |
| Modbus / OPC-UA / MQTT runtime adapters | **Deferred to v2** | Adapter abstraction is kept in the architecture so those services can drop in later. |
| BMS vendor bridges | **Phase 1 contract, customer-specific** | Generic BACnet path and point mapping ship now; vendor-specific REST/OPC bridges are selected per beta customer and otherwise treated as v2 follow-ons. |
| CMMS / ERP / MES sync | **Deferred to v2** | Phase 1 keeps export, notifications, and webhook boundaries; bi-directional sync is not part of the POC gate. |
| HVAC extension | **Operational at POC gate** | HVAC-first path is the only executable vertical in the POC. |
| Factory extension | **Deferred to v2** | Kept in roadmap/glossary/architecture boundaries so OMNYX does not become HVAC-only by accident. |

## 3 · What counts as the Phase 1 commissioning tool

The master PDF expects a commissioning workflow. In this repo, Phase 1 delivers that workflow as
an **operator/admin flow across runbook + APIs + bundles**, not as a dedicated graphical builder.

### 3.1 Source onboarding

Three supported entry paths already exist in the docs:

1. **Legacy import** from a Unicharm-style MySQL source
2. **CSV import** using the `eqp_name_handling.csv` shape
3. **BACnet discovery** to generate a candidate inventory for engineer review

See [30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md) §4 and
[32_BACNET_SIGNAL_CATALOGUE.md](32_BACNET_SIGNAL_CATALOGUE.md).

### 3.2 Device / point mapping

Phase 1 commissioning includes:

- creation of tenant/site/equipment rows,
- mapping physical BACnet objects to canonical `device_id` / `point_id`,
- assignment of units, equipment family, and legacy back-pointers,
- storage of that mapping in `app.equipment` and `app.device_points`.

That is the practical equivalent of the PDF's "source / device / point mapping" requirement.

### 3.3 Validation and live activation

The Phase 1 flow then applies:

- DQ config,
- twin model bindings,
- RL agent bindings,
- agent workflows,
- PM templates,
- approval policies,
- notification settings

through versioned config bundles via `POST /api/v1/admin/bundles/apply`.

Validation is done through the onboarding checklist in
[30_ONBOARDING_NEW_SITE.md](30_ONBOARDING_NEW_SITE.md) §11 plus the end-to-end flows in
[35_DATA_FLOWS.md](35_DATA_FLOWS.md).

### 3.4 Live config push and rollback

Phase 1 does include "live config push", but it is **API/bundle driven**:

- bundle apply writes the new relational config,
- services pick up changes through their normal refresh path,
- every change is audited,
- rollback is by re-applying the prior bundle version or restoring the previous config state.

### 3.5 What is still deferred

The only commissioning capability explicitly deferred is the **separate visual commissioning UI /
builder**. Phase 1 ships the workflow, not a standalone GUI for it.

## 4 · API stance: REST ships, GraphQL does not

The master PDF mentions REST + GraphQL. The repo docs now make the Phase 1 decision explicit:

- **Shipping contract**: REST + OpenAPI + WebSocket
- **Why**: one audited surface for humans and agents, one auth model, one generated SDK source
- **GraphQL status**: not in the Phase 1 runtime contract; if revisited later, it will be additive

This keeps the product surface aligned with [27_API_REFERENCE.md](27_API_REFERENCE.md) and the
agent tool gateway in [12_BACKEND_API_WS.md](12_BACKEND_API_WS.md).

## 5 · Integration boundary for Phase 1

Phase 1 should be read as:

- **BACnet is the exercised adapter**
- **adapter abstraction is real**
- **vendor-specific bridges are customer-specific follow-on work unless already covered by BACnet**
- **bi-directional business-system sync is not part of the POC gate**

Concretely:

- Trane/generic BACnet-style BMS connectivity fits inside the shipping BACnet path
- webhook/export/notification boundaries are preserved so CMMS/ERP integrations have a clean seam
- Maximo/ServiceNow/UpKeep/SAP PM style sync is a v2 commitment, not a demo gate requirement

## 6 · HVAC depth versus simulator reality

The master PDF's HVAC section is broader than the simulator-backed demo. The intended reading is:

- Phase 1 is **HVAC-first**, not "chiller-only forever"
- the canonical model already includes chillers, cooling towers, pumps, and AHU-family equipment
- the gate demo is intentionally anchored on the Unicharm-style chiller plant because that is the
  highest-confidence path in `gl_pbs`
- boilers, FCUs, heat exchangers, thermostats, warranty tracking, parts inventory, demand response,
  and occupancy-heavy flows stay as documented extension targets until a customer dataset exercises
  them

So the repo should be read as **architecturally HVAC-broad, operationally HVAC-narrow in the gate
demo**.

## 7 · Factory extension expectation

The Factory extension stays in the documentation for architecture, terminology, and roadmap
integrity, but it is **not** part of the executable 12-week POC acceptance boundary.

That means:

- keeping factory personas, glossary terms, and roadmap items is correct,
- claiming executable factory screens/connectors in the POC would be incorrect,
- Phase 1 in this repo is the OMNYX core plus HVAC-first deployment path.

## 8 · Reviewer rule of thumb

When a reviewer asks "is this in Phase 1?", use this test:

1. If it is in the gate demo or [17_TEST_PLAN](17_TEST_PLAN.md), it is **operational now**.
2. If it is part of onboarding / admin / bundle / contract wiring and would be exercised during a
   real customer deployment, it is **Phase 1 contract, not gate-blocking**.
3. If the docs mark it v2/v3, it is **deferred**.

If a topic does not fit cleanly into one of those three buckets, the docs are still ambiguous and
should be updated.
