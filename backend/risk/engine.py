"""
Risk scoring engine for Sentinel.
Computes explainable risk scores based on 5 core rules.
"""

from datetime import date, timedelta
from models import (
    Tender, Company, Director, PublicOfficial, Bid,
    RiskScore, RiskFactor, RiskFactorType, RiskCategory, TenderStatus
)
from graph.builder import find_cartel_clusters, find_conflict_path
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
    coi_factor = check_conflict_of_interest(
        tender, winner, directors, officials, graph
    )
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
        recommendation=recommendation
    )


def check_conflict_of_interest(
    tender: Tender,
    winner: Company | None,
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    graph: nx.Graph
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
                    f"Department: {official.department}"
                ],
                related_entity_ids=[director_id, official.id, winner.id]
            )
    
    # Check graph for indirect paths
    path = find_conflict_path(graph, winner.id, tender.procurement_officer_id)
    if path and len(path) <= 4:  # Within 3 hops
        path_description = " → ".join([
            graph.nodes[node_id].get("label", node_id) for node_id in path
        ])
        return RiskFactor(
            type=RiskFactorType.CONFLICT_OF_INTEREST,
            description=f"Connection path found between winner and procurement officer",
            weight=RISK_WEIGHTS[RiskFactorType.CONFLICT_OF_INTEREST] - 10,  # Reduced weight for indirect
            evidence=[
                f"Path: {path_description}",
                f"Path length: {len(path) - 1} connections"
            ],
            related_entity_ids=path
        )
    
    return None


def check_cartel_pattern(
    tender: Tender,
    tender_bids: list[Bid],
    companies: dict[str, Company],
    cartel_clusters: list[set[str]]
) -> RiskFactor | None:
    """
    Check if bidding companies form a suspected cartel.
    """
    bidding_company_ids = {b.company_id for b in tender_bids}
    
    for cartel in cartel_clusters:
        overlap = bidding_company_ids & cartel
        if len(overlap) >= 3:  # At least 3 cartel members bid on this tender
            cartel_names = [
                companies[cid].name for cid in overlap if cid in companies
            ]
            
            return RiskFactor(
                type=RiskFactorType.CARTEL_PATTERN,
                description=f"Suspected bidding cartel: {len(overlap)} companies that consistently "
                           f"bid together are present in this tender",
                weight=RISK_WEIGHTS[RiskFactorType.CARTEL_PATTERN],
                evidence=[
                    f"Cartel members in this tender: {', '.join(cartel_names)}",
                    f"Total cartel size: {len(cartel)} companies",
                    "Pattern: These companies consistently bid on the same tenders"
                ],
                related_entity_ids=list(overlap)
            )
    
    return None


def check_shell_company(
    tender: Tender,
    winner: Company | None
) -> RiskFactor | None:
    """
    Check if winning company was registered very recently (shell company indicator).
    """
    if not winner:
        return None
    
    # Calculate company age at time of tender deadline
    company_age_days = (tender.deadline - winner.registration_date).days
    
    if company_age_days < 30:
        return RiskFactor(
            type=RiskFactorType.SHELL_COMPANY,
            description=f"Winning company registered only {company_age_days} days before tender deadline",
            weight=RISK_WEIGHTS[RiskFactorType.SHELL_COMPANY],
            evidence=[
                f"Company: {winner.name}",
                f"Registration date: {winner.registration_date.isoformat()}",
                f"Tender deadline: {tender.deadline.isoformat()}",
                f"Company age at deadline: {company_age_days} days",
                f"Contract value: KES {tender.awarded_amount:,.0f}" if tender.awarded_amount else ""
            ],
            related_entity_ids=[winner.id]
        )
    elif company_age_days < 90:
        # Less severe but still notable
        return RiskFactor(
            type=RiskFactorType.SHELL_COMPANY,
            description=f"Winning company registered only {company_age_days} days before tender deadline",
            weight=RISK_WEIGHTS[RiskFactorType.SHELL_COMPANY] // 2,  # Reduced weight
            evidence=[
                f"Company: {winner.name}",
                f"Registration date: {winner.registration_date.isoformat()}",
                f"Tender deadline: {tender.deadline.isoformat()}",
                f"Company age at deadline: {company_age_days} days"
            ],
            related_entity_ids=[winner.id]
        )
    
    return None


