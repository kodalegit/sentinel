"""
Sentinel API - FastAPI backend for public procurement oversight.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from config import settings
from models import Bid, RiskScore
from state import AppState
from db.config import async_session
from db import repository as repo
from db.mappers import (
    company_to_pydantic,
    director_to_pydantic,
    official_to_pydantic,
    tender_to_pydantic,
    bid_to_pydantic,
    risk_factors_to_json,
)
from graph.builder import build_procurement_graph
from graph.communities import detect_communities
from ml.hybrid_scorer import HybridRiskScorer
from graph.neo4j_driver import close_neo4j_driver, check_neo4j_health
from graph.neo4j_sync import sync_graph_to_neo4j
from graph.neo4j_communities import detect_communities_neo4j
from routes.stats import router as stats_router
from routes.tenders import router as tenders_router
from routes.tenders_graph import router as tenders_graph_router
from routes.graph import router as graph_router
from routes.cases import router as cases_router
from routes.ingest import router as ingest_router
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.companies import router as companies_router
from auth.dependencies import SupervisorOrAdmin, CurrentUser


# ---------------------------------------------------------------------------
# Recompute job tracking (in-memory; survives until next restart)
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


_recompute_jobs: dict[str, dict[str, Any]] = {}


async def recompute_app_state(app: FastAPI) -> dict:
    """
    Reload all data from DB, rebuild graph, recompute risk scores,
    and update the in-memory app state. Called at startup and after ingestion.
    Returns summary stats.
    """
    data = await load_data_from_db()

    # Build NetworkX graph (always needed for ML features)
    graph = build_procurement_graph(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
    )

    # Detect communities using NetworkX (always available)
    # Neo4j sync happens in background after initial load
    communities = detect_communities(graph, data["bids"], data["companies"])

    scorer = HybridRiskScorer()
    risk_scores = scorer.score_all(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
        graph=graph,
        communities=communities,
        bids_by_tender=data["bids_by_tender"],
    )

    for tender_id, risk in risk_scores.items():
        if tender_id in graph:
            graph.nodes[tender_id]["risk_level"] = risk.category.value

    await persist_risk_scores(risk_scores)

    app.state.app_state = AppState(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
        bids_by_tender=data["bids_by_tender"],
        graph=graph,
        risk_scores=risk_scores,
        communities=communities,
    )

    s = app.state.app_state
    return {
        "tenders": len(s.tenders),
        "companies": len(s.companies),
        "nodes": s.graph.number_of_nodes(),
        "edges": s.graph.number_of_edges(),
        "communities": len(s.communities),
        "risk_scores": len(s.risk_scores),
    }


async def sync_neo4j_background(app: FastAPI):
    """
    Background task to sync graph to Neo4j and update communities.
    This runs after the main recompute completes, so the API remains responsive.
    """
    if not settings.neo4j_enabled:
        return

    try:
        neo4j_health = await check_neo4j_health()
        if neo4j_health["status"] != "healthy":
            logger.warning("Neo4j not healthy, skipping sync")
            return

        state = app.state.app_state
        neo4j_stats = await sync_graph_to_neo4j(
            companies=state.companies,
            directors=state.directors,
            officials=state.officials,
            tenders=state.tenders,
            bids=state.bids,
        )
        logger.info(f"Neo4j sync complete: {neo4j_stats}")

        # Update communities using Neo4j GDS if available
        try:
            communities = await detect_communities_neo4j()
            state.communities = communities
            logger.info(f"Updated communities from Neo4j: {len(communities)} clusters")
        except Exception as e:
            logger.warning(f"Neo4j community detection failed: {e}")

    except Exception as e:
        logger.error(f"Neo4j background sync failed: {e}")


async def load_data_from_db():
    """Load all entities from PostgreSQL and convert to Pydantic models."""
    async with async_session() as db:
        companies_db = await repo.get_companies(db)
        directors_db = await repo.get_directors(db)
        officials_db = await repo.get_officials(db)
        tenders_db = await repo.get_tenders(db)
        bids_db = await repo.get_all_bids(db)

    companies = {str(c.id): company_to_pydantic(c) for c in companies_db}
    directors = {str(d.id): director_to_pydantic(d) for d in directors_db}
    officials = {str(o.id): official_to_pydantic(o) for o in officials_db}
    tenders = {str(t.id): tender_to_pydantic(t) for t in tenders_db}
    bids = [bid_to_pydantic(b) for b in bids_db]

    bids_by_tender: dict[str, list[Bid]] = {}
    for b in bids:
        bids_by_tender.setdefault(b.tender_id, []).append(b)

    return {
        "companies": companies,
        "directors": directors,
        "officials": officials,
        "tenders": tenders,
        "bids": bids,
        "bids_by_tender": bids_by_tender,
    }


async def persist_risk_scores(risk_scores: dict[str, RiskScore]):
    """Save computed risk scores back to PostgreSQL."""
    async with async_session() as db:
        async with db.begin():
            for tender_id, risk in risk_scores.items():
                await repo.upsert_risk_assessment(
                    db=db,
                    tender_id=uuid.UUID(tender_id),
                    overall_score=risk.overall,
                    category=risk.category.value,
                    rule_factors=risk_factors_to_json(risk.factors),
                    recommendation=risk.recommendation,
                    model_version="rules-v1",
                )


async def neo4j_or_fallback(neo4j_coro, networkx_fn, *args, **kwargs):
    """
    Try Neo4j first; fall back to the NetworkX function on any failure.

    neo4j_coro  — an awaitable (already called, e.g. find_shortest_path_neo4j(a, b))
    networkx_fn — a sync callable that accepts *args, **kwargs
    """
    if settings.neo4j_enabled:
        try:
            health = await check_neo4j_health()
            if health["status"] == "healthy":
                result = await neo4j_coro
                if result is not None:
                    return result
        except Exception as e:
            logger.warning(f"Neo4j query failed, falling back to NetworkX: {e}")
    return networkx_fn(*args, **kwargs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize data on startup."""

    # --- JWT secret guard ---
    DEFAULT_SECRET = "sentinel-dev-secret-key-change-in-production"
    if settings.jwt_secret_key == DEFAULT_SECRET:
        logger.warning(
            "\n" + "=" * 70 +
            "\nWARNING: Using default JWT secret key. "
            "Set JWT_SECRET_KEY in production!\n" + "=" * 70
        )

    stats = await recompute_app_state(app)
    print(f"Loaded {stats['tenders']} tenders from PostgreSQL")
    print(f"Built graph with {stats['nodes']} nodes and {stats['edges']} edges")
    print(f"Detected {stats['communities']} bidding communities")
    print(f"Computed and persisted {stats['risk_scores']} risk scores")

    # Populate Neo4j on first boot so Neo4j-first endpoints are ready immediately.
    if settings.neo4j_enabled:
        asyncio.ensure_future(sync_neo4j_background(app))
        print("Neo4j sync scheduled (background)")

    yield

    # Cleanup Neo4j connection
    if settings.neo4j_enabled:
        await close_neo4j_driver()
    print("Shutting down Sentinel API")


