"""
Sentinel API - FastAPI backend for public procurement oversight.
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

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
from auth.dependencies import SupervisorOrAdmin


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

    # Sync to Neo4j if enabled
    neo4j_stats = None
    if settings.neo4j_enabled:
        try:
            neo4j_health = await check_neo4j_health()
            if neo4j_health["status"] == "healthy":
                neo4j_stats = await sync_graph_to_neo4j(
                    companies=data["companies"],
                    directors=data["directors"],
                    officials=data["officials"],
                    tenders=data["tenders"],
                    bids=data["bids"],
                )
                print(f"Synced to Neo4j: {neo4j_stats}")
        except Exception as e:
            print(f"Neo4j sync failed, using NetworkX fallback: {e}")

    # Detect communities (use Neo4j if available, else NetworkX)
    if settings.neo4j_enabled and neo4j_stats:
        try:
            communities = await detect_communities_neo4j()
        except Exception as e:
            print(f"Neo4j community detection failed, using NetworkX: {e}")
            communities = detect_communities(graph, data["bids"], data["companies"])
    else:
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
    result = {
        "tenders": len(s.tenders),
        "companies": len(s.companies),
        "nodes": s.graph.number_of_nodes(),
        "edges": s.graph.number_of_edges(),
        "communities": len(s.communities),
        "risk_scores": len(s.risk_scores),
    }
    if neo4j_stats:
        result["neo4j_synced"] = neo4j_stats
    return result


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize data on startup."""
    stats = await recompute_app_state(app)
    print(f"Loaded {stats['tenders']} tenders from PostgreSQL")
    print(f"Built graph with {stats['nodes']} nodes and {stats['edges']} edges")
    print(f"Detected {stats['communities']} bidding communities")
    print(f"Computed and persisted {stats['risk_scores']} risk scores")
    if stats.get("neo4j_synced"):
        print(f"Neo4j sync: {stats['neo4j_synced']}")

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


@app.post("/api/recompute")
async def recompute(request: Request, current_user: SupervisorOrAdmin):
    """Reload data from DB and recompute graph + risk scores. Requires supervisor or admin."""
    stats = await recompute_app_state(request.app)
    return {"status": "ok", "stats": stats}


@app.get("/")
def root():
    """Health check endpoint."""
    return {"name": "Sentinel API", "status": "operational", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
