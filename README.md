# Sentinel

AI-powered public procurement oversight system for Kenya government auditors and civil society.

---

## Overview

Sentinel transforms opaque tender data into actionable intelligence through:

- **Hybrid Risk Scoring**: 5 rule-based checks fused with Isolation Forest anomaly detection
- **Shadow Graph Visualization**: Reveals hidden connections between companies, directors, and officials
- **Grounded AI Explanations**: LangGraph agent with evidence packs ensures every explanation cites real data
- **Case Management**: Full investigation workflow with timeline, evidence linking, structured decisions, supervisor workload view, and notifications
- **PostgreSQL Persistence**: Production-grade async database with Alembic migrations and audit trail

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────┐  │
│  │ Dashboard│  │Tender Detail │  │Graph Explorer│  │ Cases  │  │
│  └──────────┘  └──────────────┘  └──────────────┘  └────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────┴────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────┐  ┌──────────┐  ┌──────┐  ┌─────┐  ┌──────────┐  │
│  │ Routes  │  │ Risk     │  │ Graph│  │ LLM │  │ Cases    │  │
│  │ (~25)   │  │ Engine   │  │      │  │     │  │ CRUD     │  │
│  └─────────┘  └──────────┘  └──────┘  └─────┘  └──────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AppState (typed singleton: data + latest analysis snapshot)│  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
         ▼                                       ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│       PostgreSQL 16           │   │       Neo4j 5               │
│  (Source of Truth)            │   │  (Graph Analytics)          │
├─────────────────────────────┤   ├─────────────────────────────┤
│ Tenders, Companies, Bids     │   │ GDS: Louvain, PageRank     │
│ Cases, Users, Audit Log     │   │ APOC: Path finding         │
│ Risk Assessments + Analysis Runs│ │ Community detection       │
└─────────────────────────────┘   └─────────────────────────────┘
```

---

## Project Structure

```
sentinel/
├── backend/                    # FastAPI backend
│   ├── alembic/               # Database migrations
│   ├── config.py              # Pydantic Settings (env vars)
│   ├── data/                  # Seed data and synthetic fixtures
│   ├── db/                    # SQLAlchemy models, repository, session
│   ├── graph/                 # NetworkX graph builder, communities, APIs
│   ├── intelligence/          # LangGraph agent, evidence packs
│   ├── main.py                # FastAPI app, lifespan, routers
│   ├── ml/                    # Feature engineering, Isolation Forest
│   ├── models.py              # SQLAlchemy ORM models
│   ├── routes/                # API routes (stats, tenders, graph, cases)
│   ├── risk/                  # Rule engine, hybrid scorer
│   ├── seed.py                # DB seeding script
│   └── state.py               # Typed AppState dataclass
│
├── frontend/
│   └── ui/                    # Next.js 16 + TypeScript + shadcn/ui
│       ├── src/
│       │   ├── app/           # Next.js app router pages
│       │   ├── components/    # shadcn/ui components
│       │   ├── hooks/         # React hooks
│       │   └── lib/           # Utilities
│       ├── Dockerfile
│       └── package.json
│
├── docker-compose.yml         # Full stack: frontend, backend, postgres
├── IMPLEMENTATION.md          # Detailed implementation docs
├── MILESTONES.md              # 7 milestones for hackathon (Weeks 3–9)
├── PLAN.md                    # Architecture plan, tech stack, decisions
├── PROPOSAL.md                # Initial project proposal
├── ROADMAP.md                 # 9-week technical roadmap
└── TODO.md                    # Outstanding tasks
```

---

## Tech Stack

| Layer      | Technology                                                           |
| ---------- | -------------------------------------------------------------------- |
| Frontend   | Next.js 16, TypeScript, TailwindCSS v4, shadcn/ui, React Flow        |
| Backend    | FastAPI, Python 3.12, Pydantic Settings                              |
| Database   | PostgreSQL 16, async SQLAlchemy, Alembic                             |
| Graph      | Neo4j 5 (GDS + APOC) with NetworkX fallback                          |
| ML         | scikit-learn (Isolation Forest)                                      |
| LLM        | LangChain v1, LangGraph, provider-agnostic (OpenAI/Anthropic/Ollama) |
| Deployment | Docker Compose, Railway                                              |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12 (for local development)

### Using Docker Compose

```bash
# Clone and navigate
git clone <repo-url>
cd sentinel

