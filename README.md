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
- **Neo4j-first graph APIs**: Search, pathfinding, neighborhood, tender graph, and evidence path resolution now prefer Neo4j and only fall back to NetworkX on failure
- **Cluster-first UX**: Ranked suspicious communities, progressive disclosure
- **Explainable cluster scoring**: Suspicion score messaging now reflects the shared scoring contract across NetworkX and Neo4j
- **Performance**: Hash-based edge detection (O(n) vs O(n²)), edge limits per entity, strict filtering of vague/generic shared attributes, incremental Neo4j sync, and debounced DB-backed graph search in the Graph Explorer

### Analysis Persistence

- **Persisted analysis snapshots**: Each recompute creates an `analysis_run_id` and stores linked risk assessments
- **Fast startup recovery**: Backend can load the latest persisted analysis into `AppState`
- **Snapshot metadata API**: `GET /api/analysis/latest` powers dashboard and sources-page analysis status
- **Incremental graph refresh**: Normal recompute paths upsert Neo4j nodes, prune stale nodes, and rebuild managed relationships instead of fully deleting the graph
- **Bulk snapshot writes**: Large analysis runs now persist company graph features and risk assessments in batches instead of per-row sequential writes

### LLM Intelligence

- **Evidence packs**: Structured JSON with risk factors, metrics, graph paths
- **Grounded explanations**: Every explanation cites real evidence items
- **Canonical evidence assembly**: Baseline risk factors and linked case evidence no longer duplicate the same signal in agent context
- **Template fallback**: Works without LLM API key

### Case Management

- **5-state workflow**: OPEN → INVESTIGATING → ESCALATED → RESOLVED/DISMISSED
- **Typed notes**: Timestamped, user-attributed investigation notes
- **Audit trail**: All actions logged
- **Notification workflow**: Bell-triggered slide-over with unread tracking and direct case navigation

### Admin & Investigator UX

- **Responsive shell**: Desktop sidebar with mobile drawer support across dashboard, cases, admin, and settings flows
- **Backend-owned model catalog**: Admin settings consume a static backend catalog instead of hardcoded provider/model lists
- **Knowledge base polish**: Compact, mobile-friendlier document management with metadata-only editing flow support
- **Exports**: PDF tender risk reports plus CSV bulk export for tender and case views

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
- [x] **Neo4j-First Graph Serving** (Neo4j-backed graph search, evidence/path/neighborhood resolution, incremental sync, reduced lazy NetworkX loads)
- [x] **Investigation Workflow Hardening** (case assignment, supervisor dashboard, case timeline)
- [x] **System Robustness** (Async job tracking, Pytest core logic suite, JWT guards)
- [x] **Milestone 7 Polish** (responsive shell, notifications panel, backend model catalog, knowledge-base refresh, export flows, evidence/scoring consistency)

**Next Up:**

- [x] LLM Agentic Analysis (Case Summaries, Evidence Q&A)

---

## Data Reset & Demo Seed Workflow

- **Reset application state only**:
  `uv run --prerelease=allow python seed.py reset`
- **Reset and reseed synthetic demo data**:
  `uv run --prerelease=allow python seed.py`

The reset flow is **schema-preserving**. It clears procurement, case, chat, analysis snapshot, and Neo4j graph state without dropping tables or bypassing Alembic-managed schema.

By default it:

- preserves default users and auth setup
- preserves knowledge-base documents
- preserves agent settings

### Recommended Operational Flow

- **For real-source ingestion**
  - run `uv run --prerelease=allow python seed.py reset`
  - ingest one or more real datasets via `/api/ingest/ppip/sync`, `/api/ingest/egp/tenders`, or `/api/ingest/egp/contracts`
  - trigger `/api/recompute`

- **For demo presentations**
  - run `uv run --prerelease=allow python seed.py`
  - use the synthetic seeded dataset for stable, repeatable fraud-pattern walkthroughs

### Real-Source Ingestion Notes

- Sentinel now uses a source-agnostic canonical model across PPIP, e-GP, synthetic fixtures, and future connectors.
- Current ingest semantics preserve three distinct procurement signals whenever available:
  - bidder participation
  - award outcome on the tender
  - downstream contract execution
- This lets the analysis pipeline stay useful even when a source publishes bidder rosters but not full bid pricing.
- Company `data_quality_flags` are now interpreted as **evidence quality**, not just raw entity quality:
  - `completeness_score` reflects how much structured evidence the source provided
  - `verification_score` reflects how strongly the supplier identity can be verified
  - `quality_score` blends the two while respecting source expectations

### Awards Modeling Guidance

Current schema support is intentionally lightweight:

- `Tender.awarded_to` captures the winning supplier used by rules, ML features, and graph construction
- `Tender.awarded_amount` captures headline outcome value
- `Bid.amount` is now nullable so the same model can represent either priced bids or participation-only bidder rosters
- `ContractDB` captures downstream contract linkage when contract records exist

