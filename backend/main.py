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

import networkx as nx

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
    risk_assessment_to_pydantic,
    risk_factors_to_json,
)
from graph.builder import build_procurement_graph
from graph.communities import detect_communities, Cluster
from graph.neo4j_analytics import (
    materialize_company_graph_features_neo4j,
    precompute_conflict_paths_neo4j,
    update_tender_risk_levels_neo4j,
)
from graph.neo4j_communities import detect_communities_neo4j
from ml.hybrid_scorer import HybridRiskScorer
from ml.features import materialize_company_graph_features
from graph.neo4j_driver import close_neo4j_driver, check_neo4j_health
from graph.neo4j_sync import sync_graph_to_neo4j, get_graph_stats_from_neo4j
from routes.stats import router as stats_router
from routes.tenders import router as tenders_router
from routes.tenders_graph import router as tenders_graph_router
from routes.graph import router as graph_router
from routes.cases import router as cases_router
from routes.ingest import router as ingest_router
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.companies import router as companies_router
from routes.intelligence import router as intelligence_router
from routes.settings import (
    router as settings_router,
    sync_runtime_llm_settings_from_db,
)
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

ANALYSIS_MODEL_VERSION = "hybrid-v1"


def _communities_to_json(communities: list[Cluster]) -> list[dict]:
    return [
        {
            "id": community.id,
            "company_ids": community.company_ids,
            "company_names": community.company_names,
            "size": community.size,
            "suspicion_score": community.suspicion_score,
            "shared_attributes": community.shared_attributes,
            "co_bid_count": community.co_bid_count,
            "win_pattern": community.win_pattern,
        }
        for community in communities
    ]


def _communities_from_json(items: list[dict] | None) -> list[Cluster]:
    if not items:
        return []
    return [
        Cluster(
            id=item.get("id", "cluster-unknown"),
            company_ids=item.get("company_ids", []),
            company_names=item.get("company_names", []),
            size=int(item.get("size", 0)),
            suspicion_score=float(item.get("suspicion_score", 0.0)),
            shared_attributes=item.get("shared_attributes", {}),
            co_bid_count=int(item.get("co_bid_count", 0)),
            win_pattern=item.get("win_pattern", {}),
        )
        for item in items
    ]


def _company_graph_features_from_rows(rows) -> dict[str, dict[str, int]]:
    return {
        str(row.company_id): {
            "graph_degree": row.graph_degree,
            "suspicious_edges": row.suspicious_edges,
            "official_distance": row.official_distance,
            "community_size": row.community_size,
        }
        for row in rows
    }


async def load_persisted_analysis(app: FastAPI) -> dict | None:
    data = await load_data_from_db()

    async with async_session() as db:
        analysis_run = await repo.get_latest_analysis_run(db)
        if analysis_run is None:
            return None
        risk_assessments = await repo.get_risk_assessments_for_run(db, analysis_run.id)
        feature_rows = await repo.get_company_graph_features_for_run(
            db, analysis_run.id
        )

    risk_scores = {
        str(assessment.tender_id): risk_assessment_to_pydantic(assessment)
        for assessment in risk_assessments
    }
    communities = _communities_from_json(analysis_run.communities)
    company_graph_features = _company_graph_features_from_rows(feature_rows)

    app.state.app_state = AppState(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
        bids_by_tender=data["bids_by_tender"],
        risk_scores=risk_scores,
        communities=communities,
        analysis_run_id=str(analysis_run.id),
        analysis_status=analysis_run.status,
        analysis_model_version=analysis_run.model_version,
        analysis_created_at=analysis_run.created_at,
        graph_loaded=False,
        graph_source=analysis_run.graph_source,
        snapshot_source="persisted",
        analysis_summary={
            "tenders": analysis_run.tender_count,
            "companies": analysis_run.company_count,
            "nodes": analysis_run.node_count,
            "edges": analysis_run.edge_count,
            "communities": analysis_run.community_count,
            "risk_scores": len(risk_scores),
        },
        company_graph_features=company_graph_features,
    )

    return {
        "tenders": len(data["tenders"]),
        "companies": len(data["companies"]),
        "nodes": analysis_run.node_count,
        "edges": analysis_run.edge_count,
        "communities": len(communities),
        "risk_scores": len(risk_scores),
        "analysis_run_id": str(analysis_run.id),
        "snapshot_source": "persisted",
    }


