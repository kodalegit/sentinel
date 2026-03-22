from models import Tender
from graph.neo4j_driver import get_neo4j_session


async def materialize_company_graph_features_neo4j() -> dict[str, dict[str, int]]:
    async with get_neo4j_session() as session:
        result = await session.run(
            """
            MATCH (c:Company)
            CALL {
                WITH c
                OPTIONAL MATCH (c)-[r]-()
                WHERE type(r) <> 'CO_BID'
                RETURN count(r) AS graph_degree,
                       sum(CASE WHEN coalesce(r.suspicious, false) THEN 1 ELSE 0 END) AS suspicious_edges
            }
            CALL {
                WITH c
                OPTIONAL MATCH path = (c)-[*1..2]-(neighbor:Company)
                WHERE neighbor.id <> c.id
                  AND all(rel IN relationships(path) WHERE type(rel) <> 'CO_BID')
                RETURN count(DISTINCT neighbor) AS community_size
            }
            CALL {
                WITH c
                OPTIONAL MATCH (o:Official)
                WITH c, o
                OPTIONAL MATCH path = shortestPath((c)-[*..10]-(o))
                WHERE path IS NULL OR all(rel IN relationships(path) WHERE type(rel) <> 'CO_BID')
                RETURN coalesce(min(length(path)), 99) AS official_distance
            }
            RETURN c.id AS company_id,
                   graph_degree,
                   coalesce(suspicious_edges, 0) AS suspicious_edges,
                   official_distance,
                   community_size
            """
        )

        features: dict[str, dict[str, int]] = {}
        async for record in result:
            company_id = record["company_id"]
            features[company_id] = {
                "graph_degree": int(record["graph_degree"] or 0),
                "suspicious_edges": int(record["suspicious_edges"] or 0),
                "official_distance": int(record["official_distance"] or 99),
                "community_size": int(record["community_size"] or 0),
            }

        return features


async def precompute_conflict_paths_neo4j(
    tenders: dict[str, Tender],
) -> dict[tuple[str, str], dict[str, list[str]]]:
    pairs = []
    seen_pairs: set[tuple[str, str]] = set()

    for tender in tenders.values():
        if not tender.awarded_to or not tender.procurement_officer_id:
            continue
        pair = (tender.awarded_to, tender.procurement_officer_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        pairs.append(
            {
                "company_id": tender.awarded_to,
                "official_id": tender.procurement_officer_id,
            }
        )

    if not pairs:
        return {}

    async with get_neo4j_session() as session:
        result = await session.run(
            """
            UNWIND $pairs AS pair
            MATCH (company:Company {id: pair.company_id})
            MATCH (official:Official {id: pair.official_id})
            OPTIONAL MATCH path = shortestPath((company)-[*..3]-(official))
            WHERE path IS NULL OR all(rel IN relationships(path) WHERE type(rel) <> 'CO_BID')
            RETURN pair.company_id AS company_id,
                   pair.official_id AS official_id,
                   CASE WHEN path IS NULL THEN [] ELSE [node IN nodes(path) | node.id] END AS node_ids,
                   CASE WHEN path IS NULL THEN [] ELSE [node IN nodes(path) | coalesce(node.name, node.title, node.id)] END AS node_labels
            """,
            pairs=pairs,
        )

        lookup: dict[tuple[str, str], dict[str, list[str]]] = {}
        async for record in result:
            node_ids = record["node_ids"] or []
            if not node_ids:
                continue
            lookup[(record["company_id"], record["official_id"])] = {
                "node_ids": node_ids,
                "node_labels": record["node_labels"] or [],
            }

        return lookup


async def update_tender_risk_levels_neo4j(tender_risks: dict[str, str]) -> None:
    if not tender_risks:
        return

    rows = [{"id": tender_id, "risk_level": risk_level} for tender_id, risk_level in tender_risks.items()]

    async with get_neo4j_session() as session:
        await session.run(
            """
            UNWIND $rows AS row
            MATCH (t:Tender {id: row.id})
            SET t.risk_level = row.risk_level
            """,
            rows=rows,
        )
