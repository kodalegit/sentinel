"""
Shared normalization utilities for Kenyan procurement data.
Handles dates, addresses, and data quality classification.
"""

import re
from datetime import date, datetime, timezone
from typing import Optional

from models import AddressQuality


_PUBLIC_WEBMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.co.ke",
    "gmail.co.ke",
}

_GENERIC_INBOX_PREFIXES = {
    "admin",
    "contact",
    "enquiries",
    "info",
    "office",
    "procurement",
    "sales",
    "support",
    "tenders",
}


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

# Patterns found in e-GP and PPIP data
_DATE_FORMATS = [
    "%d/%m/%Y %H:%M:%S",  # e-GP tender: "13/02/2026 10:00:00"
    "%d-%m-%Y",  # e-GP contract: "12-02-2026"
    "%Y-%m-%dT%H:%M:%SZ",  # OCDS ISO: "2025-07-01T00:00:00Z"
    "%Y-%m-%d",  # ISO date: "2025-07-01"
    "%d/%m/%Y",  # Short: "13/02/2026"
]


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    try:
        iso_value = value.replace("Z", "+00:00") if value.endswith("Z") else value
        return datetime.fromisoformat(iso_value)
    except ValueError:
        return None


def normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a date string trying multiple Kenyan formats. Returns None on failure."""
    if not value or not value.strip():
        return None
    value = value.strip()
    iso_parsed = _parse_iso_datetime(value)
    if iso_parsed is not None:
        return iso_parsed.date()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a datetime string trying multiple Kenyan formats."""
    if not value or not value.strip():
        return None
    value = value.strip()
    iso_parsed = _parse_iso_datetime(value)
    if iso_parsed is not None:
        return normalize_datetime(iso_parsed)
    for fmt in _DATE_FORMATS:
        try:
            return normalize_datetime(datetime.strptime(value, fmt))
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Address quality classification
# ---------------------------------------------------------------------------

# Known placeholder patterns in e-GP data
_PLACEHOLDER_PATTERNS = [
    re.compile(r"^PO\s*Box\s*123$", re.IGNORECASE),
    re.compile(r"^P\.?O\.?\s*Box\s*123$", re.IGNORECASE),
    re.compile(r"^N/?A$", re.IGNORECASE),
    re.compile(r"^-+$"),
    re.compile(r"^\.+$"),
    re.compile(r"^None$", re.IGNORECASE),
    re.compile(r"^null$", re.IGNORECASE),
    re.compile(r"^not\s*available$", re.IGNORECASE),
]

# Patterns indicating a specific, verifiable address
_SPECIFIC_PATTERNS = [
    re.compile(r"plot\s+\d+", re.IGNORECASE),
    re.compile(r"L\.?R\.?\s*No\.?\s*\d+", re.IGNORECASE),
    re.compile(r"building\b", re.IGNORECASE),
    re.compile(r"house\b", re.IGNORECASE),
    re.compile(r"floor\b", re.IGNORECASE),
    re.compile(r"suite\b", re.IGNORECASE),
    re.compile(r"block\b", re.IGNORECASE),
    re.compile(r"\d+\s+(st|nd|rd|th)\s+floor", re.IGNORECASE),
    re.compile(r"room\s+\d+", re.IGNORECASE),
]


def classify_address(address: Optional[str]) -> AddressQuality:
    """
    Classify a Kenyan address into quality tiers.

    SPECIFIC  — Contains plot number, LR number, building name, floor, etc.
    VAGUE     — Contains only road/area name (e.g., "MOI AVENUE", "THOME")
    PLACEHOLDER — Known default/dummy values (e.g., "PO Box 123", "N/A")
    UNKNOWN   — Empty or None
    """
    if not address or not address.strip():
        return AddressQuality.UNKNOWN

    cleaned = address.strip()

    # Check placeholder patterns first
    for pattern in _PLACEHOLDER_PATTERNS:
        if pattern.match(cleaned):
            return AddressQuality.PLACEHOLDER

    # Very short addresses are likely vague
    if len(cleaned) < 4:
        return AddressQuality.VAGUE

    # Check for specific patterns
    for pattern in _SPECIFIC_PATTERNS:
        if pattern.search(cleaned):
            return AddressQuality.SPECIFIC

    # Default: vague (road names, area names, etc.)
    return AddressQuality.VAGUE


# ---------------------------------------------------------------------------
# Data quality scoring
# ---------------------------------------------------------------------------


