"""
Unit tests for ML feature extraction.
Verifies that extract_tender_features produces correct ratio-based features
for known inputs, independent of DB or network.
Run with: pytest tests/test_ml_features.py -v
"""

import pytest
from datetime import date, datetime, timezone
import networkx as nx

from models import Tender, Company, Bid, TenderStatus
from ml.features import extract_tender_features, FEATURE_COLUMNS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date(2025, 6, 1)
NOW = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _tender(
    tid="t1",
    estimated_value=1_000_000.0,
    awarded_amount=None,
    awarded_to=None,
    category="Supplies",
    published_date=date(2025, 4, 1),
    deadline=TODAY,
    **kwargs,
) -> Tender:
    return Tender(
        id=tid,
        reference_number=f"REF-{tid}",
        title="Test Tender",
        procuring_entity="Ministry",
        category=category,
        estimated_value=estimated_value,
        awarded_amount=awarded_amount,
        awarded_to=awarded_to,
        procurement_officer_id=None,
        published_date=published_date,
        deadline=deadline,
        status=TenderStatus.AWARDED,
        **kwargs,
    )


def _company(cid="c1", registration_date=date(2020, 1, 1)) -> Company:
    return Company(
        id=cid,
        name=f"Company {cid}",
        registration_number=f"REG-{cid}",
        registration_date=registration_date,
        address="Nairobi",
        director_ids=[],
    )


def _bid(bid_id, tender_id, company_id, amount) -> Bid:
    return Bid(
        id=bid_id,
        tender_id=tender_id,
        company_id=company_id,
        amount=amount,
        submission_date=NOW,
    )


def _empty_graph() -> nx.Graph:
    return nx.Graph()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFeatureColumns:
    def test_all_expected_columns_present(self):
        tenders = {"t1": _tender()}
        df = extract_tender_features(tenders, {}, [], _empty_graph())
        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_returns_one_row_per_tender(self):
        tenders = {"t1": _tender("t1"), "t2": _tender("t2")}
        df = extract_tender_features(tenders, {}, [], _empty_graph())
        assert len(df) == 2
        assert set(df.index) == {"t1", "t2"}


class TestPriceRatio:
    def test_price_ratio_awarded_equals_estimate(self):
        tenders = {"t1": _tender(awarded_to="c1", awarded_amount=1_000_000.0)}
        bids = [_bid("b1", "t1", "c1", 1_000_000.0)]
        df = extract_tender_features(tenders, {"c1": _company()}, bids, _empty_graph())
        assert df.loc["t1", "price_ratio"] == pytest.approx(1.0)

    def test_price_ratio_zero_when_no_award(self):
        tenders = {"t1": _tender(awarded_amount=None)}
        df = extract_tender_features(tenders, {}, [], _empty_graph())
        assert df.loc["t1", "price_ratio"] == pytest.approx(0.0)

    def test_price_ratio_above_one_when_overrun(self):
        tenders = {"t1": _tender(awarded_to="c1", awarded_amount=1_500_000.0)}
        bids = [_bid("b1", "t1", "c1", 1_500_000.0)]
        df = extract_tender_features(tenders, {"c1": _company()}, bids, _empty_graph())
        assert df.loc["t1", "price_ratio"] == pytest.approx(1.5)


class TestTimelineFeature:
    def test_timeline_days_correct(self):
        tenders = {
            "t1": _tender(published_date=date(2025, 5, 1), deadline=date(2025, 5, 31))
        }
        df = extract_tender_features(tenders, {}, [], _empty_graph())
        assert df.loc["t1", "timeline_days"] == 30

    def test_timeline_fallback_when_missing(self):
        """When dates are None, it falls back to safe default."""
        tenders = {"t1": _tender(published_date=None, deadline=None)}
        df = extract_tender_features(tenders, {}, [], _empty_graph())
        assert df.loc["t1", "timeline_days"] == 30  # default fallback


