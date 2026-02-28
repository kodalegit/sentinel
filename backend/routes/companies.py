"""Company routes."""

from fastapi import APIRouter, HTTPException

from state import State
from graph.neo4j_driver import check_neo4j_health
from config import settings

router = APIRouter(prefix="/api", tags=["companies"])


@router.get("/companies/{company_id}")
def get_company(company_id: str, state: State):
    """Get company details including directors."""
    if company_id not in state.companies:
        raise HTTPException(status_code=404, detail="Company not found")

    company = state.companies[company_id]
    company_directors = [
        state.directors[did] for did in company.director_ids if did in state.directors
    ]

    return {"company": company, "directors": company_directors}
