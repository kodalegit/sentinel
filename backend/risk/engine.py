"""
Risk scoring engine for Sentinel.
Computes explainable risk scores based on 5 core rules.
"""

from datetime import date, timedelta
from models import (
    Tender,
    Company,
    Director,
    PublicOfficial,
    Bid,
    RiskScore,
    RiskFactor,
    RiskFactorType,
    RiskCategory,
    TenderStatus,
    AddressQuality,
)
from connectors.normalize import classify_address
from graph.builder import find_conflict_path
import networkx as nx


# Risk weights for each factor type
RISK_WEIGHTS = {
    RiskFactorType.CONFLICT_OF_INTEREST: 30,
    RiskFactorType.CARTEL_PATTERN: 25,
    RiskFactorType.SHELL_COMPANY: 20,
    RiskFactorType.PRICE_ANOMALY: 15,
    RiskFactorType.RUSHED_TIMELINE: 10,
}


def compute_risk_score(
    tender: Tender,
    companies: dict[str, Company],
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    bids: list[Bid],
    graph: nx.Graph,
    cartel_clusters: list[set[str]],
    all_tenders: dict[str, Tender] = None,
) -> RiskScore:
    """
    Compute a comprehensive risk score for a tender.
    Returns score with explainable factors.
    """
    factors = []
    all_tenders = all_tenders or {}

    # Get winning company if awarded
    winner = companies.get(tender.awarded_to) if tender.awarded_to else None
    tender_bids = [b for b in bids if b.tender_id == tender.id]

    # Rule 1: Conflict of Interest
    coi_factor = check_conflict_of_interest(tender, winner, directors, officials, graph)
    if coi_factor:
        factors.append(coi_factor)

    # Rule 2: Cartel Pattern
    cartel_factor = check_cartel_pattern(
        tender, tender_bids, companies, cartel_clusters
    )
    if cartel_factor:
        factors.append(cartel_factor)

    # Rule 3: Shell Company
    shell_factor = check_shell_company(tender, winner)
    if shell_factor:
        factors.append(shell_factor)

    # Rule 4: Price Anomaly
    price_factor = check_price_anomaly(tender, all_tenders)
    if price_factor:
        factors.append(price_factor)

    # Rule 5: Rushed Timeline
    timeline_factor = check_rushed_timeline(tender)
    if timeline_factor:
        factors.append(timeline_factor)

    # Calculate overall score
    overall = sum(f.weight for f in factors)
    overall = min(overall, 100)  # Cap at 100

    # Determine category
    if overall >= 50:
        category = RiskCategory.HIGH
    elif overall >= 25:
        category = RiskCategory.MEDIUM
    else:
        category = RiskCategory.LOW

    # Generate recommendation
    recommendation = generate_recommendation(factors, category)

    return RiskScore(
        overall=overall,
        category=category,
        factors=factors,
        recommendation=recommendation,
    )


def check_conflict_of_interest(
    tender: Tender,
    winner: Company | None,
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    graph: nx.Graph,
) -> RiskFactor | None:
    """
    Check if there's a relationship path between winner and procurement officer.
    """
    if not winner or not tender.procurement_officer_id:
        return None

    official = officials.get(tender.procurement_officer_id)
    if not official:
        return None

    # Check if any of the winner's directors are related to the official
    for director_id in winner.director_ids:
        if director_id in official.related_persons:
            relationship = official.related_persons[director_id]
            director = directors.get(director_id)

            return RiskFactor(
                type=RiskFactorType.CONFLICT_OF_INTEREST,
                description=f"Winning vendor's director {director.name if director else 'Unknown'} "
                f"is {relationship.value.lower().replace('_', ' ')} of "
                f"Procurement Officer {official.name}",
                weight=RISK_WEIGHTS[RiskFactorType.CONFLICT_OF_INTEREST],
                evidence=[
                    f"Director: {director.name if director else director_id}",
                    f"Official: {official.name} ({official.position})",
                    f"Relationship: {relationship.value}",
                    f"Department: {official.department}",
                ],
                related_entity_ids=[director_id, official.id, winner.id],
            )

    # Check graph for indirect paths
    path = find_conflict_path(graph, winner.id, tender.procurement_officer_id)
    if path and len(path) <= 4:  # Within 3 hops
        path_description = " → ".join(
            [graph.nodes[node_id].get("label", node_id) for node_id in path]
        )
        return RiskFactor(
            type=RiskFactorType.CONFLICT_OF_INTEREST,
            description=f"Connection path found between winner and procurement officer",
            weight=RISK_WEIGHTS[RiskFactorType.CONFLICT_OF_INTEREST]
            - 10,  # Reduced weight for indirect
            evidence=[
                f"Path: {path_description}",
                f"Path length: {len(path) - 1} connections",
            ],
            related_entity_ids=path,
        )

    return None


