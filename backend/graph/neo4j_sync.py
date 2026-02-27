"""
Sync PostgreSQL entities to Neo4j graph database.
Handles node and edge creation for the procurement graph.
"""

import logging
from typing import Any

from models import Company, Director, PublicOfficial, Tender, Bid, EdgeType
from graph.neo4j_driver import get_neo4j_session
from graph.normalization import (
    normalize_phone,
    normalize_address_key,
    is_generic_email,
    MAX_SHARED_EDGES_PER_COMPANY,
    MAX_GROUP_SIZE_ADDRESS,
    MAX_GROUP_SIZE_PHONE,
    MAX_GROUP_SIZE_EMAIL,
)

logger = logging.getLogger(__name__)


async def sync_graph_to_neo4j(
    companies: dict[str, Company],
    directors: dict[str, Director],
    officials: dict[str, PublicOfficial],
    tenders: dict[str, Tender],
    bids: list[Bid],
    tender_risks: dict[str, str] | None = None,
    incremental: bool = False,
) -> dict[str, int]:
    """
    Sync all entities from PostgreSQL to Neo4j.

    Args:
        incremental: If True, use MERGE to upsert nodes/edges without clearing.
                    If False (default), clear and rebuild entire graph.

    Returns counts of created/updated nodes and edges.
    """
    stats = {
        "companies": 0,
        "directors": 0,
        "officials": 0,
        "tenders": 0,
        "edges": 0,
        "mode": "incremental" if incremental else "full_rebuild",
    }

    async with get_neo4j_session() as session:
        # Create constraints and indexes (idempotent)
        await _create_constraints(session)

        if not incremental:
            # Full rebuild: clear existing graph
            await session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing Neo4j graph for full rebuild")

            # Create nodes
            stats["companies"] = await _create_company_nodes(session, companies)
            stats["directors"] = await _create_director_nodes(session, directors)
            stats["officials"] = await _create_official_nodes(session, officials)
            stats["tenders"] = await _create_tender_nodes(
                session, tenders, tender_risks
            )

            # Create edges
            edge_count = 0
            edge_count += await _create_director_edges(session, companies)
            edge_count += await _create_bid_edges(session, bids)
            edge_count += await _create_official_relationship_edges(session, officials)
            edge_count += await _create_shared_attribute_edges(session, companies)
            stats["edges"] = edge_count
        else:
            # Incremental: upsert nodes and edges
            stats["companies"] = await _upsert_company_nodes(session, companies)
            stats["directors"] = await _upsert_director_nodes(session, directors)
            stats["officials"] = await _upsert_official_nodes(session, officials)
            stats["tenders"] = await _upsert_tender_nodes(
                session, tenders, tender_risks
            )

            # For edges, we need to be more careful - only add missing ones
            edge_count = 0
            edge_count += await _upsert_director_edges(session, companies)
            edge_count += await _upsert_bid_edges(session, bids)
            stats["edges"] = edge_count

        logger.info(f"Neo4j sync complete: {stats}")

    return stats


async def _create_constraints(session) -> None:
    """Create uniqueness constraints and indexes."""
    constraints = [
        "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT director_id IF NOT EXISTS FOR (d:Director) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT official_id IF NOT EXISTS FOR (o:Official) REQUIRE o.id IS UNIQUE",
        "CREATE CONSTRAINT tender_id IF NOT EXISTS FOR (t:Tender) REQUIRE t.id IS UNIQUE",
    ]
    for constraint in constraints:
        try:
            await session.run(constraint)
        except Exception as e:
            # Constraint may already exist
            logger.debug(f"Constraint creation: {e}")


