"""
Sentinel API - FastAPI backend for public procurement oversight.
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Tender,
    Company,
    Director,
    PublicOfficial,
    Bid,
    RiskScore,
    RiskCategory,
    TenderStatus,
    TenderWithRisk,
    TenderDetail,
    GraphData,
    DashboardStats,
)
from db.config import get_db, async_session, engine
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
from graph.builder import (
    build_procurement_graph,
    get_tender_subgraph,
    graph_to_frontend_format,
    find_cartel_clusters,
)
from graph.communities import (
    detect_communities,
    get_cluster_subgraph,
    find_shortest_path,
    Cluster,
)
from risk.engine import compute_all_risk_scores
from ml.hybrid_scorer import HybridRiskScorer
from intelligence.evidence import build_evidence_pack
from intelligence.agent import get_agent


# Cached data loaded from PostgreSQL on startup
DATA_STORE: dict = {}
GRAPH: nx.Graph | None = None
RISK_SCORES: dict[str, RiskScore] = {}


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
                import uuid

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
    global DATA_STORE, GRAPH, RISK_SCORES

    # Load data from PostgreSQL
    DATA_STORE = await load_data_from_db()

    # Build the shadow graph
    GRAPH = build_procurement_graph(
        tenders=DATA_STORE["tenders"],
        companies=DATA_STORE["companies"],
        directors=DATA_STORE["directors"],
        officials=DATA_STORE["officials"],
        bids=DATA_STORE["bids"],
    )

    # Compute hybrid risk scores (rules + Isolation Forest)
    scorer = HybridRiskScorer()
    RISK_SCORES = scorer.score_all(
        tenders=DATA_STORE["tenders"],
        companies=DATA_STORE["companies"],
        directors=DATA_STORE["directors"],
        officials=DATA_STORE["officials"],
        bids=DATA_STORE["bids"],
        graph=GRAPH,
    )

    # Update graph with risk levels
    for tender_id, risk in RISK_SCORES.items():
        if tender_id in GRAPH:
            GRAPH.nodes[tender_id]["risk_level"] = risk.category.value

    # Persist risk scores to DB
    await persist_risk_scores(RISK_SCORES)

    print(f"Loaded {len(DATA_STORE['tenders'])} tenders from PostgreSQL")
    print(
        f"Built graph with {GRAPH.number_of_nodes()} nodes and {GRAPH.number_of_edges()} edges"
    )
    print(f"Computed and persisted {len(RISK_SCORES)} risk scores")

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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"name": "Sentinel API", "status": "operational", "version": "0.2.0"}


@app.get("/api/stats", response_model=DashboardStats)
def get_dashboard_stats():
    """Get dashboard statistics."""
    tenders = DATA_STORE["tenders"]

    high_risk = sum(1 for r in RISK_SCORES.values() if r.category == RiskCategory.HIGH)
    medium_risk = sum(
        1 for r in RISK_SCORES.values() if r.category == RiskCategory.MEDIUM
    )
    low_risk = sum(1 for r in RISK_SCORES.values() if r.category == RiskCategory.LOW)

    pending = sum(
        1
        for t in tenders.values()
        if t.status in [TenderStatus.OPEN, TenderStatus.EVALUATION]
    )

    total_value = sum(t.estimated_value for t in tenders.values())
    flagged_today = high_risk

    return DashboardStats(
        total_tenders=len(tenders),
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        low_risk_count=low_risk,
        pending_review=pending,
        total_value=total_value,
        flagged_today=flagged_today,
    )


@app.get("/api/tenders", response_model=list[TenderWithRisk])
def get_tenders(
    risk_level: Optional[RiskCategory] = Query(
        None, description="Filter by risk level"
    ),
    status: Optional[TenderStatus] = Query(None, description="Filter by tender status"),
    sort_by: str = Query("risk", description="Sort by: risk, value, date"),
    limit: int = Query(50, ge=1, le=100),
):
    """Get list of tenders with risk scores."""
    tenders = DATA_STORE["tenders"]
    bids_by_tender = DATA_STORE["bids_by_tender"]

    results = []
    for tender_id, tender in tenders.items():
        risk = RISK_SCORES.get(
            tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
        )

        if risk_level and risk.category != risk_level:
            continue
        if status and tender.status != status:
            continue

        bidder_count = len(bids_by_tender.get(tender_id, []))

        results.append(
            TenderWithRisk(tender=tender, risk=risk, bidder_count=bidder_count)
        )

    if sort_by == "risk":
        results.sort(key=lambda x: x.risk.overall, reverse=True)
    elif sort_by == "value":
        results.sort(key=lambda x: x.tender.estimated_value, reverse=True)
    elif sort_by == "date":
        results.sort(key=lambda x: x.tender.published_date, reverse=True)

    return results[:limit]


@app.get("/api/tenders/{tender_id}", response_model=TenderDetail)
def get_tender_detail(tender_id: str):
    """Get detailed tender information with full risk breakdown."""
    tenders = DATA_STORE["tenders"]
    companies = DATA_STORE["companies"]
    bids_by_tender = DATA_STORE["bids_by_tender"]

    if tender_id not in tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = tenders[tender_id]
    risk = RISK_SCORES.get(tender_id, RiskScore(overall=0, category=RiskCategory.LOW))
    tender_bids = bids_by_tender.get(tender_id, [])

    winning_company = None
    if tender.awarded_to and tender.awarded_to in companies:
        winning_company = companies[tender.awarded_to]

    return TenderDetail(
        tender=tender, risk=risk, bids=tender_bids, winning_company=winning_company
    )


@app.get("/api/tenders/{tender_id}/graph", response_model=GraphData)
def get_tender_graph(tender_id: str, depth: int = Query(2, ge=1, le=3)):
    """Get subgraph of entities connected to a specific tender."""
    if tender_id not in DATA_STORE["tenders"]:
        raise HTTPException(status_code=404, detail="Tender not found")

    subgraph = get_tender_subgraph(GRAPH, tender_id, depth=depth)
    return graph_to_frontend_format(subgraph)


@app.get("/api/graph/explore", response_model=GraphData)
def get_full_graph():
    """Get the full shadow graph for exploration."""
    return graph_to_frontend_format(GRAPH)


@app.get("/api/graph/cartels")
def get_cartel_clusters():
    """Get detected cartel clusters (legacy endpoint)."""
    clusters = find_cartel_clusters(GRAPH, DATA_STORE["bids"])
    companies = DATA_STORE["companies"]

    result = []
    for cluster in clusters:
        result.append(
            {
                "company_ids": list(cluster),
                "company_names": [
                    companies[cid].name for cid in cluster if cid in companies
                ],
                "size": len(cluster),
            }
        )

    return {"cartels": result, "total": len(clusters)}


@app.get("/api/graph/communities")
def get_communities():
    """Get detected bidding communities with suspicion scores."""
    clusters = detect_communities(GRAPH, DATA_STORE["bids"], DATA_STORE["companies"])
    return {
        "clusters": [
            {
                "id": c.id,
                "company_ids": c.company_ids,
                "company_names": c.company_names,
                "size": c.size,
                "suspicion_score": round(c.suspicion_score, 1),
                "shared_attributes": c.shared_attributes,
                "co_bid_count": c.co_bid_count,
                "win_pattern": c.win_pattern,
            }
            for c in clusters
        ],
        "total": len(clusters),
    }


@app.get("/api/graph/communities/{cluster_id}", response_model=GraphData)
def get_community_graph(
    cluster_id: str,
    include_tenders: bool = Query(True),
    include_officials: bool = Query(True),
):
    """Get the subgraph for a specific community cluster."""
    clusters = detect_communities(GRAPH, DATA_STORE["bids"], DATA_STORE["companies"])
    cluster = next((c for c in clusters if c.id == cluster_id), None)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    subgraph = get_cluster_subgraph(
        GRAPH, cluster.company_ids, include_tenders, include_officials
    )
    return graph_to_frontend_format(subgraph)


@app.get("/api/graph/path")
def get_path(
    source: str = Query(..., description="Source entity ID"),
    target: str = Query(..., description="Target entity ID"),
):
    """Find shortest path between two entities in the graph."""
    result = find_shortest_path(GRAPH, source, target)
    if result is None:
        raise HTTPException(status_code=404, detail="No path found between entities")
    return result


@app.get("/api/graph/entity/{entity_id}", response_model=GraphData)
def get_entity_neighborhood(
    entity_id: str,
    depth: int = Query(2, ge=1, le=3),
):
    """Get k-hop neighborhood around any entity."""
    if entity_id not in GRAPH:
        raise HTTPException(status_code=404, detail="Entity not found in graph")

    subgraph = get_tender_subgraph(GRAPH, entity_id, depth=depth)
    return graph_to_frontend_format(subgraph)


@app.get("/api/companies/{company_id}")
def get_company(company_id: str):
    """Get company details."""
    companies = DATA_STORE["companies"]
    directors = DATA_STORE["directors"]

    if company_id not in companies:
        raise HTTPException(status_code=404, detail="Company not found")

    company = companies[company_id]
    company_directors = [
        directors[did] for did in company.director_ids if did in directors
    ]

    return {"company": company, "directors": company_directors}


@app.get("/api/tenders/{tender_id}/evidence")
def get_evidence_pack(tender_id: str):
    """Get structured evidence pack for a tender."""
    tenders = DATA_STORE["tenders"]
    companies = DATA_STORE["companies"]
    bids_by_tender = DATA_STORE["bids_by_tender"]

    if tender_id not in tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = tenders[tender_id]
    risk = RISK_SCORES.get(tender_id, RiskScore(overall=0, category=RiskCategory.LOW))
    tender_bids = bids_by_tender.get(tender_id, [])

    pack = build_evidence_pack(tender, risk, tender_bids, companies, GRAPH)
    return pack.to_dict()


@app.get("/api/tenders/{tender_id}/explain")
async def explain_tender_risk(tender_id: str):
    """Get AI-generated explanation for a tender's risk score."""
    tenders = DATA_STORE["tenders"]
    companies = DATA_STORE["companies"]
    bids_by_tender = DATA_STORE["bids_by_tender"]

    if tender_id not in tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = tenders[tender_id]
    risk = RISK_SCORES.get(tender_id, RiskScore(overall=0, category=RiskCategory.LOW))
    tender_bids = bids_by_tender.get(tender_id, [])

    pack = build_evidence_pack(tender, risk, tender_bids, companies, GRAPH)
    agent = get_agent()
    result = await agent.explain(pack)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