# Start full stack
docker compose up

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Neo4j Browser: http://localhost:7474
```

### Local Development

**Backend:**

```bash
cd backend
uv sync --dev --prerelease=allow
source .venv/bin/activate
python -m alembic upgrade head
python seed.py
uvicorn main:app --reload
```

In dev, use `uv run --prerelease=allow fastapi dev main.py` to run the app.

Note: The backend currently depends on `shap==0.50.0`, which pulls prerelease builds of `numba/llvmlite` for Python 3.12. If you're using `uv`, include `--prerelease=allow` when syncing/running.

**Frontend:**

```bash
cd frontend/ui
pnpm install
pnpm dev
```

### **LLM Configuration (optional)**

Set in `.env` to enable AI-powered explanations:

```bash
LLM_MODEL=gpt-5-mini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Or use Ollama for local models:
LLM_MODEL=llama3
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434/v1
```

Without an LLM key, the system falls back to structured template explanations.

---

## Key Features

### Risk Detection

- **Rule-based**: 5 checks (shell company, conflict of interest, pricing anomalies, timeline anomalies, bid rotation)
- **ML-based**: Isolation Forest anomaly detection on 12 engineered features
- **Hybrid scoring**: 60% rules / 40% ML fusion

### Graph Analytics

- **Hybrid architecture**: PostgreSQL (source of truth) + Neo4j (analytics)
- **Shadow graph**: Companies, directors, officials, bids as nodes
- **Community detection**: Neo4j GDS Louvain with NetworkX fallback
- **Path finding**: Neo4j shortest paths with sub-millisecond traversals
- **Cluster-first UX**: Ranked suspicious communities, progressive disclosure
- **Performance**: Hash-based edge detection (O(n) vs O(n²)), edge limits per entity, and strict filtering of vague/generic shared attributes

### Analysis Persistence

- **Persisted analysis snapshots**: Each recompute creates an `analysis_run_id` and stores linked risk assessments
- **Fast startup recovery**: Backend can load the latest persisted analysis into `AppState`
- **Snapshot metadata API**: `GET /api/analysis/latest` powers dashboard and sources-page analysis status

### LLM Intelligence

- **Evidence packs**: Structured JSON with risk factors, metrics, graph paths
- **Grounded explanations**: Every explanation cites real evidence items
- **Template fallback**: Works without LLM API key

### Case Management

- **5-state workflow**: OPEN → INVESTIGATING → ESCALATED → RESOLVED/DISMISSED
- **Typed notes**: Timestamped, user-attributed investigation notes
- **Audit trail**: All actions logged

### Authentication & Authorization

- **JWT-based auth**: Access (30min) + refresh (7 day) tokens
- **Role-based access**: auditor, supervisor, admin roles with different permissions
- **User attribution**: All case actions tracked to logged-in user
- **Admin user management**: Create, edit, deactivate users

---

## Current Status

**Complete:**

- [x] PostgreSQL backend with async SQLAlchemy + Alembic migrations
- [x] Hybrid risk engine (rules + Isolation Forest)
- [x] Graph analytics (Neo4j + NetworkX fallback)
- [x] LLM intelligence (LangGraph agent, evidence packs)
- [x] Case management (5-state workflow, typed notes, 7 API endpoints)
- [x] UI overhaul (shadcn/ui components, dashboard, graph explorer, cases page)
- [x] Infrastructure (Docker Compose, Dockerfiles, Railway configs)
- [x] Backend refactor (Pydantic settings, modular routes, typed AppState)
- [x] **Authentication & User Management** (JWT auth, role-based access, admin user management)
- [x] **PPIP/e-GP Data Ingestion** (connectors, provenance, multi-signal detection)
- [x] **Neo4j Hybrid Architecture** (GDS algorithms, PostgreSQL sync, graceful fallback)
- [x] **Graph Performance Optimization** (O(n) edge detection, pagination, large graph handling)
- [x] **Persisted Analysis Snapshots** (analysis runs, snapshot-aware risk loading, latest snapshot metadata endpoint)
- [x] **Graph Noise Reduction** (specific-only shared address edges, generic phone/email suppression, aligned Neo4j filtering)
- [x] **Investigation Workflow Hardening** (case assignment, supervisor dashboard, case timeline)
- [x] **System Robustness** (Async job tracking, Pytest core logic suite, JWT guards)

**Next Up:**

- [ ] LLM Agentic Analysis (Case Summaries, Evidence Q&A)
- [ ] CSV/PDF ingestion for additional data sources

---

## Default Credentials

| User         | Password   | Role       | Permissions                            |
| ------------ | ---------- | ---------- | -------------------------------------- |
| `admin`      | `admin123` | Admin      | Full access, user management           |
| `supervisor` | `super123` | Supervisor | Case management, escalation, dismissal |
| `auditor`    | `audit123` | Auditor    | View, investigate, add notes           |

---

**Track**: Governance & Public Policy  
**Owner**: Victor Kimani
