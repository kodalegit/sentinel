import networkx as nx

from graph.builder import build_procurement_graph
from state import AppState


def ensure_runtime_graph(state: AppState) -> nx.Graph:
    if state.graph_loaded:
        return state.graph

    graph = build_procurement_graph(
        tenders=state.tenders,
        companies=state.companies,
        directors=state.directors,
        officials=state.officials,
        bids=state.bids,
    )

    for tender_id, risk in state.risk_scores.items():
        if tender_id in graph:
            graph.nodes[tender_id]["risk_level"] = risk.category.value

    state.graph = graph
    state.graph_loaded = True
    if not state.graph_source or state.graph_source == "persisted":
        state.graph_source = "networkx-lazy"
    return graph
