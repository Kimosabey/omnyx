# 07 · Kafka Pipeline

## 1 · Why Kafka, decided

Already proven in the gl_pbs [KAFKA_VERDICT_AND_REQUIREMENTS.md](../../../../simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md). Highlights:

| Requirement | Verdict |
|---|---|
| Multiple consumers need the same data | ✅ DB writer + WS bridge + Twin + RL + Agentic AI |
| Buffer if consumer goes offline | ✅ 7-day retention |
| Replay for fault analysis | ✅ Twin / RL bootstrap, agentic memory |
| Scale to 100 sites | ✅ proven 4,913 msg/s on a laptop |
| Decouple producer and consumer rates | ✅ DAL writes fast, DB writer drains at its pace |

## 2 · Broker layout (POC: single-broker KRaft)

Reuses the exact compose block from gl_pbs `docker-compose.yml`. KRaft mode — no Zookeeper.

```yaml
kafka:
  image: confluentinc/cp-kafka:7.6.1
  container_name: gl-kafka
  ports: ["9092:9092"]
  environment:
    KAFKA_NODE_ID: 1
    KAFKA_PROCESS_ROLES: 'broker,controller'
    KAFKA_CONTROLLER_QUORUM_VOTERS: '1@localhost:9093'
    KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093,PLAINTEXT_INTERNAL://0.0.0.0:29092'
    KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://localhost:9092,PLAINTEXT_INTERNAL://kafka:29092'
    KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
    KAFKA_HEAP_OPTS: "-Xmx2G -Xms1G"
    KAFKA_LOG_RETENTION_HOURS: 168       # 7 days
    KAFKA_LOG_RETENTION_BYTES: -1
    KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
    KAFKA_NUM_PARTITIONS: 12
    KAFKA_DEFAULT_REPLICATION_FACTOR: 1
    CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
```

Production deployment (§15) switches to a 3-broker quorum.

## 3 · Topics (declarative — created via init job, not auto-create)

Auto-create is **off** so a typo in a producer doesn't spawn a phantom topic.

| Topic | Partitions | Retention | Producers | Consumers |
|---|---|---|---|---|
| `raw.bacnet.{device_id}` | 12 | 7 d | dal-bacnet, dal-replay | db-writer, ws-bridge, twin-broker, rl-broker |
| `cmd.bacnet.{device_id}` | 6 | 24 h | api-service | dal-bacnet |
| `reply.bacnet.{request_id}` | 6 | 1 h | dal-bacnet | api-service |
| `dq.events` | 6 | 30 d | dal-bacnet, dq-etl | db-writer, agentic-ai |
| `twin.fdd.alerts` | 6 | 30 d | twin-broker | db-writer, ws-bridge, agentic-ai |
| `rl.actions` | 6 | 30 d | rl-broker | db-writer, ws-bridge, dal-bacnet (for live mode) |
| `agent.activity` | 6 | 14 d | agentic-ai | ws-bridge (live feed), db-writer |
| `health.{service}` | 3 | 7 d | all | prometheus (via exporter) |

Note on `raw.bacnet.{device_id}` topics: we use one topic per device for the POC (≤ 100 devices). At >1 000 devices, switch to a single `raw.bacnet` topic with `device_id` as key — already designed for in the canonical model.

## 4 · Topic creation script

`infra/kafka/create_topics.sh`, executed by a one-shot `kafka-init` container in compose:

