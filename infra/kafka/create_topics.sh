#!/bin/sh
set -eu

BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

create_topic() {
  topic="$1"
  /opt/bitnami/kafka/bin/kafka-topics.sh \
    --bootstrap-server "$BOOTSTRAP_SERVER" \
    --create \
    --if-not-exists \
    --topic "$topic" \
    --partitions 1 \
    --replication-factor 1
}

create_topic "dq.events"
create_topic "twin.fdd.alerts"
create_topic "rl.actions"
create_topic "agent.activity"
create_topic "notifications.inapp"
