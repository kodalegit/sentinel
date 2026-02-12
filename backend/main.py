"""
Sentinel API - FastAPI backend for public procurement oversight.
"""

import uuid

from fastapi import FastAPI
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
from routes.stats import router as stats_router
from routes.tenders import router as tenders_router
from routes.tenders_graph import router as tenders_graph_router
from routes.graph import router as graph_router
from routes.cases import router as cases_router


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
    # Load data from PostgreSQL
    data = await load_data_from_db()

    # Build the shadow graph
    graph = build_procurement_graph(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
    )

    # Detect communities once (Louvain) — cached for routes and rule engine
    communities = detect_communities(graph, data["bids"], data["companies"])

    # Compute hybrid risk scores (rules + Isolation Forest)
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

    # Update graph with risk levels
    for tender_id, risk in risk_scores.items():
        if tender_id in graph:
            graph.nodes[tender_id]["risk_level"] = risk.category.value

    # Persist risk scores to DB
    await persist_risk_scores(risk_scores)

    # Store typed state on the app
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
    print(f"Loaded {len(s.tenders)} tenders from PostgreSQL")
    print(
        f"Built graph with {s.graph.number_of_nodes()} nodes and {s.graph.number_of_edges()} edges"
    )
    print(f"Detected {len(s.communities)} bidding communities")
    print(f"Computed and persisted {len(s.risk_scores)} risk scores")

    yield

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


@app.get("/")
def root():
    """Health check endpoint."""
    return {"name": "Sentinel API", "status": "operational", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
