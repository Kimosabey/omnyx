"""
Kafka publisher — serialises PointReading and sends to telemetry.raw.
"""
import json
import logging
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import KafkaError

from .config import settings
from .models import PointReading
from . import metrics

log = logging.getLogger("publisher")


class KafkaPublisher:
    def __init__(self) -> None:
        self._producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=5,
            linger_ms=50,
            batch_size=32768,
        )
        log.info("Kafka producer ready → %s", settings.kafka_bootstrap_servers)

    def publish(self, reading: PointReading) -> None:
        payload = reading.to_kafka_dict()
        try:
            self._producer.send(
                settings.kafka_topic_raw,
                key=reading.point_id,
                value=payload,
            )
            metrics.readings_published.labels(
                tenant_id=reading.tenant_id,
                quality_flag=reading.quality.flag,
            ).inc()
            for flag in reading.quality.dq_flags:
                metrics.dq_flags_raised.labels(flag=flag).inc()
        except KafkaError as exc:
            metrics.kafka_publish_errors.inc()
            log.error("Kafka publish failed for %s: %s", reading.point_id, exc)

    def publish_batch(self, readings: list[PointReading]) -> None:
        for r in readings:
            self.publish(r)
        self._producer.flush()

    def close(self) -> None:
        self._producer.flush()
        self._producer.close()
