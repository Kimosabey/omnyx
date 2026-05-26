export const config = {
  port:           parseInt(process.env.PORT           ?? "8000"),
  metricsPort:    parseInt(process.env.METRICS_PORT   ?? "9091"),
  nodeEnv:        process.env.NODE_ENV                ?? "development",

  // App / primary DB (source + app schemas)
  appDbUrl:       process.env.APP_DB_URL              ?? "postgresql://omnyx:change-me@postgres:5432/omnyx",
  // Telemetry DB (TimescaleDB) — read-only for charts/reports
  telemetryDbUrl: process.env.TELEMETRY_DB_URL        ?? "postgresql://omnyx:change-me@timescaledb:5432/omnyx_ts",

  redisUrl:       process.env.REDIS_URL               ?? "redis://redis:6379",
  kafkaBrokers:   (process.env.KAFKA_BOOTSTRAP_SERVERS ?? "kafka:9092").split(","),

  keycloakJwksUrl:   process.env.KEYCLOAK_JWKS_URL   ?? "http://keycloak:8080/realms/omnyx/protocol/openid-connect/certs",
  keycloakIssuer:    process.env.KEYCLOAK_ISSUER      ?? "http://keycloak:8080/realms/omnyx",
  keycloakClientId:  process.env.KEYCLOAK_CLIENT_ID   ?? "omnyx-api",
  keycloakSecret:    process.env.KEYCLOAK_CLIENT_SECRET ?? "omnyx-api-secret-change-me",

  tenantId:       process.env.TENANT_ID               ?? "unicharm",

  dbPoolMin:  2,
  dbPoolMax: 20,
} as const;
