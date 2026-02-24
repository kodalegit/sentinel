"""
Community detection using Neo4j Graph Data Science library.
Falls back to NetworkX if GDS is not available.
"""

import logging
from dataclasses import dataclass
from collections import defaultdict

from graph.neo4j_driver import get_neo4j_session, check_gds_available
from graph.communities import Cluster

logger = logging.getLogger(__name__)


async def detect_communities_neo4j(
    min_cluster_size: int = 2,
) -> list[Cluster]:
    """
    Detect communities using Neo4j GDS Louvain algorithm.
    Returns clusters ranked by suspicion score.
    """
    gds_available = await check_gds_available()
    
    if not gds_available:
        logger.warning("Neo4j GDS not available, community detection will use basic approach")
        return await _detect_communities_basic()
    
    return await _detect_communities_gds(min_cluster_size)


async def _detect_communities_gds(min_cluster_size: int = 2) -> list[Cluster]:
    """Use Neo4j GDS Louvain for community detection."""
    async with get_neo4j_session() as session:
        # Drop existing graph projection if exists
        try:
            await session.run("CALL gds.graph.drop('procurement-graph', false)")
        except Exception:
            pass
        
        # Create graph projection for community detection
        # Focus on companies and their relationships
        await session.run("""
            CALL gds.graph.project(
                'procurement-graph',
                ['Company', 'Director'],
                {
                    DIRECTED_BY: {orientation: 'UNDIRECTED'},
                    SHARES_ADDRESS: {orientation: 'UNDIRECTED'},
                    SHARES_PHONE: {orientation: 'UNDIRECTED'},
                    SHARES_EMAIL: {orientation: 'UNDIRECTED'},
                    SHARES_DIRECTOR: {orientation: 'UNDIRECTED'}
                }
            )
        """)
        
        # Run Louvain community detection
        result = await session.run("""
            CALL gds.louvain.stream('procurement-graph')
            YIELD nodeId, communityId
            WITH gds.util.asNode(nodeId) AS node, communityId
            WHERE node:Company
            RETURN node.id AS companyId, node.name AS companyName, communityId
            ORDER BY communityId
        """)
        
        # Group companies by community
        communities: dict[int, list[tuple[str, str]]] = defaultdict(list)
        async for record in result:
            communities[record["communityId"]].append(
                (record["companyId"], record["companyName"])
            )
        
        # Clean up projection
        await session.run("CALL gds.graph.drop('procurement-graph', false)")
        
        # Build cluster objects
        clusters = []
        for idx, (community_id, members) in enumerate(communities.items()):
            if len(members) < min_cluster_size:
                continue
            
            company_ids = [m[0] for m in members]
            company_names = [m[1] for m in members]
            
            # Get cluster details
            shared = await _get_shared_attributes(session, company_ids)
            co_bids = await _count_co_bids(session, company_ids)
            score = _calculate_suspicion_score(shared, co_bids, len(company_ids))
            
            clusters.append(
                Cluster(
                    id=f"cluster-{idx}",
                    company_ids=company_ids,
                    company_names=company_names,
                    size=len(company_ids),
                    suspicion_score=score,
                    shared_attributes=shared,
                    co_bid_count=co_bids,
                    win_pattern={"total_bids": 0, "bids_per_company": {}},
                )
            )
        
        return sorted(clusters, key=lambda c: c.suspicion_score, reverse=True)


async def _detect_communities_basic() -> list[Cluster]:
    """Basic community detection without GDS - uses connected components."""
    async with get_neo4j_session() as session:
        # Find connected components via shared attributes
        result = await session.run("""
            MATCH (c1:Company)-[:SHARES_ADDRESS|SHARES_PHONE|SHARES_EMAIL|SHARES_DIRECTOR]-(c2:Company)
            WITH c1, collect(DISTINCT c2) AS connected
            RETURN c1.id AS companyId, c1.name AS companyName, 
                   [c IN connected | c.id] AS connectedIds
        """)
        
        # Build clusters from connected components
        visited = set()
        clusters = []
        idx = 0
        
        async for record in result:
            company_id = record["companyId"]
            if company_id in visited:
                continue
            
            # BFS to find all connected companies
            cluster_ids = {company_id}
            cluster_ids.update(record["connectedIds"])
            visited.update(cluster_ids)
            
            if len(cluster_ids) >= 2:
                # Get names
                names_result = await session.run("""
                    MATCH (c:Company)
                    WHERE c.id IN $ids
                    RETURN c.id AS id, c.name AS name
                """, ids=list(cluster_ids))
                
                company_ids = []
                company_names = []
                async for name_record in names_result:
                    company_ids.append(name_record["id"])
                    company_names.append(name_record["name"])
                
                shared = await _get_shared_attributes(session, company_ids)
                co_bids = await _count_co_bids(session, company_ids)
                score = _calculate_suspicion_score(shared, co_bids, len(company_ids))
                
                clusters.append(
                    Cluster(
                        id=f"cluster-{idx}",
                        company_ids=company_ids,
                        company_names=company_names,
                        size=len(company_ids),
                        suspicion_score=score,
                        shared_attributes=shared,
                        co_bid_count=co_bids,
                        win_pattern={"total_bids": 0, "bids_per_company": {}},
                    )
                )
                idx += 1
        
        return sorted(clusters, key=lambda c: c.suspicion_score, reverse=True)