def check_cartel_pattern(
    tender: Tender,
    tender_bids: list[Bid],
    companies: dict[str, Company],
    cartel_clusters: list[set[str]],
) -> RiskFactor | None:
    """
    Check if bidding companies form a suspected cartel.
    """
    bidding_company_ids = {b.company_id for b in tender_bids}

    for cartel in cartel_clusters:
        overlap = bidding_company_ids & cartel
        if len(overlap) >= 3:  # At least 3 cartel members bid on this tender
            cartel_names = [companies[cid].name for cid in overlap if cid in companies]

            return RiskFactor(
                type=RiskFactorType.CARTEL_PATTERN,
                description=f"Suspected bidding cartel: {len(overlap)} companies that consistently "
                f"bid together are present in this tender",
                weight=RISK_WEIGHTS[RiskFactorType.CARTEL_PATTERN],
                evidence=[
                    f"Cartel members in this tender: {', '.join(cartel_names)}",
                    f"Total cartel size: {len(cartel)} companies",
                    "Pattern: These companies consistently bid on the same tenders",
                ],
                related_entity_ids=list(overlap),
            )

    return None


# ---------------------------------------------------------------------------
# Multi-signal shell company detection weights
# ---------------------------------------------------------------------------
_SHELL_SIGNAL_WEIGHTS = {
    "company_age_very_new": 25,  # < 30 days old
    "company_age_new": 12,  # < 90 days old
    "address_placeholder": 15,  # "PO Box 123" default
    "address_vague": 8,  # "MOI AVENUE" — road name only
    "address_missing": 10,  # No address at all
    "no_directors": 12,  # Zero directors listed
    "no_ownership": 8,  # No ownership info
    "generic_email": 5,  # Gmail/Yahoo contact
    "large_value_new_company": 20,  # High contract value + new company
    "missing_registration": 10,  # No registration date
}
_SHELL_THRESHOLD = 40


def check_shell_company(tender: Tender, winner: Company | None) -> RiskFactor | None:
    """
    Multi-signal shell company detection.
    Combines registration recency, address quality, director/ownership
    completeness, email patterns, and contract value signals.
    Works under Kenya's sparse/generic data reality.
    """
    if not winner:
        return None

    signals = []
    composite_score = 0
    evidence = [f"Company: {winner.name}"]
    quality = winner.data_quality_flags or {}
    source_expectations = quality.get("source_expectations", {})

    # --- Signal 1: Company age ---
    if winner.registration_date and tender.deadline:
        company_age_days = (tender.deadline - winner.registration_date).days
        if company_age_days < 30:
            composite_score += _SHELL_SIGNAL_WEIGHTS["company_age_very_new"]
            signals.append("company_age_very_new")
            evidence.append(f"Registered only {company_age_days} days before deadline")
        elif company_age_days < 90:
            composite_score += _SHELL_SIGNAL_WEIGHTS["company_age_new"]
            signals.append("company_age_new")
            evidence.append(f"Registered only {company_age_days} days before deadline")
    elif not winner.registration_date:
        composite_score += _SHELL_SIGNAL_WEIGHTS["missing_registration"]
        signals.append("missing_registration")
        evidence.append("No registration date on record")

    # --- Signal 2: Address quality ---
    addr = winner.physical_address or winner.address
    addr_quality = classify_address(addr)
    if addr_quality == AddressQuality.PLACEHOLDER:
        composite_score += _SHELL_SIGNAL_WEIGHTS["address_placeholder"]
        signals.append("address_placeholder")
        evidence.append(f"Placeholder address: '{addr}'")
    elif addr_quality == AddressQuality.VAGUE:
        composite_score += _SHELL_SIGNAL_WEIGHTS["address_vague"]
        signals.append("address_vague")
        evidence.append(f"Vague address: '{addr}'")
    elif addr_quality == AddressQuality.UNKNOWN:
        composite_score += _SHELL_SIGNAL_WEIGHTS["address_missing"]
        signals.append("address_missing")
        evidence.append("No address on record")

    # --- Signal 3: Director count ---
    director_count = quality.get("director_count", len(winner.director_ids))
    if director_count == 0 and source_expectations.get("expects_directors", True):
        composite_score += _SHELL_SIGNAL_WEIGHTS["no_directors"]
        signals.append("no_directors")
        evidence.append("No directors listed")

    # --- Signal 4: Ownership info ---
    if quality.get("has_ownership") is False and source_expectations.get(
        "expects_ownership", True
    ):
        composite_score += _SHELL_SIGNAL_WEIGHTS["no_ownership"]
        signals.append("no_ownership")
        evidence.append("No ownership records")

    # --- Signal 5: Generic email domain ---
    if (
        quality.get("email_is_public_webmail") is True
        or quality.get("email_is_generic") is True
    ):
        composite_score += _SHELL_SIGNAL_WEIGHTS["generic_email"]
        signals.append("generic_email")
        evidence.append(f"Generic email: {winner.contact_email}")

    # --- Signal 6: Large contract + new company ---
    if tender.awarded_amount and tender.awarded_amount > 1_000_000:
        is_new = (
            "company_age_very_new" in signals
            or "company_age_new" in signals
            or "missing_registration" in signals
        )
        if is_new:
            composite_score += _SHELL_SIGNAL_WEIGHTS["large_value_new_company"]
            signals.append("large_value_new_company")
            evidence.append(
                f"Large contract KES {tender.awarded_amount:,.0f} awarded to new/unverifiable company"
            )

    # --- Threshold check ---
    if composite_score < _SHELL_THRESHOLD // 2:
        return None

    # Scale weight proportionally to composite
    max_weight = RISK_WEIGHTS[RiskFactorType.SHELL_COMPANY]
    weight = min(max_weight, int(max_weight * composite_score / 100))
    if composite_score >= _SHELL_THRESHOLD:
        weight = max_weight  # Full weight if threshold met

    signal_summary = ", ".join(signals)
    return RiskFactor(
        type=RiskFactorType.SHELL_COMPANY,
        description=f"Shell company indicators ({len(signals)} signals: {signal_summary})",
        weight=weight,
        evidence=evidence,
        related_entity_ids=[winner.id],
    )