async def persist_analysis_snapshot(
    *,
    risk_scores: dict[str, RiskScore],
    communities: list[Cluster],
    company_graph_features: dict[str, dict[str, int]],
    scorer: HybridRiskScorer,
    summary: dict[str, int],
    graph_source: str,
) -> str:
    async with async_session() as db:
        async with db.begin():
            analysis_run = await repo.create_analysis_run(
                db=db,
                status="COMPLETED",
                graph_source=graph_source,
                model_version=ANALYSIS_MODEL_VERSION,
                tender_count=summary["tenders"],
                company_count=summary["companies"],
                node_count=summary["nodes"],
                edge_count=summary["edges"],
                community_count=summary["communities"],
                run_metadata=summary,
                communities=_communities_to_json(communities),
            )
            await repo.create_company_graph_features(
                db=db,
                analysis_run_id=analysis_run.id,
                company_features=company_graph_features,
            )

            ml_scores = scorer.last_ml_scores
            model_version = f"{ANALYSIS_MODEL_VERSION}:{analysis_run.id}"
            for tender_id, risk in risk_scores.items():
                ml_row = None
                if ml_scores is not None and tender_id in ml_scores.index:
                    ml_row = ml_scores.loc[tender_id]
                await repo.upsert_risk_assessment(
                    db=db,
                    analysis_run_id=analysis_run.id,
                    tender_id=uuid.UUID(tender_id),
                    overall_score=risk.overall,
                    category=risk.category.value,
                    rule_factors=risk_factors_to_json(risk.factors),
                    recommendation=risk.recommendation,
                    ml_anomaly_score=(
                        float(ml_row["anomaly_score"]) if ml_row is not None else None
                    ),
                    ml_feature_importance=(
                        ml_row["feature_importance"] if ml_row is not None else None
                    ),
                    model_version=model_version,
                )

    return str(analysis_run.id)


