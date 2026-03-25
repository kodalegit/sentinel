"""
Community detection using Neo4j Graph Data Science library.
Falls back to NetworkX if GDS is not available.
"""

import logging
from collections import defaultdict

from graph.neo4j_driver import get_neo4j_session, check_gds_available
from graph.communities import Cluster, calculate_suspicion_score

logger = logging.getLogger(__name__)
GDS_PROJECTION_NAME = "procurement-graph"


async def detect_communities_neo4j(
    min_cluster_size: int = 2,
) -> list[Cluster]:
    """
    Detect communities using Neo4j GDS Louvain algorithm.
    Returns clusters ranked by suspicion score.
    """
    gds_available = await check_gds_available()

    if not gds_available:
        logger.warning(
            "Neo4j GDS not available, community detection will use basic approach"
        )
        return await _detect_communities_basic()

    return await _detect_communities_gds(min_cluster_size)


async def _detect_communities_gds(min_cluster_size: int = 2) -> list[Cluster]:
    """Use Neo4j GDS Louvain for community detection."""
    async with get_neo4j_session() as session:
        await _drop_projection_if_exists(session)

        # Create graph projection for strict company-company co-bid communities.
        await session.run(
            """
            CALL gds.graph.project(
                $graph_name,
                ['Company'],
                {
                    CO_BID: {orientation: 'UNDIRECTED'}
                }
            )
        """,
            graph_name=GDS_PROJECTION_NAME,
        )

        # Run Louvain community detection
        result = await session.run(
            """
            CALL gds.louvain.stream($graph_name)
            YIELD nodeId, communityId
            WITH gds.util.asNode(nodeId) AS node, communityId
            WHERE node:Company
            RETURN node.id AS companyId, node.name AS companyName, communityId
            ORDER BY communityId
        """,
            graph_name=GDS_PROJECTION_NAME,
        )

        # Group companies by community
        communities: dict[int, list[tuple[str, str]]] = defaultdict(list)
        # Eagerly consume all records to avoid session buffering issues
        records = [record async for record in result]
        for record in records:
            communities[record["communityId"]].append(
                (record["companyId"], record["companyName"])
            )

        # Clean up projection
        await _drop_projection_if_exists(session)

        # Build cluster objects
        clusters = []
        for idx, (_community_id, members) in enumerate(communities.items()):
            if len(members) < min_cluster_size:
                continue

            id_to_name: dict[str, str] = {}
            for company_id, company_name in members:
                id_to_name.setdefault(company_id, company_name)
            company_ids = sorted(id_to_name.keys())
            company_names = [id_to_name[cid] for cid in company_ids]

            # Get cluster details
            shared = await _get_shared_attributes(session, company_ids)
            co_bids = await _count_co_bids(session, company_ids)
            if co_bids <= 0:
                continue

            suspicious_edge_count = await _count_suspicious_edges(session, company_ids)
            score = calculate_suspicion_score(
                shared, co_bids, len(company_ids), suspicious_edge_count
            )

            clusters.append(
                Cluster(
                    id=f"cluster-{idx}",
                    company_ids=company_ids,
                    company_names=company_names,
                    size=len(company_ids),
                    suspicion_score=score,
                    shared_attributes=shared,
                    co_bid_count=co_bids,
                    win_pattern={
                        "total_bids": 0,
                        "bids_per_company": {},
                        "total_awards": 0,
                        "awards_per_company": {},
                    },
                )
            )

        return sorted(clusters, key=lambda c: c.suspicion_score, reverse=True)