def check_price_anomaly(
    tender: Tender, all_tenders: dict[str, Tender]
) -> RiskFactor | None:
    """
    Check if awarded amount is significantly above estimate or comparable tenders.
    """
    if not tender.awarded_amount or not tender.estimated_value:
        return None
    if tender.estimated_value <= 0:
        return None

    # Check against estimate
    price_ratio = tender.awarded_amount / tender.estimated_value

    if price_ratio > 1.5:  # More than 150% of estimate
        percentage = int((price_ratio - 1) * 100)

        # Find comparable tenders in same category
        comparable = [
            t
            for t in all_tenders.values()
            if t.id != tender.id
            and t.category == tender.category
            and t.awarded_amount
            and t.status == TenderStatus.AWARDED
        ]

        evidence = [
            f"Awarded amount: KES {tender.awarded_amount:,.0f}",
            f"Estimated value: KES {tender.estimated_value:,.0f}",
            f"Deviation: {percentage}% above estimate",
        ]

        if comparable:
            avg_comparable = sum(t.awarded_amount for t in comparable) / len(comparable)
            if tender.awarded_amount > avg_comparable * 1.5:
                evidence.append(f"Category average: KES {avg_comparable:,.0f}")

        return RiskFactor(
            type=RiskFactorType.PRICE_ANOMALY,
            description=f"Contract awarded at {percentage}% above estimated value",
            weight=RISK_WEIGHTS[RiskFactorType.PRICE_ANOMALY],
            evidence=evidence,
            related_entity_ids=[tender.id],
        )

    return None


def check_rushed_timeline(tender: Tender) -> RiskFactor | None:
    """
    Check if tender had unusually short submission window.
    """
    if not tender.deadline or not tender.published_date:
        return None
    submission_window = (tender.deadline - tender.published_date).days

    if submission_window <= 5:
        return RiskFactor(
            type=RiskFactorType.RUSHED_TIMELINE,
            description=f"Tender had only {submission_window}-day submission window",
            weight=RISK_WEIGHTS[RiskFactorType.RUSHED_TIMELINE],
            evidence=[
                f"Published: {tender.published_date.isoformat()}",
                f"Deadline: {tender.deadline.isoformat()}",
                f"Window: {submission_window} days",
                "Standard window should be 14-21 days for competitive bidding",
            ],
            related_entity_ids=[tender.id],
        )
    elif submission_window <= 7:
        return RiskFactor(
            type=RiskFactorType.RUSHED_TIMELINE,
            description=f"Tender had short {submission_window}-day submission window",
            weight=RISK_WEIGHTS[RiskFactorType.RUSHED_TIMELINE] // 2,
            evidence=[
                f"Published: {tender.published_date.isoformat()}",
                f"Deadline: {tender.deadline.isoformat()}",
                f"Window: {submission_window} days",
            ],
            related_entity_ids=[tender.id],
        )

    return None


def generate_recommendation(factors: list[RiskFactor], category: RiskCategory) -> str:
    """Generate actionable recommendation based on risk factors."""
    if category == RiskCategory.LOW:
        return "No immediate action required. Routine monitoring recommended."

    recommendations = []

    for factor in factors:
        if factor.type == RiskFactorType.CONFLICT_OF_INTEREST:
            recommendations.append(
                "Request conflict of interest declarations from all parties"
            )
        elif factor.type == RiskFactorType.CARTEL_PATTERN:
            recommendations.append("Review bidding patterns across related tenders")
        elif factor.type == RiskFactorType.SHELL_COMPANY:
            recommendations.append("Verify company credentials and track record")
        elif factor.type == RiskFactorType.PRICE_ANOMALY:
            recommendations.append("Conduct market price verification")
        elif factor.type == RiskFactorType.RUSHED_TIMELINE:
            recommendations.append("Review justification for expedited timeline")
        elif factor.type == RiskFactorType.ML_ANOMALY:
            recommendations.append("Review ML-flagged anomaly patterns in detail")

    if category == RiskCategory.HIGH:
        recommendations.append("Escalate to Internal Audit for immediate review")
        recommendations.append("Consider freezing payment pending investigation")

    # Deduplicate and format
    unique_recs = list(dict.fromkeys(recommendations))
    return " • ".join(unique_recs)
