import argparse
import asyncio
import json
import time
from typing import Any

from fastapi import FastAPI

from graph.neo4j_analytics import (
    materialize_company_graph_features_neo4j,
    precompute_conflict_paths_neo4j,
    update_tender_risk_levels_neo4j,
)
from graph.neo4j_communities import detect_communities_neo4j
from graph.neo4j_driver import check_neo4j_health
from graph.neo4j_sync import get_graph_stats_from_neo4j, sync_graph_to_neo4j
from main import load_data_from_db, persist_analysis_snapshot, recompute_app_state
from ml.hybrid_scorer import HybridRiskScorer


def _record_metric(metrics: list[dict[str, Any]], stage: str, started_at: float, **extra: Any) -> None:
    metrics.append(
        {
            "stage": stage,
            "seconds": round(time.perf_counter() - started_at, 6),
            **extra,
        }
    )


async def _prepare_neo4j_analysis() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    list[Any],
    dict[str, dict[str, int]],
    dict[str, Any],
    HybridRiskScorer,
    dict[str, Any],
]:
    metrics: list[dict[str, Any]] = []

    started = time.perf_counter()
    data = await load_data_from_db()
    _record_metric(
        metrics,
        "load_data_from_db",
        started,
        tenders=len(data["tenders"]),
        companies=len(data["companies"]),
        bids=len(data["bids"]),
    )

    started = time.perf_counter()
    health = await check_neo4j_health()
    _record_metric(metrics, "check_neo4j_health", started, status=health.get("status"))

    started = time.perf_counter()
    await sync_graph_to_neo4j(
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        tenders=data["tenders"],
        bids=data["bids"],
        incremental=True,
    )
    _record_metric(metrics, "sync_graph_to_neo4j", started)

    started = time.perf_counter()
    communities = await detect_communities_neo4j()
    _record_metric(metrics, "detect_communities_neo4j", started, communities=len(communities))

    started = time.perf_counter()
    company_graph_features = await materialize_company_graph_features_neo4j()
    _record_metric(
        metrics,
        "materialize_company_graph_features_neo4j",
        started,
        rows=len(company_graph_features),
    )

    started = time.perf_counter()
    conflict_paths = await precompute_conflict_paths_neo4j(data["tenders"])
    _record_metric(
        metrics,
        "precompute_conflict_paths_neo4j",
        started,
        rows=len(conflict_paths),
    )

    started = time.perf_counter()
    scorer = HybridRiskScorer()
    risk_scores = scorer.score_all(
        tenders=data["tenders"],
        companies=data["companies"],
        directors=data["directors"],
        officials=data["officials"],
        bids=data["bids"],
        graph=None,
        communities=communities,
        bids_by_tender=data["bids_by_tender"],
        company_graph_features=company_graph_features,
        conflict_paths=conflict_paths,
    )
    _record_metric(metrics, "score_all", started, rows=len(risk_scores))

    started = time.perf_counter()
    await update_tender_risk_levels_neo4j(
        {tender_id: risk.category.value for tender_id, risk in risk_scores.items()}
    )
    _record_metric(metrics, "update_tender_risk_levels_neo4j", started, rows=len(risk_scores))

    started = time.perf_counter()
    neo4j_stats = await get_graph_stats_from_neo4j()
    _record_metric(
        metrics,
        "get_graph_stats_from_neo4j",
        started,
        nodes=neo4j_stats.get("total_nodes", 0),
        edges=neo4j_stats.get("total_edges", 0),
    )

    summary = {
        "tenders": len(data["tenders"]),
        "companies": len(data["companies"]),
        "nodes": neo4j_stats.get("total_nodes", 0),
        "edges": neo4j_stats.get("total_edges", 0),
        "communities": len(communities),
        "risk_scores": len(risk_scores),
    }
    return (
        summary,
        metrics,
        data,
        risk_scores,
        communities,
        company_graph_features,
        neo4j_stats,
        scorer,
        health,
    )


async def profile_neo4j_stages() -> dict[str, Any]:
    summary, metrics, _data, _risk_scores, _communities, _company_graph_features, _neo4j_stats, _scorer, health = await _prepare_neo4j_analysis()
    return {
        "mode": "neo4j-stages",
        "health": health,
        "summary": summary,
        "metrics": metrics,
    }


async def profile_snapshot_persistence(graph_source: str) -> dict[str, Any]:
    (
        summary,
        metrics,
        _data,
        risk_scores,
        communities,
        company_graph_features,
        _neo4j_stats,
        scorer,
        _health,
    ) = await _prepare_neo4j_analysis()
    started = time.perf_counter()
    analysis_run_id = await persist_analysis_snapshot(
        risk_scores=risk_scores,
        communities=communities,
        company_graph_features=company_graph_features,
        scorer=scorer,
        summary=summary,
        graph_source=graph_source,
    )
    _record_metric(metrics, "persist_analysis_snapshot", started, analysis_run_id=analysis_run_id)
    return {
        "mode": "snapshot",
        "summary": summary,
        "analysis_run_id": analysis_run_id,
        "metrics": metrics,
    }


async def profile_full_recompute(timeout_seconds: float) -> dict[str, Any]:
    app = FastAPI()
    started = time.perf_counter()
    result = await recompute_app_state(
        app,
        prefer_neo4j_primary=True,
        neo4j_timeout_seconds=timeout_seconds,
    )
    return {
        "mode": "recompute",
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "graph_source": app.state.app_state.graph_source,
        "result": result,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["neo4j-stages", "snapshot", "recompute"],
        default="neo4j-stages",
    )
    parser.add_argument("--neo4j-timeout-seconds", type=float, default=15.0)
    parser.add_argument("--graph-source", default="neo4j")
    args = parser.parse_args()

    if args.mode == "neo4j-stages":
        result = await profile_neo4j_stages()
    elif args.mode == "snapshot":
        result = await profile_snapshot_persistence(args.graph_source)
    else:
        result = await profile_full_recompute(args.neo4j_timeout_seconds)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