async def _detect_communities_basic() -> list[Cluster]:
    """Basic community detection without GDS using co-bid connected components."""
    async with get_neo4j_session() as session:
        # Build company-pair adjacency from strict analytic co-bid edges.
        result = await session.run(
            """
            MATCH (c1:Company)-[:CO_BID]-(c2:Company)
            WHERE c1.id < c2.id
            RETURN c1.id AS c1_id, c1.name AS c1_name,
                   c2.id AS c2_id, c2.name AS c2_name
        """
        )

        adjacency: dict[str, set[str]] = defaultdict(set)
        company_names: dict[str, str] = {}
        # Eagerly consume all records to avoid session buffering issues
        records = [record async for record in result]
        for record in records:
            c1_id = record["c1_id"]
            c2_id = record["c2_id"]
            adjacency[c1_id].add(c2_id)
            adjacency[c2_id].add(c1_id)
            company_names[c1_id] = record["c1_name"]
            company_names[c2_id] = record["c2_name"]

        # Build clusters from connected components (DFS).
        visited: set[str] = set()
        clusters = []
        idx = 0

        for company_id in adjacency:
            if company_id in visited:
                continue

            stack = [company_id]
            component: set[str] = set()
            while stack:
                current = stack.pop()
                if current in component:
                    continue
                component.add(current)
                stack.extend(adjacency[current] - component)

            visited.update(component)

            if len(component) < 2:
                continue

            company_ids = sorted(component)
            cluster_company_names = [company_names.get(cid, cid) for cid in company_ids]
            shared = await _get_shared_attributes(session, company_ids)
            co_bids = await _count_co_bids(session, company_ids)
            if co_bids <= 0:
                continue

            suspicious_edge_count = await _count_suspicious_edges(session, company_ids)
            score = calculate_suspicion_score(
                shared, co_bids, len(company_ids), suspicious_edge_count
            )

            clusters.append(
                Cluster(
                    id=f"cluster-{idx}",
                    company_ids=company_ids,
                    company_names=cluster_company_names,
                    size=len(component),
                    suspicion_score=score,
                    shared_attributes=shared,
                    co_bid_count=co_bids,
                    win_pattern={
                        "total_bids": 0,
                        "bids_per_company": {},
                        "total_awards": 0,
                        "awards_per_company": {},
                    },
                )
            )
            idx += 1

        return sorted(clusters, key=lambda c: c.suspicion_score, reverse=True)


async def _drop_projection_if_exists(session) -> None:
    """Drop the temporary GDS projection if it exists."""
    result = await session.run(
        """
        CALL gds.graph.exists($graph_name)
        YIELD exists
        RETURN exists
        """,
        graph_name=GDS_PROJECTION_NAME,
    )
    record = await result.single()
    if not record or not record["exists"]:
        return

    await session.run(
        """
        CALL gds.graph.drop($graph_name, false)
        YIELD graphName
        RETURN graphName
        """,
        graph_name=GDS_PROJECTION_NAME,
    )


async def _get_shared_attributes(session, company_ids: list[str]) -> dict:
    """Get shared attributes for a cluster from Neo4j."""
    shared = {"addresses": [], "phones": [], "directors": []}

    # Shared addresses
    result = await session.run(
        """
        MATCH (c1:Company)-[r:SHARES_ADDRESS]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
        WITH coalesce(c1.physical_address, c1.address) AS address,
             collect(DISTINCT c1.id) + collect(DISTINCT c2.id) AS company_ids
        WHERE address IS NOT NULL AND trim(address) <> ''
        RETURN address,
               company_ids AS companies
        ORDER BY address
    """,
        ids=company_ids,
    )
    # Eagerly consume all records
    address_records = [record async for record in result]
    for record in address_records:
        if record["address"]:
            shared["addresses"].append(
                {
                    "address": record["address"],
                    "companies": list(set(record["companies"])),
                }
            )

    # Shared phones
    result = await session.run(
        """
        MATCH (c1:Company)-[r:SHARES_PHONE]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
        WITH c1.phone AS phone,
             collect(DISTINCT c1.id) + collect(DISTINCT c2.id) AS company_ids
        WHERE phone IS NOT NULL AND trim(phone) <> ''
        RETURN phone,
               company_ids AS companies
        ORDER BY phone
    """,
        ids=company_ids,
    )
    # Eagerly consume all records
    phone_records = [record async for record in result]
    for record in phone_records:
        if record["phone"]:
            shared["phones"].append(
                {
                    "phone": record["phone"],
                    "companies": list(set(record["companies"])),
                }
            )

    # Shared directors
    result = await session.run(
        """
        MATCH (c1:Company)-[:DIRECTED_BY]->(d:Director)<-[:DIRECTED_BY]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
        RETURN d.id AS director_id,
               collect(DISTINCT c1.id) + collect(DISTINCT c2.id) AS companies
        ORDER BY director_id
    """,
        ids=company_ids,
    )
    # Eagerly consume all records
    director_records = [record async for record in result]
    for record in director_records:
        shared["directors"].append(
            {
                "director_id": record["director_id"],
                "companies": list(set(record["companies"])),
            }
        )

    return shared