def check_price_anomaly(
    tender: Tender,
    all_tenders: dict[str, Tender]
) -> RiskFactor | None:
    """
    Check if awarded amount is significantly above estimate or comparable tenders.
    """
    if not tender.awarded_amount or not tender.estimated_value:
        return None
    
    # Check against estimate
    price_ratio = tender.awarded_amount / tender.estimated_value
    
    if price_ratio > 1.5:  # More than 150% of estimate
        percentage = int((price_ratio - 1) * 100)
        
        # Find comparable tenders in same category
        comparable = [
            t for t in all_tenders.values()
            if t.id != tender.id
            and t.category == tender.category
            and t.awarded_amount
            and t.status == TenderStatus.AWARDED
        ]
        
        evidence = [
            f"Awarded amount: KES {tender.awarded_amount:,.0f}",
            f"Estimated value: KES {tender.estimated_value:,.0f}",
            f"Deviation: {percentage}% above estimate"
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
            related_entity_ids=[tender.id]
        )
    
    return None


def check_rushed_timeline(tender: Tender) -> RiskFactor | None:
    """
    Check if tender had unusually short submission window.
    """
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
                "Standard window should be 14-21 days for competitive bidding"
            ],
            related_entity_ids=[tender.id]
        )
    elif submission_window <= 7:
        return RiskFactor(
            type=RiskFactorType.RUSHED_TIMELINE,
            description=f"Tender had short {submission_window}-day submission window",
            weight=RISK_WEIGHTS[RiskFactorType.RUSHED_TIMELINE] // 2,
            evidence=[
                f"Published: {tender.published_date.isoformat()}",
                f"Deadline: {tender.deadline.isoformat()}",
                f"Window: {submission_window} days"
            ],
            related_entity_ids=[tender.id]
        )
    
    return None


def generate_recommendation(factors: list[RiskFactor], category: RiskCategory) -> str:
    """Generate actionable recommendation based on risk factors."""
    if category == RiskCategory.LOW:
        return "No immediate action required. Routine monitoring recommended."
    
    recommendations = []
    
    for factor in factors:
        if factor.type == RiskFactorType.CONFLICT_OF_INTEREST:
            recommendations.append("Request conflict of interest declarations from all parties")
        elif factor.type == RiskFactorType.CARTEL_PATTERN:
            recommendations.append("Review bidding patterns across related tenders")
        elif factor.type == RiskFactorType.SHELL_COMPANY:
            recommendations.append("Verify company credentials and track record")
        elif factor.type == RiskFactorType.PRICE_ANOMALY:
            recommendations.append("Conduct market price verification")
        elif factor.type == RiskFactorType.RUSHED_TIMELINE:
            recommendations.append("Review justification for expedited timeline")
    
    if category == RiskCategory.HIGH:
        recommendations.append("Escalate to Internal Audit for immediate review")
        recommendations.append("Consider freezing payment pending investigation")
    
    # Deduplicate and format
    unique_recs = list(dict.fromkeys(recommendations))
    return " • ".join(unique_recs)


def compute_all_risk_scores(
    tenders: dict[str, Tender],
    companies: dict[str, Company],
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    bids: list[Bid],
    graph: nx.Graph
) -> dict[str, RiskScore]:
    """
    Compute risk scores for all tenders.
    """
    # Pre-compute cartel clusters once
    cartel_clusters = find_cartel_clusters(graph, bids)
    
    results = {}
    for tender_id, tender in tenders.items():
        results[tender_id] = compute_risk_score(
            tender=tender,
            companies=companies,
            directors=directors,
            officials=officials,
            bids=bids,
            graph=graph,
            cartel_clusters=cartel_clusters,
            all_tenders=tenders
        )
    
    return results
