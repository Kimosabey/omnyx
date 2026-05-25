# 24 · Observability

Prometheus + Loki + Grafana stack, already in compose. This doc fixes the **metrics, log fields, and trace identifiers** every service must emit so dashboards are consistent.

## 1 · Three signals

| Signal | Tool | Where |
|---|---|---|
| Metrics | Prometheus + service-side `prom-client` / `prometheus_client` | scraped on each service's `/metrics` |
| Logs | Pino (Node) / structlog (Python) → stdout → Promtail → Loki | structured JSON |
| Traces | OpenTelemetry — kept as a v2 add; POC carries `request_id` end-to-end | `request_id` header propagation only |

## 2 · Common labels every metric must carry

| Label | Example |
|---|---|
| `service` | `dal-bacnet`, `api-service`, `agentic-ai`, … |
| `tenant_id` | `unicharm` |
| `site_id` | when known |
| `env` | `dev`, `staging`, `prod` |
| `version` | git SHA short |

`tenant_id` on a metric is what makes per-customer dashboards possible.

## 3 · Per-service metrics catalogue

### dal-bacnet

| Metric | Type | Labels |
|---|---|---|
| `bacnet_read_total` | counter | `device_id`, `strategy=rpm|single`, `result=ok|fail` |
| `bacnet_read_duration_seconds` | histogram | `device_id` |
| `cov_filter_passed_total` | counter | `device_id` |
| `cov_filter_dropped_total` | counter | `device_id` |
| `dq_tier1_checks_total` | counter | `check=frozen|spike|range|...`, `result=good|suspect|bad|imputed|missing` |
| `dq_tier1_duration_seconds` | histogram | (no extra labels) |
| `dq_imputations_total` | counter | `method=lkg|twin|linear|...` |
| `kafka_producer_queue_size` | gauge | — |
| `kafka_producer_send_total` | counter | `topic`, `result=ok|fail` |

### db-writer

| Metric | Type | Labels |
|---|---|---|
| `kafka_consumer_lag` | gauge | `topic`, `partition` |
| `db_insert_total` | counter | `table`, `result=ok|fail` |
| `db_insert_duration_seconds` | histogram | `table` |

### api-service

| Metric | Type | Labels |
|---|---|---|
| `http_request_duration_seconds` | histogram | `method`, `route`, `status` |
| `http_request_total` | counter | same |
| `agent_tool_call_total` | counter | `tool`, `tier`, `result=ok|fail|denied_rbac|denied_approval` |
| `rule_eval_total` | counter | `rule_kind`, `result=ok|alert_fired|no_change` |
| `alerts_open_count` | gauge | `severity` |

### ws-bridge

| Metric | Type | Labels |
|---|---|---|
| `ws_clients_connected` | gauge | — |
| `ws_messages_sent_total` | counter | `channel` |
| `ws_message_lag_seconds` | histogram | (snapshot publish minus measurement timestamp) |

### twin-broker

| Metric | Type | Labels |
|---|---|---|
| `twin_step_total` | counter | `twin_model_id`, `device_id` |
| `twin_residual_z` | histogram | `point_id` |
| `twin_fdd_alerts_total` | counter | `fault_code`, `severity` |
| `twin_prediction_mape` | gauge | `twin_model_id`, `device_id`, `output` |

### rl-broker

| Metric | Type | Labels |
|---|---|---|
| `rl_actions_total` | counter | `agent_id`, `mode=shadow|live|paused`, `result=emitted|suppressed_dq|safety_bound_hit` |
| `rl_reward` | gauge | `agent_id` |
| `rl_safety_violations_total` | counter | `agent_id` |

### agentic-ai

| Metric | Type | Labels |
|---|---|---|
| `agent_run_started_total` | counter | `workflow_id` |
| `agent_run_finished_total` | counter | `workflow_id`, `status=succeeded|failed|loop_guard|budget|awaiting_approval` |
| `agent_run_duration_seconds` | histogram | `workflow_id` |
| `agent_tokens_total` | counter | `agent=planner|executor|validator`, `kind=input|output|cache_read|cache_write` |
| `agent_cost_usd_total` | counter | `workflow_id` |

### dq-etl

