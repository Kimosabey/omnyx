COMPOSE_FILE=infra/compose/docker-compose.yml
COMPOSE=docker compose -f $(COMPOSE_FILE)

.PHONY: deps build up down reset smoke lint test e2e fmt backup-pg export-openapi reseed seed-unicharm seed-dq-config seed-rules seed-twin-models seed-rl-agents seed-workflows support-bundle release-gate

deps:
	@echo "Install language-level dependencies per service (scaffold target)."

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v

smoke:
	powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1

lint:
	@echo "Lint scaffold target."

test:
	@echo "Unit test scaffold target."

e2e:
	@echo "End-to-end scaffold target."

fmt:
	@echo "Format scaffold target."

backup-pg:
	@echo "Backing up Postgres to backups/omnyx.sql"
	powershell -Command "New-Item -ItemType Directory -Force -Path backups | Out-Null"
	$(COMPOSE) exec postgres sh -lc "pg_dump -U $$POSTGRES_USER $$POSTGRES_DB" > backups/omnyx.sql

export-openapi:
	@echo "Export OpenAPI scaffold target."

reseed:
	@echo "Reseed scaffold target."

seed-unicharm:
	@echo "Seed Unicharm scaffold target."

seed-dq-config:
	@echo "Seed DQ config scaffold target."

seed-rules:
	@echo "Seed rules scaffold target."

seed-twin-models:
	@echo "Seed twin models scaffold target."

seed-rl-agents:
	@echo "Seed RL agents scaffold target."

seed-workflows:
	@echo "Seed workflows scaffold target."

support-bundle:
	powershell -ExecutionPolicy Bypass -File scripts/support-bundle.ps1

release-gate:
	powershell -ExecutionPolicy Bypass -File scripts/release-gate.ps1