async def recompute_app_state(
    app: FastAPI,
    *,
    prefer_neo4j_primary: bool = True,
    neo4j_timeout_seconds: float = 15.0,
) -> dict:
    """
    Reload all data from DB, rebuild graph, recompute risk scores,
    and update the in-memory app state. Called at startup and after ingestion.
    Returns summary stats.
    """
    data = await load_data_from_db()

    if settings.neo4j_enabled and prefer_neo4j_primary:
        try:
            async with asyncio.timeout(neo4j_timeout_seconds):
                neo4j_health = await check_neo4j_health()
                if neo4j_health["status"] != "healthy":
                    raise RuntimeError("Neo4j health check did not return healthy")

                await sync_graph_to_neo4j(
                    companies=data["companies"],
                    directors=data["directors"],
                    officials=data["officials"],
                    tenders=data["tenders"],
                    bids=data["bids"],
                    incremental=True,
                )

                communities = await detect_communities_neo4j()
                company_graph_features = (
                    await materialize_company_graph_features_neo4j()
                )
                conflict_paths = await precompute_conflict_paths_neo4j(data["tenders"])

            scorer = HybridRiskScorer()
            risk_scores = scorer.score_all(
                tenders=data["tenders"],
                companies=data["companies"],
                directors=data["directors"],
                officials=data["officials"],
                bids=data["bids"],
                graph=None,
                communities=communities,
                bids_by_tender=data["bids_by_tender"],
                company_graph_features=company_graph_features,
                conflict_paths=conflict_paths,
            )

            await update_tender_risk_levels_neo4j(
                {
                    tender_id: risk.category.value
                    for tender_id, risk in risk_scores.items()
                }
            )

            neo4j_stats = await get_graph_stats_from_neo4j()
            summary = {
                "tenders": len(data["tenders"]),
                "companies": len(data["companies"]),
                "nodes": neo4j_stats.get("total_nodes", 0),
                "edges": neo4j_stats.get("total_edges", 0),
                "communities": len(communities),
                "risk_scores": len(risk_scores),
            }
            analysis_run_id = await persist_analysis_snapshot(
                risk_scores=risk_scores,
                communities=communities,
                company_graph_features=company_graph_features,
                scorer=scorer,
                summary=summary,
                graph_source="neo4j",
            )

            app.state.app_state = AppState(
                tenders=data["tenders"],
                companies=data["companies"],
                directors=data["directors"],
                officials=data["officials"],
                bids=data["bids"],
                bids_by_tender=data["bids_by_tender"],
                graph=nx.Graph(),
                graph_loaded=False,
                graph_source="neo4j",
                risk_scores=risk_scores,
                communities=communities,
                analysis_run_id=analysis_run_id,
                analysis_status="COMPLETED",
                analysis_model_version=ANALYSIS_MODEL_VERSION,
                analysis_created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                snapshot_source="fresh",
                analysis_summary=summary,
                company_graph_features=company_graph_features,
            )

            return {
                **summary,
                "analysis_run_id": analysis_run_id,
                "snapshot_source": "fresh",
            }
        except TimeoutError:
            logger.warning(
                "Neo4j primary analysis timed out after %.1fs during graph preparation; falling back to NetworkX",
                neo4j_timeout_seconds,
            )
        except Exception:
            logger.exception("Neo4j primary analysis failed, falling back to NetworkX")

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
    communities = detect_communities(
        graph, data["tenders"], data["bids"], data["companies"]
    )
    company_graph_features = materialize_company_graph_features(graph)

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
        company_graph_features=company_graph_features,
    )

    for tender_id, risk in risk_scores.items():
        if tender_id in graph:
            graph.nodes[tender_id]["risk_level"] = risk.category.value

    summary = {
        "tenders": len(data["tenders"]),
        "companies": len(data["companies"]),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "communities": len(communities),
        "risk_scores": len(risk_scores),
    }
    analysis_run_id = await persist_analysis_snapshot(
        risk_scores=risk_scores,
        communities=communities,
        company_graph_features=company_graph_features,
        scorer=scorer,
        summary=summary,
        graph_source="networkx",
    )

    app.state.app_state = AppState(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
        bids_by_tender=data["bids_by_tender"],
        graph=graph,
        graph_loaded=True,
        graph_source="networkx",
        risk_scores=risk_scores,
        communities=communities,
        analysis_run_id=analysis_run_id,
        analysis_status="COMPLETED",
        analysis_model_version=ANALYSIS_MODEL_VERSION,
        analysis_created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        snapshot_source="fresh",
        analysis_summary=summary,
        company_graph_features=company_graph_features,
    )

    return {**summary, "analysis_run_id": analysis_run_id, "snapshot_source": "fresh"}


async def sync_neo4j_background(app: FastAPI):
    """
    Background task to sync graph to Neo4j.
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
            incremental=True,
        )
        await update_tender_risk_levels_neo4j(
            {
                tender_id: risk.category.value
                for tender_id, risk in state.risk_scores.items()
            }
        )
        logger.info(f"Neo4j sync complete: {neo4j_stats}")

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
            "\n" + "=" * 70 + "\nWARNING: Using default JWT secret key. "
            "Set JWT_SECRET_KEY in production!\n" + "=" * 70
        )

    await sync_runtime_llm_settings_from_db()

    stats = await load_persisted_analysis(app)
    if stats is None:
        stats = await recompute_app_state(app, prefer_neo4j_primary=False)
        print(f"Loaded {stats['tenders']} tenders from PostgreSQL")
        print(f"Built graph with {stats['nodes']} nodes and {stats['edges']} edges")
        print(f"Detected {stats['communities']} bidding communities")
        print(f"Computed and persisted {stats['risk_scores']} risk scores")

        if settings.neo4j_enabled and app.state.app_state.graph_source != "neo4j":
            asyncio.ensure_future(sync_neo4j_background(app))
            print("Neo4j sync scheduled (background)")
    else:
        print(f"Loaded {stats['tenders']} tenders from PostgreSQL")
        print(f"Loaded persisted analysis snapshot {stats['analysis_run_id']}")
        print(f"Loaded {stats['communities']} bidding communities")
        print(f"Loaded {stats['risk_scores']} persisted risk scores")

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
app.include_router(intelligence_router)
app.include_router(settings_router)


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
    jobs = [{"job_id": jid, **jdata} for jid, jdata in _recompute_jobs.items()]
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
        for k in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
        ]
    )
    llm_status = (
        "configured" if llm_configured else "no_api_key (template fallback active)"
    )

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
