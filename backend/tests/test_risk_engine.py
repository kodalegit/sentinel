"""
Unit tests for the risk scoring engine.
Tests each rule in isolation with deterministic fixture data.
Run with: pytest tests/test_risk_engine.py -v
"""

import pytest
from datetime import date, datetime, timezone

from models import (
    Tender,
    Company,
    Director,
    PublicOfficial,
    Bid,
    TenderStatus,
    RiskFactorType,
)
from risk.engine import (
    check_conflict_of_interest,
    check_cartel_pattern,
    check_shell_company,
    check_price_anomaly,
    check_rushed_timeline,
)
import networkx as nx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TODAY = date(2025, 6, 1)
NOW = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def _tender(**kwargs) -> Tender:
    defaults = dict(
        id="tender-1",
        reference_number="PPIP/2025/001",
        title="Office Supplies",
        procuring_entity="Ministry of Finance",
        category="Supplies",
        estimated_value=1_000_000.0,
        awarded_amount=None,
        awarded_to=None,
        procurement_officer_id=None,
        published_date=date(2025, 5, 1),
        deadline=TODAY,
        status=TenderStatus.AWARDED,
    )
    defaults.update(kwargs)
    return Tender(**defaults)


def _company(**kwargs) -> Company:
    defaults = dict(
        id="company-1",
        name="Acme Ltd",
        registration_number="REG001",
        registration_date=date(2020, 1, 1),
        address="123 Main St, Nairobi",
        phone="0712345678",
        contact_email="acme@email.co.ke",
        director_ids=[],
    )
    defaults.update(kwargs)
    return Company(**defaults)


def _official(**kwargs) -> PublicOfficial:
    defaults = dict(
        id="official-1",
        name="Jane Wanjiru",
        department="Procurement",
        position="Procurement Officer",
    )
    defaults.update(kwargs)
    return PublicOfficial(**defaults)


def _director(**kwargs) -> Director:
    defaults = dict(
        id="director-1",
        name="John Doe",
        national_id="ID123456",
        company_ids=["company-1"],
    )
    defaults.update(kwargs)
    return Director(**defaults)


def _bid(**kwargs) -> Bid:
    defaults = dict(
        id="bid-1",
        tender_id="tender-1",
        company_id="company-1",
        amount=950_000.0,
        submission_date=NOW,
    )
    defaults.update(kwargs)
    return Bid(**defaults)


# ---------------------------------------------------------------------------
# check_conflict_of_interest
# ---------------------------------------------------------------------------


class TestConflictOfInterest:
    def test_no_conflict_when_no_award(self):
        tender = _tender(awarded_to=None, procurement_officer_id="official-1")
        factor = check_conflict_of_interest(tender, None, {}, {}, nx.Graph())
        assert factor is None

    def test_no_conflict_when_no_officer(self):
        tender = _tender(awarded_to="company-1", procurement_officer_id=None)
        company = _company()
        factor = check_conflict_of_interest(tender, company, {}, {}, nx.Graph())
        assert factor is None

    def test_detects_shared_director(self):
        """Company and official share a director — conflict expected."""
        tender = _tender(awarded_to="company-1", procurement_officer_id="official-1")
        company = _company(director_ids=["director-1"])
        official = _official()
        director = _director(id="director-1")

        # Build graph: company -> director, official -> director
        G = nx.Graph()
        G.add_node("company-1", type="COMPANY", label="Acme Ltd")
        G.add_node("director-1", type="DIRECTOR", label="John Doe")
        G.add_node("official-1", type="OFFICIAL", label="Jane Wanjiru")
        G.add_edge("company-1", "director-1", relationship="DIRECTOR_OF")
        G.add_edge("official-1", "director-1", relationship="RELATED_TO")

        factor = check_conflict_of_interest(
            tender, company, {"director-1": director}, {"official-1": official}, G
        )
        assert factor is not None
        assert factor.type == RiskFactorType.CONFLICT_OF_INTEREST

    def test_no_conflict_when_unconnected(self):
        tender = _tender(awarded_to="company-1", procurement_officer_id="official-1")
        company = _company()
        official = _official()

        G = nx.Graph()
        G.add_node("company-1", type="COMPANY")
        G.add_node("official-1", type="OFFICIAL")
        # No path between them

        factor = check_conflict_of_interest(
            tender, company, {}, {"official-1": official}, G
        )
        assert factor is None


# ---------------------------------------------------------------------------
# check_cartel_pattern
# ---------------------------------------------------------------------------


