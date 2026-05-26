from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    kafka_bootstrap_servers: str = Field("kafka:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_group_id: str = Field("db-writer", env="KAFKA_GROUP_ID")
    kafka_topic_raw: str = "telemetry.raw"
    kafka_topic_audit: str = "audit.events"
    kafka_topic_agent: str = "agent.activity"

    postgres_url: str = Field(
        "postgresql://omnyx:change-me@postgres:5432/omnyx", env="POSTGRES_URL"
    )

    tenant_id: str = Field("unicharm", env="TENANT_ID")

    # Write batch — flush to DB after N messages or T seconds
    batch_size: int = Field(200, env="BATCH_SIZE")
    batch_timeout_s: float = Field(2.0, env="BATCH_TIMEOUT_S")

    metrics_port: int = Field(8011, env="METRICS_PORT")

    class Config:
        env_file = ".env"


settings = Settings()
