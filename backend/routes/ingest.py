"""
Ingestion API routes for Sentinel.
Provides endpoints for PPIP OCDS sync and e-GP payload ingestion.
Requires supervisor or admin role.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from connectors.ppip import sync_ppip_fiscal_year
from connectors.egp import normalize_egp_tenders, normalize_egp_contract
from db.config import async_session
from auth.dependencies import SupervisorOrAdmin
from db.models import (
    CompanyDB,
    DirectorDB,
    TenderDB,
    BidDB,
    ContractDB,
    OwnershipDB,
    CompanyDirectorDB,
)
from connectors.normalize import normalize_datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PPIPSyncRequest(BaseModel):
    fiscal_year: str = Field(..., description="Fiscal year e.g. '2025-2026'")


class PPIPSyncAcceptedResponse(BaseModel):
    status: str
    fiscal_year: str
    job_id: str


class PPIPSyncStatusResponse(BaseModel):
    status: str
    fiscal_year: str
    stats: dict | None = None
    error: str | None = None
    processed_releases: int | None = None
    total_releases: int | None = None


class EGPTenderRequest(BaseModel):
    respData: Optional[dict] = None
    tenderDetails: Optional[list[dict]] = None


class EGPContractRequest(BaseModel):
    contracts: list[dict] = Field(
        ..., description="List of e-GP contract detail payloads"
    )


class IngestResponse(BaseModel):
    status: str
    message: str
    counts: dict = Field(default_factory=dict)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


_ppip_sync_jobs: dict[str, dict[str, Any]] = {}
PPIP_PERSIST_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Helper: persist entities to DB
# ---------------------------------------------------------------------------


def _chunked(values: list[Any], size: int = 1000):
    for i in range(0, len(values), size):
        yield values[i : i + size]


async def _load_companies_by_registration(
    db, registration_numbers: list[str]
) -> dict[str, CompanyDB]:
    companies: dict[str, CompanyDB] = {}
    unique_numbers = [value for value in dict.fromkeys(registration_numbers) if value]
    for chunk in _chunked(unique_numbers):
        result = await db.execute(
            select(CompanyDB).where(CompanyDB.registration_number.in_(chunk))
        )
        for company in result.scalars():
            companies[company.registration_number] = company
    return companies


async def _load_tenders_by_reference(
    db, reference_numbers: list[str]
) -> dict[str, TenderDB]:
    tenders: dict[str, TenderDB] = {}
    unique_numbers = [value for value in dict.fromkeys(reference_numbers) if value]
    for chunk in _chunked(unique_numbers):
        result = await db.execute(
            select(TenderDB).where(TenderDB.reference_number.in_(chunk))
        )
        for tender in result.scalars():
            tenders[tender.reference_number] = tender
    return tenders


async def _load_contracts_by_number(
    db, contract_numbers: list[str]
) -> dict[str, ContractDB]:
    contracts: dict[str, ContractDB] = {}
    unique_numbers = [value for value in dict.fromkeys(contract_numbers) if value]
    for chunk in _chunked(unique_numbers):
        result = await db.execute(
            select(ContractDB).where(ContractDB.contract_number.in_(chunk))
        )
        for contract in result.scalars():
            contracts[contract.contract_number] = contract
    return contracts


async def _load_bids_by_tender_ids(
    db, tender_ids: list[uuid.UUID]
) -> dict[tuple[str, str], BidDB]:
    bids: dict[tuple[str, str], BidDB] = {}
    unique_ids = list(dict.fromkeys(tender_ids))
    for chunk in _chunked(unique_ids):
        result = await db.execute(select(BidDB).where(BidDB.tender_id.in_(chunk)))
        for bid in result.scalars():
            bids[(str(bid.tender_id), str(bid.company_id))] = bid
    return bids


async def _persist_company(
    db,
    company,
    existing_companies: Optional[dict[str, CompanyDB]] = None,
) -> Optional[CompanyDB]:
    """Persist a company, skipping duplicates by registration_number."""
    existing = None
    if existing_companies is not None:
        existing = existing_companies.get(company.registration_number)
    else:
        result = await db.execute(
            select(CompanyDB).where(
                CompanyDB.registration_number == company.registration_number
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        updated = False

        def maybe_fill(attr_name, value):
            nonlocal updated
            if value in (None, ""):
                return
            current = getattr(existing, attr_name)
            if current in (None, ""):
                setattr(existing, attr_name, value)
                updated = True

        maybe_fill("name", company.name)
        maybe_fill("registration_date", company.registration_date)
        maybe_fill("address", company.address)
        maybe_fill("phone", company.phone)
        maybe_fill("physical_address", company.physical_address)
        maybe_fill("postal_address", company.postal_address)
        maybe_fill("postal_code", company.postal_code)
        maybe_fill("contact_email", company.contact_email)
        maybe_fill("supplier_type", company.supplier_type)
        maybe_fill("brs_number", company.brs_number)
        maybe_fill("egp_registration_number", company.egp_registration_number)
        maybe_fill("source_system", company.source_system)
        maybe_fill("source_record_id", company.source_record_id)

        incoming_quality = company.data_quality_flags or {}
        existing_quality = existing.data_quality_flags or {}
        if incoming_quality and (
            not existing_quality
            or incoming_quality.get("quality_score", 0)
            > existing_quality.get("quality_score", 0)
        ):
            existing.data_quality_flags = incoming_quality
            updated = True

        if updated:
            existing.ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return existing

    db_company = CompanyDB(
        id=uuid.uuid4(),
        name=company.name,
        registration_number=company.registration_number,
        registration_date=company.registration_date,
        address=company.address,
        phone=company.phone,
        physical_address=company.physical_address,
        postal_address=company.postal_address,
        postal_code=company.postal_code,
        contact_email=company.contact_email,
        supplier_type=company.supplier_type,
        brs_number=company.brs_number,
        egp_registration_number=company.egp_registration_number,
        source_system=company.source_system,
        source_record_id=company.source_record_id,
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
        data_quality_flags=company.data_quality_flags,
    )
    db.add(db_company)
    if existing_companies is not None:
        existing_companies[company.registration_number] = db_company
    return db_company


async def _persist_tender(
    db,
    tender,
    existing_tenders: Optional[dict[str, TenderDB]] = None,
) -> Optional[TenderDB]:
    """Persist a tender, skipping duplicates by reference_number."""
    existing = None
    if existing_tenders is not None:
        existing = existing_tenders.get(tender.reference_number)
    else:
        result = await db.execute(
            select(TenderDB).where(TenderDB.reference_number == tender.reference_number)
        )
        existing = result.scalar_one_or_none()

    if existing:
        if tender.awarded_to and existing.awarded_to is None:
            existing.awarded_to = tender.awarded_to
        if tender.awarded_amount and existing.awarded_amount is None:
            existing.awarded_amount = tender.awarded_amount
        incoming_status = (
            tender.status.value if hasattr(tender.status, "value") else tender.status
        )
        if existing.status != incoming_status and incoming_status == "AWARDED":
            existing.status = incoming_status
        if tender.ocds_id and not existing.ocds_id:
            existing.ocds_id = tender.ocds_id
        if tender.source_record_id and not existing.source_record_id:
            existing.source_record_id = tender.source_record_id
        return existing

    db_tender = TenderDB(
        id=uuid.uuid4(),
        reference_number=tender.reference_number,
        title=tender.title,
        description=tender.description,
        procuring_entity=tender.procuring_entity,
        category=tender.category,
        estimated_value=tender.estimated_value,
        awarded_amount=tender.awarded_amount,
        published_date=tender.published_date,
        deadline=tender.deadline,
        status=(
            tender.status.value if hasattr(tender.status, "value") else tender.status
        ),
        procurement_method=tender.procurement_method,
        procurement_category=tender.procurement_category,
        pe_type=tender.pe_type,
        currency=tender.currency,
        ocds_id=tender.ocds_id,
        buyer_id=tender.buyer_id,
        source_system=tender.source_system,
        source_record_id=tender.source_record_id,
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(db_tender)
    if existing_tenders is not None:
        existing_tenders[tender.reference_number] = db_tender
    return db_tender


async def _persist_bid(
    db,
    bid,
    tender_db_id,
    company_db_id,
    existing_bids: Optional[dict[tuple[str, str], BidDB]] = None,
) -> Optional[BidDB]:
    """Persist a bid, skipping duplicates by tender/company."""
    normalized_submission_date = normalize_datetime(bid.submission_date)
    bid_key = (str(tender_db_id), str(company_db_id))
    existing = None
    if existing_bids is not None:
        existing = existing_bids.get(bid_key)
    else:
        result = await db.execute(
            select(BidDB).where(
                BidDB.tender_id == tender_db_id,
                BidDB.company_id == company_db_id,
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        if existing.amount is None and bid.amount is not None:
            existing.amount = bid.amount
        if existing.technical_score is None and bid.technical_score is not None:
            existing.technical_score = bid.technical_score
        return existing

    db_bid = BidDB(
        id=uuid.uuid4(),
        tender_id=tender_db_id,
        company_id=company_db_id,
        amount=bid.amount,
        submission_date=normalized_submission_date,
        technical_score=bid.technical_score,
    )
    db.add(db_bid)
    if existing_bids is not None:
        existing_bids[bid_key] = db_bid
    return db_bid


async def _persist_contract(
    db,
    contract,
    tender_db_id=None,
    company_db_id=None,
    existing_contracts: Optional[dict[str, ContractDB]] = None,
) -> Optional[ContractDB]:
    """Persist a contract, skipping duplicates by contract_number."""
    existing = None
    if existing_contracts is not None:
        existing = existing_contracts.get(contract.contract_number)
    else:
        result = await db.execute(
            select(ContractDB).where(
                ContractDB.contract_number == contract.contract_number
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        return existing

    resolved_tender_id = tender_db_id or contract.tender_id
    resolved_company_id = company_db_id or contract.company_id

    db_contract = ContractDB(
        id=uuid.uuid4(),
        tender_id=resolved_tender_id,
        company_id=resolved_company_id,
        contract_number=contract.contract_number,
        title=contract.title,
        description=contract.description,
        contract_amount=contract.contract_amount,
        currency=contract.currency,
        start_date=contract.start_date,
        end_date=contract.end_date,
        effective_date=contract.effective_date,
        status=contract.status,
        procurement_method=contract.procurement_method,
        procurement_category=contract.procurement_category,
        agpo_group=contract.agpo_group,
        reservation_group=contract.reservation_group,
        is_agpo_reserved=contract.is_agpo_reserved,
        pe_name=contract.pe_name,
        pe_type=contract.pe_type,
        source_system=contract.source_system,
        source_record_id=contract.source_record_id,
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(db_contract)
    if existing_contracts is not None:
        existing_contracts[contract.contract_number] = db_contract
    return db_contract


async def _run_ppip_sync(fiscal_year: str, job: dict[str, Any] | None = None) -> dict:
    try:
        result = await sync_ppip_fiscal_year(fiscal_year)
    except Exception as e:
        logger.error(f"PPIP fetch failed: {e}")
        raise HTTPException(status_code=502, detail=f"PPIP API error: {str(e)}")

    tenders_saved = 0
    companies_saved = 0
    bids_saved = 0
    contracts_saved = 0
    total_releases = len(result["releases"])
    if job is not None:
        job["processed_releases"] = 0
        job["total_releases"] = total_releases
    registration_numbers = list(
        {
            company.registration_number
            for release_bundle in result["releases"]
            for company in release_bundle["companies"]
            if company.registration_number
        }
    )
    reference_numbers = list(
        {
            release_bundle["tender"].reference_number
            for release_bundle in result["releases"]
            if release_bundle["tender"].reference_number
        }
    )
    contract_numbers = list(
        {
            contract.contract_number
            for release_bundle in result["releases"]
            for contract in release_bundle["contracts"]
            if contract.contract_number
        }
    )

    async with async_session() as db:
        try:
            existing_companies = await _load_companies_by_registration(
                db, registration_numbers
            )
            existing_tenders = await _load_tenders_by_reference(db, reference_numbers)
            existing_contracts = await _load_contracts_by_number(db, contract_numbers)
            existing_bids = await _load_bids_by_tender_ids(
                db, [tender.id for tender in existing_tenders.values()]
            )

            for index, release_bundle in enumerate(result["releases"], start=1):
                company_id_map: dict[str, str] = {}

                for company in release_bundle["companies"]:
                    saved_company = await _persist_company(
                        db,
                        company,
                        existing_companies=existing_companies,
                    )
                    if saved_company:
                        company_id_map[company.id] = saved_company.id
                        companies_saved += 1

                tender = release_bundle["tender"]
                if tender.awarded_to:
                    tender.awarded_to = company_id_map.get(tender.awarded_to)
                saved_tender = await _persist_tender(
                    db,
                    tender,
                    existing_tenders=existing_tenders,
                )
                tender_db_id = saved_tender.id if saved_tender else None
                if saved_tender:
                    tenders_saved += 1

                if tender_db_id:
                    for bid in release_bundle["bids"]:
                        company_db_id = company_id_map.get(bid.company_id)
                        if not company_db_id:
                            continue
                        saved_bid = await _persist_bid(
                            db,
                            bid,
                            tender_db_id=tender_db_id,
                            company_db_id=company_db_id,
                            existing_bids=existing_bids,
                        )
                        if saved_bid:
                            bids_saved += 1

                    for contract in release_bundle["contracts"]:
                        company_db_id = (
                            company_id_map.get(contract.company_id)
                            if contract.company_id
                            else None
                        )
                        saved_contract = await _persist_contract(
                            db,
                            contract,
                            tender_db_id=tender_db_id,
                            company_db_id=company_db_id,
                            existing_contracts=existing_contracts,
                        )
                        if saved_contract:
                            contracts_saved += 1

                if index % PPIP_PERSIST_BATCH_SIZE == 0:
                    await db.flush()
                    await db.commit()
                    if job is not None:
                        job["processed_releases"] = index
                    logger.info(
                        "PPIP sync FY %s persisted %s/%s release bundles",
                        fiscal_year,
                        index,
                        total_releases,
                    )

            await db.flush()
            await db.commit()
            if job is not None:
                job["processed_releases"] = total_releases
        except Exception:
            await db.rollback()
            raise

    stats = result["stats"]
    stats["tenders_persisted"] = tenders_saved
    stats["companies_persisted"] = companies_saved
    stats["bids_persisted"] = bids_saved
    stats["contracts_persisted"] = contracts_saved

    return {
        "status": "ok",
        "fiscal_year": fiscal_year,
        "stats": stats,
    }


async def _run_ppip_sync_job(job_id: str, fiscal_year: str):
    _ppip_sync_jobs[job_id]["status"] = JobStatus.RUNNING
    _ppip_sync_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        result = await _run_ppip_sync(fiscal_year, _ppip_sync_jobs[job_id])
        _ppip_sync_jobs[job_id].update(
            status=JobStatus.DONE,
            fiscal_year=fiscal_year,
            stats=result["stats"],
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.info("PPIP sync job %s completed for FY %s", job_id, fiscal_year)
    except HTTPException as e:
        _ppip_sync_jobs[job_id].update(
            status=JobStatus.FAILED,
            fiscal_year=fiscal_year,
            error=str(e.detail),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.error(
            "PPIP sync job %s failed for FY %s: %s", job_id, fiscal_year, e.detail
        )
    except Exception as e:
        _ppip_sync_jobs[job_id].update(
            status=JobStatus.FAILED,
            fiscal_year=fiscal_year,
            error=str(e),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        logger.error("PPIP sync job %s failed for FY %s: %s", job_id, fiscal_year, e)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ppip/sync", response_model=PPIPSyncAcceptedResponse, status_code=202)
async def sync_ppip(
    request: PPIPSyncRequest,
    current_user: SupervisorOrAdmin,
):
    """
    Sync PPIP OCDS tenders for a given fiscal year.
    Fetches from tenders.go.ke, normalizes, and persists.
    Requires supervisor or admin role.
    """
    job_id = str(uuid.uuid4())
    _ppip_sync_jobs[job_id] = {
        "status": JobStatus.PENDING,
        "fiscal_year": request.fiscal_year,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": current_user.username,
        "processed_releases": 0,
        "total_releases": None,
    }
    asyncio.create_task(_run_ppip_sync_job(job_id, request.fiscal_year))
    return PPIPSyncAcceptedResponse(
        status="accepted",
        fiscal_year=request.fiscal_year,
        job_id=job_id,
    )


@router.get("/ppip/sync/status/{job_id}", response_model=PPIPSyncStatusResponse)
async def sync_ppip_status(job_id: str, current_user: SupervisorOrAdmin):
    job = _ppip_sync_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    raw_status = job["status"]
    status = raw_status.value if isinstance(raw_status, JobStatus) else str(raw_status)
    return PPIPSyncStatusResponse(
        status=status,
        fiscal_year=job["fiscal_year"],
        stats=job.get("stats"),
        error=job.get("error"),
        processed_releases=job.get("processed_releases"),
        total_releases=job.get("total_releases"),
    )


@router.post("/egp/tenders", response_model=IngestResponse)
async def ingest_egp_tenders(
    request: EGPTenderRequest, current_user: SupervisorOrAdmin
):
    """
    Ingest e-GP tender list payload.
    Accepts the shape returned by Kenya's e-GP tender API.
    Requires supervisor or admin role.
    """
    payload = {}
    if request.respData:
        payload = {"respData": request.respData}
    elif request.tenderDetails:
        payload = {"respData": {"tenderDetails": request.tenderDetails}}
    else:
        raise HTTPException(status_code=400, detail="Provide respData or tenderDetails")

    tenders = normalize_egp_tenders(payload)
    saved_count = 0

    async with async_session() as db:
        async with db.begin():
            for tender in tenders:
                saved = await _persist_tender(db, tender)
                if saved:
                    saved_count += 1

    return IngestResponse(
        status="ok",
        message=f"Ingested {saved_count} tenders from e-GP",
        counts={"tenders_normalized": len(tenders), "tenders_persisted": saved_count},
    )


@router.post("/egp/contracts", response_model=IngestResponse)
async def ingest_egp_contracts(
    request: EGPContractRequest, current_user: SupervisorOrAdmin
):
    """
    Ingest e-GP contract detail payloads.
    Each item should have contractmaindata, contractmoredetails, supplierdetails.
    """
    tenders_saved = 0
    companies_saved = 0
    contracts_saved = 0
    directors_saved = 0
    ownership_saved = 0

    async with async_session() as db:
        async with db.begin():
            for payload in request.contracts:
                result = normalize_egp_contract(payload)
                if not result:
                    continue

                # Persist company
                company = result["company"]
                db_company = await _persist_company(db, company)
                company_db_id = db_company.id if db_company else None

                # Persist directors
                for director in result["directors"]:
                    from sqlalchemy import select

                    existing = await db.execute(
                        select(DirectorDB).where(DirectorDB.name == director.name)
                    )
                    db_director = existing.scalar_one_or_none()
                    if not db_director:
                        db_director = DirectorDB(name=director.name)
                        db.add(db_director)
                        await db.flush()
                        directors_saved += 1

                    # Link to company
                    if company_db_id:
                        existing_link = await db.execute(
                            select(CompanyDirectorDB).where(
                                CompanyDirectorDB.company_id == company_db_id,
                                CompanyDirectorDB.director_id == db_director.id,
                            )
                        )
                        if not existing_link.scalar_one_or_none():
                            db.add(
                                CompanyDirectorDB(
                                    company_id=company_db_id,
                                    director_id=db_director.id,
                                )
                            )

                # Persist ownership records
                for ownership in result["ownership"]:
                    if company_db_id:
                        db.add(
                            OwnershipDB(
                                company_id=company_db_id,
                                owner_name=ownership.owner_name,
                                nationality=ownership.nationality,
                                postal_address=ownership.postal_address,
                            )
                        )
                        ownership_saved += 1

                # Persist tender stub (if available)
                tender_db_id = None
                if result.get("tender"):
                    db_tender = await _persist_tender(db, result["tender"])
                    if db_tender:
                        tender_db_id = db_tender.id
                        # Link awarded_to
                        if company_db_id and not db_tender.awarded_to:
                            db_tender.awarded_to = company_db_id
                        tenders_saved += 1

                # Persist contract
                contract = result["contract"]
                db_contract = await _persist_contract(
                    db,
                    contract,
                    tender_db_id=tender_db_id,
                    company_db_id=company_db_id,
                )
                if db_contract:
                    contracts_saved += 1

            await db.flush()

    return IngestResponse(
        status="ok",
        message=f"Ingested {contracts_saved} contracts from e-GP",
        counts={
            "tenders": tenders_saved,
            "companies": companies_saved,
            "contracts": contracts_saved,
            "directors": directors_saved,
            "ownership_records": ownership_saved,
        },
    )
