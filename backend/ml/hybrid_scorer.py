"""
Hybrid risk scorer combining rule-based detection with Isolation Forest ML.
"""

import networkx as nx
import pandas as pd

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
)
from risk.engine import compute_risk_score
from graph.builder import find_cartel_clusters
from ml.features import extract_tender_features
from ml.anomaly_detector import AnomalyDetector

# Weight split between rules and ML
RULE_WEIGHT = 0.6
ML_WEIGHT = 0.4


class HybridRiskScorer:
    """
    Combines rule-based risk factors with ML anomaly detection.
    """

    def __init__(self):
        self.detector = AnomalyDetector()

    def fit(
        self,
        tenders: dict[str, Tender],
        companies: dict[str, Company],
        bids: list[Bid],
        graph: nx.Graph,
    ):
        """Train the Isolation Forest on current data."""
        features_df = extract_tender_features(tenders, companies, bids, graph)
        self.detector.fit(features_df)
        self.detector.save("default")

    def score_all(
        self,
        tenders: dict[str, Tender],
        companies: dict[str, Company],
        directors: dict[str, Director],
        officials: dict[str, PublicOfficial],
        bids: list[Bid],
        graph: nx.Graph,
    ) -> dict[str, RiskScore]:
        """
        Compute hybrid risk scores for all tenders.
        Falls back to rules-only if ML model is not fitted.
        """
        # Extract features and score with ML
        features_df = extract_tender_features(tenders, companies, bids, graph)
        ml_scores = None

        if not self.detector.is_fitted:
            loaded = self.detector.load("default")
            if not loaded:
                self.fit(tenders, companies, bids, graph)

        if self.detector.is_fitted:
            ml_scores = self.detector.score(features_df)

        # Build lookup structures
        bids_by_tender: dict[str, list[Bid]] = {}
        for b in bids:
            bids_by_tender.setdefault(b.tender_id, []).append(b)

        # Pre-compute cartel clusters once
        cartel_clusters = find_cartel_clusters(graph, bids)

        results = {}
        for tid, tender in tenders.items():
            tender_bids = bids_by_tender.get(tid, [])

            # Rule-based score
            rule_risk = compute_risk_score(
                tender=tender,
                companies=companies,
                directors=directors,
                officials=officials,
                bids=tender_bids,
                graph=graph,
                cartel_clusters=cartel_clusters,
                all_tenders=tenders,
            )

            # ML anomaly score
            ml_anomaly_score = 0.0
            ml_importance = {}
            if ml_scores is not None and tid in ml_scores.index:
                row = ml_scores.loc[tid]
                ml_anomaly_score = row["anomaly_score"]
                ml_importance = row["feature_importance"]

            # Fuse scores
            fused_score = int(
                RULE_WEIGHT * rule_risk.overall + ML_WEIGHT * ml_anomaly_score
            )
            fused_score = min(100, max(0, fused_score))

            # Add ML factor if significant
            factors = list(rule_risk.factors)
            if ml_anomaly_score >= 50:
                top_features = ", ".join(
                    f"{k} ({v:.0%})" for k, v in list(ml_importance.items())[:3]
                )
                factors.append(
                    RiskFactor(
                        type=RiskFactorType.PRICE_ANOMALY,
                        description=f"ML anomaly detection flagged this tender (score: {ml_anomaly_score:.0f}/100). Top signals: {top_features}",
                        weight=int(ml_anomaly_score * ML_WEIGHT * 0.4),
                        evidence=[
                            f"Isolation Forest anomaly score: {ml_anomaly_score:.1f}/100",
                            f"Top contributing features: {top_features}",
                        ],
                        related_entity_ids=[],
                    )
                )

            # Categorize
            if fused_score >= 50:
                category = RiskCategory.HIGH
            elif fused_score >= 25:
                category = RiskCategory.MEDIUM
            else:
                category = RiskCategory.LOW

            results[tid] = RiskScore(
                overall=fused_score,
                category=category,
                factors=factors,
                recommendation=rule_risk.recommendation,
            )

        return results
