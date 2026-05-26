# 31 · Open Source & On-Premise

**Verdict: 100 % of the OMNYX runtime is open-source and can run on customer hardware with zero external dependency.** The only optional cloud call is the Anthropic Claude API, and an **Ollama fallback ships from day one** so you can switch to fully air-gapped operation with one environment-variable change.

## 1 · Every component with its license

### 1.1 Infrastructure

| Component | Version | License | Open? | On-prem? |
|---|---|---|---|---|
| PostgreSQL | 16 | PostgreSQL License (MIT-equivalent) | ✅ | ✅ |
| TimescaleDB Community | 2.14 | Apache 2.0 + Timescale License (TSL) — features we use are Apache | ✅ | ✅ |
| pgvector | 0.6 | PostgreSQL License | ✅ | ✅ |
| Apache Kafka | 7.6.1 via Confluent Community Image | Apache 2.0 (CP Community image: Confluent Community License) | ✅ | ✅ |
| Redis | 7.2 | BSD-3-Clause (versions ≤ 7.2 — we pin 7.2 deliberately) | ✅ | ✅ |
| Keycloak | 24 | Apache 2.0 | ✅ | ✅ |
| Prometheus | 2.51 | Apache 2.0 | ✅ | ✅ |
| Grafana | 10.4 OSS edition | AGPL-3.0 | ✅ | ✅ |
| Loki | 2.9 | AGPL-3.0 | ✅ | ✅ |
| Grafana Alloy | latest | Apache 2.0 | ✅ | ✅ | replaces EOL Promtail (March 2026) |
| MinIO | RELEASE.2024-* | AGPL-3.0 (community) | ✅ | ✅ |
| Kafka UI (provectus) | latest | Apache 2.0 | ✅ | ✅ |
| Docker / Docker Compose | 24 / v2 | Apache 2.0 | ✅ | ✅ |
| Kubernetes (v3 path) | 1.30 | Apache 2.0 | ✅ | ✅ |
| Strimzi (Kafka operator, v3) | latest | Apache 2.0 | ✅ | ✅ |
| CloudNativePG (Postgres operator, v3) | latest | Apache 2.0 | ✅ | ✅ |
| Traefik / nginx | latest | MIT / BSD-2-Clause | ✅ | ✅ |
| cert-manager | latest | Apache 2.0 | ✅ | ✅ |
| Vault (External Secrets, v3) | OSS | MPL-2.0 | ✅ | ✅ |

> **Pinning Redis at 7.2** is deliberate — Redis 7.4+ uses RSALv2/SSPLv1 which is not OSS by OSI definition. 7.2 (BSD-3-Clause) gives us a reproducible Redis-API-compatible base. Drop-in alternative: **Valkey** (Linux Foundation fork, BSD-3-Clause) — already validated.

### 1.2 Languages & runtimes

| Component | License | Notes |
|---|---|---|
| Python 3.12 | PSF License (BSD-compat) | ✅ |
| Node.js 20 LTS | MIT | ✅ |
| TypeScript 5 | Apache 2.0 | ✅ |
| Vite 5 | MIT | ✅ |

### 1.3 Backend libraries (api-service, ws-bridge, db-writer, agentic-ai)

| Library | License |
|---|---|
| Fastify 4 | MIT |
| `@fastify/jwt`, `@fastify/cors`, `@fastify/rate-limit`, `@fastify/swagger`, `@fastify/websocket` | MIT |
| Zod | MIT |
| Prisma | Apache 2.0 |
| `kafkajs` | MIT |
| `ioredis` | MIT |
| `bullmq` | MIT |
| `pino`, `pino-pretty` | MIT |
| `prom-client` | Apache 2.0 |
| `@anthropic-ai/sdk` | MIT |

### 1.4 Edge & Python services (dal-bacnet, dal-replay, dq-etl, twin-broker, rl-broker)

