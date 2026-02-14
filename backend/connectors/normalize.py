"""
Shared normalization utilities for Kenyan procurement data.
Handles dates, addresses, and data quality classification.
"""

import re
from datetime import date, datetime
from typing import Optional

from models import AddressQuality


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

# Patterns found in e-GP and PPIP data
_DATE_FORMATS = [
    "%d/%m/%Y %H:%M:%S",  # e-GP tender: "13/02/2026 10:00:00"
    "%d-%m-%Y",            # e-GP contract: "12-02-2026"
    "%Y-%m-%dT%H:%M:%SZ", # OCDS ISO: "2025-07-01T00:00:00Z"
    "%Y-%m-%d",            # ISO date: "2025-07-01"
    "%d/%m/%Y",            # Short: "13/02/2026"
]


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a date string trying multiple Kenyan formats. Returns None on failure."""
    if not value or not value.strip():
        return None
    value = value.strip()
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
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
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
) -> dict:
    """
    Compute data quality flags for a company entity.
    Returns a dict with individual flags and a composite quality score (0-100).
    """
    flags = {}
    score = 0
    max_score = 0

    # Name present
    max_score += 15
    if name and name.strip():
        score += 15
        flags["has_name"] = True
    else:
        flags["has_name"] = False

    # Physical address quality
    max_score += 20
    addr_quality = classify_address(physical_address)
    flags["address_quality"] = addr_quality.value
    if addr_quality == AddressQuality.SPECIFIC:
        score += 20
    elif addr_quality == AddressQuality.VAGUE:
        score += 8
    elif addr_quality == AddressQuality.PLACEHOLDER:
        score += 0
    # UNKNOWN: 0

    # Postal address (not placeholder)
    max_score += 10
    postal_quality = classify_address(postal_address)
    flags["postal_quality"] = postal_quality.value
    if postal_quality in (AddressQuality.SPECIFIC, AddressQuality.VAGUE):
        score += 10
    elif postal_quality == AddressQuality.PLACEHOLDER:
        score += 0

    # Contact email present
    max_score += 10
    if contact_email and "@" in contact_email:
        score += 10
        flags["has_email"] = True
        # Check for generic email domains
        domain = contact_email.split("@")[-1].lower()
        flags["email_is_generic"] = domain in (
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
            "yahoo.co.ke", "gmail.co.ke",
        )
    else:
        flags["has_email"] = False
        flags["email_is_generic"] = None

    # BRS number present
    max_score += 15
    if brs_number and brs_number.strip():
        score += 15
        flags["has_brs"] = True
    else:
        flags["has_brs"] = False

    # Directors listed
    max_score += 15
    director_count = len(directors) if directors else 0
    flags["director_count"] = director_count
    if director_count > 0:
        score += 15
    flags["has_directors"] = director_count > 0

    # Ownership info
    max_score += 15
    owner_count = len(ownership) if ownership else 0
    flags["owner_count"] = owner_count
    if owner_count > 0:
        score += 15
    flags["has_ownership"] = owner_count > 0

    flags["quality_score"] = round((score / max_score) * 100) if max_score > 0 else 0
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
