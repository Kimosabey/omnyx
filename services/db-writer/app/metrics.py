from prometheus_client import Counter, Histogram, Gauge, start_http_server

rows_written = Counter(
    "db_writer_rows_written_total",
    "Rows written to telemetry.readings",
    ["tenant_id", "quality_flag"],
)

write_latency = Histogram(
    "db_writer_write_latency_seconds",
    "Time to flush a batch to Postgres",
    buckets=[0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

kafka_lag = Gauge(
    "db_writer_kafka_lag_messages",
    "Approximate consumer lag (messages behind)",
)

write_errors = Counter(
    "db_writer_write_errors_total",
    "Postgres write failures",
)

audit_rows_written = Counter(
    "db_writer_audit_rows_written_total",
    "Audit events written to audit.events",
)


def start_metrics(port: int) -> None:
    start_http_server(port)
