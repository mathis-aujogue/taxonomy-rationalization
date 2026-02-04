# 🎯 Taxonomy Rationalization

**AI-Powered Category Matching**

Map client taxonomies to your internal taxonomy using **hybrid matching**: semantic (vector) search for fast candidate retrieval and an AI model for accurate selection. Optional **description generation** enriches categories with AI-written descriptions to improve match quality.

---

## 📋 Overview

When working with multiple clients, each may use different category taxonomies. This project maps client-specific categories to a standardized internal taxonomy, enabling:

- **Unified spend analysis** across clients
- **Automated category matching** at scale
- **High accuracy** via hybrid matching
- **Transparent decisions** with confidence scores and reasoning

### The Problem

```
Client Taxonomy                    →    Internal Taxonomy
─────────────────                        ─────────────────
Canteen Services                  →    FOOD SERVICES
Cleaning Services and goods       →    JANITORIAL SERVICES
```

Manual matching is time-consuming, error-prone, and hard to audit. This tool automates it.

---

## ⚡ Hybrid Matching

**Balanced speed and accuracy** (~5–10 min for 200+ categories)

- **Step 1**: Vector search (Azure OpenAI + pgvector) retrieves top-k similar categories from the internal taxonomy.
- **Step 2**: An AI model selects the best match from those candidates and explains why.

Optional **description generation** adds or enriches category descriptions before ingestion, improving match accuracy.

---

## 🏗️ Architecture

```
┌─────────────────┐
│ Client Taxonomy │  (CSV: L1, L2, L3, optional definitions)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Optional: Description Generation   │  (AI augments categories)
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Ingest → PostgreSQL + pgvector    │  (vectors for L1, L2, L3, descriptions)
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Hybrid Matcher                     │  (vector search + model selection)
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Output: Matched CSV, Report, Stats │
└─────────────────────────────────────┘
```

---

## 🛠️ Quick Start

### Prerequisites

- **Python 3.13+** and **uv** (package manager)
- **Docker** and **Docker Compose** (for PostgreSQL + pgvector)
- **Node.js** and **npm** (for the frontend)
- **Azure OpenAI** API keys

### 1. Install dependencies

```bash
# Clone and enter the repo
git clone <repository-url>
cd taxonomy-rationalization

# Backend (Python)
uv sync

# Frontend (Node) – only needed for the web UI
cd frontend && npm install && cd ..
```

### 2. Environment

```bash
cp .env.example .env
# Edit .env with your Azure OpenAI credentials and DB URL (see Configuration below)
```

### 3. Run with the web interface (recommended)

Use three terminals:

**Terminal 1 – Database (Docker must be running)**

```bash
make db
```

**Terminal 2 – Backend API**

```bash
make api
```

**Terminal 3 – Frontend**

```bash
make frontend
```

Then open **http://localhost:5173**. From the UI you can:

- Upload and ingest taxonomies (our + client)
- Optionally run **description generation** on a taxonomy
- Run **hybrid matching** and review/export results

### 4. Run from the command line (no frontend)

```bash
# Start DB (in one terminal)
docker-compose up -d

# Ingest our taxonomy (one-time)
uv run backend/ingest_taxonomy.py --input-csv assets/our_taxonomy.csv

# Optional: generate descriptions then re-ingest (or use the web “Augment” step)
uv run backend/generate_descriptions.py assets/our_taxonomy.csv assets/our_taxonomy_enriched.csv

# Run hybrid matching (our_target_id client_target_id, e.g. shq_hybrid zalando_hybrid)
uv run backend/hybrid_matcher.py our_target_id client_target_id
```

---

## 🖥️ How to run the frontend

### Requirements

- **Docker** (for PostgreSQL): start the DB with `make db` or `docker-compose up -d`.
- **uv**: used by the backend. Install from [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/) or:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Backend deps**: from project root run `uv sync`.
- **Frontend deps**: run `npm install` inside `frontend/` (or use the one-time setup in Quick Start).

### Steps (using the Makefile)

1. **Start the database** (Docker must be running):

   ```bash
   make db
   ```

   Leave this running. In another terminal:

2. **Start the API**:

   ```bash
   make api
   ```

   API will be at **http://localhost:8000**.

3. **Start the frontend**:

   ```bash
   make frontend
   ```

   App will be at **http://localhost:5173**.

Optional: set `VITE_API_URL=http://localhost:8000` in `frontend/.env` if the API is not on that URL.

---

## 📊 Features

- **Hybrid matching**: Vector search + AI selection for speed and accuracy.
- **Description generation**: Optional step to add or enrich category descriptions before ingestion.
- **Confidence scores** (0.0–1.0) and reasoning for each match.
- **Web UI**: Ingest, augment, match, review, and export without using the CLI.

---

## 📁 Project structure

```
taxonomy-rationalization/
├── backend/
│   ├── api/                    # FastAPI (main, services, generate_descriptions_api)
│   ├── hybrid_matcher.py       # Hybrid matching
│   ├── generate_descriptions.py # CLI description generation
│   ├── ingest_taxonomy.py      # Ingest into vector DB
│   ├── ingest_hybrid_embeddings.py
│   └── utils/                  # Helpers
├── frontend/                   # React + Vite + TypeScript
├── assets/                     # our_taxonomy.csv, their_taxonomy.csv
├── makefile                    # db, api, frontend targets
├── docker-compose.yml          # PostgreSQL + pgvector
└── pyproject.toml              # Python deps (uv)
```

---

## 🔧 Configuration

### Environment variables

```bash
# Database URL format:
LOCAL_POSTGRESQL_URL=postgresql://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/<DBNAME>

# Azure OpenAI / Embedding credentials
AZURE_CHAT_API_KEY=<your-azure-chat-api-key>
AZURE_EMBEDDING_API_KEY=<your-azure-embedding-api-key>
AZURE_CHAT_ENDPOINT=https://<your-resource-name>.openai.azure.com/
AZURE_EMBEDDING_ENDPOINT=https://<your-resource-name>.openai.azure.com/
AZURE_CHAT_MODEL=gpt-5.1-chat
AZURE_EMBEDDING_MODEL=text-embedding-small-3
AZURE_API_VERSION=2024-12-01-preview

GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b

```

See `.env.example` for a full template.

---

## 📚 Documentation

- **[docs/WEB_INTERFACE_README.md](docs/WEB_INTERFACE_README.md)** – Web UI usage (ingestion, description generation, matching, export).
- **[docs/HYBRID_MATCHER_METHODS.md](docs/HYBRID_MATCHER_METHODS.md)** – Hybrid matcher methods, weights, and CLI.

---

**Ready to run?** Start with `make db`, then `make api`, then `make frontend`, and open http://localhost:5173.
