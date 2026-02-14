"""
PPIP OCDS Connector.
Fetches OCDS 1.1 releases from Kenya's tenders.go.ke API,
normalizes to internal schema, and persists with provenance.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx

from connectors.normalize import (
    parse_date,
    normalize_name,
    clean_amount,
    classify_address,
    compute_company_quality_flags,
)
from models import (
    Tender,
    Company,
    Contract,
    TenderStatus,
    AddressQuality,
)

logger = logging.getLogger(__name__)


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


def normalize_ocds_tender(release: dict) -> Optional[Tender]:
    """
    Normalize an OCDS release into our internal Tender model.
    Handles both 'tender'-only and 'contract' tagged releases.
    """
    ocid = release.get("ocid")
    tender_data = release.get("tender", {})
    buyer = release.get("buyer", {})
    tags = release.get("tag", [])

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
    awarded_company_name = None
    if awards:
        first_award = awards[0]
        award_value = first_award.get("value", {})
        awarded_amount = clean_amount(award_value.get("amount"))
        suppliers = first_award.get("suppliers", [])
        if suppliers:
            awarded_company_name = suppliers[0].get("name")

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
        procuring_entity=buyer.get("name", "Unknown"),
        category=tender_data.get("mainProcurementCategory"),
        estimated_value=estimated_value,
        published_date=published_date,
        deadline=deadline,
        status=tender_status,
        awarded_amount=awarded_amount,
        procurement_method=method_details or method,
        procurement_category=tender_data.get("mainProcurementCategory"),
        currency=currency,
        ocds_id=ocid,
        buyer_id=buyer.get("id"),
        source_system="ppip",
        source_record_id=ocid,
    )


def extract_ocds_companies(release: dict) -> list[Company]:
    """
    Extract company/supplier entities from OCDS release parties.
    Parties with role 'supplier' or 'tenderer' become Company objects.
    """
    parties = release.get("parties", [])
    companies = []

    for party in parties:
        roles = party.get("roles", [])
        if not any(r in roles for r in ("supplier", "tenderer")):
            continue

        identifier = party.get("identifier", {})
        address = party.get("address", {})
        contact = party.get("contactPoint", {})

        name = party.get("name", "")
        if not name:
            continue

        reg_number = identifier.get("id", "")
        if not reg_number:
            # Generate a stable ID from name
            reg_number = f"PPIP-{normalize_name(name)}"

        physical_addr = address.get("streetAddress", "")
        postal_code = address.get("postalCode", "")
        locality = address.get("locality", "")
        region = address.get("region", "")

        # Build a combined address string
        addr_parts = [p for p in [physical_addr, locality, region] if p]
        combined_address = ", ".join(addr_parts) if addr_parts else None

        quality_flags = compute_company_quality_flags(
            name=name,
            physical_address=physical_addr,
            postal_address=None,
            contact_email=contact.get("email"),
            brs_number=None,
            directors=[],
            ownership=[],
        )

        companies.append(
            Company(
                id=str(uuid.uuid4()),
                name=name,
                registration_number=reg_number,
                address=combined_address,
                physical_address=physical_addr or None,
                postal_code=postal_code or None,
                contact_email=contact.get("email"),
                phone=contact.get("telephone"),
                source_system="ppip",
                source_record_id=release.get("ocid"),
                data_quality_flags=quality_flags,
            )
        )

    return companies


def extract_ocds_contracts(release: dict) -> list[Contract]:
    """
    Extract contract entities from OCDS release.
    Only present in releases tagged with 'contract'.
    """
    raw_contracts = release.get("contracts", [])
    awards = {a.get("id"): a for a in release.get("awards", [])}
    buyer = release.get("buyer", {})
    contracts = []

    for rc in raw_contracts:
        contract_id = rc.get("id", "")
        if not contract_id:
            continue

        value = rc.get("value", {})
        period = rc.get("period", {})

        # Get supplier from linked award
        award_id = rc.get("awardID")
        award = awards.get(award_id, {})

        contracts.append(
            Contract(
                id=str(uuid.uuid4()),
                contract_number=contract_id,
                title=rc.get("title"),
                description=rc.get("description"),
                contract_amount=clean_amount(value.get("amount")),
                currency=value.get("currency", "KES"),
                start_date=parse_date(period.get("startDate")),
                end_date=parse_date(period.get("endDate")),
                effective_date=parse_date(rc.get("dateSigned")),
                status=rc.get("status"),
                pe_name=buyer.get("name"),
                source_system="ppip",
                source_record_id=release.get("ocid"),
            )
        )

    return contracts


async def sync_ppip_fiscal_year(fiscal_year: str) -> dict:
    """
    Full sync pipeline: fetch OCDS releases, normalize, return structured data.
    Returns dict with tenders, companies, and contracts ready for persistence.
    """
    releases = await fetch_ocds_releases(fiscal_year)

    all_tenders = []
    all_companies = []
    all_contracts = []
    skipped = 0

    for release in releases:
        tender = normalize_ocds_tender(release)
        if tender:
            all_tenders.append(tender)
        else:
            skipped += 1

        companies = extract_ocds_companies(release)
        all_companies.extend(companies)

        contracts = extract_ocds_contracts(release)
        all_contracts.extend(contracts)

    logger.info(
        f"PPIP sync complete: {len(all_tenders)} tenders, "
        f"{len(all_companies)} companies, {len(all_contracts)} contracts, "
        f"{skipped} skipped"
    )

    return {
        "tenders": all_tenders,
        "companies": all_companies,
        "contracts": all_contracts,
        "stats": {
            "releases_fetched": len(releases),
            "tenders_normalized": len(all_tenders),
            "companies_extracted": len(all_companies),
            "contracts_extracted": len(all_contracts),
            "skipped": skipped,
        },
    }