async def _count_co_bids(session, company_ids: list[str]) -> int:
    """Count tenders where multiple cluster members bid."""
    result = await session.run(
        """
        MATCH (c:Company)-[:BID_ON]->(t:Tender)
        WHERE c.id IN $ids
        WITH t, count(DISTINCT c) AS bidder_count
        WHERE bidder_count >= 2
        RETURN count(t) AS co_bid_count
    """,
        ids=company_ids,
    )
    record = await result.single()
    return record["co_bid_count"] if record else 0


async def _count_suspicious_edges(session, company_ids: list[str]) -> int:
    """Count suspicious relationships within a cluster."""
    result = await session.run(
        """
        MATCH (c1:Company)-[r]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
          AND coalesce(r.suspicious, false) = true
        RETURN count(r) AS suspicious_edge_count
        """,
        ids=company_ids,
    )
    record = await result.single()
    return record["suspicious_edge_count"] if record else 0


async def find_shortest_path_neo4j(source_id: str, target_id: str) -> dict | None:
    """Find shortest path between two entities using Neo4j."""
    async with get_neo4j_session() as session:
        result = await session.run(
            """
            MATCH path = shortestPath(
                (source {id: $source_id})-[*..10]-(target {id: $target_id})
            )
            RETURN path,
                   [n IN nodes(path) | {id: n.id, type: labels(n)[0], label: coalesce(n.name, n.title, n.id)}] AS nodes,
                   [r IN relationships(path) | {type: type(r), suspicious: coalesce(r.suspicious, false)}] AS rels
        """,
            source_id=source_id,
            target_id=target_id,
        )

        record = await result.single()
        if not record:
            return None

        path_nodes = record["nodes"]
        path_rels = record["rels"]

        # Build edges with source/target
        path_edges = []
        for i, rel in enumerate(path_rels):
            path_edges.append(
                {
                    "source": path_nodes[i]["id"],
                    "target": path_nodes[i + 1]["id"],
                    "relationship": rel["type"],
                    "suspicious": rel["suspicious"],
                }
            )

        return {
            "nodes": path_nodes,
            "edges": path_edges,
            "length": len(path_edges),
        }


async def get_entity_neighborhood_neo4j(
    entity_id: str,
    depth: int = 2,
    limit_nodes: int = 100,
) -> dict:
    """Get k-hop neighborhood around an entity from Neo4j."""
    async with get_neo4j_session() as session:
        result = await session.run(
            """
            MATCH (center {id: $entity_id})
            CALL apoc.path.subgraphAll(center, {
                maxLevel: $depth,
                limit: $limit
            })
            YIELD nodes, relationships
            RETURN 
                [n IN nodes | {
                    id: n.id, 
                    type: labels(n)[0], 
                    label: coalesce(n.name, n.title, n.id),
                    risk_level: n.risk_level
                }] AS nodes,
                [r IN relationships | {
                    source: startNode(r).id,
                    target: endNode(r).id,
                    relationship: type(r),
                    suspicious: coalesce(r.suspicious, false)
                }] AS edges
        """,
            entity_id=entity_id,
            depth=depth,
            limit=limit_nodes,
        )

        record = await result.single()
        if not record:
            return {"nodes": [], "edges": []}

        return {
            "nodes": record["nodes"],
            "edges": record["edges"],
        }


