# Hardware Suitability Evaluation — Varanasi Airport Deployment

This document evaluates the suitability of the proposed onsite server workstation for the Graylinx AI Operations Intelligence Platform deployment at **Varanasi Airport**.

---

## 1. Executive Summary

- **Target System**: Graylinx Platform (API, PostgreSQL with pgvector, Redis, and local Ollama inference)
- **Status**: 🔴 **FAIL (Incompatible in Default Configuration)**
- **Verdict**: The proposed PC is a standard office desktop configuration and is not suitable for hosting database systems alongside local AI models. It completely lacks a dedicated NVIDIA GPU, has critically low RAM (8 GB), and uses a low-tier CPU (Intel i5). Major upgrades are required to make it compatible, or a dedicated AI workstation should be procured instead.

---

## 2. Proposed Hardware Specification

The proposed hardware specification is:
*   **CPU**: Intel Core i5 (Generation/core count not specified)
*   **System RAM**: 8 GB
*   **Storage**: 512 GB (SSD/HDD type not specified)
*   **Graphics (GPU)**: Integrated UMA (No dedicated graphics card)

---

## 3. Gap Analysis

| Component | Proposed Specification | Graylinx Minimum Requirement | Graylinx Recommended Specification | Verdict | Impact Analysis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GPU / VRAM** | Integrated UMA (No GPU) | NVIDIA GPU ($\ge$ 12 GB VRAM) | NVIDIA GPU ($\ge$ 20 GB VRAM) | 🔴 **FAIL** | Local AI models cannot run on the GPU. CPU inference will take several minutes per response, causing system timeouts. |
| **System RAM** | 8 GB | 16 GB | 32 GB to 64 GB | 🔴 **FAIL** | Critical Out-of-Memory (OOM) risk. Docker services and the 9 GB Qwen model will crash the system on startup. |
| **Processor (CPU)** | Intel Core i5 | 8-Core CPU (recent gen i7/Ryzen 7) | 12 to 24-Core CPU | ⚠️ **RISK** | Older Core i5 CPUs (with 4 to 6 cores) will bottleneck when running the telemetry aggregation API and background workers. |
| **Storage** | 512 GB | 512 GB SSD | 1 TB NVMe SSD | ⚠️ **WARNING** | Sufficient size for database startup, but **must be an SSD**. If it is a mechanical HDD, database reads/writes will bottleneck the platform. |

---

## 4. Upgrade Action Plan

To deploy Graylinx on the proposed **Varanasi Airport** desktop PC, you must execute the following upgrades:

### 1. Graphics Card (GPU) Addition
- **Action**: Install a dedicated NVIDIA GPU.
- **Recommended Option**: 
  - **NVIDIA RTX 4060 Ti (16GB)** or **RTX 4070 (12GB/16GB)**.
  - *Note*: Ensure the PC's power supply unit (PSU) and physical motherboard layout can accommodate a dedicated graphics card. Most standard i5 office PCs ship with low-profile cases and weak 200W-300W power supplies, which cannot support dedicated GPUs.

### 2. RAM Expansion
- **Action**: Upgrade system memory to prevent out-of-memory crashes.
- **Recommended Option**: Add RAM to reach at least **32 GB DDR4/DDR5 RAM** (remove the existing 8GB stick and install a 2x16GB kit).
  - *Kafka Future Planning Note*: Since Apache Kafka is planned for future phases, upgrading to **64 GB RAM** is strongly recommended to handle Kafka brokers and JVM heap allocations alongside databases and Ollama.

### 3. Storage Verification
- **Action**: Verify that the 512 GB drive is an SSD (preferably NVMe M.2). If it is a mechanical SATA HDD, replace it with a **512 GB or 1 TB NVMe SSD**.

---

## 5. Recommended Alternative Workstation

Given the typical limitations of standard Intel i5 office desktops (low-power power supplies, small form-factor cases), it is often cheaper and safer to purchase a dedicated server/workstation rather than attempting to upgrade this PC. 

**Procurement Spec Checklist**:
- **CPU**: Intel Core i7-13700 / i7-14700 or AMD Ryzen 7 7700
- **RAM**: 32 GB DDR5
- **Storage**: 1 TB NVMe SSD
- **GPU**: NVIDIA RTX 4060 Ti 16GB or NVIDIA RTX 4000 Ada (20GB VRAM)
- **Power Supply**: 650W or higher

For general deployment setup, refer back to the [ON_PREMISE_DEPLOYMENT_GUIDE.md](file:///d:/Harshan/HVAC%20AI%20Operations%20Intelligence%20Platform/docs/operations/ON_PREMISE_DEPLOYMENT_GUIDE.md).