async def _create_company_nodes(session, companies: dict[str, Company]) -> int:
    """Create Company nodes in Neo4j."""
    if not companies:
        return 0

    company_data = [
        {
            "id": c.id,
            "name": c.name,
            "address": c.address or "",
            "phone": c.phone or "",
            "email": c.contact_email or "",
            "registration_date": (
                c.registration_date.isoformat() if c.registration_date else None
            ),
            "supplier_type": c.supplier_type or "",
            "physical_address": c.physical_address or "",
        }
        for c in companies.values()
    ]

    result = await session.run(
        """
        UNWIND $companies AS c
        CREATE (comp:Company {
            id: c.id,
            name: c.name,
            address: c.address,
            phone: c.phone,
            email: c.email,
            registration_date: c.registration_date,
            supplier_type: c.supplier_type,
            physical_address: c.physical_address
        })
        RETURN count(comp) as count
    """,
        companies=company_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_director_nodes(session, directors: dict[str, Director]) -> int:
    """Create Director nodes in Neo4j."""
    if not directors:
        return 0

    director_data = [
        {
            "id": d.id,
            "name": d.name,
            "id_number": d.id_number or "",
        }
        for d in directors.values()
    ]

    result = await session.run(
        """
        UNWIND $directors AS d
        CREATE (dir:Director {
            id: d.id,
            name: d.name,
            id_number: d.id_number
        })
        RETURN count(dir) as count
    """,
        directors=director_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_official_nodes(session, officials: dict[str, PublicOfficial]) -> int:
    """Create Official nodes in Neo4j."""
    if not officials:
        return 0

    official_data = [
        {
            "id": o.id,
            "name": o.name,
            "position": o.position or "",
            "department": o.department or "",
        }
        for o in officials.values()
    ]

    result = await session.run(
        """
        UNWIND $officials AS o
        CREATE (off:Official {
            id: o.id,
            name: o.name,
            position: o.position,
            department: o.department
        })
        RETURN count(off) as count
    """,
        officials=official_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_tender_nodes(
    session,
    tenders: dict[str, Tender],
    tender_risks: dict[str, str] | None = None,
) -> int:
    """Create Tender nodes in Neo4j."""
    if not tenders:
        return 0

    tender_risks = tender_risks or {}
    tender_data = [
        {
            "id": t.id,
            "title": t.title,
            "value": float(t.value) if t.value else 0.0,
            "status": t.status or "",
            "procurement_method": t.procurement_method or "",
            "risk_level": tender_risks.get(t.id, "LOW"),
        }
        for t in tenders.values()
    ]

    result = await session.run(
        """
        UNWIND $tenders AS t
        CREATE (ten:Tender {
            id: t.id,
            title: t.title,
            value: t.value,
            status: t.status,
            procurement_method: t.procurement_method,
            risk_level: t.risk_level
        })
        RETURN count(ten) as count
    """,
        tenders=tender_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_director_edges(session, companies: dict[str, Company]) -> int:
    """Create DIRECTED_BY edges between companies and directors."""
    edges = []
    for company in companies.values():
        for director_id in company.director_ids:
            edges.append(
                {
                    "company_id": company.id,
                    "director_id": director_id,
                }
            )

    if not edges:
        return 0

    result = await session.run(
        """
        UNWIND $edges AS e
        MATCH (c:Company {id: e.company_id})
        MATCH (d:Director {id: e.director_id})
        CREATE (c)-[r:DIRECTED_BY]->(d)
        RETURN count(r) as count
    """,
        edges=edges,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_bid_edges(session, bids: list[Bid]) -> int:
    """Create BID_ON edges between companies and tenders."""
    if not bids:
        return 0

    bid_data = [
        {
            "company_id": b.company_id,
            "tender_id": b.tender_id,
            "amount": float(b.amount) if b.amount else 0.0,
            "is_winner": b.is_winner,
        }
        for b in bids
    ]

    result = await session.run(
        """
        UNWIND $bids AS b
        MATCH (c:Company {id: b.company_id})
        MATCH (t:Tender {id: b.tender_id})
        CREATE (c)-[r:BID_ON {amount: b.amount, is_winner: b.is_winner}]->(t)
        RETURN count(r) as count
    """,
        bids=bid_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_official_relationship_edges(
    session,
    officials: dict[str, PublicOfficial],
) -> int:
    """Create relationship edges between officials and directors."""
    edges = []
    for official in officials.values():
        for rel in official.relationships:
            edges.append(
                {
                    "official_id": official.id,
                    "director_id": rel.director_id,
                    "relationship_type": rel.relationship_type,
                }
            )

    if not edges:
        return 0

    result = await session.run(
        """
        UNWIND $edges AS e
        MATCH (o:Official {id: e.official_id})
        MATCH (d:Director {id: e.director_id})
        CREATE (o)-[r:RELATED_TO {type: e.relationship_type}]->(d)
        SET r.suspicious = true
        RETURN count(r) as count
    """,
        edges=edges,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _create_shared_attribute_edges(session, companies: dict[str, Company]) -> int:
    """Create edges for shared addresses, phones, and emails using Neo4j."""
    from collections import defaultdict

    total = 0

    # 1. Shared addresses using Python-side normalization
    address_groups: dict[str, list[str]] = defaultdict(list)
    for company in companies.values():
        if company.physical_address:
            key = normalize_address_key(company.physical_address)
            if key:
                address_groups[key].append(company.id)

    address_edges = []
    edge_count = defaultdict(int)
    for group in address_groups.values():
        if len(group) < 2 or len(group) > MAX_GROUP_SIZE_ADDRESS:
            continue
        for i, id1 in enumerate(group):
            if edge_count[id1] >= MAX_SHARED_EDGES_PER_COMPANY:
                continue
            for id2 in group[i + 1 :]:
                if edge_count[id2] >= MAX_SHARED_EDGES_PER_COMPANY:
                    continue
                address_edges.append({"id1": id1, "id2": id2})
                edge_count[id1] += 1
                edge_count[id2] += 1

    if address_edges:
        result = await session.run(
            """
            UNWIND $edges AS e
            MATCH (c1:Company {id: e.id1})
            MATCH (c2:Company {id: e.id2})
            CREATE (c1)-[r:SHARES_ADDRESS {suspicious: true}]->(c2)
            RETURN count(r) as count
        """,
            edges=address_edges,
        )
        record = await result.single()
        total += record["count"] if record else 0

    # 2. Shared phones using Python-side normalization
    phone_groups: dict[str, list[str]] = defaultdict(list)
    for company in companies.values():
        if company.phone:
            norm_phone = normalize_phone(company.phone)
            if norm_phone:
                phone_groups[norm_phone].append(company.id)

    phone_edges = []
    edge_count = defaultdict(int)
    for group in phone_groups.values():
        if len(group) < 2 or len(group) > MAX_GROUP_SIZE_PHONE:
            continue
        for i, id1 in enumerate(group):
            if edge_count[id1] >= MAX_SHARED_EDGES_PER_COMPANY:
                continue
            for id2 in group[i + 1 :]:
                if edge_count[id2] >= MAX_SHARED_EDGES_PER_COMPANY:
                    continue
                phone_edges.append({"id1": id1, "id2": id2})
                edge_count[id1] += 1
                edge_count[id2] += 1

    if phone_edges:
        result = await session.run(
            """
            UNWIND $edges AS e
            MATCH (c1:Company {id: e.id1})
            MATCH (c2:Company {id: e.id2})
            CREATE (c1)-[r:SHARES_PHONE {suspicious: true}]->(c2)
            RETURN count(r) as count
        """,
            edges=phone_edges,
        )
        record = await result.single()
        total += record["count"] if record else 0

    # 3. Shared emails using Python-side normalization
    email_groups: dict[str, list[str]] = defaultdict(list)
    for company in companies.values():
        if company.contact_email:
            email = company.contact_email.strip().lower()
            if email and "@" in email and not is_generic_email(email):
                email_groups[email].append(company.id)

    email_edges = []
    edge_count = defaultdict(int)
    for group in email_groups.values():
        if len(group) < 2 or len(group) > MAX_GROUP_SIZE_EMAIL:
            continue
        for i, id1 in enumerate(group):
            if edge_count[id1] >= MAX_SHARED_EDGES_PER_COMPANY:
                continue
            for id2 in group[i + 1 :]:
                if edge_count[id2] >= MAX_SHARED_EDGES_PER_COMPANY:
                    continue
                email_edges.append({"id1": id1, "id2": id2})
                edge_count[id1] += 1
                edge_count[id2] += 1

    if email_edges:
        result = await session.run(
            """
            UNWIND $edges AS e
            MATCH (c1:Company {id: e.id1})
            MATCH (c2:Company {id: e.id2})
            CREATE (c1)-[r:SHARES_EMAIL {suspicious: true}]->(c2)
            RETURN count(r) as count
        """,
            edges=email_edges,
        )
        record = await result.single()
        total += record["count"] if record else 0

    # 4. Shared directors (companies with common directors)
    result = await session.run(
        """
        MATCH (c1:Company)-[:DIRECTED_BY]->(d:Director)<-[:DIRECTED_BY]-(c2:Company)
        WHERE c1.id < c2.id
        WITH c1, c2, collect(d.name) as shared_directors
        CREATE (c1)-[r:SHARES_DIRECTOR {suspicious: true, directors: shared_directors}]->(c2)
        RETURN count(r) as count
    """
    )
    record = await result.single()
    total += record["count"] if record else 0

    logger.info(f"Created {total} shared attribute edges")
    return total


async def _upsert_company_nodes(session, companies: dict[str, Company]) -> int:
    """Upsert Company nodes using MERGE (incremental sync)."""
    if not companies:
        return 0

    company_data = [
        {
            "id": c.id,
            "name": c.name,
            "address": c.address or "",
            "phone": c.phone or "",
            "email": c.contact_email or "",
            "registration_date": (
                c.registration_date.isoformat() if c.registration_date else None
            ),
            "supplier_type": c.supplier_type or "",
            "physical_address": c.physical_address or "",
        }
        for c in companies.values()
    ]

    result = await session.run(
        """
        UNWIND $companies AS c
        MERGE (comp:Company {id: c.id})
        SET comp.name = c.name,
            comp.address = c.address,
            comp.phone = c.phone,
            comp.email = c.email,
            comp.registration_date = c.registration_date,
            comp.supplier_type = c.supplier_type,
            comp.physical_address = c.physical_address
        RETURN count(comp) as count
    """,
        companies=company_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _upsert_director_nodes(session, directors: dict[str, Director]) -> int:
    """Upsert Director nodes using MERGE (incremental sync)."""
    if not directors:
        return 0

    director_data = [
        {
            "id": d.id,
            "name": d.name,
            "id_number": d.id_number or "",
        }
        for d in directors.values()
    ]

    result = await session.run(
        """
        UNWIND $directors AS d
        MERGE (dir:Director {id: d.id})
        SET dir.name = d.name,
            dir.id_number = d.id_number
        RETURN count(dir) as count
    """,
        directors=director_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _upsert_official_nodes(session, officials: dict[str, PublicOfficial]) -> int:
    """Upsert Official nodes using MERGE (incremental sync)."""
    if not officials:
        return 0

    official_data = [
        {
            "id": o.id,
            "name": o.name,
            "department": o.department or "",
            "position": o.position or "",
        }
        for o in officials.values()
    ]

    result = await session.run(
        """
        UNWIND $officials AS o
        MERGE (off:Official {id: o.id})
        SET off.name = o.name,
            off.department = o.department,
            off.position = o.position
        RETURN count(off) as count
    """,
        officials=official_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _upsert_tender_nodes(
    session, tenders: dict[str, Tender], tender_risks: dict[str, str] | None = None
) -> int:
    """Upsert Tender nodes using MERGE (incremental sync)."""
    if not tenders:
        return 0

    tender_risks = tender_risks or {}
    tender_data = [
        {
            "id": t.id,
            "title": t.title,
            "reference": t.reference_number or "",
            "value": float(t.estimated_value) if t.estimated_value else 0.0,
            "status": t.status or "",
            "risk_level": tender_risks.get(t.id, "LOW"),
        }
        for t in tenders.values()
    ]

    result = await session.run(
        """
        UNWIND $tenders AS t
        MERGE (ten:Tender {id: t.id})
        SET ten.title = t.title,
            ten.reference = t.reference,
            ten.value = t.value,
            ten.status = t.status,
            ten.risk_level = t.risk_level
        RETURN count(ten) as count
    """,
        tenders=tender_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _upsert_director_edges(session, companies: dict[str, Company]) -> int:
    """Upsert DIRECTED_BY edges using MERGE (incremental sync)."""
    edges = []
    for company in companies.values():
        for director_id in company.director_ids:
            edges.append({"company_id": company.id, "director_id": director_id})

    if not edges:
        return 0

    result = await session.run(
        """
        UNWIND $edges AS e
        MATCH (c:Company {id: e.company_id})
        MATCH (d:Director {id: e.director_id})
        MERGE (c)-[r:DIRECTED_BY]->(d)
        RETURN count(r) as count
    """,
        edges=edges,
    )

    record = await result.single()
    return record["count"] if record else 0


async def _upsert_bid_edges(session, bids: list[Bid]) -> int:
    """Upsert BID_ON edges using MERGE (incremental sync)."""
    if not bids:
        return 0

    bid_data = [
        {
            "company_id": b.company_id,
            "tender_id": b.tender_id,
            "amount": float(b.amount) if b.amount else 0.0,
            "is_winner": b.is_winner,
        }
        for b in bids
    ]

    result = await session.run(
        """
        UNWIND $bids AS b
        MATCH (c:Company {id: b.company_id})
        MATCH (t:Tender {id: b.tender_id})
        MERGE (c)-[r:BID_ON]->(t)
        SET r.amount = b.amount,
            r.is_winner = b.is_winner
        RETURN count(r) as count
    """,
        bids=bid_data,
    )

    record = await result.single()
    return record["count"] if record else 0


async def get_graph_stats_from_neo4j() -> dict[str, Any]:
    """Get graph statistics from Neo4j."""
    async with get_neo4j_session() as session:
        # Node counts by label
        result = await session.run(
            """
            CALL db.labels() YIELD label
            CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) as count', {}) YIELD value
            RETURN label, value.count as count
        """
        )
        node_types = {}
        async for record in result:
            node_types[record["label"]] = record["count"]

        # Edge counts by type
        result = await session.run(
            """
            CALL db.relationshipTypes() YIELD relationshipType
            CALL apoc.cypher.run('MATCH ()-[r:`' + relationshipType + '`]->() RETURN count(r) as count', {}) YIELD value
            RETURN relationshipType, value.count as count
        """
        )
        edge_types = {}
        async for record in result:
            edge_types[record["relationshipType"]] = record["count"]

        # Totals
        result = await session.run("MATCH (n) RETURN count(n) as nodes")
        record = await result.single()
        total_nodes = record["nodes"] if record else 0

        result = await session.run("MATCH ()-[r]->() RETURN count(r) as edges")
        record = await result.single()
        total_edges = record["edges"] if record else 0

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_types": node_types,
            "edge_types": edge_types,
        }
