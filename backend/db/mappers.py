"""
Mappers between SQLAlchemy DB models and Pydantic API models.
Allows the existing risk engine and graph builder to work unchanged.
"""

from db.models import (
    CompanyDB, DirectorDB, OfficialDB,
    TenderDB, BidDB, RiskAssessmentDB,
)
from models import (
    Company, Director, PublicOfficial, Tender, Bid,
    RiskScore, RiskFactor, RiskFactorType, RiskCategory,
    TenderStatus, RelationshipType,
)


def company_to_pydantic(db_obj: CompanyDB) -> Company:
    return Company(
        id=str(db_obj.id),
        name=db_obj.name,
        registration_number=db_obj.registration_number,
        registration_date=db_obj.registration_date,
        address=db_obj.address,
        phone=db_obj.phone,
        director_ids=[str(d.id) for d in db_obj.directors] if db_obj.directors else [],
    )


def director_to_pydantic(db_obj: DirectorDB) -> Director:
    return Director(
        id=str(db_obj.id),
        name=db_obj.name,
        national_id=db_obj.national_id,
        company_ids=[str(c.id) for c in db_obj.companies] if db_obj.companies else [],
    )


def official_to_pydantic(db_obj: OfficialDB) -> PublicOfficial:
    related = {}
    if db_obj.related_persons:
        for rel in db_obj.related_persons:
            related[str(rel.person_id)] = RelationshipType(rel.relationship_type)
    return PublicOfficial(
        id=str(db_obj.id),
        name=db_obj.name,
        department=db_obj.department,
        position=db_obj.position,
        related_persons=related,
    )


def tender_to_pydantic(db_obj: TenderDB) -> Tender:
    return Tender(
        id=str(db_obj.id),
        reference_number=db_obj.reference_number,
        title=db_obj.title,
        description=db_obj.description or "",
        procuring_entity=db_obj.procuring_entity,
        category=db_obj.category or "",
        estimated_value=db_obj.estimated_value,
        published_date=db_obj.published_date,
        deadline=db_obj.deadline,
        status=TenderStatus(db_obj.status),
        awarded_to=str(db_obj.awarded_to) if db_obj.awarded_to else None,
        awarded_amount=db_obj.awarded_amount,
        procurement_officer_id=str(db_obj.procurement_officer_id) if db_obj.procurement_officer_id else None,
    )


def bid_to_pydantic(db_obj: BidDB) -> Bid:
    return Bid(
        id=str(db_obj.id),
        tender_id=str(db_obj.tender_id),
        company_id=str(db_obj.company_id),
        amount=db_obj.amount,
        submission_date=db_obj.submission_date,
        technical_score=db_obj.technical_score,
    )


def risk_assessment_to_pydantic(db_obj: RiskAssessmentDB) -> RiskScore:
    """Convert a DB risk assessment back to the Pydantic RiskScore."""
    factors = []
    if db_obj.rule_factors:
        for f in db_obj.rule_factors:
            factors.append(RiskFactor(
                type=RiskFactorType(f["type"]),
                description=f["description"],
                weight=f["weight"],
                evidence=f.get("evidence", []),
                related_entity_ids=f.get("related_entity_ids", []),
            ))
    return RiskScore(
        overall=db_obj.overall_score,
        category=RiskCategory(db_obj.category),
        factors=factors,
        recommendation=db_obj.recommendation,
    )


def risk_factors_to_json(factors: list[RiskFactor]) -> list[dict]:
    """Serialize risk factors for JSON storage in DB."""
    return [
        {
            "type": f.type.value,
            "description": f.description,
            "weight": f.weight,
            "evidence": f.evidence,
            "related_entity_ids": f.related_entity_ids,
        }
        for f in factors
    ]
