# Sentinel

AI-powered public procurement oversight system for Kenya government auditors and civil society.

---

## Overview

Sentinel transforms opaque tender data into actionable intelligence through:

- **Hybrid Risk Scoring**: 5 rule-based checks fused with Isolation Forest anomaly detection
- **Shadow Graph Visualization**: Reveals hidden connections between companies, directors, and officials
- **Grounded AI Explanations**: LangGraph agent with evidence packs ensures every explanation cites real data
- **Case Management**: Full investigation workflow — open cases, add notes, transition through status stages
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
│  │ (~20)   │  │ Engine   │  │      │  │     │  │ CRUD     │  │
│  └─────────┘  └──────────┘  └──────┘  └─────┘  └──────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AppState (typed singleton: tenders, graph, risks)        │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                    PostgreSQL 16                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Core: Tenders, Bids, Companies, Directors, Officials    │   │
│  │ Risk: Risk Assessments (versioned)                        │   │
│  │ Cases: Cases, Case Notes, Audit Log                       │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
sentinel/
├── backend/                    # FastAPI backend
│   ├── alembic/               # Database migrations
│   ├── config.py              # Pydantic Settings (env vars)
│   ├── data/                  # Seed data, synthetic generator (planned)
│   ├── db/                    # SQLAlchemy models, repository, session
│   ├── graph/                 # NetworkX graph builder, communities, APIs
│   ├── intelligence/          # LangGraph agent, evidence packs
│   ├── jobs/                  # ARQ worker, tasks (planned)
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
| Graph      | NetworkX, Louvain community detection                                |
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
```

### Local Development

**Backend:**

```bash
cd backend
uv sync --dev
source .venv/bin/activate
python -m alembic upgrade head
python seed.py
uvicorn main:app --reload
```

**Frontend:**

```bash
cd frontend/ui
pnpm install
pnpm dev
```

---

## Key Features

### Risk Detection

- **Rule-based**: 5 checks (shell company, conflict of interest, pricing anomalies, timeline anomalies, bid rotation)
- **ML-based**: Isolation Forest anomaly detection on 12 engineered features
- **Hybrid scoring**: 60% rules / 40% ML fusion

### Graph Analytics

- **Shadow graph**: Companies, directors, officials, bids as nodes
- **Community detection**: Louvain algorithm reveals bidding rings
- **Path finding**: Shortest paths between any two entities
- **Cluster-first UX**: Ranked suspicious communities, progressive disclosure

### LLM Intelligence

- **Evidence packs**: Structured JSON with risk factors, metrics, graph paths
- **Grounded explanations**: Every explanation cites real evidence items
- **Template fallback**: Works without LLM API key

### Case Management

- **5-state workflow**: OPEN → INVESTIGATING → ESCALATED → RESOLVED/DISMISSED
- **Typed notes**: Timestamped, user-attributed investigation notes
- **Audit trail**: All actions logged

---

## Current Status (Week 2)

**Complete:**

- [x] PostgreSQL backend with async SQLAlchemy + Alembic migrations
- [x] Hybrid risk engine (rules + Isolation Forest)
- [x] Graph analytics (NetworkX + Louvain)
- [x] LLM intelligence (LangGraph agent, evidence packs)
- [x] Case management (5-state workflow, typed notes, 7 API endpoints)
- [x] UI overhaul (shadcn/ui components, dashboard, graph explorer, cases page)
- [x] Infrastructure (Docker Compose, Dockerfiles, Railway configs)
- [x] Backend refactor (Pydantic settings, modular routes, typed AppState)

**Upcoming (Week 3):**

- [ ] Production startup pipeline (automated migrations, health checks)
- [ ] Redis + ARQ worker for async background jobs
- [ ] Data ingestion API (POST tenders/companies)
- [ ] Configurable synthetic data generator

---

**Track**: Governance & Public Policy  
**Owner**: Victor Kimani
