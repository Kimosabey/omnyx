export const config = {
  port:             parseInt(process.env.WS_PORT         ?? "8765"),
  kafkaBrokers:     (process.env.KAFKA_BOOTSTRAP_SERVERS ?? "kafka:9092").split(","),
  kafkaGroupId:     "ws-bridge",
  kafkaTopicRaw:    "telemetry.raw",
  keycloakJwksUrl:  process.env.KEYCLOAK_JWKS_URL        ?? "http://keycloak:8080/realms/omnyx/protocol/openid-connect/certs",
  keycloakIssuer:   process.env.KEYCLOAK_ISSUER          ?? "http://keycloak:8080/realms/omnyx",
  tenantId:         process.env.TENANT_ID                ?? "unicharm",
  snapshotIntervalMs: parseInt(process.env.SNAPSHOT_INTERVAL_MS ?? "5000"),
} as const;
