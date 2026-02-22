Project for the "**Advanced Computer Networking**" class (2025-26) at Pisa University.<br>
Group work carried out by the students: [Luca Arduini](https://github.com/LucaArduini), [Valerio Triolo](https://github.com/valeriot30).

# 📡 BGP Network Automation & Traffic Engineering

<p align="center">
  <img src="topology/topology.png" alt="Network Topology Diagram" width="800" />
</p>

This repository hosts the final project for the **Advanced Computer Networking** course (2025-2026) at the **University of Pisa**.

The project implements a **fully automated pipeline** for the design, emulation, and dynamic optimization of a Transit Autonomous System (AS65020). It leverages **Containerlab**, **FRRouting (FRR)**, and **Python** to manage configuration lifecycles and perform closed-loop Traffic Engineering (TE) based on mathematical optimization.

---

## 🚀 Project Overview

The goal is to automate the operations of a simplified Service Provider network. The system moves beyond static configurations, introducing a **Manager Node** that acts as an intelligent control plane.

### Key Features
*   **Single Source of Truth:** The entire topology, IP addressing, and relationships are defined in a generic `data.yaml` file.
*   **Automated Configuration:** Jinja2 templates generate valid FRR configurations (`.conf`) for all routers (PEs, CEs, GWs) automatically.
*   **Network Emulation:** One-click deployment using **Containerlab**, simulating a realistic multi-AS environment with Linux Bridges and Docker containers.
*   **Dynamic Traffic Engineering (TE):** A Python-based automation loop that:
    1.  Generates/Ingests traffic matrices.
    2.  Solves **Mixed-Integer Linear Programming (MILP)** models to optimize load balancing.
    3.  Injects BGP policies (**MED** and **Local Preference**) into running routers via `docker exec`.

---

## 🏗️ Network Architecture

The emulated network represents **AS65020**, a transit provider connecting Customers to the Internet.

*   **Core (AS65020):**
    *   **2 Provider Edges (PE1, PE2):** Entry points for customer traffic.
    *   **2 Gateways (GW1, GW2):** Exit points towards Upstream providers.
    *   **Manager Node:** A specialized Alpine container running the Python optimization logic.
*   **Customers:** 2 Customer ASes (CE1, CE2).
*   **Upstreams:** 2 Upstream Providers connecting to the Internet.

---

## 🧠 Traffic Engineering Logic

The core of this project is the `manager.py` script, which performs two sequential optimization stages using `scipy`:

### 1. Ingress Optimization (PE Selection)
*   **Goal:** Balance the load between PE1 and PE2 to prevent entry bottlenecks.
*   **Algorithm:** MILP model minimizing the load difference between PEs.
*   **Actuation:** Manipulates **BGP MED**.
    *   *Selected PE:* MED 100
    *   *Backup PE:* MED 200

### 2. Egress Optimization (Gateway Selection)
*   **Goal:** Optimize the saturation of upstream links (GW to Upstream), respecting different link capacities.
*   **Algorithm:** Minimax Saturation model (MILP).
*   **Actuation:** Manipulates **BGP Local Preference**.
    *   *Selected GW:* Local Preference 200 (Highest wins in iBGP)
    *   *Backup GW:* Local Preference 100

---

## 📂 Project Structure

```text
├── automation/            # Core Python logic (Manager)
│   ├── manager.py         # Main orchestration script
│   ├── build_config.py    # Config generation logic
│   ├── build_topology.py  # Containerlab file generation
│   ├── generate_traffic.py# Synthetic traffic matrix generator
│   └── ...
├── templates/             # Jinja2 templates (frr.conf, topology)
├── tests/                 # Validation scripts (pings, traceroute, te)
├── bootstrap.sh           # VM setup script
├── teardown.sh            # VM cleanup script
├── orchestrator.py        # Deployment pipeline (Local -> VM)
├── install.py             # Dependency installer
└── data.yaml              # Topology Source of Truth
```

---

## 🛠️ Installation & Usage

This project is executed through a set of automated **pipelines**, split between:

- **Host machine (your laptop/PC)**: generates artifacts and deploys them to the VM.
- **Target machine (Linux VM)**: runs Docker + Containerlab and hosts the emulated network.

### 1. Prerequisites

**Host machine**
- **Python** 3.x

**Target VM**
- **Docker**
- **Containerlab**

### 2. Host Machine Setup (Dependencies)

Install local Python dependencies required by the orchestration scripts:

```bash
python3 install.py
```

### 3. Deploy to the VM (Orchestration Pipeline)

From the **host machine**, run:

```bash
python3 orchestrator.py
```

This pipeline performs:

1. **Artifact generation**
   - Generates the Containerlab topology file (e.g., `topology/network.clab.yml`)
   - Generates router configurations under `configs/`

2. **Synchronization to the VM**
   - Connects via SSH/SCP using credentials from `.env`
   - Uploads the necessary folders and scripts (`configs/`, `automation/`, `tests/`, `bootstrap.sh`, `teardown.sh`, and the Manager build files)

### 4. Bootstrap the Lab on the VM

SSH into the **target VM**, move into the project directory, then start the bootstrap pipeline:

```bash
# On the VM
./bootstrap.sh
```

`bootstrap.sh` will:
- verify prerequisites and connectivity,
- build the custom **Manager** image,
- deploy the lab with **Containerlab** using the generated topology.

### 5. Run Traffic Engineering (inside the Manager container)


Once the topology is up, open a shell in the Manager container:

```bash
docker exec -it clab-project-manager sh
```

Then start the control loop:

```bash
python3 automation/manager.py
```

The manager generates/loads a traffic matrix, solves the MILP optimizations, and applies BGP policies (**MED** and **Local Preference**) on the running routers.

---

## 🧪 Testing & Validation

Run tests from the **VM** (or any machine that can access the same Docker daemon used by Containerlab).

### Connectivity Check

Verifies end-to-end reachability (ICMP):

```bash
python3 tests/pings.py
```

### TE Validation

Performs traceroute analysis to confirm that packets follow the optimized paths:

```bash
python3 tests/te.py
```

---

## 🧹 Cleanup

To stop the emulation and restore a clean VM state, run:

```bash
# On the VM
./teardown.sh
```