| Library | License |
|---|---|
| `bacpypes` | MIT |
| `confluent-kafka` (Python) | Apache 2.0 |
| `aiokafka` | Apache 2.0 |
| `pydantic` 2 | MIT |
| `pandas` | BSD-3-Clause |
| `numpy` | BSD-3-Clause |
| `scipy` | BSD-3-Clause |
| `scikit-learn` | BSD-3-Clause |
| `stable-baselines3` (optional v2 RL) | MIT |
| `psycopg[binary]`, `asyncpg` | LGPL / Apache 2.0 |
| `APScheduler` | MIT |
| `prometheus-client` | Apache 2.0 |
| `httpx` | BSD-3-Clause |
| `structlog` | MIT / Apache 2.0 |

### 1.5 Frontend (React SPA)

| Library | License |
|---|---|
| React 18 / React-DOM | MIT |
| `react-router-dom` 6 | MIT |
| Chakra UI 2 | MIT |
| `@emotion/*` | MIT |
| Framer Motion | MIT |
| `lucide-react` | ISC |
| Recharts | MIT |
| TanStack Query | MIT |
| `react-markdown`, `remark-gfm` | MIT |
| Vitest, `@testing-library/react` | MIT |

### 1.6 The one exception — and the fallback

| Component | License | Required for OMNYX? |
|---|---|---|
| **Anthropic Claude API** | Proprietary (cloud service) | **Optional**. Default in POC because of model quality + tool-use reliability. |
| **Ollama** + `qwen2.5:14b` | Ollama MIT, Qwen 2.5 Apache 2.0 | **Open + on-prem**. Set `LLM_BACKEND=ollama` and OMNYX never calls out. |

Switch is one env-var:

```bash
# infra/compose/.env
LLM_BACKEND=ollama
OLLAMA_URL=http://<your-ollama-host>:11434
```

`agentic-ai` reads this on startup. All three roles (Planner/Executor/Validator) switch in lockstep. We already validated this path in the THERMYNX stack — `qwen2.5:14b` on a single RTX 4000 Ada (20 GB VRAM) handles the workload.

## 2 · No telemetry, no phone-home

| Service | Outbound call when LLM_BACKEND=ollama |
|---|---|
| dal-bacnet | none |
| db-writer | none |
| api-service | none |
| ws-bridge | none |
| twin-broker | none |
| rl-broker | none |
| agentic-ai | only your Ollama host |
| dq-etl | none |
| frontend | only your origin |
| Keycloak | none |
| Prometheus / Grafana / Loki | none |

Verified by the egress allowlist in [`23_SECURITY §5`](23_SECURITY.md). The compose stack runs unplugged from the internet — only the LLM API needs network, and only when you choose Claude.

## 3 · No "phone home for license"

- No commercial license server.
- No usage-metering call-back.
- No watermark on data.
- Customer's data, customer's hardware, customer's network.

## 4 · OMNYX itself

OMNYX source code (this repo) is **Graylinx proprietary** — sold as a commercial product. That's the only thing in the stack that isn't OSS. But because every dependency is OSS + on-prem, customers can audit the full software bill of materials and host everything in their data centre.

If a customer requires a 100 %-OSS reference architecture, every dependency above is documented; the only commercial component is the OMNYX application source itself.

## 5 · Air-gap deployment

| Requirement | Provided by OMNYX |
|---|---|
| No internet during install | Use a local container registry; mirror images once, then disconnect |
| No internet during runtime | `LLM_BACKEND=ollama` |
| Local certificate authority | Traefik/nginx works with any CA; documented |
| Local DNS | All inter-service uses Docker DNS / k8s DNS |
| Local time | NTP optional; documented for synchronised audit |
| Local package mirror | All Python/Node deps pre-bundled in images |

The whole stack has been validated to come up with `docker compose up -d` while disconnected from the internet, provided images are pulled to the host registry first.

## 6 · Sovereign-data posture

| Concern | Posture |
|---|---|
| Customer data leaves the network | Never (with Ollama) |
| Telemetry stored | Customer's Postgres on customer hardware |
| Model training data | Customer-only, optional federated learning is v3 |
| LLM prompts (when Claude is used) | Anthropic data-use policy applies; documented in `infra/operations/LLM_DATA_POLICY.md` per-customer |
| Backups | Customer-controlled MinIO; customer-supplied encryption key |

## 7 · Summary

> Every infrastructure component is open-source. Every application library is open-source. The only network call OMNYX makes by default is to the Claude API, and that one call can be redirected to a local Ollama with one env var. On-prem, air-gappable, sovereign by design.
