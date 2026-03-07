import networkx as nx

from models import Company, Director, PublicOfficial, Tender, TenderStatus
from graph.builder import build_procurement_graph
from graph.communities import _find_shared_attributes


def _company(**kwargs) -> Company:
    defaults = dict(
        id="company-1",
        name="Acme Ltd",
        registration_number="REG001",
        registration_date=None,
        address="Nairobi",
        phone="0712345678",
        contact_email="ops@acme.co.ke",
        director_ids=[],
    )
    defaults.update(kwargs)
    return Company(**defaults)


def _director(**kwargs) -> Director:
    defaults = dict(
        id="director-1",
        name="Jane Doe",
        national_id=None,
        company_ids=[],
    )
    defaults.update(kwargs)
    return Director(**defaults)


def _official(**kwargs) -> PublicOfficial:
    defaults = dict(
        id="official-1",
        name="Officer One",
        department="Procurement",
        position="Officer",
    )
    defaults.update(kwargs)
    return PublicOfficial(**defaults)


def _tender(**kwargs) -> Tender:
    defaults = dict(
        id="tender-1",
        reference_number="REF-1",
        title="Office Supplies",
        description="",
        procuring_entity="Ministry",
        category="Supplies",
        estimated_value=1000000.0,
        published_date=None,
        deadline=None,
        status=TenderStatus.OPEN,
    )
    defaults.update(kwargs)
    return Tender(**defaults)


def test_build_procurement_graph_skips_vague_shared_address_edges():
    companies = {
        "company-1": _company(
            id="company-1",
            address="Moi Avenue",
            phone="0712345678",
            contact_email="alpha@acme.co.ke",
        ),
        "company-2": _company(
            id="company-2",
            name="Beta Ltd",
            address="Moi Avenue",
            phone="0723456789",
            contact_email="beta@beta.co.ke",
        ),
    }

    graph = build_procurement_graph(
        tenders={},
        companies=companies,
        directors={},
        officials={},
        bids=[],
    )

    assert not graph.has_edge("company-1", "company-2")


def test_build_procurement_graph_skips_generic_shared_phone_edges():
    companies = {
        "company-1": _company(
            id="company-1",
            phone="0700000000",
            address="Plot 12 River Road Nairobi",
            contact_email="alpha@acme.co.ke",
        ),
        "company-2": _company(
            id="company-2",
            name="Beta Ltd",
            phone="0700000000",
            address="Plot 99 Mombasa Road Nairobi",
            contact_email="beta@beta.co.ke",
        ),
    }

    graph = build_procurement_graph(
        tenders={},
        companies=companies,
        directors={},
        officials={},
        bids=[],
    )

    assert not graph.has_edge("company-1", "company-2")


def test_build_procurement_graph_keeps_specific_shared_address_edges():
    companies = {
        "company-1": _company(
            id="company-1",
            physical_address="4th Floor Westlands Plaza Nairobi",
            phone="0712345678",
            contact_email="alpha@acme.co.ke",
        ),
        "company-2": _company(
            id="company-2",
            name="Beta Ltd",
            physical_address="4th Floor Westlands Plaza Nairobi",
            phone="0723456789",
            contact_email="beta@beta.co.ke",
        ),
    }

    graph = build_procurement_graph(
        tenders={},
        companies=companies,
        directors={},
        officials={},
        bids=[],
    )

    assert graph.has_edge("company-1", "company-2")
    assert graph.edges["company-1", "company-2"]["relationship"] == "SHARES_ADDRESS"


def test_find_shared_attributes_ignores_vague_addresses_and_generic_phones():
    companies = {
        "company-1": _company(
            id="company-1",
            address="Moi Avenue",
            phone="0700000000",
            contact_email="alpha@acme.co.ke",
        ),
        "company-2": _company(
            id="company-2",
            name="Beta Ltd",
            address="Moi Avenue",
            phone="0700000000",
            contact_email="beta@beta.co.ke",
        ),
    }

    shared = _find_shared_attributes(nx.Graph(), ["company-1", "company-2"], companies)

    assert shared["addresses"] == []
    assert shared["phones"] == []
