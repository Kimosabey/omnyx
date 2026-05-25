# 15 · Deployment — On-Premise

> **Default sale: one big PC at the customer's site, on their network.** All 18 OMNYX containers fit on one host (proven on the dev laptop). Multi-host topologies are documented for large customers but **not the default**.
>
> Each customer = their own install on their own hardware. Graylinx never hosts customer data. See [`37_DEPLOYMENT_MODEL.md`](37_DEPLOYMENT_MODEL.md).

Three deployment targets. **POC and the typical customer use (A) — one big PC.** Large multi-building customers use (B). v3 multi-site at scale uses (C).

## A · Single-host Docker Compose (POC)

Everything on one machine. Verified runs on the dev laptop (Intel Core Ultra 7 155H, 24 GB RAM, Windows 11). Linux preferred; Windows-via-WSL2 acceptable.

### A.1 Host requirements

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores | 8+ cores |
| RAM | 16 GB | 32 GB |
| Disk | 100 GB SSD | 500 GB NVMe |
| Network | 100 Mbps | 1 Gbps |
| OS | Ubuntu 22.04 LTS | same |
| Docker | 24.x | 24.x |
| Compose | v2 | v2 |

### A.2 docker-compose.yml outline

`infra/compose/docker-compose.yml` — full file in repo. Sketch:

```yaml
name: omnyx
volumes: { kafka_data:, pg_data:, redis_data:, keycloak_data:, grafana_data:, loki_data: }
networks: { omnyx_net: }

services:

  # ---- core infra ----
  kafka:
    image: confluentinc/cp-kafka:7.6.1
    # (KRaft config — see 07_KAFKA_PIPELINE.md §2)
    networks: [omnyx_net]
    ports: ["9092:9092"]
    volumes: [kafka_data:/var/lib/kafka/data]
    healthcheck: { test: ["CMD","kafka-broker-api-versions","--bootstrap-server","localhost:9092"], interval: 10s }

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    ports: ["8080:8080"]
    environment: { KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:29092 }
    networks: [omnyx_net]
    depends_on: { kafka: { condition: service_healthy } }

  kafka-init:
    image: confluentinc/cp-kafka:7.6.1
    entrypoint: ["bash","/init.sh"]
    volumes: ["../kafka/create_topics.sh:/init.sh"]
    networks: [omnyx_net]
    depends_on: { kafka: { condition: service_healthy } }
    restart: "no"

  postgres:
    image: timescale/timescaledb-ha:pg16
    environment: { POSTGRES_PASSWORD: ${POSTGRES_PASSWORD} }
    ports: ["5432:5432"]
    volumes:
      - pg_data:/home/postgres/pgdata/data
      - ../postgres/migrations:/docker-entrypoint-initdb.d
    networks: [omnyx_net]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    networks: [omnyx_net]
    volumes: [redis_data:/data]

  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    command: ["start-dev","--import-realm"]
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    ports: ["8081:8080"]
    volumes: ["../keycloak/realm-export.json:/opt/keycloak/data/import/realm-export.json"]
    networks: [omnyx_net]

  prometheus:
    image: prom/prometheus:v2.51
    volumes: ["../prometheus:/etc/prometheus"]
    ports: ["9090:9090"]
    networks: [omnyx_net]

  grafana:
    image: grafana/grafana:10.4
    ports: ["3000:3000"]
    volumes: [grafana_data:/var/lib/grafana, "../grafana:/etc/grafana/provisioning"]
    networks: [omnyx_net]

  loki:
    image: grafana/loki:2.9
    ports: ["3100:3100"]
    volumes: [loki_data:/loki]
    networks: [omnyx_net]

  promtail:
    image: grafana/promtail:2.9
    volumes: ["../prometheus/promtail.yml:/etc/promtail/config.yml","/var/lib/docker/containers:/var/lib/docker/containers:ro"]
    networks: [omnyx_net]

  # ---- field simulator (bind-mounted from gl_pbs) ----
  bacnet-sim:
    build: { context: ../../../../simulations/gl_pbs, dockerfile: Dockerfile.sim }
    network_mode: "host"     # BACnet UDP needs host networking
    ports: ["7091-7101:7091-7101"]

  # ---- OMNYX services ----
  dal-bacnet:
    build: ../../services/dal-bacnet
    network_mode: "host"     # also UDP
    environment:
      KAFKA_BROKERS: localhost:9092
      POSTGRES_URL: postgresql://omnyx:${POSTGRES_PASSWORD}@localhost:5432/omnyx
      BACNET_INI: /app/config/GLBACpypes.ini
      COV_THRESHOLD_PCT: "3"
    volumes: ["../../../../simulations/gl_pbs/config:/app/config:ro","../../../../simulations/gl_pbs/data:/app/data:ro"]

  dal-replay:
    build: ../../services/dal-replay
    profiles: ["replay"]     # only runs when explicitly enabled
    environment:
      KAFKA_BROKERS: kafka:29092
      UNICHARM_URL: mysql://ro_user:${UNICHARM_RO_PW}@${UNICHARM_HOST}:3307/unicharm

  db-writer:
    build: ../../services/db-writer
    environment:
      KAFKA_BROKERS: kafka:29092
      POSTGRES_URL: postgresql://omnyx:${POSTGRES_PASSWORD}@postgres:5432/omnyx
    networks: [omnyx_net]
    depends_on: [kafka, postgres]

  dq-etl:
    build: ../../services/dq-etl
    environment:
      POSTGRES_URL: postgresql://omnyx:${POSTGRES_PASSWORD}@postgres:5432/omnyx
      UNICHARM_URL: mysql://ro_user:${UNICHARM_RO_PW}@${UNICHARM_HOST}:3307/unicharm
    networks: [omnyx_net]

  twin-broker:
    build: ../../services/twin-broker
    environment:
      KAFKA_BROKERS: kafka:29092
      POSTGRES_URL: postgresql://omnyx:${POSTGRES_PASSWORD}@postgres:5432/omnyx
    networks: [omnyx_net]

  rl-broker:
    build: ../../services/rl-broker
    environment:
      KAFKA_BROKERS: kafka:29092
      POSTGRES_URL: postgresql://omnyx:${POSTGRES_PASSWORD}@postgres:5432/omnyx
    networks: [omnyx_net]

  agentic-ai:
    build: ../../services/agentic-ai
    environment:
      KAFKA_BROKERS: kafka:29092
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LLM_BACKEND: ${LLM_BACKEND:-claude}                 # claude | ollama
      OLLAMA_URL: ${OLLAMA_URL:-http://host.docker.internal:11434}
      API_BASE_URL: http://api-service:8000
      KEYCLOAK_TOKEN_URL: http://keycloak:8080/realms/omnyx/protocol/openid-connect/token
    networks: [omnyx_net]

  api-service:
    build: ../../services/api-service
    ports: ["8000:8000"]
    environment:
      KAFKA_BROKERS: kafka:29092
      POSTGRES_URL: postgresql://omnyx:${POSTGRES_PASSWORD}@postgres:5432/omnyx
      REDIS_URL: redis://redis:6379
      KEYCLOAK_JWKS_URL: http://keycloak:8080/realms/omnyx/protocol/openid-connect/certs
    networks: [omnyx_net]
    depends_on: [postgres, kafka, redis, keycloak]

  ws-bridge:
    build: ../../services/ws-bridge
    ports: ["8765:8765"]
    environment:
      KAFKA_BROKERS: kafka:29092
      KEYCLOAK_JWKS_URL: http://keycloak:8080/realms/omnyx/protocol/openid-connect/certs
    networks: [omnyx_net]

  frontend:
    build: ../../services/frontend
    ports: ["80:80"]
    environment:
      VITE_API_BASE: http://localhost:8000
      VITE_WS_BASE: ws://localhost:8765
      VITE_KEYCLOAK_URL: http://localhost:8081
    networks: [omnyx_net]
```