def compute_company_quality_flags(
    name: Optional[str],
    physical_address: Optional[str],
    postal_address: Optional[str],
    contact_email: Optional[str],
    brs_number: Optional[str],
    directors: Optional[list] = None,
    ownership: Optional[list] = None,
    source_system: Optional[str] = None,
) -> dict:
    """
    Compute source-aware evidence quality flags for a company entity.
    Returns a dict with field coverage, verification strength, and a composite
    evidence quality score (0-100).
    """
    normalized_source = (source_system or "unknown").strip().lower()
    source_expectations = {
        "expects_brs": normalized_source in {"egp", "synthetic"},
        "expects_directors": normalized_source in {"egp", "synthetic"},
        "expects_ownership": normalized_source in {"egp", "synthetic"},
        "expects_postal_address": normalized_source in {"egp", "synthetic"},
    }

    flags = {
        "source_system": normalized_source,
        "source_expectations": source_expectations,
    }

    completeness_score = 0
    completeness_max = 0
    verification_score = 0
    verification_max = 0

    def add_completeness(weight: int, condition: bool):
        nonlocal completeness_score, completeness_max
        completeness_max += weight
        if condition:
            completeness_score += weight

    def add_verification(weight: int, points: int):
        nonlocal verification_score, verification_max
        verification_max += weight
        verification_score += max(0, min(points, weight))

    email_value = (contact_email or "").strip().lower()
    local_part = email_value.split("@", 1)[0] if "@" in email_value else ""
    domain = email_value.split("@", 1)[1] if "@" in email_value else ""

    # Name present
    if name and name.strip():
        flags["has_name"] = True
    else:
        flags["has_name"] = False
    add_completeness(20, flags["has_name"])
    add_verification(10, 10 if flags["has_name"] else 0)

    # Physical address quality
    addr_quality = classify_address(physical_address)
    flags["address_quality"] = addr_quality.value
    if addr_quality == AddressQuality.SPECIFIC:
        add_completeness(25, True)
        add_verification(20, 20)
    elif addr_quality == AddressQuality.VAGUE:
        add_completeness(25, True)
        add_verification(20, 8)
    else:
        add_completeness(25, False)
        add_verification(20, 0)

    # Postal address (not placeholder)
    postal_quality = classify_address(postal_address)
    flags["postal_quality"] = postal_quality.value
    postal_weight = 10 if source_expectations["expects_postal_address"] else 0
    postal_present = postal_quality in (AddressQuality.SPECIFIC, AddressQuality.VAGUE)
    add_completeness(postal_weight, postal_present)
    add_verification(5, 5 if postal_present else 0)

    # Contact email present
    if contact_email and "@" in contact_email:
        flags["has_email"] = True
        flags["email_is_public_webmail"] = domain in _PUBLIC_WEBMAIL_DOMAINS
        flags["email_is_generic_inbox"] = local_part in _GENERIC_INBOX_PREFIXES
        flags["email_is_generic"] = flags["email_is_public_webmail"]
    else:
        flags["has_email"] = False
        flags["email_is_public_webmail"] = None
        flags["email_is_generic_inbox"] = None
        flags["email_is_generic"] = None
    add_completeness(10, flags["has_email"])
    if flags["has_email"]:
        if flags["email_is_public_webmail"]:
            add_verification(15, 6)
        elif flags["email_is_generic_inbox"]:
            add_verification(15, 10)
        else:
            add_verification(15, 15)
    else:
        add_verification(15, 0)

    # BRS number present
    if brs_number and brs_number.strip():
        flags["has_brs"] = True
    else:
        flags["has_brs"] = False
    brs_weight = 10 if source_expectations["expects_brs"] else 0
    add_completeness(brs_weight, flags["has_brs"])
    add_verification(25, 25 if flags["has_brs"] else 0)

    # Directors listed
    director_count = len(directors) if directors else 0
    flags["director_count"] = director_count
    flags["has_directors"] = director_count > 0
    director_weight = 15 if source_expectations["expects_directors"] else 0
    add_completeness(director_weight, flags["has_directors"])
    add_verification(15, 15 if flags["has_directors"] else 0)

    # Ownership info
    owner_count = len(ownership) if ownership else 0
    flags["owner_count"] = owner_count
    flags["has_ownership"] = owner_count > 0
    ownership_weight = 10 if source_expectations["expects_ownership"] else 0
    add_completeness(ownership_weight, flags["has_ownership"])
    add_verification(10, 10 if flags["has_ownership"] else 0)

    completeness_pct = (
        round((completeness_score / completeness_max) * 100)
        if completeness_max > 0
        else 0
    )
    verification_pct = (
        round((verification_score / verification_max) * 100)
        if verification_max > 0
        else 0
    )
    flags["completeness_score"] = completeness_pct
    flags["verification_score"] = verification_pct
    flags["quality_score"] = round(
        (completeness_pct * 0.45) + (verification_pct * 0.55)
    )
    return flags


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------


def normalize_name(name: Optional[str]) -> Optional[str]:
    """Normalize a person/company name: strip, uppercase, collapse whitespace."""
    if not name:
        return None
    return re.sub(r"\s+", " ", name.strip().upper())


def clean_amount(value) -> Optional[float]:
    """Parse a monetary amount from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value.strip())
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    return None