This is a good default for now because it keeps the ingest path simple and aligned with what the current analytics stack actually consumes.

**Upside of adding a separate `AwardDB`:**

- preserves full OCDS award history rather than flattening to a single winner
- supports multi-award/framework tenders
- preserves award-level metadata such as award status, descriptions, periods, and multiple suppliers
- enables richer downstream analysis of award amendments and outcome provenance

**Downside of adding a separate `AwardDB`:**

- introduces another central entity that must be loaded, synced, and kept consistent across PostgreSQL, NetworkX, Neo4j, and evidence packs
- increases ingest and recompute complexity before the current analytics pipeline fully consumes award-level detail
- may add storage and modeling overhead without immediate scoring benefit

**Note on award dates and registration checks:**

- The current schema does not store a dedicated award date; risk checks use the tender deadline as the closest proxy. This is sufficient to flag the strong case of a company registering after the deadline, but it cannot distinguish finer cases such as registration after a formal award date but before a later deadline artifact.
- If/when you add `AwardDB` (or a dedicated `award_date` on `Tender`), update the shell-company and chronology checks to compare registration to the true award date and contract timings for stronger evidence.

**Recommended path:**

- keep the current tender + bid + contract model as the operational baseline
- add `AwardDB` only when you are ready to use multi-award or award-lifecycle analysis in scoring, evidence, or case workflows
- if added later, keep `Tender.awarded_to` as a denormalized convenience field for the current risk and graph pipeline

### Data Quality & Shared-Attribute Heuristics

The current direction is designed to stay robust across Kenyan procurement sources with uneven fidelity:

- shared email/phone/address links remain conservative to avoid graph noise and false-positive cartel clusters
- missing supplier profile fields are treated as limited evidence, not automatic proof of suspicious behavior
- bidder participation is preserved even when price disclosures are absent
- price-spread and winner-margin analytics activate only when actual bid amounts exist
- synthetic data remains the clearest way to communicate the intended product behavior, while real-source ingestion demonstrates graceful degradation under sparse or uneven data

## Performance Notes

- **Small seeded datasets** may still feel faster with pure in-memory NetworkX because there is no database roundtrip cost.
- **Larger datasets** benefit from Neo4j-first graph traversal because request-time pathfinding, search, and neighborhood queries no longer depend on loading the full NetworkX graph.
- **Runtime monitoring** now uses lightweight structured timing logs for recompute and snapshot stages instead of heavy always-on profilers.
- The main remaining scale constraints are now mostly **Python-side**:
  - full entity hydration from PostgreSQL into Python memory
  - batch `score_all()` evaluation across all tenders
  - per-tender ML feature extraction
  - Isolation Forest fitting and SHAP explainability cost
  - full recompute orchestration across large analysis runs, even after snapshot persistence batching

This means the recommended architecture remains hybrid: PostgreSQL as source of truth, Neo4j as the primary graph engine, and Python for bounded scoring and ML.

### Performance Monitoring

- **Recommended default**: keep the built-in timing logs enabled and use the profiling script only when you need a focused benchmark.
- **Runtime logs**: recompute now emits `performance_metric` log lines for `load_data`, Neo4j graph preparation, `score_all`, snapshot persistence, and total wall time.
- **Snapshot logs**: analysis snapshot persistence also emits per-stage timings for analysis-run creation, company feature writes, risk assessment payload preparation, and bulk risk assessment insertion.

Example log shape:

```text
performance_metric event=recompute stage=neo4j_graph_prepare duration_ms=2711.4 communities=2 company_graph_features=11012 conflict_paths=11
performance_metric event=analysis_snapshot stage=create_risk_assessments duration_ms=842.7 rows=12705
```

### Profiling Script

From `backend/`, you can run:

- **Neo4j stage benchmark**
  - `uv run --prerelease=allow python profile_recompute.py --mode neo4j-stages`
- **Snapshot persistence benchmark**
  - `uv run --prerelease=allow python profile_recompute.py --mode snapshot --graph-source neo4j`
- **Full recompute benchmark**
  - `uv run --prerelease=allow python profile_recompute.py --mode recompute --neo4j-timeout-seconds 15`

The profiler prints JSON with per-stage timings so you can compare datasets, detect regressions, and see whether time is being spent in Neo4j graph prep, Python scoring, or PostgreSQL persistence.

## Default Credentials

| User         | Password   | Role       | Permissions                            |
| ------------ | ---------- | ---------- | -------------------------------------- |
| `admin`      | `admin123` | Admin      | Full access, user management           |
| `supervisor` | `super123` | Supervisor | Case management, escalation, dismissal |
| `auditor`    | `audit123` | Auditor    | View, investigate, add notes           |

---

**Track**: Governance & Public Policy  
**Owner**: Victor Kimani
