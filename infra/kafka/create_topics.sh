#!/bin/sh
set -eu

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

# Wait until broker is fully ready
until /opt/kafka/bin/kafka-broker-api-versions.sh \
    --bootstrap-server "$BOOTSTRAP" > /dev/null 2>&1; do
  echo "Waiting for Kafka broker at $BOOTSTRAP ..."
  sleep 3
done
echo "Kafka ready — creating topics"

create_topic() {
  local topic="$1"
  local partitions="${2:-1}"
  local retention_ms="${3:-604800000}"   # default 7 days
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "$BOOTSTRAP" \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions "$partitions" \
    --replication-factor 1 \
    --config "retention.ms=$retention_ms"
  echo "  topic: $topic  partitions=$partitions  retention=${retention_ms}ms"
}

# --- Topics from 07_KAFKA_PIPELINE.md ---
# 3 partitions on telemetry.raw for parallel consumers (db-writer, twin, rl)
create_topic "telemetry.raw"       3  604800000    # 7 d
create_topic "telemetry.dq"        3  604800000    # 7 d
create_topic "commands.bacnet"     1  86400000     # 1 d  (write-back commands)
create_topic "dq.events"           1  604800000    # 7 d
create_topic "twin.fdd.alerts"     1  2592000000   # 30 d
create_topic "rl.actions"          1  604800000    # 7 d
create_topic "agent.activity"      1  2592000000   # 30 d
create_topic "audit.events"        1  -1           # infinite (replicated to PG by db-writer)
create_topic "notifications.inapp" 1  604800000    # 7 d

echo "All topics created."
