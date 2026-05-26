from prometheus_client import Counter, Gauge, Histogram, start_http_server

readings_published = Counter(
    "dal_bacnet_readings_published_total",
    "Total PointReadings published to Kafka",
    ["tenant_id", "quality_flag"],
)

dq_flags_raised = Counter(
    "dal_bacnet_dq_flags_total",
    "DQ flag counts by type",
    ["flag"],
)

read_latency = Histogram(
    "dal_bacnet_read_latency_seconds",
    "Time to complete one full poll cycle across all DDCs",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

devices_active = Gauge(
    "dal_bacnet_devices_active",
    "Number of DDCs successfully polled in last cycle",
)

devices_offline = Gauge(
    "dal_bacnet_devices_offline",
    "Number of DDCs that failed in last cycle",
)

kafka_publish_errors = Counter(
    "dal_bacnet_kafka_publish_errors_total",
    "Kafka publish failures",
)


def start_metrics(port: int) -> None:
    start_http_server(port)