async def search_graph_entities_neo4j(query: str, limit: int = 12) -> list[dict]:
    """Search graph entities directly in Neo4j without materializing NetworkX."""
    normalized_search = query.strip().lower()
    if not normalized_search:
        return []

    async with get_neo4j_session() as session:
        result = await session.run(
            """
            MATCH (n)
            WHERE (n:Company OR n:Director OR n:Official OR n:Tender)
              AND toLower(coalesce(n.name, n.title, n.id)) CONTAINS $search
            WITH n,
                 CASE
                    WHEN n:Company THEN 'COMPANY'
                    WHEN n:Director THEN 'DIRECTOR'
                    WHEN n:Official THEN 'OFFICIAL'
                    ELSE 'TENDER'
                 END AS node_type,
                 coalesce(n.name, n.title, n.id) AS label
            OPTIONAL MATCH (n)<-[:DIRECTED_BY]-(c:Company)
            WITH n, node_type, label, count(DISTINCT c) AS company_count
            RETURN n.id AS id,
                   node_type AS type,
                   label,
                   n.risk_level AS risk_level,
                   CASE
                       WHEN node_type = 'TENDER' THEN coalesce(n.reference, n.procuring_entity, n.procurement_method)
                       WHEN node_type = 'OFFICIAL' THEN CASE
                           WHEN coalesce(n.department, '') <> '' AND coalesce(n.position, '') <> ''
                               THEN n.department + ' · ' + n.position
                           ELSE coalesce(n.department, n.position)
                       END
                       WHEN node_type = 'COMPANY' THEN coalesce(n.address, n.source_system)
                       WHEN node_type = 'DIRECTOR' AND company_count > 0 THEN
                           'Linked to ' + toString(company_count) + ' ' + CASE WHEN company_count = 1 THEN 'company' ELSE 'companies' END
                       ELSE null
                   END AS subtitle,
                   CASE WHEN toLower(label) STARTS WITH $search THEN 0 ELSE 1 END AS rank_prefix,
                   size(label) AS rank_length,
                   toLower(label) AS rank_label
            ORDER BY rank_prefix, rank_length, rank_label
            LIMIT $limit
            """,
            search=normalized_search,
            limit=limit,
        )
        records = [record async for record in result]

    return [
        {
            "id": record["id"],
            "type": record["type"],
            "label": record["label"],
            "risk_level": record["risk_level"],
            "subtitle": record["subtitle"],
        }
        for record in records
    ]


async def get_cluster_subgraph_neo4j(
    company_ids: list[str],
    include_tenders: bool = True,
    include_officials: bool = True,
) -> dict:
    """Get subgraph for a cluster from Neo4j."""
    async with get_neo4j_session() as session:
        # Build node types to include
        node_types = ["Company", "Director"]
        if include_tenders:
            node_types.append("Tender")
        if include_officials:
            node_types.append("Official")

        result = await session.run(
            """
            MATCH (c:Company)
            WHERE c.id IN $company_ids
            OPTIONAL MATCH (c)-[r1]-(neighbor)
            WHERE any(label IN labels(neighbor) WHERE label IN $node_types)
            WITH collect(DISTINCT c) + collect(DISTINCT neighbor) AS all_nodes,
                 collect(DISTINCT r1) AS all_rels
            UNWIND all_nodes AS n
            WITH collect(DISTINCT n) AS nodes, all_rels
            UNWIND all_rels AS r
            WITH nodes, collect(DISTINCT r) AS rels
            RETURN 
                [n IN nodes WHERE n IS NOT NULL | {
                    id: n.id,
                    type: labels(n)[0],
                    label: coalesce(n.name, n.title, n.id),
                    risk_level: n.risk_level
                }] AS nodes,
                [r IN rels WHERE r IS NOT NULL | {
                    source: startNode(r).id,
                    target: endNode(r).id,
                    relationship: type(r),
                    suspicious: coalesce(r.suspicious, false)
                }] AS edges
        """,
            company_ids=company_ids,
            node_types=node_types,
        )

        record = await result.single()
        if not record:
            return {"nodes": [], "edges": []}

        return {
            "nodes": record["nodes"],
            "edges": record["edges"],
        }
