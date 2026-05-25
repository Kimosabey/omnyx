# 19 · Risks & Open Questions

Captured up front so they can be tracked rather than discovered late.

## 1 · Risks

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Twin physics model is too crude → FDD has false positives | Medium | High | Start with a known good chiller mathematical model (Carnot + ε-NTU + part-load curve); calibrate from 90 d Unicharm replay; gate FDD alerts behind `z≥3 + persistence ≥ N` |
| R2 | Agentic AI cost runaway (loops, expensive Opus calls) | Medium | Medium | Hard per-workflow token budget + monthly customer cap + loop-guard that aborts after 5 same-tool calls; alerting at 80 % of budget |
| R3 | Claude API outage breaks demo | Low | High | `LLM_BACKEND=ollama` fallback ships from day 1 (qwen2.5:14b on Tailscale Ollama already in HVAC stack); demo can switch in under 30 s |
| R4 | Unicharm read-only credential rotated or revoked mid-replay | Low | Medium | `dal-replay` is resumable via `replay_progress`; document credential refresh path with their DBA |
| R5 | BACnet RPM rejection bug regresses when porting read code | Medium | Medium | Port `bacnet/read_strategy.py` and `bacnet/read_thread.py` from gl_pbs verbatim (the [RCA fix](../../../../simulations/gl_pbs/docs/RCA_RPM_No_Response.md) is preserved); add a CI test that runs against a mock non-RPM device |
| R6 | DQ false positives drown the inbox during early tuning | High | Medium | Ship with conservative thresholds (wide z-score bands, long hold-times); per-point overrides table; nightly "alert noise" report for AI Ops Specialist to retune |
| R7 | Single-broker Kafka is a SPOF for the POC demo | Low | High | Single-broker is acceptable for POC scope; documented k8s/Strimzi path for production HA; volumes survive container restart |
| R8 | Operator distrust of autonomous actions | Medium | Medium | Default everything to **Tier 2 max** for new customers; ramp autonomy only after AI Ops Specialist sign-off and an audit-window review |
| R9 | Postgres + Kafka + everything-else on one host → noisy neighbour | Medium | Low | Documented sizing (15 §D); production path moves Kafka and Postgres to separate hosts |
| R10 | Frontend bundle bloats because we keep THERMYNX kit and add OMNYX kit | Low | Low | Module federation: THERMYNX routes lazy-loaded only for users with that role |

## 2 · Open Questions

PRD §13 plus the new ones we identified while writing this plan.

| Q | Owner | Decision needed by |
|---|---|---|
| Which vertical extension is v2 — Factory or Water? | Product | Before Phase 2 kickoff |
| Twin data schema: standardise or per-customer adapter? | Engineering | Before second twin model |
| RL agent versioning + roll-back UX | AI Ops | Before any LIVE promotion |
| Agentic AI monthly cost ceiling per customer | Finance + Product | Before first beta customer |
| Default autonomy tier for new customer (currently Tier 2) | Product | Before first beta |
| Compliance scope: GDPR? HIPAA-equivalent for industrial? SOX? | Legal | Before beta sign-off |
| On-prem LLM required at v1? | Product + Security | Before beta if any customer disallows external API |
| Brand: confirm **OMNYX** wordmark — trademark check, domain availability | Brand + Legal | Before any external use |
| THERMYNX continues as a separate sales SKU or as a bundled extension? | Sales | Before pricing model |
| Unicharm cutover plan: does the existing ETL stay alive during overlap, or is OMNYX day-1 the source? | Customer success + Unicharm IT | Before Unicharm migration begins |

## 3 · Things that could move the timeline

- **Customer-supplied twin models** materially earlier than W8 → we skip our seed twin and ship theirs.
- **Customer's existing RL agents** delivered before W9 → we wrap them in our broker interface, skip offline training.
- **Agent-tool surface area** grows beyond the initial 18 tools → +1 day per tool plus tests.
- **Multi-tenant requirement** lands before MVP → +1 week (tenant-id propagation through every query).

## 4 · "We will know we're off-plan if…"

- Week 4 ends without a `QualityFlag != GOOD` event reaching the UI.
- Week 8 ends without an `Alert(source=twin_fdd)` from an injected drift.
- Week 10 ends without an autonomous WO creation in the agent activity feed.
- DQ event volume in production is > 5× POC volume (would indicate the simulator is too benign — re-tune from Unicharm replay).