class TestCompanyAgeFeature:
    def test_company_age_days_calculated(self):
        reg_date = date(2023, 6, 1)
        # deadline = TODAY = 2025-06-01 → 730 days
        tenders = {"t1": _tender(awarded_to="c1")}
        companies = {"c1": _company(registration_date=reg_date)}
        df = extract_tender_features(tenders, companies, [], _empty_graph())
        expected_days = (TODAY - reg_date).days
        assert df.loc["t1", "company_age_days"] == expected_days

    def test_company_age_zero_when_no_winner(self):
        tenders = {"t1": _tender(awarded_to=None)}
        df = extract_tender_features(tenders, {}, [], _empty_graph())
        assert df.loc["t1", "company_age_days"] == 0


class TestGraphFeatures:
    def test_graph_degree_captured(self):
        G = nx.Graph()
        G.add_node("c1", type="COMPANY")
        G.add_node("t1", type="TENDER")
        G.add_node("dir1", type="DIRECTOR")
        G.add_edge("c1", "t1", relationship="BID_ON")
        G.add_edge("c1", "dir1", relationship="DIRECTOR_OF")

        tenders = {"t1": _tender(awarded_to="c1")}
        df = extract_tender_features(tenders, {"c1": _company()}, [], G)
        assert df.loc["t1", "graph_degree"] == 2

    def test_official_distance_capped_at_10(self):
        """If no official in graph, distance defaults to 99 → capped at 10."""
        G = nx.Graph()
        G.add_node("c1", type="COMPANY")
        tenders = {"t1": _tender(awarded_to="c1")}
        df = extract_tender_features(tenders, {"c1": _company()}, [], G)
        assert df.loc["t1", "official_distance"] == 10

    def test_official_distance_short_path(self):
        """Direct company→official link should give distance 1."""
        G = nx.Graph()
        G.add_node("c1", type="COMPANY")
        G.add_node("off1", type="OFFICIAL")
        G.add_edge("c1", "off1", relationship="RELATED_TO")

        tenders = {"t1": _tender(awarded_to="c1")}
        df = extract_tender_features(tenders, {"c1": _company()}, [], G)
        assert df.loc["t1", "official_distance"] == 1


class TestBidFeatures:
    def test_bidder_count(self):
        tenders = {"t1": _tender(awarded_to="c1", awarded_amount=900_000.0)}
        bids = [
            _bid("b1", "t1", "c1", 900_000.0),
            _bid("b2", "t1", "c2", 950_000.0),
            _bid("b3", "t1", "c3", 1_000_000.0),
        ]
        df = extract_tender_features(tenders, {"c1": _company()}, bids, _empty_graph())
        assert df.loc["t1", "bidder_count"] == 3

    def test_participation_only_bids_do_not_create_price_spread(self):
        tenders = {"t1": _tender(awarded_to="c1", awarded_amount=900_000.0)}
        bids = [
            _bid("b1", "t1", "c1", None),
            _bid("b2", "t1", "c2", None),
            _bid("b3", "t1", "c3", None),
        ]
        df = extract_tender_features(tenders, {"c1": _company()}, bids, _empty_graph())
        assert df.loc["t1", "bidder_count"] == 3
        assert df.loc["t1", "bid_spread_ratio"] == pytest.approx(0.0)
        assert df.loc["t1", "winner_margin_ratio"] == pytest.approx(0.0)

    def test_win_rate(self):
        """Company c1 wins 1 out of 2 tenders → win_rate = 0.5."""
        tenders = {
            "t1": _tender("t1", awarded_to="c1"),
            "t2": _tender("t2", awarded_to="c2"),
        }
        bids = [
            _bid("b1", "t1", "c1", 900_000.0),
            _bid("b2", "t2", "c1", 950_000.0),
            _bid("b3", "t2", "c2", 900_000.0),
        ]
        companies = {"c1": _company("c1"), "c2": _company("c2")}
        df = extract_tender_features(tenders, companies, bids, _empty_graph())
        assert df.loc["t1", "win_rate"] == pytest.approx(0.5)
