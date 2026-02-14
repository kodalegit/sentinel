"""
Mappers between SQLAlchemy DB models and Pydantic API models.
Allows the existing risk engine and graph builder to work unchanged.
"""

from db.models import (
    CompanyDB,
    DirectorDB,
    OfficialDB,
    TenderDB,
    BidDB,
    RiskAssessmentDB,
    ContractDB,
    OwnershipDB,
)
from models import (
    Company,
    Director,
    PublicOfficial,
    Tender,
    Bid,
    RiskScore,
    RiskFactor,
    RiskFactorType,
    RiskCategory,
    TenderStatus,
    RelationshipType,
    Contract,
    Ownership,
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
        supplier_type=db_obj.supplier_type,
        brs_number=db_obj.brs_number,
        egp_registration_number=db_obj.egp_registration_number,
        contact_email=db_obj.contact_email,
        physical_address=db_obj.physical_address,
        postal_address=db_obj.postal_address,
        postal_code=db_obj.postal_code,
        source_system=db_obj.source_system,
        source_record_id=db_obj.source_record_id,
        data_quality_flags=db_obj.data_quality_flags,
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
        procurement_officer_id=(
            str(db_obj.procurement_officer_id)
            if db_obj.procurement_officer_id
            else None
        ),
        procurement_method=db_obj.procurement_method,
        procurement_category=db_obj.procurement_category,
        pe_type=db_obj.pe_type,
        currency=db_obj.currency,
        ocds_id=db_obj.ocds_id,
        buyer_id=db_obj.buyer_id,
        source_system=db_obj.source_system,
        source_record_id=db_obj.source_record_id,
        data_quality_flags=db_obj.data_quality_flags,
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
            factors.append(
                RiskFactor(
                    type=RiskFactorType(f["type"]),
                    description=f["description"],
                    weight=f["weight"],
                    evidence=f.get("evidence", []),
                    related_entity_ids=f.get("related_entity_ids", []),
                )
            )
    return RiskScore(
        overall=db_obj.overall_score,
        category=RiskCategory(db_obj.category),
        factors=factors,
        recommendation=db_obj.recommendation,
    )


def contract_to_pydantic(db_obj: ContractDB) -> Contract:
    return Contract(
        id=str(db_obj.id),
        tender_id=str(db_obj.tender_id) if db_obj.tender_id else None,
        company_id=str(db_obj.company_id) if db_obj.company_id else None,
        contract_number=db_obj.contract_number,
        title=db_obj.title,
        description=db_obj.description,
        contract_amount=db_obj.contract_amount,
        currency=db_obj.currency,
        start_date=db_obj.start_date,
        end_date=db_obj.end_date,
        effective_date=db_obj.effective_date,
        status=db_obj.status,
        procurement_method=db_obj.procurement_method,
        procurement_category=db_obj.procurement_category,
        agpo_group=db_obj.agpo_group,
        reservation_group=db_obj.reservation_group,
        is_agpo_reserved=db_obj.is_agpo_reserved,
        pe_name=db_obj.pe_name,
        pe_type=db_obj.pe_type,
        source_system=db_obj.source_system,
        source_record_id=db_obj.source_record_id,
    )


def ownership_to_pydantic(db_obj: OwnershipDB) -> Ownership:
    return Ownership(
        id=str(db_obj.id),
        company_id=str(db_obj.company_id),
        owner_name=db_obj.owner_name,
        nationality=db_obj.nationality,
        postal_address=db_obj.postal_address,
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
