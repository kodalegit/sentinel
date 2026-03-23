"""
PPIP OCDS Connector.
Fetches OCDS 1.1 releases from Kenya's tenders.go.ke API,
normalizes to internal schema, and persists with provenance.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

import httpx

from connectors.normalize import (
    parse_date,
    parse_datetime,
    normalize_name,
    clean_amount,
    compute_company_quality_flags,
)
from models import (
    Bid,
    Tender,
    Company,
    Contract,
    TenderStatus,
)

logger = logging.getLogger(__name__)


def _limit_text(value: Optional[str], max_length: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _canonical_company_name(name: Optional[str]) -> Optional[str]:
    normalized = normalize_name(name)
    if not normalized:
        return None
    normalized = re.sub(r"\bLIMITED\b", "LTD", normalized)
    normalized = re.sub(r"\bCOMPANY\b", "CO", normalized)
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _build_company(party: dict, release: dict) -> Optional[Company]:
    identifier = party.get("identifier", {})
    address = party.get("address", {})
    contact = party.get("contactPoint", {})

    name = (
        party.get("name") or identifier.get("legalName") or contact.get("name") or ""
    ).strip()
    if not name:
        return None

    reg_number = (
        identifier.get("id")
        or str(party.get("id") or "").strip()
        or f"PPIP-{_canonical_company_name(name) or normalize_name(name)}"
    )

    physical_addr = (address.get("streetAddress") or "").strip()
    postal_code = (address.get("postalCode") or "").strip()
    locality = (address.get("locality") or "").strip()
    region = (address.get("region") or "").strip()
    addr_parts = [part for part in [physical_addr, locality, region] if part]
    combined_address = ", ".join(addr_parts) if addr_parts else None

    quality_flags = compute_company_quality_flags(
        name=name,
        physical_address=physical_addr or None,
        postal_address=None,
        contact_email=contact.get("email"),
        brs_number=None,
        directors=[],
        ownership=[],
        source_system="ppip",
    )

    return Company(
        id=str(uuid.uuid4()),
        name=name,
        registration_number=reg_number,
        address=combined_address,
        physical_address=physical_addr or None,
        postal_code=postal_code or None,
        contact_email=contact.get("email"),
        phone=contact.get("telephone"),
        source_system="ppip",
        source_record_id=str(
            party.get("id") or identifier.get("id") or release.get("ocid") or reg_number
        ),
        data_quality_flags=quality_flags,
    )


def _build_company_lookup(
    companies: list[Company],
) -> tuple[dict[str, str], dict[str, str]]:
    by_registration: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for company in companies:
        by_registration[company.registration_number] = company.id
        canonical_name = _canonical_company_name(company.name)
        if canonical_name and canonical_name not in by_name:
            by_name[canonical_name] = company.id
    return by_registration, by_name


def _resolve_company_id(
    supplier: dict,
    by_registration: dict[str, str],
    by_name: dict[str, str],
) -> Optional[str]:
    supplier_id = str(
        supplier.get("id") or supplier.get("identifier", {}).get("id") or ""
    ).strip()
    if supplier_id and supplier_id in by_registration:
        return by_registration[supplier_id]

    supplier_name = supplier.get("name") or supplier.get("identifier", {}).get(
        "legalName"
    )
    canonical_name = _canonical_company_name(supplier_name)
    if canonical_name:
        return by_name.get(canonical_name)
    return None


async def fetch_ocds_releases(
    fiscal_year: str,
) -> list[dict]:
    """
    Fetch OCDS releases from PPIP for a given fiscal year.
    E.g., fiscal_year="2025-2026"
    Returns raw OCDS release dicts.
    """
    from config import settings

    url = f"{settings.ppip_base_url}/tenders"
    params = {"fy": fiscal_year}

    async with httpx.AsyncClient(timeout=settings.ppip_timeout) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    releases = data.get("releases", [])
    logger.info(f"PPIP: Fetched {len(releases)} releases for FY {fiscal_year}")
    return releases


def normalize_ocds_tender(
    release: dict, awarded_to: Optional[str] = None
) -> Optional[Tender]:
    """
    Normalize an OCDS release into our internal Tender model.
    Handles both 'tender'-only and 'contract' tagged releases.
    """
    ocid = release.get("ocid")
    tender_data = release.get("tender", {})
    buyer = release.get("buyer", {})

    if not tender_data:
        return None

    # Extract reference number from tender ID or OCID
    tender_id = tender_data.get("id", "")
    ref_number = tender_id or ocid or ""
    if not ref_number:
        return None

    # Determine status
    status_map = {
        "active": TenderStatus.OPEN,
        "complete": TenderStatus.AWARDED,
        "cancelled": TenderStatus.CANCELLED,
        "planned": TenderStatus.OPEN,
    }
    raw_status = tender_data.get("status", "active")
    tender_status = status_map.get(raw_status, TenderStatus.OPEN)

    # If we have awards, mark as awarded
    awards = release.get("awards", [])
    if awards and tender_status == TenderStatus.OPEN:
        tender_status = TenderStatus.AWARDED

    # Extract value
    value = tender_data.get("value", {})
    estimated_value = clean_amount(value.get("amount"))
    currency = value.get("currency", "KES")

    # Award amount (take the first award if present)
    awarded_amount = None
    if awards:
        first_award = awards[0]
        award_value = first_award.get("value", {})
        awarded_amount = clean_amount(award_value.get("amount"))

    # Tender period
    tender_period = tender_data.get("tenderPeriod", {})
    published_date = parse_date(tender_period.get("startDate"))
    deadline = parse_date(tender_period.get("endDate"))

    # Procurement method
    method = tender_data.get("procurementMethod", "")
    method_details = tender_data.get("procurementMethodDetails", "")

    return Tender(
        id=str(uuid.uuid4()),
        reference_number=ref_number,
        title=tender_data.get("title", "Untitled"),
        description=tender_data.get("description"),
        procuring_entity=_limit_text(buyer.get("name", "Unknown"), 255) or "Unknown",
        category=_limit_text(tender_data.get("mainProcurementCategory"), 100),
        estimated_value=estimated_value,
        published_date=published_date,
        deadline=deadline,
        status=tender_status,
        awarded_to=awarded_to,
        awarded_amount=awarded_amount,
        procurement_method=_limit_text(method_details or method, 100),
        procurement_category=_limit_text(
            tender_data.get("mainProcurementCategory"), 100
        ),
        currency=_limit_text(currency, 10) or "KES",
        ocds_id=ocid,
        buyer_id=_limit_text(buyer.get("id"), 50),
        source_system=_limit_text("ppip", 20),
        source_record_id=ocid,
    )


def extract_ocds_companies(release: dict) -> list[Company]:
    """
    Extract company/supplier entities from OCDS release parties.
    Parties with role 'supplier' or 'tenderer' become Company objects.
    """
    parties = release.get("parties", [])
    companies: list[Company] = []
    seen_registration_numbers: set[str] = set()
    seen_names: set[str] = set()

    for party in parties:
        roles = party.get("roles", [])
        if not any(r in roles for r in ("supplier", "tenderer")):
            continue

        company = _build_company(party, release)
        if company is None:
            continue

        canonical_name = _canonical_company_name(company.name)
        if company.registration_number in seen_registration_numbers:
            continue
        if canonical_name and canonical_name in seen_names:
            continue

        seen_registration_numbers.add(company.registration_number)
        if canonical_name:
            seen_names.add(canonical_name)
        companies.append(company)

    for award in release.get("awards", []):
        for supplier in award.get("suppliers", []):
            company = _build_company(supplier, release)
            if company is None:
                continue
            canonical_name = _canonical_company_name(company.name)
            if company.registration_number in seen_registration_numbers:
                continue
            if canonical_name and canonical_name in seen_names:
                continue
            seen_registration_numbers.add(company.registration_number)
            if canonical_name:
                seen_names.add(canonical_name)
            companies.append(company)

    return companies


def extract_ocds_bids(
    release: dict, tender: Tender, companies: list[Company]
) -> list[Bid]:
    by_registration, by_name = _build_company_lookup(companies)
    tender_period = release.get("tender", {}).get("tenderPeriod", {})
    submission_date = parse_datetime(tender_period.get("endDate")) or parse_datetime(
        release.get("date")
    )
    if submission_date is None:
        submission_date = datetime.utcnow()

    bids: list[Bid] = []
    for company in companies:
        supplier_ref = {
            "id": company.source_record_id,
            "name": company.name,
            "identifier": {
                "id": company.registration_number,
                "legalName": company.name,
            },
        }
        company_id = (
            _resolve_company_id(supplier_ref, by_registration, by_name) or company.id
        )
        bids.append(
            Bid(
                id=str(uuid.uuid4()),
                tender_id=tender.id,
                company_id=company_id,
                amount=None,
                submission_date=submission_date,
            )
        )
    return bids


def extract_ocds_contracts(
    release: dict,
    tender: Tender,
    companies: list[Company],
) -> list[Contract]:
    """
    Extract contract entities from OCDS release.
    Only present in releases tagged with 'contract'.
    """
    raw_contracts = release.get("contracts", [])
    awards = {a.get("id"): a for a in release.get("awards", [])}
    buyer = release.get("buyer", {})
    by_registration, by_name = _build_company_lookup(companies)
    contracts = []

    for rc in raw_contracts:
        contract_id = rc.get("id", "")
        if not contract_id:
            continue

        value = rc.get("value", {})
        period = rc.get("period", {})

        award_id = rc.get("awardID")
        award = awards.get(award_id, {})
        company_id = None
        suppliers = award.get("suppliers", [])
        if suppliers:
            company_id = _resolve_company_id(suppliers[0], by_registration, by_name)

        contracts.append(
            Contract(
                id=str(uuid.uuid4()),
                tender_id=tender.id,
                company_id=company_id,
                contract_number=contract_id,
                title=rc.get("title"),
                description=rc.get("description"),
                contract_amount=clean_amount(value.get("amount")),
                currency=_limit_text(value.get("currency", "KES"), 10) or "KES",
                start_date=parse_date(period.get("startDate")),
                end_date=parse_date(period.get("endDate")),
                effective_date=parse_date(rc.get("dateSigned")),
                status=_limit_text(rc.get("status"), 50),
                procurement_method=_limit_text(rc.get("procurementMethod"), 100),
                procurement_category=_limit_text(
                    rc.get("mainProcurementCategory"), 100
                ),
                pe_name=_limit_text(buyer.get("name"), 255),
                pe_type=_limit_text(buyer.get("identifier", {}).get("scheme"), 100),
                source_system=_limit_text("ppip", 20),
                source_record_id=contract_id,
            )
        )

    return contracts


async def sync_ppip_fiscal_year(fiscal_year: str) -> dict:
    """
    Full sync pipeline: fetch OCDS releases, normalize, return structured data.
    Returns dict with release bundles ready for persistence.
    """
    releases = await fetch_ocds_releases(fiscal_year)

    normalized_releases = []
    tender_count = 0
    company_count = 0
    bid_count = 0
    contract_count = 0
    skipped = 0

    for release in releases:
        companies = extract_ocds_companies(release)
        company_count += len(companies)
        by_registration, by_name = _build_company_lookup(companies)

        awarded_to = None
        for award in release.get("awards", []):
            suppliers = award.get("suppliers", [])
            if suppliers:
                awarded_to = _resolve_company_id(suppliers[0], by_registration, by_name)
                if awarded_to:
                    break

        tender = normalize_ocds_tender(release, awarded_to=awarded_to)
        if tender:
            tender_count += 1
        else:
            skipped += 1

        bids = extract_ocds_bids(release, tender, companies) if tender else []
        bid_count += len(bids)
        contracts = extract_ocds_contracts(release, tender, companies) if tender else []
        contract_count += len(contracts)
        if tender:
            normalized_releases.append(
                {
                    "tender": tender,
                    "companies": companies,
                    "bids": bids,
                    "contracts": contracts,
                }
            )

    logger.info(
        f"PPIP sync complete: {tender_count} tenders, "
        f"{company_count} companies, {bid_count} bids, "
        f"{contract_count} contracts, "
        f"{skipped} skipped"
    )

    return {
        "releases": normalized_releases,
        "stats": {
            "releases_fetched": len(releases),
            "tenders_normalized": tender_count,
            "companies_extracted": company_count,
            "bids_extracted": bid_count,
            "contracts_extracted": contract_count,
            "skipped": skipped,
        },
    }