app = FastAPI(
    title="Sentinel API",
    description="Public Procurement Guardian - AI-powered oversight system",
    version="0.2.0",
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(stats_router)
app.include_router(tenders_router)
app.include_router(tenders_graph_router)
app.include_router(graph_router)
app.include_router(cases_router)
app.include_router(ingest_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(companies_router)


async def _run_recompute_job(job_id: str, app: FastAPI):
    """
    Background task that runs recompute and updates the job status dict.
    Safe to fire-and-forget from the recompute endpoint.
    """
    _recompute_jobs[job_id]["status"] = JobStatus.RUNNING
    _recompute_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        stats = await recompute_app_state(app)
        if settings.neo4j_enabled:
            await sync_neo4j_background(app)
        _recompute_jobs[job_id].update(
            status=JobStatus.DONE,
            stats=stats,
            neo4j_sync="completed" if settings.neo4j_enabled else "disabled",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"Recompute job {job_id} completed: {stats}")
    except Exception as e:
        _recompute_jobs[job_id].update(
            status=JobStatus.FAILED,
            error=str(e),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.error(f"Recompute job {job_id} failed: {e}")


@app.post("/api/recompute", status_code=202)
async def recompute(
    request: Request,
    current_user: SupervisorOrAdmin,
):
    """
    Trigger a full graph + risk-score recomputation.
    Returns 202 Accepted immediately with a job_id.
    Poll GET /api/recompute/status/{job_id} for completion.
    Requires supervisor or admin.
    """
    job_id = str(uuid.uuid4())
    _recompute_jobs[job_id] = {
        "status": JobStatus.PENDING,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": current_user.username,
    }
    asyncio.ensure_future(_run_recompute_job(job_id, request.app))
    return {"status": "accepted", "job_id": job_id}


@app.get("/api/recompute/status/{job_id}")
async def recompute_status(
    job_id: str,
    current_user: CurrentUser,
):
    """Poll the status of a recompute job."""
    job = _recompute_jobs.get(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/recompute/jobs")
async def list_recompute_jobs(
    current_user: SupervisorOrAdmin,
):
    """List recent recompute jobs (most recent first, last 20)."""
    jobs = [
        {"job_id": jid, **jdata}
        for jid, jdata in _recompute_jobs.items()
    ]
    # Sort by queued_at descending
    jobs.sort(key=lambda j: j.get("queued_at", ""), reverse=True)
    return {"jobs": jobs[:20]}


@app.get("/api/health")
async def health_check():
    """Component health check — PostgreSQL, Neo4j, and LLM availability."""
    from db.config import async_session
    from sqlalchemy import text as sa_text

    # PostgreSQL
    pg_status = "unknown"
    try:
        async with async_session() as db:
            await db.execute(sa_text("SELECT 1"))
        pg_status = "healthy"
    except Exception as e:
        pg_status = f"unhealthy: {e}"

    # Neo4j
    neo4j_status = "disabled"
    if settings.neo4j_enabled:
        neo4j_health = await check_neo4j_health()
        neo4j_status = neo4j_health["status"]

    # LLM (check if any LLM API key env-var is set, without actually calling the API)
    import os
    llm_configured = any(
        os.environ.get(k)
        for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"]
    )
    llm_status = "configured" if llm_configured else "no_api_key (template fallback active)"

    overall = "healthy" if pg_status == "healthy" else "degraded"

    return {
        "status": overall,
        "components": {
            "postgresql": pg_status,
            "neo4j": neo4j_status,
            "llm": llm_status,
            "llm_model": settings.llm_model,
            "llm_provider": settings.llm_provider,
        },
    }


@app.get("/")
def root():
    """Health check endpoint."""
    return {"name": "Sentinel API", "status": "operational", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
