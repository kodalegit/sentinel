"""
Shared normalization helpers for graph edge detection.
Used by both NetworkX builder and Neo4j sync to ensure consistent edge creation.
"""

import re
from typing import Set

# Maximum edges per company for shared attributes to prevent explosion
MAX_SHARED_EDGES_PER_COMPANY = 50

# Maximum group size - if more companies share an attribute, it's likely generic
MAX_GROUP_SIZE_ADDRESS = 100
MAX_GROUP_SIZE_PHONE = 50
MAX_GROUP_SIZE_EMAIL = 50

# Compiled regex patterns for address parsing
_PLOT_PATTERN = re.compile(r"plot\s*(\d+)", re.IGNORECASE)
_LR_PATTERN = re.compile(r"l\.?r\.?\s*no?\.?\s*(\d+)", re.IGNORECASE)
_BUILDING_PATTERN = re.compile(
    r"(\w+)\s+(building|house|plaza|towers?|place|centre|center)", re.IGNORECASE
)

# Filler words to ignore in address normalization
ADDRESS_FILLER_WORDS: Set[str] = {
    "road",
    "street",
    "avenue",
    "along",
    "off",
    "near",
    "the",
    "and",
    "po",
    "box",
    "nairobi",
    "kenya",
    "mombasa",
    "kisumu",
    "nakuru",
    "eldoret",
    "thika",
    "nyeri",
    "machakos",
    "county",
    "town",
    "city",
}

# Generic email prefixes that shouldn't create edges
GENERIC_EMAIL_PREFIXES = [
    "info@",
    "admin@",
    "contact@",
    "sales@",
    "support@",
    "noreply@",
    "no-reply@",
    "test@",
    "example@",
    "enquiries@",
    "enquiry@",
    "office@",
    "general@",
    "help@",
    "mail@",
]


def normalize_phone(phone: str | None) -> str | None:
    """
    Normalize phone number for comparison.
    Strips all non-digit characters and returns None for empty/invalid.
    
    Examples:
        "+254 712 345 678" -> "254712345678"
        "0712-345-678" -> "0712345678"
        "" -> None
    """
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    # Minimum valid phone length (Kenya local numbers are 10 digits)
    if len(digits) < 6:
        return None
    return digits


def normalize_address_key(addr: str) -> str | None:
    """
    Create a normalized key for address grouping.
    Returns None for addresses that are too vague to group reliably.
    
    Uses multiple strategies to extract a groupable key:
    1. Plot number (e.g., "Plot 45" -> "plot:45")
    2. LR number (e.g., "L.R. No. 1234" -> "lr:1234")
    3. Building name (e.g., "Westlands Plaza" -> "building:westlands plaza")
    4. Token set (if >= 3 meaningful tokens)
    
    Returns None for:
    - Empty addresses
    - PO Box only addresses
    - Addresses with < 3 meaningful tokens
    """
    if not addr:
        return None
        
    a = addr.lower().strip()

    # 1. Try plot number
    m = _PLOT_PATTERN.search(a)
    if m:
        return f"plot:{m.group(1)}"

    # 2. Try LR number
    m = _LR_PATTERN.search(a)
    if m:
        return f"lr:{m.group(1)}"

    # 3. Try building name
    m = _BUILDING_PATTERN.search(a)
    if m:
        return f"building:{m.group(0).lower()}"

    # 4. For specific addresses, use normalized token set
    tokens = set(re.findall(r"\w+", a))
    meaningful = tokens - ADDRESS_FILLER_WORDS
    
    # Filter out pure numbers (like PO Box numbers)
    meaningful = {t for t in meaningful if not t.isdigit()}

    # Need at least 3 meaningful tokens for a reliable key
    if len(meaningful) >= 3:
        return f"tokens:{'-'.join(sorted(meaningful))}"

    return None


def is_generic_email(email: str) -> bool:
    """
    Check if email is a generic/placeholder that shouldn't create edges.
    
    Generic emails like info@company.com are commonly used as defaults
    and would create false connections between unrelated companies.
    
    Examples:
        "info@company.com" -> True
        "john.doe@company.com" -> False
        "admin@example.org" -> True
    """
    if not email:
        return True
    email_lower = email.lower().strip()
    return any(email_lower.startswith(p) for p in GENERIC_EMAIL_PREFIXES)


def addresses_similar(addr1: str, addr2: str) -> bool:
    """
    Check if two addresses are suspiciously similar.
    
    Uses multiple matching strategies for Kenya's varied address formats:
    1. Exact match after normalization
    2. Plot number matching (e.g., 'Plot 45' ~ 'Plot 45A')
    3. LR number matching (e.g., 'L.R. No. 1234')
    4. Building name matching (e.g., 'Westlands Plaza')
    5. High token overlap (>= 60%) for SPECIFIC addresses
    """
    if not addr1 or not addr2:
        return False
        
    a1 = addr1.lower().strip()
    a2 = addr2.lower().strip()

    # Exact match after normalization
    if a1 == a2:
        return True

    # 1. Plot number match
    m1 = _PLOT_PATTERN.search(a1)
    m2 = _PLOT_PATTERN.search(a2)
    if m1 and m2 and m1.group(1) == m2.group(1):
        return True

    # 2. LR number match
    lr1 = _LR_PATTERN.search(a1)
    lr2 = _LR_PATTERN.search(a2)
    if lr1 and lr2 and lr1.group(1) == lr2.group(1):
        return True

    # 3. Building name match
    b1 = _BUILDING_PATTERN.search(a1)
    b2 = _BUILDING_PATTERN.search(a2)
    if b1 and b2:
        if b1.group(0).lower() == b2.group(0).lower():
            return True

    # 4. High token overlap for addresses with enough detail
    tokens1 = set(re.findall(r"\w+", a1))
    tokens2 = set(re.findall(r"\w+", a2))
    
    if len(tokens1) >= 3 and len(tokens2) >= 3:
        overlap = tokens1 & tokens2
        meaningful_overlap = overlap - ADDRESS_FILLER_WORDS
        min_tokens = min(
            len(tokens1 - ADDRESS_FILLER_WORDS), 
            len(tokens2 - ADDRESS_FILLER_WORDS)
        )
        if min_tokens > 0 and len(meaningful_overlap) / min_tokens >= 0.6:
            return True

    return False
