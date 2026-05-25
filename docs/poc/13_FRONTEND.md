# 13 · Frontend — OMNYX Console (React 18)

Reuses the **THERMYNX design system** (Graylinx Brand v2 tokens) verbatim. New routes for OMNYX-level views; HVAC-specific routes live in the THERMYNX vertical extension.

## 1 · App shell

```
omnyx-console/
├── src/
│   ├── app/
│   │   ├── routes/              ← React Router v6 route tree
│   │   ├── theme/               ← Chakra theme = Brand v2 from BRANDING.md
│   │   ├── auth/                ← Keycloak adapter, RBAC guards
│   │   └── shell/               ← Sidebar, topbar, footer "OMNYX · by Graylinx"
│   ├── features/
│   │   ├── portfolio/           ← Portfolio dashboard (multi-site overview)
│   │   ├── site/                ← Site detail (devices grid)
│   │   ├── device/              ← Device drilldown w/ twin overlay
│   │   ├── alerts/              ← Alert inbox + detail
│   │   ├── work-orders/         ← Kanban + detail; kiosk-optimised
│   │   ├── dq/                  ← Data quality dashboard
│   │   ├── twin/                ← Twin diagnostics, RUL, fault tree
│   │   ├── rl/                  ← RL dashboard
│   │   ├── agents/              ← Agentic AI activity feed + approvals
│   │   ├── reports/             ← Generated reports
│   │   └── admin/               ← Users, sites, equipment, DQ config
│   ├── lib/                     ← API client (codegen from OpenAPI), WS client
│   └── components/              ← Shared UI from THERMYNX kit
└── public/
```

## 2 · Routes (PRD-aligned)

| Path | Audience | Key data |
|---|---|---|
| `/` (Portfolio) | Portfolio Manager | Site list, health, alert counts, DQ score per site |
| `/sites/:siteId` | Site Operator | Device grid, twin sync status, online/offline |
| `/devices/:deviceId` | Operator + Engineer | Live trend + **twin overlay**, alerts, WOs, RL link |
| `/alerts` | Operator | Inbox by severity, twin/rule/dq sources |
| `/work-orders` | Maintenance Tech (tablet) | Kanban + dispatch detail (parts list, diagnosis) |
| `/work-orders/kiosk` | Maintenance Tech | Tablet-only big-tap mode |
| `/dq` | AI Ops Specialist | Per-sensor health score, drift trend, gap histogram |
| `/twin/:deviceId` | Operations Engineer | RUL countdown, fault tree, predicted vs actual chart |
| `/rl` | AI Ops Specialist | Agent registry, reward curves, action distribution |
| `/agents` | AI Ops Specialist | Workflow list, **live activity feed**, run history |
| `/approvals` | Operator / Manager | Pending Tier-3+ tool calls, decide with full context |
| `/reports` | Portfolio Manager | Daily / weekly auto-reports |
| `/admin/*` | Admin | Sites, users, equipment, DQ config, rules |
| `/health` | All | Stack status; same data as `/healthz` API |

## 3 · Real-time wiring

- Single WebSocket connection per tab to `wss://host:8765/?token=<JWT>`.
- `useWebSocketChannel(channel)` hook subscribes/unsubscribes via JSON control frames.
- Plant snapshot at 5 s drives live cards in `/`, `/sites/*`, `/devices/*`.
- Alerts are push-on-fire (no polling).
- Agent activity feed subscribes per-workflow.

## 4 · Twin overlay rendering (`/devices/:id`)

Recharts dual-line:
- actual `value_num` from `telemetry.readings_1m` (solid line)
- predicted from `telemetry.twin_states` matched by timestamp (dashed line + uncertainty band)
- residual heat strip below
- annotations for `Alert.fired_at` with twin source

## 5 · Agent activity feed

Subscribes to `agent.activity.{workflow_id}`. Each step renders as a card:

```
💭 Planner — "Plan: gather context for chiller_1 critical alert; if RUL<30d open WO"
🛠️  Executor — get_twin_diagnosis(device_id=chiller_1)
✅ Executor result — {fault_code:"BEARING_WEAR", rul_days:14, ...}
🛠️  Executor — create_work_order({...})
✅ Executor result — {wo_id:"WO-2026-0123", ...}
🧐 Validator — "WO created and reflects diagnosis. APPROVED."
🏁 Done — 4.2s, 9.1k tokens, $0.08
```

Operators can pause, take over, or replay any run.

## 6 · DQ dashboard

- Per-sensor health score grid (green/amber/red).
- Flag distribution donut: GOOD / SUSPECT / IMPUTED / BAD / MISSING.
- Drift trend chart (rolling 30 d residual vs twin prediction).
- Gap frequency histogram.
- Quick-action: open a calibration WO.

## 7 · THERMYNX vertical extension routes

When the user has the `thermynx_hvac` role / extension licence, additional routes mount under `/extensions/thermynx`:
- `/extensions/thermynx/efficiency` — kW/TR bands per chiller (existing UI).
- `/extensions/thermynx/maintenance` — predictive maintenance health score.
- `/extensions/thermynx/forecast` — load forecast.
- `/extensions/thermynx/agent-modes` — the 5 existing agent modes (Investigator, Optimizer, Daily Brief, Root Cause, Maintenance).

These are the screens already shipping at Unicharm; they keep their look-and-feel and are rendered inside the OMNYX shell. No rewrite needed — they're imported as a federated module.

## 8 · Voice & casing

Identical to THERMYNX (the user is the same operator). See [`../../BRANDING.md`](../../BRANDING.md):
- Page titles: Title Case.
- Eyebrows: UPPERCASE 0.1em tracking.
- Buttons: Sentence case ("Scan now").
- Empty states: factual, no emoji.
- Loading: single `…` ellipsis.
