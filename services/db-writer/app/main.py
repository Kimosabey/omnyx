"""
OMNYX DB-Writer — Kafka consumer → TimescaleDB writer
Consumes telemetry.raw and audit.events topics.
Batches writes for efficiency.
"""
import json
import logging
import signal
import time
from contextlib import suppress

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from .config import settings
from .writer import DBWriter
from .metrics import start_metrics, kafka_lag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)-8s %(message)s",
)
log = logging.getLogger("main")

_running = True


def _shutdown(sig, frame):
    global _running
    log.info("Signal %s received, shutting down", sig)
    _running = False


def _build_consumer() -> KafkaConsumer:
    retries = 0
    while True:
        try:
            consumer = KafkaConsumer(
                settings.kafka_topic_raw,
                settings.kafka_topic_audit,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=int(settings.batch_timeout_s * 1000),
                max_poll_records=settings.batch_size,
            )
            log.info(
                "Kafka consumer ready → %s topics=%s",
                settings.kafka_bootstrap_servers,
                [settings.kafka_topic_raw, settings.kafka_topic_audit],
            )
            return consumer
        except KafkaError as exc:
            retries += 1
            wait = min(2 ** retries, 30)
            log.warning("Kafka connect failed (%s), retry in %ds", exc, wait)
            time.sleep(wait)


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("DB-Writer starting — tenant=%s", settings.tenant_id)

    start_metrics(settings.metrics_port)
    log.info("Metrics on :%d", settings.metrics_port)

    writer = DBWriter()
    consumer = _build_consumer()

    telemetry_batch: list[dict] = []
    audit_batch: list[dict] = []
    last_flush = time.time()

    log.info("Consuming — batch_size=%d, batch_timeout=%.1fs",
             settings.batch_size, settings.batch_timeout_s)

    while _running:
        try:
            # poll() returns a dict of {TopicPartition: [ConsumerRecord]}
            records = consumer.poll(timeout_ms=int(settings.batch_timeout_s * 1000),
                                    max_records=settings.batch_size)

            for tp, msgs in records.items():
                for msg in msgs:
                    if tp.topic == settings.kafka_topic_raw:
                        telemetry_batch.append(msg.value)
                    elif tp.topic == settings.kafka_topic_audit:
                        audit_batch.append(msg.value)

            now = time.time()
            should_flush = (
                len(telemetry_batch) >= settings.batch_size
                or (len(telemetry_batch) > 0 and now - last_flush >= settings.batch_timeout_s)
            )

            if should_flush:
                if telemetry_batch:
                    written = writer.write_readings(telemetry_batch)
                    log.info("Flushed %d readings to DB", written)
                    telemetry_batch.clear()

                if audit_batch:
                    writer.write_audit(audit_batch)
                    log.info("Flushed %d audit events to DB", len(audit_batch))
                    audit_batch.clear()

                last_flush = time.time()

        except Exception as exc:
            log.error("Consumer loop error: %s", exc)
            time.sleep(2.0)

    # Final flush
    with suppress(Exception):
        if telemetry_batch:
            writer.write_readings(telemetry_batch)
        if audit_batch:
            writer.write_audit(audit_batch)

    with suppress(Exception):
        consumer.close()
    with suppress(Exception):
        writer.close()

    log.info("DB-Writer stopped")


if __name__ == "__main__":
    main()
