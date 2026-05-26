from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    kafka_bootstrap_servers: str = Field("localhost:9095", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic_raw: str = "telemetry.raw"
    kafka_topic_dq: str = "dq.events"

    postgres_url: str = Field("postgresql://omnyx:change-me@localhost:5432/omnyx", env="POSTGRES_URL")

    tenant_id: str = Field("unicharm", env="TENANT_ID")

    # Path to GLBACpypes.ini (written by bacnet_name_launcher)
    bacnet_ini: str = Field("/app/config/GLBACpypes.ini", env="BACNET_INI")

    # Path to eqp_name_handling.csv
    csv_path: str = Field("/app/data/eqp_name_handling.csv", env="CSV_PATH")

    # CoV threshold — skip publish if abs((new-old)/old) < threshold
    cov_threshold_pct: float = Field(3.0, env="COV_THRESHOLD_PCT")

    # Polling interval in seconds
    poll_interval_s: float = Field(5.0, env="POLL_INTERVAL_S")

    # BACnet timeout per request (seconds)
    bacnet_timeout_s: float = Field(15.0, env="BACNET_TIMEOUT_S")

    # RPM batch size (points per ReadPropertyMultiple)
    rpm_batch_size: int = Field(15, env="RPM_BATCH_SIZE")

    # Heartbeat — publish ALL values every N seconds regardless of CoV
    heartbeat_s: float = Field(900.0, env="HEARTBEAT_S")

    # Metrics HTTP port
    metrics_port: int = Field(8010, env="METRICS_PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
