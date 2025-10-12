# SysGen 🚀
**An AI-Native Model-Based Systems Engineering Framework for UAV Design**

---

### 🧠 Overview

SysGen integrates **SysML v2**, **AI**, and **model-based systems engineering (MBSE)** to automate UAV subsystem design, verification, and manufacturability.  
It leverages [SysON](https://mbse-syson.org) as the modeling backend and combines it with Python-based AI agents and surrogate physics models for system-level optimization.

---

### ⚙️ Setup Summary

1. **Install Java 17 and Docker.**  
   Make sure both are available on your Mac:
   ```bash
   java -version
   docker version
Run PostgreSQL in Docker:

bash
Copy code
docker run --name syson-postgres \
  -e POSTGRES_DB=syson \
  -e POSTGRES_USER=syson \
  -e POSTGRES_PASSWORD=syson \
  -p 5432:5432 -d postgres:15
Run SysON locally:

bash
Copy code
java -jar syson-application-2025.10.0.jar \
  --spring.datasource.url=jdbc:postgresql://localhost:5432/syson \
  --spring.datasource.username=syson \
  --spring.datasource.password=syson \
  --server.port=8443
Access the SysON UI:
Visit https://localhost:8443 in your browser.
(Accept the self-signed certificate warning.)

🧩 Version Control for SysML Models
SysGen exports SysML v2 project data from SysON into local .json files and commits them to GitHub for version control and branching.
This allows you to:

Track every design change (diffs)

Collaborate using branches and PRs

Preserve historical versions of your system models

Use the included export_syson.py script to automatically export and version your models.

Example usage:

bash
Copy code
SYSON_BASE_URL=https://localhost:8443 \
SYSON_VERIFY_TLS=false \
python3 export_syson.py
🧱 Architecture Overview
css
Copy code
┌────────────────────────────┐
│   AI Agents (Python)       │  ← Requirement decomposition & design synthesis
│   ├── LLMs / Surrogate ML  │
└──────────▲─────────────────┘
           │ REST API
┌──────────┴────────────┐
│ SysON (SysML v2)      │  ← Model-based design & traceability
│ HTTPS @ localhost:8443│
└──────────▲────────────┘
           │ JDBC
┌──────────┴────────────┐
│ PostgreSQL (Docker)   │  ← Model and requirement storage
└────────────────────────┘
🧮 Roadmap
 Integrate AI-based requirement decomposition

 Add automated SysML v2 model validation

 Implement generative CAD linkage

 Publish UAV subsystem case studies

🧑‍💻 Author
Chance LaVoie
Carnegie Mellon University
SysGen Project – AI-Native MBSE for UAV Systems
