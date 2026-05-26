COMPOSE_FILE := infra/compose/docker-compose.yml
COMPOSE      := docker compose -f $(COMPOSE_FILE)

.PHONY: up up-infra up-app up-sim up-replay down reset logs ps \
        seed seed-dq seed-rules seed-twin seed-rl seed-workflows \
        smoke health backup-pg export-openapi support-bundle release-gate \
        build build-app lint test e2e fmt reseed

# ============================================================
# Gate 1 — Infra only
# ============================================================

up-infra:
	@echo "→ Starting infra stack (Kafka, Postgres, Redis, Keycloak, Grafana, Loki)"
	$(COMPOSE) up -d
	@echo "→ Waiting for services to become healthy..."
	@$(MAKE) health

up: up-infra   ## alias

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v
	@echo "All volumes removed."

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

# ============================================================
# Gate 2 — App services
# ============================================================

up-app:
	@echo "→ Starting OMNYX application services"
	$(COMPOSE) --profile app up -d

up-sim:
	@echo "→ Starting BACnet simulator (gl_pbs)"
	$(COMPOSE) --profile simulator up -d

up-replay:
	@echo "→ Running Unicharm history replay (one-shot)"
	$(COMPOSE) --profile replay run --rm dal-replay

up-all: up-infra up-app up-sim

# ============================================================
# Seed data
# ============================================================

seed: seed-dq seed-rules
	@echo "→ Seed complete"

seed-dq:
	@echo "→ Verifying DQ config seed (in 002_seed_poc.sql)"
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-omnyx} -d $${POSTGRES_DB:-omnyx} \
	  -c "SELECT count(*) AS dq_rules FROM app.data_quality_config;"

seed-rules:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-omnyx} -d $${POSTGRES_DB:-omnyx} \
	  -c "SELECT count(*) AS alert_rules FROM app.alert_rules;"

seed-twin:
	@echo "→ Seed twin model via API (implement when twin-broker is running)"

seed-rl:
	@echo "→ Seed RL agent via API (implement when rl-broker is running)"

seed-workflows:
	@echo "→ Seed agent workflows via API (implement when agentic-ai is running)"

reseed: reset up-infra
	@echo "→ Fresh infra + seed complete"

# ============================================================
# Health checks
# ============================================================

health:
	@echo "Kafka:     " && $(COMPOSE) exec kafka /opt/bitnami/kafka/bin/kafka-broker-api-versions.sh \
	    --bootstrap-server localhost:9092 > /dev/null 2>&1 && echo "OK" || echo "NOT READY"
	@echo "Postgres:  " && $(COMPOSE) exec postgres pg_isready -U $${POSTGRES_USER:-omnyx} > /dev/null 2>&1 \
	    && echo "OK" || echo "NOT READY"
	@echo "Redis:     " && $(COMPOSE) exec redis redis-cli ping 2>/dev/null | grep -q PONG && echo "OK" || echo "NOT READY"
	@echo "Keycloak:  " && curl -sf http://localhost:8081/realms/omnyx > /dev/null 2>&1 && echo "OK" || echo "NOT READY"
	@echo "Grafana:   " && curl -sf http://localhost:3000/api/health > /dev/null 2>&1 && echo "OK" || echo "NOT READY"
	@echo "Prometheus:" && curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1 && echo "OK" || echo "NOT READY"

smoke:
	powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1

# ============================================================
# Build
# ============================================================

build: build-infra build-app

build-infra:
	$(COMPOSE) build kafka-ui grafana prometheus loki

build-app:
	$(COMPOSE) --profile app build

# ============================================================
# Ops
# ============================================================

backup-pg:
	@echo "→ Backing up Postgres to backups/omnyx.sql"
	powershell -Command "New-Item -ItemType Directory -Force -Path backups | Out-Null"
	$(COMPOSE) exec postgres sh -lc "pg_dump -U $$POSTGRES_USER $$POSTGRES_DB" > backups/omnyx.sql
	@echo "→ Backup written to backups/omnyx.sql"

export-openapi:
	@echo "→ OpenAPI export (implement when api-service is running)"

support-bundle:
	powershell -ExecutionPolicy Bypass -File scripts/support-bundle.ps1

release-gate:
	powershell -ExecutionPolicy Bypass -File scripts/release-gate.ps1

# ============================================================
# Dev quality
# ============================================================

lint:
	@echo "→ Lint (implement per-service)"

test:
	@echo "→ Unit tests (implement per-service)"

e2e:
	@echo "→ End-to-end (implement when full stack is up)"

fmt:
	@echo "→ Format (implement per-service)"
