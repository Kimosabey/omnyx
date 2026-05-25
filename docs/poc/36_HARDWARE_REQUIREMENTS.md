# 36 · Hardware Requirements (Authoritative — for Management / Sales / Procurement)

**Use this doc to negotiate hardware spec with site teams, management, and sales.** It is the spec OMNYX needs to run as the end-product on a customer's premises.

> **Default deployment shape: one big PC at the customer's site, on the customer's network, running the entire OMNYX stack.** That's the POC, and that's the production beta. Two-machine and Kubernetes topologies exist as documented options for large customers, but the standard sale is "one box, one customer, on-prem".
>
> Graylinx's internal server and the developer laptop are **dev-only**. They never serve a customer.

---

## 1 · The hardware we (Graylinx) have — internal use only

### 1.1 Graylinx internal server — *dev bench, not a customer service*

```
Model       : Dell Pro Max Tower T2 (FCT2250)
CPU         : Intel Core Ultra 9 285K  · 24 cores · 3.7 GHz
RAM         : 32 GB
GPU         : NVIDIA RTX 4000 Ada Generation · 20 GB VRAM
OS          : Windows 11 Pro 64-bit
Ollama installed : qwen2.5:14b · llama3.3 · mistral-small · nomic-embed-text ·
                   gpt-oss:120b · nemotron-cascade-2 · llama3.2 · llama3.2-vision · phi
```

**Purpose**: Internal dev bench. The team builds OMNYX images here, tests new LLMs, and uses it as a reference machine. **It does not host customer workloads. Customer sites do not call into it.**

### 1.2 Dev laptop — *POC bring-up, not a customer service*

```
Model       : HP Laptop 14-ep1xxx
CPU         : Intel Core Ultra 7 155H · 22 cores · 3.8 GHz
RAM         : 24 GB
GPU         : Intel integrated only
OS          : Windows 11 Home
```

**Purpose**: Runs the full POC (all 18 containers + gl_pbs simulator). Demo machine for leadership.

---

## 2 · Customer-site deployment model — one big PC

**The customer's site runs everything on one big PC.** That single box is the entire OMNYX install for that customer.

```
                ╔═══════════════════════════════════════════════════╗
                ║       Customer's single OMNYX server               ║
                ║                                                     ║
                ║   • Kafka  • Postgres+TimescaleDB  • Redis          ║
                ║   • Keycloak  • Prometheus+Grafana+Loki             ║
                ║   • dal-bacnet  • db-writer  • ws-bridge            ║
                ║   • api-service  • twin-broker  • rl-broker         ║
                ║   • dq-etl  • agentic-ai  • frontend                ║
                ║                                                     ║
                ║   (Optional) Ollama on local GPU for air-gap        ║
                ╚═══════════════════════════════════════════════════╝
                  │                                              │
                  │ BACnet/IP UDP                                │ HTTPS / WS
                  ▼                                              ▼
              site DDCs                                operator browsers / tablets
                                              (same LAN, no internet exposure)

Outbound (only if Topology C): api.anthropic.com   ← only egress
```

The 18 OMNYX containers fit on one host. Proven on the dev laptop today. The customer's box is sized to comfortably host all of them with headroom.