async def _get_shared_attributes(session, company_ids: list[str]) -> dict:
    """Get shared attributes for a cluster from Neo4j."""
    shared = {"addresses": [], "phones": [], "directors": []}
    
    # Shared addresses
    result = await session.run("""
        MATCH (c1:Company)-[r:SHARES_ADDRESS]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
        RETURN c1.physical_address AS address, 
               collect(DISTINCT c1.name) + collect(DISTINCT c2.name) AS companies
    """, ids=company_ids)
    async for record in result:
        if record["address"]:
            shared["addresses"].append({
                "address": record["address"],
                "companies": list(set(record["companies"])),
            })
    
    # Shared phones
    result = await session.run("""
        MATCH (c1:Company)-[r:SHARES_PHONE]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
        RETURN c1.phone AS phone,
               collect(DISTINCT c1.name) + collect(DISTINCT c2.name) AS companies
    """, ids=company_ids)
    async for record in result:
        if record["phone"]:
            shared["phones"].append({
                "phone": record["phone"],
                "companies": list(set(record["companies"])),
            })
    
    # Shared directors
    result = await session.run("""
        MATCH (c1:Company)-[:DIRECTED_BY]->(d:Director)<-[:DIRECTED_BY]-(c2:Company)
        WHERE c1.id IN $ids AND c2.id IN $ids AND c1.id < c2.id
        RETURN d.name AS director,
               collect(DISTINCT c1.name) + collect(DISTINCT c2.name) AS companies
    """, ids=company_ids)
    async for record in result:
        shared["directors"].append({
            "director_id": record["director"],
            "companies": list(set(record["companies"])),
        })
    
    return shared


async def _count_co_bids(session, company_ids: list[str]) -> int:
    """Count tenders where multiple cluster members bid."""
    result = await session.run("""
        MATCH (c:Company)-[:BID_ON]->(t:Tender)
        WHERE c.id IN $ids
        WITH t, count(DISTINCT c) AS bidder_count
        WHERE bidder_count >= 2
        RETURN count(t) AS co_bid_count
    """, ids=company_ids)
    record = await result.single()
    return record["co_bid_count"] if record else 0


def _calculate_suspicion_score(
    shared: dict,
    co_bid_count: int,
    cluster_size: int,
) -> float:
    """Calculate suspicion score for a cluster."""
    score = 0.0
    
    # Shared attributes (up to 30 points)
    score += min(15, len(shared.get("addresses", [])) * 10)
    score += min(10, len(shared.get("phones", [])) * 10)
    score += min(5, len(shared.get("directors", [])) * 5)
    
    # Co-bidding frequency (up to 30 points)
    score += min(30, co_bid_count * 5)
    
    # Cluster size bonus (up to 20 points)
    score += min(20, (cluster_size - 1) * 5)
    
    return min(100, score)


async def find_shortest_path_neo4j(source_id: str, target_id: str) -> dict | None:
    """Find shortest path between two entities using Neo4j."""
    async with get_neo4j_session() as session:
        result = await session.run("""
            MATCH path = shortestPath(
                (source {id: $source_id})-[*..10]-(target {id: $target_id})
            )
            RETURN path,
                   [n IN nodes(path) | {id: n.id, type: labels(n)[0], label: coalesce(n.name, n.title, n.id)}] AS nodes,
                   [r IN relationships(path) | {type: type(r), suspicious: coalesce(r.suspicious, false)}] AS rels
        """, source_id=source_id, target_id=target_id)
        
        record = await result.single()
        if not record:
            return None
        
        path_nodes = record["nodes"]
        path_rels = record["rels"]
        
        # Build edges with source/target
        path_edges = []
        for i, rel in enumerate(path_rels):
            path_edges.append({
                "source": path_nodes[i]["id"],
                "target": path_nodes[i + 1]["id"],
                "relationship": rel["type"],
                "suspicious": rel["suspicious"],
            })
        
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
        result = await session.run("""
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
        """, entity_id=entity_id, depth=depth, limit=limit_nodes)
        
        record = await result.single()
        if not record:
            return {"nodes": [], "edges": []}
        
        return {
            "nodes": record["nodes"],
            "edges": record["edges"],
        }


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
        
        result = await session.run("""
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
        """, company_ids=company_ids, node_types=node_types)
        
        record = await result.single()
        if not record:
            return {"nodes": [], "edges": []}
        
        return {
            "nodes": record["nodes"],
            "edges": record["edges"],
        }
