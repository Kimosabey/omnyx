# Hardware Suitability Evaluation — AIIMS Madurai Deployment

This document evaluates the suitability of the proposed onsite server workstation for the Graylinx AI Operations Intelligence Platform deployment at **AIIMS Madurai**.

---

## 1. Executive Summary

- **Target System**: Graylinx Platform (API, PostgreSQL with pgvector, Redis, and local Ollama inference)
- **Status**: 🔴 **FAIL (Incompatible in Default Configuration)**
- **Verdict**: The proposed PC lacks a dedicated GPU, has insufficient system RAM, uses a slow mechanical HDD, and has an underpowered power supply unit (PSU). However, the CPU is excellent, and the workstation can be made compatible by applying the hardware upgrades detailed in Section 4.

---

## 2. Proposed Hardware Specification

The proposed hardware specification is:
*   **Model**: HP Z2 Tower G9 Workstation (A2AQ7PT)
*   **Power Supply**: 500 W
*   **CPU**: Intel Core i7-14700 (5.40 GHz, 33MB cache, 20 Cores)
*   **System RAM**: 8 GB (1x8GB)
*   **Storage**: 1 TB 7200RPM SATA HDD
*   **Graphics (GPU)**: Integrated UMA (No dedicated graphics card)
*   **OS**: Linux-Ready

---

## 3. Gap Analysis

| Component | Proposed Specification | Graylinx Minimum Requirement | Graylinx Recommended Specification | Verdict | Impact Analysis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GPU / VRAM** | Integrated UMA (No GPU) | NVIDIA GPU ($\ge$ 12 GB VRAM) | NVIDIA GPU ($\ge$ 20 GB VRAM) | 🔴 **FAIL** | AI inference will fall back to CPU, slowing generation speeds to 1–2 tokens/sec. Streaming queries will time out. |
| **System RAM** | 8 GB | 16 GB | 32 GB to 64 GB | 🔴 **FAIL** | Out-Of-Memory (OOM) crash. The OS, Docker stack, and LLM model (~9 GB) cannot load together. |
| **Storage** | 1 TB 7200RPM SATA HDD | 512 GB SSD | 1 TB NVMe SSD | 🔴 **FAIL** | High database query latencies. Initial load times of AI model files from disk will take several minutes. |
| **Power Supply** | 500 W | 650 W | 750 W to 850 W | ⚠️ **RISK** | Underpowered. A 500W PSU cannot safely power both the Core i7-14700 and a high-performance NVIDIA GPU under full load. |
| **CPU** | Intel Core i7-14700 (20 Cores) | 8-Core CPU | 12 to 24-Core CPU | 🟢 **PASS** | Excellent processing power for standard API routes, anomaly scans, and database operations. |

---

## 4. Upgrade Action Plan

To deploy Graylinx on the proposed **HP Z2 Tower G9**, you must procure and install the following upgrade components:

### 1. Dedicated GPU Upgrade
- **Action**: Purchase and install a dedicated NVIDIA GPU with high VRAM.
- **Recommended Options**:
  - *Option A (Recommended)*: **NVIDIA RTX 4000 Ada SFF** (20 GB VRAM). Fits the power envelope best.
  - *Option B (Budget/Alternative)*: **NVIDIA RTX 4060 Ti (16GB version)**. Ensure it is the 16GB VRAM model, not the 8GB version.

### 2. RAM Expansion
- **Action**: Remove the existing 8 GB stick and install a dual-channel memory kit.
- **Recommended Option**: **32 GB DDR5 RAM Kit (2 x 16GB)** or **64 GB DDR5 RAM Kit (2 x 32GB)**.
  - *Kafka Future Planning Note*: Because Apache Kafka is planned for future phases, upgrading to **64 GB RAM** is highly recommended (instead of 32 GB) to prevent JVM and database memory swapping issues.

### 3. High-Speed Storage Addition
- **Action**: Install an NVMe SSD as the primary boot drive. Keep the 1 TB HDD as a secondary drive for system backups and database dumps.
- **Recommended Option**: **1 TB NVMe M.2 SSD** (e.g., Samsung 990 Pro or Crucial T500).

### 4. Power Supply Unit Upgrade
- **Action**: Upgrade the internal power supply if choosing a standard high-power GPU.
- **Recommended Option**: **700W+ PSU** compatible with the HP proprietary motherboard layout, or choose a low-power GPU like the *RTX 4000 Ada SFF* which runs on 70W and can run on the stock 500W PSU.

---

## 5. Alternative: Ready-to-Deploy Pre-Builts

If you wish to avoid manual hardware upgrades, purchase a workstation pre-configured for local AI. Below is an alternative configuration example:

- **Workstation**: Dell Precision 3660 / 5860 Tower or HP Z2 G9 with upgraded options.
- **Spec Checklist**:
  - Intel Core i7 or i9 (13th/14th Gen)
  - 32 GB or 64 GB DDR5 RAM
  - 1 TB NVMe SSD
  - NVIDIA RTX 4000 Ada (20GB VRAM) or RTX 4080 (16GB VRAM)
  - 750W or 1000W Power Supply Unit

For general deployment setup, refer back to the [ON_PREMISE_DEPLOYMENT_GUIDE.md](file:///d:/Harshan/HVAC%20AI%20Operations%20Intelligence%20Platform/docs/operations/ON_PREMISE_DEPLOYMENT_GUIDE.md).