class TestCartelPattern:
    def test_detects_cartel_when_all_bidders_in_cluster(self):
        """3+ companies from same cartel cluster bid on same tender → cartel flag."""
        tender = _tender()
        bids = [
            _bid(id="b1", company_id="company-1"),
            _bid(id="b2", company_id="company-2"),
            _bid(id="b3", company_id="company-3"),
        ]
        companies = {
            "company-1": _company(id="company-1"),
            "company-2": _company(id="company-2", name="Beta Ltd"),
            "company-3": _company(id="company-3", name="Gamma Ltd"),
        }
        cartel_clusters = [{"company-1", "company-2", "company-3"}]

        factor = check_cartel_pattern(tender, bids, companies, cartel_clusters)
        assert factor is not None
        assert factor.type == RiskFactorType.CARTEL_PATTERN

    def test_no_cartel_when_bidders_not_in_same_cluster(self):
        tender = _tender()
        bids = [
            _bid(id="b1", company_id="company-1"),
            _bid(id="b2", company_id="company-2"),
        ]
        companies = {
            "company-1": _company(id="company-1"),
            "company-2": _company(id="company-2", name="Beta"),
        }
        # Each company is in its own separate cluster
        cartel_clusters = [{"company-1"}, {"company-2"}]

        factor = check_cartel_pattern(tender, bids, companies, cartel_clusters)
        assert factor is None

    def test_no_cartel_with_single_bidder(self):
        tender = _tender()
        bids = [_bid()]
        factor = check_cartel_pattern(tender, bids, {}, [{"company-1"}])
        assert factor is None


# ---------------------------------------------------------------------------
# check_shell_company
# ---------------------------------------------------------------------------


class TestShellCompany:
    def test_detects_newly_registered_company(self):
        """Company registered 10 days before award deadline AND high value → shell signal."""
        tender = _tender(
            awarded_to="company-1",
            estimated_value=5_000_000.0,
            awarded_amount=5_000_000.0,
        )
        # 10 days before deadline → very new
        company = _company(registration_date=date(2025, 5, 22))
        factor = check_shell_company(tender, company)
        assert factor is not None
        assert factor.type == RiskFactorType.SHELL_COMPANY

    def test_detects_registration_after_tender_deadline(self):
        tender = _tender(
            awarded_to="company-1",
            estimated_value=5_000_000.0,
            awarded_amount=5_000_000.0,
            deadline=date(2025, 6, 1),
        )
        company = _company(registration_date=date(2025, 6, 10))
        factor = check_shell_company(tender, company)
        assert factor is not None
        assert factor.type == RiskFactorType.SHELL_COMPANY
        assert any("after tender deadline" in item.lower() for item in factor.evidence)

    def test_no_flag_for_established_company(self):
        """Old company with specific address, directors, and corporate email → no flag."""
        tender = _tender(awarded_to="company-1")
        # Old company, specific address, directors listed, corporate email
        company = _company(
            registration_date=date(2010, 1, 1),
            address="4th Floor, Westlands Plaza, Nairobi, Kenya",  # specific
            director_ids=["director-1"],  # has directors
            contact_email="info@acmeltd.co.ke",  # corporate domain
            data_quality_flags={"director_count": 1, "email_is_generic": False},
        )
        factor = check_shell_company(tender, company)
        assert factor is None

    def test_ppip_sparse_profile_is_not_penalized_for_missing_directors(self):
        tender = _tender(awarded_to="company-1", awarded_amount=750_000.0)
        company = _company(
            registration_date=date(2018, 1, 1),
            address="5th Floor Kimathi House Nairobi",
            contact_email="supplier@firm.co.ke",
            data_quality_flags={
                "director_count": 0,
                "has_ownership": False,
                "email_is_public_webmail": False,
                "source_expectations": {
                    "expects_directors": False,
                    "expects_ownership": False,
                },
            },
        )
        factor = check_shell_company(tender, company)
        assert factor is None

    def test_no_flag_when_no_winner(self):
        tender = _tender(awarded_to=None)
        factor = check_shell_company(tender, None)
        assert factor is None


# ---------------------------------------------------------------------------
# check_price_anomaly
# ---------------------------------------------------------------------------


class TestPriceAnomaly:
    def test_detects_large_price_deviation(self):
        """Awarded amount significantly above estimate → price anomaly."""
        tender = _tender(
            awarded_to="company-1",
            estimated_value=1_000_000.0,
            awarded_amount=1_600_000.0,  # 60% over estimate
        )
        factor = check_price_anomaly(tender, {})
        assert factor is not None
        assert factor.type == RiskFactorType.PRICE_ANOMALY

    def test_no_flag_within_normal_range(self):
        tender = _tender(
            awarded_to="company-1",
            estimated_value=1_000_000.0,
            awarded_amount=1_050_000.0,  # 5% over — fine
        )
        factor = check_price_anomaly(tender, {})
        assert factor is None

    def test_no_flag_without_awarded_amount(self):
        tender = _tender(awarded_to="company-1", awarded_amount=None)
        factor = check_price_anomaly(tender, {})
        assert factor is None


# ---------------------------------------------------------------------------
# check_rushed_timeline
# ---------------------------------------------------------------------------


class TestRushedTimeline:
    def test_flags_very_short_window(self):
        """5-day submission window is too short."""
        tender = _tender(
            published_date=date(2025, 5, 26),
            deadline=TODAY,  # 6 days
        )
        factor = check_rushed_timeline(tender)
        assert factor is not None
        assert factor.type == RiskFactorType.RUSHED_TIMELINE

    def test_no_flag_for_adequate_window(self):
        tender = _tender(
            published_date=date(2025, 4, 1),
            deadline=TODAY,  # 61 days
        )
        factor = check_rushed_timeline(tender)
        assert factor is None