```bash
#!/usr/bin/env bash
set -euo pipefail
B=kafka:29092
kafka-topics --bootstrap-server $B --if-not-exists --create --topic dq.events --partitions 6 --replication-factor 1 --config retention.ms=2592000000
kafka-topics --bootstrap-server $B --if-not-exists --create --topic twin.fdd.alerts --partitions 6 --replication-factor 1
kafka-topics --bootstrap-server $B --if-not-exists --create --topic rl.actions --partitions 6 --replication-factor 1
kafka-topics --bootstrap-server $B --if-not-exists --create --topic agent.activity --partitions 6 --replication-factor 1
for d in DDC01 DDC01_01 DDC02 DDC03 DDC04 DDC05 DDC06 DDC07 DDC07_01 DDC09 DDC10 chiller_1 chiller_2 cooling_tower_1 cooling_tower_2 condenser_pump_1 condenser_pump_3 primary_pump_1 primary_pump_2 primary_pump_3 plant; do
  kafka-topics --bootstrap-server $B --if-not-exists --create --topic "raw.bacnet.$d" --partitions 12 --replication-factor 1
done
echo "Topics ready."
```

## 5 · Consumer groups

| Group | Members | Reset policy |
|---|---|---|
| `db-writer` | 1 db-writer instance | `latest` for live, `earliest` for back-fill |
| `ws-bridge` | 1 ws-bridge | `latest` |
| `twin-broker` | 1 per twin model | `latest`; back-fill done via offset reset on retrain |
| `rl-broker` | 1 per RL agent | `earliest` for shadow training, `latest` for live |
| `agentic-ai` | 1 | `latest` |
| `prom-kafka-exporter` | 1 | n/a |

Lag SLOs (alerts in Grafana):
- `db-writer` lag < 1 000 messages
- `ws-bridge` lag < 100 messages
- `twin-broker` lag < 500 messages

## 6 · Producer settings (DAL)

```python
producer = Producer({
  "bootstrap.servers": "kafka:29092",
  "client.id": "dal-bacnet",
  "compression.type": "snappy",
  "linger.ms": 50,            # batch a bit, real load is 2 msg/s, this is fine
  "batch.size": 65536,
  "acks": "1",                # single-broker POC; "all" in production
  "enable.idempotence": True,
  "max.in.flight.requests.per.connection": 5,
})
```

## 7 · Schema strategy

POC: **JSON only**. Every payload is `PointBatch` JSON (or one of the other dataclasses in §05). Easy to debug, no schema registry to operate. Same as the proven `kafka_bacnet_bridge.py` payload.

v2 path: **Avro + Confluent Schema Registry**. Producer/consumer libraries already abstracted behind a `Codec` interface so the swap is one file.

## 8 · Sizing — proven and projected

From the gl_pbs real-stack test (Scenario 4):

| Metric | Value |
|---|---|
| Real msg/s (COV-filtered) | 2.1 |
| Kafka CPU avg | 1.0 % |
| Kafka RAM | ~470 MB |
| MySQL CPU avg | 0.6 % |
| End-to-end delivery | 100 % over 34 min |
| Disk growth | ~0.5 MB/s per site at the broker |

Projected for the new platform with twin + RL + agentic AI consumers added: 4× consumer count → ~4 % broker CPU; still vastly under any threshold. POC laptop (Core Ultra 7 + 24 GB) handles 50 sites easily.

## 9 · Operational concerns

| Concern | Handling |
|---|---|
| Broker down | Producer buffers in memory `queue.buffering.max.messages = 100000`. After that, DAL drops the oldest batches and emits `dq.events` of type `KAFKA_BACKPRESSURE`. |
| Consumer fell behind | Grafana lag alert; consumer reads at own pace; no producer pressure. |
| Disk fill | 7-d retention + size-based retention cap (`KAFKA_LOG_RETENTION_BYTES` set in production). |
| Re-bootstrapping | A new consumer with same `group.id` picks up at last committed offset; back-fill consumers use a different `group.id` to avoid trampling live offsets. |
| UI | Kafka UI on port 8080, exactly as in gl_pbs. |

## 10 · Backpressure into DAL

If the Kafka producer queue exceeds `queue_threshold`, DAL:
1. Stops new COV publishes (still polls BACnet so we don't lose RPM cadence).
2. Emits `DEVICE_DATA_QUALITY_DEGRADED` per affected device.
3. Resumes when queue depth drops below `queue_resume`.

This is critical at sites with intermittent links — the simulator can be set to lose UDP packets to demo the behaviour.
