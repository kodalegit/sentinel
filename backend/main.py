"""
Sentinel API - FastAPI backend for public procurement oversight.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import networkx as nx

from models import (
    Tender, Company, Director, PublicOfficial, Bid,
    RiskScore, RiskCategory, TenderStatus,
    TenderWithRisk, TenderDetail, GraphData, DashboardStats
)
from data.synthetic import get_data_store
from graph.builder import (
    build_procurement_graph, get_tender_subgraph,
    graph_to_frontend_format, find_cartel_clusters
)
from risk.engine import compute_all_risk_scores


# Global data store (in-memory for MVP)
DATA_STORE = {}
GRAPH: nx.Graph = None
RISK_SCORES: dict[str, RiskScore] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize data on startup."""
    global DATA_STORE, GRAPH, RISK_SCORES
    
    # Load synthetic data
    DATA_STORE = get_data_store()
    
    # Build the shadow graph
    GRAPH = build_procurement_graph(
        tenders=DATA_STORE["tenders"],
        companies=DATA_STORE["companies"],
        directors=DATA_STORE["directors"],
        officials=DATA_STORE["officials"],
        bids=DATA_STORE["bids"],
    )
    
    # Compute risk scores for all tenders
    RISK_SCORES = compute_all_risk_scores(
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
    
    print(f"✓ Loaded {len(DATA_STORE['tenders'])} tenders")
    print(f"✓ Built graph with {GRAPH.number_of_nodes()} nodes and {GRAPH.number_of_edges()} edges")
    print(f"✓ Computed {len(RISK_SCORES)} risk scores")
    
    yield
    
    # Cleanup if needed
    print("Shutting down Sentinel API")


app = FastAPI(
    title="Sentinel API",
    description="Public Procurement Guardian - AI-powered oversight system",
    version="0.1.0",
    lifespan=lifespan
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
    return {
        "name": "Sentinel API",
        "status": "operational",
        "version": "0.1.0"
    }


@app.get("/api/stats", response_model=DashboardStats)
def get_dashboard_stats():
    """Get dashboard statistics."""
    tenders = DATA_STORE["tenders"]
    
    high_risk = sum(1 for r in RISK_SCORES.values() if r.category == RiskCategory.HIGH)
    medium_risk = sum(1 for r in RISK_SCORES.values() if r.category == RiskCategory.MEDIUM)
    low_risk = sum(1 for r in RISK_SCORES.values() if r.category == RiskCategory.LOW)
    
    pending = sum(
        1 for t in tenders.values()
        if t.status in [TenderStatus.OPEN, TenderStatus.EVALUATION]
    )
    
    total_value = sum(t.estimated_value for t in tenders.values())
    
    # Count tenders flagged with high risk (simulating "today")
    flagged_today = high_risk  # For demo purposes
    
    return DashboardStats(
        total_tenders=len(tenders),
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        low_risk_count=low_risk,
        pending_review=pending,
        total_value=total_value,
        flagged_today=flagged_today
    )


@app.get("/api/tenders", response_model=list[TenderWithRisk])
def get_tenders(
    risk_level: Optional[RiskCategory] = Query(None, description="Filter by risk level"),
    status: Optional[TenderStatus] = Query(None, description="Filter by tender status"),
    sort_by: str = Query("risk", description="Sort by: risk, value, date"),
    limit: int = Query(50, ge=1, le=100)
):
    """Get list of tenders with risk scores."""
    tenders = DATA_STORE["tenders"]
    bids_by_tender = DATA_STORE["bids_by_tender"]
    
    results = []
    for tender_id, tender in tenders.items():
        risk = RISK_SCORES.get(tender_id, RiskScore(overall=0, category=RiskCategory.LOW))
        
        # Apply filters
        if risk_level and risk.category != risk_level:
            continue
        if status and tender.status != status:
            continue
        
        bidder_count = len(bids_by_tender.get(tender_id, []))
        
        results.append(TenderWithRisk(
            tender=tender,
            risk=risk,
            bidder_count=bidder_count
        ))
    
    # Sort
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
        tender=tender,
        risk=risk,
        bids=tender_bids,
        winning_company=winning_company
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
    """Get detected cartel clusters."""
    clusters = find_cartel_clusters(GRAPH, DATA_STORE["bids"])
    companies = DATA_STORE["companies"]
    
    result = []
    for cluster in clusters:
        result.append({
            "company_ids": list(cluster),
            "company_names": [companies[cid].name for cid in cluster if cid in companies],
            "size": len(cluster)
        })
    
    return {"cartels": result, "total": len(clusters)}


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
    
    return {
        "company": company,
        "directors": company_directors
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