| Metric | Type | Labels |
|---|---|---|
| `dq_job_runs_total` | counter | `job`, `result=ok|fail` |
| `dq_job_duration_seconds` | histogram | `job` |
| `sensor_drift_detected_total` | counter | (per run) |
| `gap_reconciled_total` | counter | (per run) |

## 4 · Log structure (every service)

Mandatory JSON keys:

| Field | Source |
|---|---|
| `ts` | ISO-8601 UTC |
| `level` | `debug|info|warn|error|fatal` |
| `service` | constant per service |
| `version` | git SHA |
| `tenant_id` | from request context (when applicable) |
| `request_id` | from `x-request-id` header; generated if absent |
| `msg` | human-readable |
| `extra` | arbitrary structured payload |

Redaction list per service prevents secret leakage; covers `password`, `token`, `apiKey`, `Authorization`, `secret`.

Example log line:

```json
{"ts":"2026-05-25T11:23:01.412Z","level":"info","service":"api-service","version":"a1b2c3d","tenant_id":"unicharm","request_id":"01HXYZ...","msg":"agent tool call","extra":{"tool":"create_work_order","tier":2,"workflow_id":"investigate_alert","duration_ms":127}}
```

## 5 · Grafana dashboards (provisioned)

`infra/grafana/provisioning/dashboards/`:

| Dashboard | Audience | Panels |
|---|---|---|
| OMNYX Overview | Portfolio Mgr | KPIs, Kafka lag, Postgres connections, error rate, agent runs/h, RL safety violations |
| Telemetry pipeline | Ops Engineer | dal-bacnet read rate, COV %, DQ flag distribution, Kafka throughput, db-writer lag |
| Data quality | AI Ops | per-sensor health score, drift heat map, gap rate, Tier-2 job runs |
| Digital twin | AI Ops | residual z heatmap, MAPE per model, FDD alerts |
| RL | AI Ops | reward curves per agent, action distribution, safety violations |
| Agentic AI | AI Ops | runs/hour, status mix, tokens, cost, validator rejection rate |
| Infrastructure | Ops | CPU/RAM/disk per container, Postgres TPS, Redis ops/s, Loki ingest rate |

## 6 · Alerts in Prometheus (alertmanager)

| Alert | Condition | Severity |
|---|---|---|
| KafkaConsumerLagHigh | `kafka_consumer_lag{service="db-writer"} > 1000` for 5 m | warning |
| WSLagHigh | `histogram_quantile(0.95, ws_message_lag_seconds_bucket) > 5` for 2 m | warning |
| AgentBudgetNear | `increase(agent_cost_usd_total[1h]) > 0.8 * monthly_budget/720` | warning |
| RLSafetyViolation | `increase(rl_safety_violations_total[5m]) > 0` | critical |
| TwinMAPEDegraded | `twin_prediction_mape > 2 * baseline_mape` for 1 h | warning |
| DQWidespread | `increase(dq_tier1_checks_total{result=~"bad|missing"}[5m]) / increase(dq_tier1_checks_total[5m]) > 0.3` | critical |
| PostgresDiskHigh | `pg_disk_usage > 0.8` | warning |
| BrokerDown | Kafka exporter unreachable for 1 m | critical |

## 7 · Health check matrix

Re-stated for clarity (same as [16_POC_RUNBOOK §10](16_POC_RUNBOOK.md)):

```
api-service     /healthz        deps: pg, kafka, redis, keycloak, llm, twin-broker, rl-broker, agentic-ai
db-writer       /healthz        deps: pg, kafka
ws-bridge       /healthz        deps: kafka, keycloak
twin-broker     /healthz        deps: pg, kafka, llm (if used)
rl-broker      /healthz         deps: pg, kafka
agentic-ai      /healthz        deps: kafka, api-service, anthropic (or ollama)
dal-bacnet      /healthz        deps: kafka, BACnet socket bound
dq-etl          /healthz        deps: pg, kafka
```

## 8 · Trace propagation (v2)

`x-request-id` is already mandatory. v2 adds OpenTelemetry instrumentation across services so a single span tree covers `request → tool → DB → kafka → agent → tool → DB`. Tempo (or Jaeger) joins the obs stack.
