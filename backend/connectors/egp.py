"""
e-GP Ingestion Adapter.
Accepts Kenya e-GP platform payloads (tender lists and contract details),
normalizes to internal schema, and returns structured data for persistence.
"""

import logging
import uuid
from typing import Optional

from connectors.normalize import (
    parse_date,
    parse_datetime,
    normalize_name,
    clean_amount,
    classify_address,
    compute_company_quality_flags,
)
from models import (
    Tender,
    Company,
    Director,
    Contract,
    Ownership,
    TenderStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# e-GP Tender List Ingestion
# ---------------------------------------------------------------------------


def normalize_egp_tenders(payload: dict) -> list[Tender]:
    """
    Normalize e-GP tender list response.
    Expected shape: {"respData": {"totalCount": N, "tenderDetails": [...]}}
    """
    resp_data = payload.get("respData", payload)
    tender_details = resp_data.get("tenderDetails", [])

    tenders = []
    for item in tender_details:
        ref = item.get("tenderrefno", "")
        if not ref:
            continue

        deadline = parse_datetime(item.get("bidsubmissionenddate"))
        published = parse_datetime(item.get("bidsubmissionstartdate"))

        tenders.append(
            Tender(
                id=str(uuid.uuid4()),
                reference_number=ref,
                title=item.get("tendertitle", "Untitled").strip(),
                procuring_entity=item.get("procuringEntity", "Unknown").strip(),
                category=item.get("procurementCategory"),
                procurement_method=item.get("procurementMethod"),
                procurement_category=item.get("procurementCategory"),
                published_date=published.date() if published else None,
                deadline=deadline.date() if deadline else None,
                status=TenderStatus.OPEN,
                source_system="egp",
                source_record_id=str(item.get("tenderdetailid", ref)),
            )
        )

    logger.info(f"e-GP: Normalized {len(tenders)} tenders from payload")
    return tenders


# ---------------------------------------------------------------------------
# e-GP Contract Detail Ingestion
# ---------------------------------------------------------------------------


def normalize_egp_contract(payload: dict) -> dict:
    """
    Normalize a single e-GP contract detail payload.
    Expected shape: {"contractmaindata": {...}, "contractmoredetails": {...}, "supplierdetails": {...}}

    Returns dict with keys: tender, company, contract, directors, ownership
    """
    main = payload.get("contractmaindata", {})
    more = payload.get("contractmoredetails", {})
    supplier = payload.get("supplierdetails", {})
    supplier_details = supplier.get("details", {})
    director_info = supplier.get("directorInfo", [])
    ownership_info = supplier.get("ownershipInfo", [])

    contract_number = main.get("contractNumber", "")
    if not contract_number:
        return {}

    # --- Build Company ---
    company_name = main.get("supplierName", "").strip()
    company_egp_id = str(main.get("companyId", ""))
    brs_number = supplier_details.get("brsNumber")
    egp_reg = supplier_details.get("egpRegistrationNumber")
    reg_number = brs_number or egp_reg or f"EGP-{company_egp_id}"

    physical_addr = supplier_details.get("pePhysicalAddress")
    postal_addr = supplier_details.get("pePostalAddress")
    contact_email = supplier_details.get("contactEmail")
    supplier_type = supplier_details.get("supplierType")

    quality_flags = compute_company_quality_flags(
        name=company_name,
        physical_address=physical_addr,
        postal_address=postal_addr,
        contact_email=contact_email,
        brs_number=brs_number,
        directors=director_info,
        ownership=ownership_info,
        source_system="egp",
    )

    company_id = str(uuid.uuid4())
    company = Company(
        id=company_id,
        name=company_name,
        registration_number=reg_number,
        address=physical_addr,
        physical_address=physical_addr,
        postal_address=postal_addr,
        contact_email=contact_email,
        supplier_type=supplier_type,
        brs_number=brs_number,
        egp_registration_number=egp_reg,
        source_system="egp",
        source_record_id=company_egp_id,
        data_quality_flags=quality_flags,
    )

    # --- Build Directors ---
    directors = []
    for d in director_info:
        name = d.get("name", "").strip()
        if not name:
            continue
        directors.append(
            Director(
                id=str(uuid.uuid4()),
                name=normalize_name(name) or name,
                company_ids=[company_id],
            )
        )

    # --- Build Ownership records ---
    ownership_records = []
    seen_owners = set()
    for o in ownership_info:
        name = o.get("name", "").strip()
        if not name:
            continue
        normalized = normalize_name(name)
        if normalized in seen_owners:
            continue
        seen_owners.add(normalized)
        ownership_records.append(
            Ownership(
                id=str(uuid.uuid4()),
                company_id=company_id,
                owner_name=normalized or name,
                nationality=o.get("nationality"),
                postal_address=o.get("postalAddress"),
            )
        )

    # --- Build Contract ---
    agpo_name = main.get("agpoName", "-")
    reservation = main.get("reservationGroup", "-")
    is_agpo = main.get("isReservationApplicable", "No") == "Yes"

    pe_physical = more.get("pePhysicalAddress", "")
    pe_postal = more.get("pePostalAddress", "")
    pe_type = more.get("peType")
    tender_ref = more.get("tenderReferenceNumber")

    contract = Contract(
        id=str(uuid.uuid4()),
        contract_number=contract_number,
        title=main.get("contractTitle") or main.get("description"),
        description=main.get("description"),
        contract_amount=clean_amount(main.get("contractAmount")),
        currency="KES",
        start_date=parse_date(main.get("startDate")),
        end_date=parse_date(main.get("endDate")),
        effective_date=parse_date(main.get("effectiveDate")),
        status=main.get("status"),
        procurement_method=main.get("procurementMethod")
        or more.get("procurementMethod"),
        procurement_category=main.get("procurementCategory"),
        agpo_group=agpo_name if agpo_name != "-" else None,
        reservation_group=reservation if reservation != "-" else None,
        is_agpo_reserved=is_agpo,
        pe_name=main.get("peName"),
        pe_type=pe_type,
        source_system="egp",
        source_record_id=contract_number,
    )

    # --- Build a stub Tender from contract data (for linking) ---
    tender = None
    if tender_ref:
        tender = Tender(
            id=str(uuid.uuid4()),
            reference_number=tender_ref,
            title=more.get("tenderTitle") or main.get("contractTitle", ""),
            procuring_entity=main.get("peName", "Unknown"),
            category=main.get("procurementCategory"),
            procurement_method=main.get("procurementMethod"),
            procurement_category=main.get("procurementCategory"),
            pe_type=pe_type,
            awarded_to=company_id,
            awarded_amount=clean_amount(main.get("contractAmount")),
            status=TenderStatus.AWARDED,
            source_system="egp",
            source_record_id=tender_ref,
        )

    return {
        "company": company,
        "directors": directors,
        "ownership": ownership_records,
        "contract": contract,
        "tender": tender,
    }


def normalize_egp_contracts(payloads: list[dict]) -> dict:
    """
    Normalize a batch of e-GP contract detail payloads.
    Returns aggregated dict with all entities.
    """
    all_companies = []
    all_directors = []
    all_ownership = []
    all_contracts = []
    all_tenders = []

    for payload in payloads:
        result = normalize_egp_contract(payload)
        if not result:
            continue

        all_companies.append(result["company"])
        all_directors.extend(result["directors"])
        all_ownership.extend(result["ownership"])
        all_contracts.append(result["contract"])
        if result.get("tender"):
            all_tenders.append(result["tender"])

    logger.info(
        f"e-GP: Normalized {len(all_contracts)} contracts, "
        f"{len(all_companies)} companies, {len(all_directors)} directors, "
        f"{len(all_ownership)} ownership records"
    )

    return {
        "tenders": all_tenders,
        "companies": all_companies,
        "directors": all_directors,
        "ownership": all_ownership,
        "contracts": all_contracts,
    }
