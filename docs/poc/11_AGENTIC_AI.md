# 11 · Agentic AI Framework

Implements PRD §08 verbatim: Planner / Executor / Validator on Anthropic Claude, with a tool gateway that hits the same REST API a human uses. No custom orchestration framework — straight Anthropic SDK + a thin runner.

## 1 · Service shape (`agentic-ai`)

```
agentic-ai (Node.js / TypeScript)
  ├── triggers
  │     • Kafka: alerts (twin.fdd.alerts, dq.events with severity>=warning)
  │     • Scheduler: BullMQ cron jobs (daily report, weekly RL review)
  │     • HTTP: POST /agent/run (operator-initiated)
  ├── orchestrator
  │     • assemble system prompts per agent role
  │     • Claude prompt caching on system prompt + tool defs
  │     • run loop: Planner → Executor → Validator (replanning supported)
  │     • emits AgentEvent to topic agent.activity (UI reads this live)
  │     • persists run lifecycle to app.agent_runs
  ├── tool gateway client
  │     • all tools resolve to HTTPS calls into api-service
  │     • approval gates enforce by 'approval_tier' on the tool definition
  ├── approval router
  │     • Tier 3+ → POST /approvals/request → human action required
  │     • polls or subscribes for the approval verdict
  └── memory
      • embeddings.knowledge for RAG context
      • app.agent_runs for recent precedent on same device/fault
```

## 2 · Agent roles and models

| Role | Model | Why this model | Temp |
|---|---|---|---|
| Planner | Claude **Opus 4.7** (or Sonnet 4.6 fallback) | Long-context, deep reasoning, decomposition | 0.2 |
| Executor | Claude **Sonnet 4.6** | Fast, capable tool use | 0 |
| Validator | Claude **Sonnet 4.6**, separate context | Independent perspective from Executor | 0 |

Each role has its own system prompt and tool subset:
- Planner: read-only tools (`get_*`).
- Executor: read + write tools (`create_work_order`, `send_notification`, `write_setpoint`, …).
- Validator: read-only tools (verifies what Executor did happened).

Local fallback: `LLM_BACKEND=ollama` switches all three to `qwen2.5:14b` for air-gap demos.

## 3 · Tool registry (initial set)

All tools are Fastify routes under `/api/v1/tools/*`, each with Zod-typed input/output. The agent SDK calls them via `tool_use` blocks; the tool registry file generates the JSON Schema the SDK expects.

| Tool name | Tier | Purpose |
|---|---|---|
| `get_telemetry` | 1 | Pull readings for a point in a time range |
| `get_equipment` | 1 | Resolve equipment metadata |
| `get_twin_diagnosis` | 1 | Latest twin state + RUL for a device |
| `get_alerts` | 1 | Active / historical alerts |
| `get_work_orders` | 1 | WO list filtered by device, technician, status |
| `get_rl_performance` | 1 | Recent reward curve, action distribution |
| `query_historical_trends` | 1 | Continuous-aggregate-backed roll-ups |
| `compare_periods` | 1 | Diff two time ranges |
| `simulate_on_twin` | 1 | Forward-roll twin under candidate inputs |
| `predict_with_rl` | 1 | Ask the RL agent what action it would take given state |
| `create_work_order` | 2 | Auto-generate from twin diagnosis |
| `assign_technician` | 2 | Suggest + assign (subject to skills match) |
| `send_notification` | 2 | Email / SMS / in-app push |
| `generate_report` | 2 | PDF/HTML via report templates |
| `write_setpoint` | 3 | BACnet write within configured bounds |
| `change_mode` | 3 | Equipment mode (auto/manual/off) |
| `start_equipment` | 4 | Operator approval required |
| `stop_equipment` | 4 | Operator approval required |
| `plant_shutdown` | 5 | Manager approval + dual auth |

Tiers map directly to the PRD §08 "Approval Tiers" table.

## 4 · POC workflows (three shipping)

### Workflow A — "Investigate Alert" (Kafka-triggered, autonomous)

Trigger: any `Alert` with `source=twin_fdd` and `severity in (warning, critical)`.

```
Planner: receive alert
  → plan: gather context, validate diagnosis, choose response
  → tools chosen: get_equipment, get_twin_diagnosis, get_alerts(history),
                  get_work_orders(device, recent), query_historical_trends

Executor: execute plan
  → if twin diagnosis confirmed + RUL < 30 d:
      create_work_order(diagnosis, recommended_parts)
      assign_technician(skills_match)
      send_notification(technician, 'high')
  → else if RUL > 30 d but degradation visible:
      create_work_order(severity=watch)
      send_notification(maintenance_lead, 'low')
  → emit progress on agent.activity

Validator: review
  → re-fetch WO and confirm created with expected fields
  → re-check that the diagnosis still holds (no flapping)
  → mark workflow complete or trigger replan
```

### Workflow B — "Daily Operations Report" (scheduled 06:00)

```
Planner: aggregate yesterday's data, identify highlights, draft sections.
Executor: query telemetry (yesterday window), get_alerts, get_work_orders,
          get_rl_performance, get_twin_diagnoses → generate_report → send_notification.
Validator: cross-check the headline numbers against the queries; reject if mismatch.
```

### Workflow C — "Drift Handling" (DQ-triggered)

Trigger: `SENSOR_DRIFT_DETECTED` from Tier 2 ETL.

```
Planner: confirm drift is real (not ETL artefact), estimate calibration urgency.
Executor: get_sensor_drift_history, get_twin_prediction_accuracy, get_last_calibration_date
          → create_calibration_work_order (Tier 2, no approval)
          → notify_calibration_team
          → apply_interim_drift_correction (Tier 3 — auto if delta < 5 %, else approval)
Validator: confirm WO created, correction applied, sensor_health_score updated.
```

## 5 · Approval surfaces

Tier 3+ workflows hit `POST /approvals/request`. The frontend exposes:
- **Operator inbox** at `/approvals` — pending tool calls with rich context (what tool, what args, who proposed, why).
- **Sidebar badge** count.
- **Tablet kiosk** view for technicians.

Decisions persist to `audit.events`. Agent run resumes on approval and continues, or aborts on rejection.

## 6 · UI: Agent Activity Feed

Subscribes to topic `agent.activity` via the WebSocket bridge. Renders each step:
- 💭 Planner thought
- 🛠️ Executor tool call (with args)
- ✅ Executor tool result (collapsed JSON)
- 🧐 Validator verdict
- 🔒 Approval request → pending → resolved
- 🏁 Workflow done

Operators can pause, take over, or replay any workflow from the feed (PRD §08 "Human Override").

## 7 · Cost model and ceilings

| Workflow class | Tokens / run | Estimated cost |
|---|---|---|
| Simple (3–5 tool calls) | ~5 k input + ~1 k output | ~$0.05–0.15 |
| Complex (10–20) | ~20 k | ~$0.20–0.50 |
| Long-running (50+) | ~80 k | ~$1.00–3.00 |

Hard limits enforced:
- Per-workflow token budget (env `AGENT_MAX_TOKENS`, default 200 k).
- Per-customer monthly cap with `WIDESPREAD_AGENT_LOOPS` alert at 80 %.
- Loop guard: same tool called > 5× in a workflow → abort + escalate.

## 8 · Audit and compliance

Every step lands in three places:
1. Kafka `agent.activity` — live UI.
2. `app.agent_runs` — workflow lifecycle row.
3. `audit.events` — immutable trail of every tool call + every approval decision.

The audit table is what an operations engineer or compliance auditor queries — never the live `agent_runs`.