### A.3 Bring-up commands

```bash
cd /d/Harshan/graylinx-v2/omnyx/infra/compose
cp .env.example .env       # fill in passwords + ANTHROPIC_API_KEY
docker compose up -d       # core
docker compose --profile replay up dal-replay   # one-shot history load
```

Total ~18 containers, ~3 GB RAM steady state. See [16_POC_RUNBOOK.md](16_POC_RUNBOOK.md) for full bring-up checklist.

---

## B · Production beta — Two machines

From [KAFKA_VERDICT_AND_REQUIREMENTS.md §5](../../../../simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md):

| Machine 1 — Edge | Machine 2 — Server |
|---|---|
| Intel i5, 8 GB, 64 GB SSD, 1 Gbps | Intel i7/Xeon, 32 GB, 2 TB SSD, 1–10 Gbps |
| Runs `dal-bacnet`, local Kafka producer | Runs everything else |
| `network_mode: host` for BACnet | Standard bridge |

Edge and server linked by Tailscale or wireguard. Kafka producer compresses + batches before WAN.

---

## C · Multi-site Kubernetes (v3 path)

| Layer | Choice |
|---|---|
| Orchestration | Vanilla Kubernetes 1.30 or k3s for smaller sites |
| Kafka | Strimzi operator, 3-broker quorum, KRaft |
| Postgres | CloudNativePG operator, 1 primary + 2 replicas, PITR via pgBackRest |
| Secrets | External Secrets Operator → Vault |
| Ingress | Traefik or NGINX with cert-manager (Let's Encrypt or private CA) |
| GPU | Per PRD §12 — 1 GPU per 50–100 sites for twin / RL inference; nvidia-device-plugin |

Helm chart skeleton lives at `infra/helm/omnyx/` (placeholder for v3 — not built in POC).

## D · Hardware sizing summary (PRD-aligned)

| Sites | DDCs | est. msg/s | CPU | RAM | Profile |
|---|---|---|---|---|---|
| 1 (POC) | 11 | 2 | i5 4-core | 16 GB | Single-host A |
| 1–10 | 110 | 21 | i3 4-core | 8 GB | A still fine |
| 10–50 | 550 | 105 | i5 6-core | 16 GB | Two-machine B |
| 50–100 | 1 100 | 210 | i7 8-core | 32 GB | B with bigger server |
| 100–500 | 5 500 | 1 000+ | Xeon, separate Kafka host | 64 GB | C (k8s + GPU) |

## E · Backups

- Postgres: `pg_basebackup` nightly + WAL archive every 5 m → S3-compatible MinIO running on the same host.
- Kafka: retention is the only "backup" (7 d). Critical topics (`agent.activity`, `audit.events`) replicated to Postgres by `db-writer` so loss of broker doesn't lose history.
- Keycloak: `kc.sh export --realm omnyx` nightly to MinIO.
