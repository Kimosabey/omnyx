# 26 · CI / CD

POC ships with reproducible builds + a smoke pipeline. Production-grade pipeline (multi-env, blue/green, canary) is documented but built in v2.

## 1 · Repo layout (already in place)

```
omnyx/
├── .github/workflows/        ← GitHub Actions (or .gitlab-ci.yml for GitLab; both committed)
├── services/<svc>/Dockerfile
├── services/<svc>/tests/
├── infra/compose/docker-compose.yml
├── infra/postgres/migrations/   ← alembic
├── shared/                    ← canonical models (Python + TS generation)
├── scripts/                   ← bring-up, smoke, fault-injection
└── Makefile                   ← every task is one make target
```

## 2 · Make targets (developer experience)

| Target | Action |
|---|---|
| `make deps` | Install all language-level deps for every service |
| `make build` | Build every Docker image |
| `make up` | `docker compose up -d` |
| `make down` | Stop without deleting volumes |
| `make reset` | Stop + delete volumes |
| `make seed-*` | Seed bundles (see [16_RUNBOOK §2](16_POC_RUNBOOK.md)) |
| `make smoke` | Run the smoke test set |
| `make fmt` | Format every language (prettier, ruff, gofumpt-like) |
| `make lint` | Lint every language (eslint, ruff, mypy) |
| `make test` | Unit tests for every service |
| `make e2e` | End-to-end test using simulator |
| `make ingest-knowledge` | RAG corpus refresh |
| `make backup-pg` | pg_dump → ./backups/ |

## 3 · CI pipeline (GitHub Actions example, mirrors GitLab)

```
.github/workflows/ci.yml
  on: [push, pull_request]
  jobs:
    lint:
      strategy: matrix [node, python]
      runs: checkout → setup → make lint
    test:
      strategy: matrix [node, python]
      runs: checkout → setup → make test  (per service)
    docker-build:
      strategy: matrix [services]
      runs: docker build with caching, scan with trivy, SBOM with syft
    integration:
      needs: [test, docker-build]
      services: postgres, kafka, redis (compose-up minimal)
      runs: make seed-* && make smoke
    e2e:
      needs: integration
      runs: make e2e (uses test simulator, 1 min real-stack run)
    publish:
      needs: [lint, test, docker-build, integration, e2e]
      if: main
      runs: docker push graylinx/omnyx-* tagged with git SHA + latest
```

## 4 · Image tags & versions

| Image | Tag pattern |
|---|---|
| `graylinx/omnyx-api-service` | `<git-sha>`, `<branch>-latest`, `v<semver>` on release |
| All other services | same |
| `graylinx/omnyx-frontend` | `<git-sha>` + Vite-bundled assets |

Production deploys pin to `v<semver>`, not `latest`. POC pins to `latest` for convenience.

## 5 · Migrations in CI

- Alembic migrations are applied automatically by the `migrate` container in compose (run-once dependency before api-service starts).
- CI runs `alembic upgrade head` against an ephemeral Postgres + a fresh `alembic downgrade -1; alembic upgrade head` to verify reversibility.

## 6 · Testing strategy

| Layer | Framework | What it covers |
|---|---|---|
| Unit | Python: pytest. Node: vitest. | Pure logic (DQ checks, twin physics, agent prompt builder) |
| Integration | docker-compose minimal | DAL → Kafka → DB → API path; rules engine; tool gateway |
| E2E | docker-compose full + simulator | Six-step demo runs end to end |
| Load (informational) | `stress_test_kafka.py` from gl_pbs | Pinned in [17_TEST §11](17_TEST_PLAN.md) |
| Contract | Schemathesis against api-service `/openapi.json` | Catch backward-incompat changes |
| LLM regression | Recorded fixtures (`agentic-ai/tests/fixtures/*.json`) replayed; deterministic mode | Validator + planner output structure |

## 7 · Release flow

POC: continuous deploy to dev environment on merge to main.
v2 production releases:

```
feature branch → PR → CI green → merge to main
   ↓ (auto)
deploy to staging
   ↓ (smoke + e2e)
manual promotion to prod
   ↓
blue / green: keep N-1 image running until /healthz is green on N for 5 min
   ↓
old replicas terminated
```

## 8 · Rollback

| Failure | Action |
|---|---|
| Migration broken | `alembic downgrade -1` is reversible; container restart |
| Service crash post-deploy | `docker compose rollout <svc> v<prev>` |
| Twin model bad | flip `app.twin_models.active=false`, twin-broker reloads in 60 s |
| RL agent misbehaving | `POST /rl/agents/{id}/pause` (Tier 4 protected) |
| Agentic workflow loop | flip `app.agent_workflows.active=false`; running runs cancel within 60 s |

## 9 · Documentation in CI

- Every PR that touches a route runs `redocly lint` against `openapi.yaml`.
- Every PR that adds/removes a Kafka topic must update [07_KAFKA §3](07_KAFKA_PIPELINE.md) — checked by a CODEOWNERS gate.
- Every PR that adds a column to a hypertable must update [08_STORAGE](08_STORAGE_TIMESCALEDB.md) / [08a](08a_DATABASE_DESIGN.md).

## 10 · Performance budget enforcement

A nightly job replays a recorded synthetic workload through the full stack and fails CI if:
- p95 dashboard latency > 2 s
- p95 telemetry-to-WS > 5 s
- Kafka lag end-of-run > 100 msgs
- DQ p95 inline duration > 50 ms

Numbers track the [01_SCOPE §4](01_SCOPE_AND_SUCCESS.md) success metrics directly.