Two-machine or k8s topologies are **available** for large customers ([§7](#7--scale-tier-only-when-the-customer-actually-needs-it)) but are **not** the default sale.

---

## 3 · LLM placement — only two valid choices for a customer site

| Topology | LLM hosting | GPU needed on the site PC? | Internet at site? | Use when |
|---|---|---|---|---|
| **A** — On-site Ollama | runs on the **customer's** GPU on the same PC | **Yes** (≥ 16 GB VRAM, RTX 4000 Ada SFF class) | not required (air-gap) | Customer mandates air-gap |
| **C** — Claude API | Anthropic (cloud) | **No** | Yes (outbound only, allowlist `api.anthropic.com`) | Customer allows internet egress |

> There is **no** option where the customer's site talks to a Graylinx-hosted LLM. Graylinx is not in the data path. Ever.

POC and beta default: **Topology C**. Switch to A only when the customer's compliance team requires it.

---

## 4 · The single-box hardware spec (one big PC)

The whole stack must fit on one machine. These are the numbers you take to procurement.

### 4.1 With Topology C (Claude API) — **the standard sale**

| Component | **Minimum** (will run, smaller sites) | **Recommended** (every new site) | **Heavy** (large site, 500+ points) |
|---|---|---|---|
| **CPU** | 8 cores · Intel i7 14-gen / Ryzen 7 7700 | **12+ cores · i7-14700 / Ryzen 9** | 16+ cores · i9 / Xeon W |
| **RAM** | 32 GB DDR5 | **64 GB DDR5** | 128 GB DDR5 ECC |
| **Storage (boot + OMNYX)** | 1 TB NVMe SSD | **1 TB NVMe SSD (Gen 4)** | 2 TB NVMe Gen 4 RAID-1 |
| **Storage (cold archive, optional)** | none | 2 TB SATA HDD | 4–8 TB HDD RAID |
| **GPU** | none | **none** | none |
| **PSU** | 500 W 80+ Bronze | **650 W 80+ Gold** | 850 W 80+ Gold |
| **Network** | 1 Gbps Ethernet | 1 Gbps + Wi-Fi backup | 2.5 / 10 Gbps |
| **OS** | Ubuntu 22.04 LTS (recommended) or Windows Server 2022 | same | same |
| **Internet** | 5 Mbps sustained outbound | **25 Mbps** | 100 Mbps |
| **UPS** | 600 VA (15 min runtime) | 1500 VA (30 min) | 3000 VA + generator interface |

**Reference platforms** (any of these meet "Recommended"):
- HP Z2 Tower G9 with i7-14700 + 64 GB RAM + 1 TB NVMe (no GPU). ~₹1.5–1.8 lakh.
- Dell Precision 3680 Tower with i7-14700 + 64 GB RAM + 1 TB NVMe. ~₹1.6–2 lakh.
- Lenovo ThinkStation P3 Tower equivalent.

### 4.2 With Topology A (on-site Ollama for air-gap) — **add GPU + RAM**

Same base spec as 4.1 PLUS:

| Add-on | **Minimum** | **Recommended** |
|---|---|---|
| **GPU** | NVIDIA RTX 4000 Ada SFF · 20 GB VRAM · 70 W (fits 500 W PSU) | NVIDIA RTX 6000 Ada · 48 GB · 300 W |
| **Extra RAM** | + 16 GB (for model load / KV cache offload) | + 32 GB |
| **Extra disk** | + 200 GB NVMe (for model files; qwen2.5:14b alone is 9 GB) | + 500 GB |
| **PSU upgrade** | none if RTX 4000 Ada SFF (70 W) | 850 W if RTX 6000 Ada |
| **Local LLM model** | `qwen2.5:14b` (9 GB, ~50 tok/s on RTX 4000 Ada) | `mistral-small` or `qwen2.5:14b` |

**Reference Topology-A platform:**
- HP Z2 Tower G9 i7-14700 + 64 GB RAM + 1 TB NVMe + **RTX 4000 Ada SFF 20 GB**. ~₹3.7–4 lakh.

---

## 5 · Why these numbers — the budget breakdown

Justifies "Recommended" so procurement understands what each line buys.

| Container / function | Steady RAM | Why it needs what it needs |
|---|---|---|
| Kafka (KRaft, JVM) | 1.5–2 GB | Heap + page-cache; we set `-Xmx2G`. Already proven (1 % CPU at 2 msg/s in [`KAFKA_VERDICT`](../../../../simulations/gl_pbs/docs/planning/KAFKA_VERDICT_AND_REQUIREMENTS.md)). |
| PostgreSQL + TimescaleDB | 2–4 GB | `shared_buffers=2GB`, `work_mem=64MB×conns`, plus continuous-aggregate refresh bursts |
| Redis | 150 MB | BullMQ queues + cache |
| Keycloak | 600 MB | Standard JVM heap |
| api-service (Node) | 300 MB | Fastify + Prisma + Kafka client |
| ws-bridge | 150 MB | one connection per logged-in operator |
| db-writer | 200 MB | Kafka consumer + batched DB insert |
| twin-broker (Python) | 400 MB | physics models in numpy |
| rl-broker (Python) | 300 MB | shadow-mode policy in memory |
| agentic-ai (Node) | 250 MB | SDK + token state |
| dal-bacnet (Python) | 200 MB | bacpypes + DQ Tier 1 |
| dq-etl (idle) | 150 MB → 1.5 GB during nightly | jobs use pandas/numpy briefly |
| Prometheus + Grafana + Loki + Promtail | 1 GB | scrapes + dashboards + log ingest |
| OS + Docker daemon | 1.5–2 GB | Linux kernel + container runtime |
| **STEADY TOTAL** | **~9 GB** | — |
| ETL / continuous-aggregate burst | + 4–6 GB | hourly / daily peaks |
| Spare for the OS page cache (DB perf) | want 6+ GB free | NVMe still cached cleanly |
| **MINIMUM RAM** | **32 GB** | (16 GB technically boots but no headroom; 32 GB is the actual floor for a production site) |
| **RECOMMENDED RAM** | **64 GB** | gives the OS its page-cache slack; supports continuous-aggregate refresh without swap |

CPU: the rules engine, Tier-1 DQ, and twin step are the hot loops. 8 cores is the floor; 12 cores is comfortable; 16 cores covers analytics workloads.

NVMe is non-negotiable because Postgres + Kafka are I/O bound. A spinning HDD will bottleneck even small workloads — verified pain point from AIIMS Madurai's 7200 RPM disk.

---

## 6 · Existing-site re-evaluation

For management / sales: this is what each existing site needs to do to be ready for OMNYX.

### 6.1 AIIMS Madurai — HP Z2 Tower G9 i7-14700 / 8 GB / 1 TB HDD / no GPU / 500 W

**The good news**: the chassis and CPU are excellent (i7-14700 is the same chip in our "Recommended" spec). Only RAM + disk are weak.

#### If customer allows internet (Topology C — most likely)
| Component | Current | Need | Action | Approx cost |
|---|---|---|---|---|
| CPU | i7-14700 (20 cores) | 8+ cores | ✅ keep | — |
| RAM | 8 GB | 32–64 GB | 🔧 add 2×32 GB DDR5 | ₹10–14 k |
| Disk | 1 TB HDD | 1 TB NVMe | 🔧 add 1 TB NVMe M.2; keep HDD for backups | ₹6–8 k |
| GPU | none | none | ✅ keep | — |
| PSU | 500 W | 500 W | ✅ keep | — |
| **TOTAL** | | | | **~₹16–22 k per site** |

#### If air-gap required (Topology A)
| Add to above | Spec | Approx cost |
|---|---|---|
| GPU | NVIDIA RTX 4000 Ada SFF 20 GB · 70 W | ₹2.2–2.5 lakh |
| (RAM bump from 32 to 64 GB) | | included above |
| Extra NVMe for models | 200 GB | already covered by 1 TB NVMe |
| PSU | stays at 500 W (Ada SFF needs only 70 W) | — |
| **TOTAL (incl. base upgrade)** | | **~₹2.4–2.7 lakh per site** |

### 6.2 Varanasi Airport — i5 / 8 GB / 512 GB unknown / no GPU

The i5 (gen unknown) is the question mark.

#### If i5 ≥ 12-gen, ≥ 6 cores, has free DDR4/5 slots and M.2

| Component | Action | Approx cost |
|---|---|---|
| RAM upgrade to 32 GB | 🔧 | ₹8–12 k |
| NVMe SSD if existing is HDD | 🔧 | ₹4–6 k |
| GPU | not needed (Topology C) | — |
| **TOTAL** | | **~₹12–18 k** |

#### Otherwise — replace the box
Procure a Tier "Recommended" PC at **~₹1.5–1.8 lakh** (i7-14700 / 64 GB / 1 TB NVMe / no GPU).

### 6.3 Unicharm Chennai

THERMYNX continues on existing hardware through M1–M3 cutover (see [`../migration/UNICHARM_TO_OMNYX.md`](../migration/UNICHARM_TO_OMNYX.md)). Likely the existing server already meets or beats Topology C "Recommended". Verify during M2 phase. Most plausibly **no new hardware purchase needed**.

---

## 7 · Scale tier — only when the customer actually needs it

Most customer sites are **one big PC**, full stop. The exceptions:

| Customer profile | Layout | Hardware |
|---|---|---|
| Single site, ≤ 500 points | **One big PC** (Tier "Recommended") | ₹1.5–2 lakh (no GPU) / ₹3.5–4 lakh (with GPU) |
| Single site, ≥ 500 points or strict latency | One big PC, sized "Heavy" | ₹3–4 lakh |
| Multi-building campus under one customer | One central server + lightweight `dal-bacnet` boxes at each building | central ₹3–4 lakh + ₹40–60 k per BACnet edge |
| Multi-site enterprise with HA mandate | k8s on customer's existing cluster | software-only sale |

Do not propose two-host or k8s unless the customer asks. The single-host story is the default and sells faster.

---

## 8 · Internet bandwidth (Topology C)

| Activity | Approx bandwidth |
|---|---|
| Agent workflow (Planner / Executor / Validator) | 20–500 KB per workflow |
| Daily Operations Report generation | 100–300 KB |
| Continuous twin/RL/agent steady state | < 50 kbps |
| Bursts during incident response | up to 2 Mbps for a few seconds |

A **5 Mbps** outbound link comfortably runs hundreds of agent workflows per day. **25 Mbps** is generous for any plausible single-site workload.

---

## 9 · UPS, power, cooling

| Spec | Min | Rec |
|---|---|---|
| UPS | 600 VA, 15 min runtime | 1500 VA, 30 min |
| Power draw of the PC (Topology C, idle → load) | 80 → 250 W | 100 → 300 W |
| Power draw of the PC (Topology A, idle → load) | 150 → 350 W | 180 → 400 W |
| Cooling | normal office aircon | dedicated server-room aircon for Topology A |
| Rack | tower fine; or 4U rack-mount (Dell PowerEdge T550 class) | as customer requires |

---

## 10 · One-page procurement card (for management)

> **OMNYX site PC — recommended order:**
>
> - **Make**: HP Z2 Tower G9 / Dell Precision 3680 Tower / Lenovo ThinkStation P3
> - **CPU**: Intel Core i7-14700 (20 cores) or equivalent
> - **RAM**: **64 GB** DDR5
> - **Storage**: **1 TB NVMe Gen 4 SSD** (primary) + optional 2 TB HDD (backups)
> - **GPU**: **None** (skip — LLM is via Claude API). Only add NVIDIA RTX 4000 Ada SFF 20 GB **if** the site requires air-gap.
> - **PSU**: 650 W 80+ Gold
> - **OS**: Ubuntu 22.04 LTS
> - **Network**: 1 Gbps wired + 25 Mbps internet (if Topology C)
> - **UPS**: 1500 VA, 30 min runtime
>
> **Approx ex-tax price (India, 2026)**: ₹1.5–2.0 lakh per site (Topology C) · ₹3.5–4.0 lakh per site (Topology A with GPU).

---

## 11 · The negotiating points (for management discussion)

When the conversation goes "we already have an i5 office PC — can we use that?", these are the lines:

1. **8 GB RAM is a non-starter.** Even with the most lightweight stack, OMNYX needs **32 GB minimum, 64 GB for production**. RAM is cheap; this is the first ask.
2. **HDD is a non-starter.** OMNYX must run on NVMe. SATA SSD will work but NVMe is half the price and twice the speed. Always specify NVMe Gen 4.
3. **No GPU is fine** if the customer allows outbound to Anthropic. Most do. Pre-clear this with their security team — saves ₹2.5 lakh per site.
4. **PSU is fine at stock** unless adding a GPU. The RTX 4000 Ada SFF is the only sensible GPU for our use case and it runs at 70 W (no PSU upgrade).
5. **CPU is rarely the blocker.** Most office i5s 12-gen+ are fine for Tier 1 (small sites). Modern i7s are great for everything.
6. **OS preference: Ubuntu LTS** for Docker reliability + better Postgres / Kafka performance vs Windows. Windows works but loses ~10 % throughput.
7. **One PC = one customer = one install.** Sales should never propose a shared OMNYX server across customers.

---

## 12 · Summary by deployment type

| Deployment | Min hardware | Recommended hardware | Approx cost |
|---|---|---|---|
| **POC (Graylinx internal)** | 16 GB / 8 cores / 256 NVMe | Dev laptop (Ultra 7 / 24 GB) | already owned |
| **Customer site, Topology C (default)** | 32 GB / 8 cores / 1 TB NVMe / no GPU | 64 GB / i7-14700 / 1 TB NVMe / no GPU / 650 W | ₹1.5–2 lakh |
| **Customer site, Topology A (air-gap)** | 48 GB / 8 cores / 1 TB NVMe / RTX 4000 Ada SFF | 64 GB / i7-14700 / 1 TB NVMe / RTX 4000 Ada SFF | ₹3.5–4 lakh |
| **Multi-building campus, central server** | 64 GB / 12 cores / 1 TB NVMe | 128 GB / 16 cores / 2 TB NVMe | ₹3–4 lakh + edges |
| **Existing AIIMS Madurai (upgrade)** | RAM + NVMe | (Topology C) ₹16–22 k upgrade | very cheap |
| **Existing Varanasi (upgrade or new)** | depends on i5 | ₹12–18 k upgrade or new ₹1.5 lakh box | depends |

---

## 13 · References in this repo

- [`37_DEPLOYMENT_MODEL.md`](37_DEPLOYMENT_MODEL.md) — why one customer = one install = one big PC
- [`15_DEPLOYMENT_ONPREMISE.md`](15_DEPLOYMENT_ONPREMISE.md) — compose stack details for the one-PC default
- [`31_OPENSOURCE_LICENSING.md`](31_OPENSOURCE_LICENSING.md) — every dependency is OSS; air-gap deployment posture
- [`23_SECURITY.md`](23_SECURITY.md) — what the network egress allowlist looks like
- Legacy hardware audits: [`HARDWARE_EVALUATION_AIIMS_MADURAI.md`](../site-evaluations/HARDWARE_EVALUATION_AIIMS_MADURAI.md), [`HARDWARE_EVALUATION_VARANASI_AIRPORT.md`](../site-evaluations/HARDWARE_EVALUATION_VARANASI_AIRPORT.md)
