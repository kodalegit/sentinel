"""Tender routes."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from models import (
    RiskScore,
    RiskCategory,
    TenderStatus,
    TenderWithRisk,
    TenderDetail,
)
from state import State
from intelligence.evidence import build_evidence_pack, build_evidence_pack_async
from intelligence.agent import get_agent

router = APIRouter(prefix="/api", tags=["tenders"])


@router.get("/tenders", response_model=list[TenderWithRisk])
def get_tenders(
    state: State,
    risk_level: Optional[RiskCategory] = Query(
        None, description="Filter by risk level"
    ),
    status: Optional[TenderStatus] = Query(None, description="Filter by tender status"),
    sort_by: str = Query("risk", description="Sort by: risk, value, date"),
    limit: int = Query(50, ge=1, le=100),
):
    """Get list of tenders with risk scores."""
    results = []
    for tender_id, tender in state.tenders.items():
        risk = state.risk_scores.get(
            tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
        )

        if risk_level and risk.category != risk_level:
            continue
        if status and tender.status != status:
            continue

        bidder_count = len(state.bids_by_tender.get(tender_id, []))

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


@router.get("/tenders/{tender_id}", response_model=TenderDetail)
def get_tender_detail(tender_id: str, state: State):
    """Get detailed tender information with full risk breakdown."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = state.tenders[tender_id]
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_bids = state.bids_by_tender.get(tender_id, [])

    winning_company = None
    if tender.awarded_to and tender.awarded_to in state.companies:
        winning_company = state.companies[tender.awarded_to]

    return TenderDetail(
        tender=tender, risk=risk, bids=tender_bids, winning_company=winning_company
    )


@router.get("/tenders/{tender_id}/evidence")
async def get_evidence_pack(tender_id: str, state: State):
    """Get structured evidence pack for a tender."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = state.tenders[tender_id]
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_bids = state.bids_by_tender.get(tender_id, [])

    pack = await build_evidence_pack_async(tender, risk, tender_bids, state.companies, state.graph)
    return pack.to_dict()


@router.get("/tenders/{tender_id}/explain")
async def explain_tender_risk(tender_id: str, state: State):
    """Get AI-generated explanation for a tender's risk score."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = state.tenders[tender_id]
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_bids = state.bids_by_tender.get(tender_id, [])

    # Use async variant so Neo4j paths are resolved before LLM prompt is built
    pack = await build_evidence_pack_async(tender, risk, tender_bids, state.companies, state.graph)
    agent = get_agent()
    result = await agent.explain(pack)
    return result

