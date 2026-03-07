"""
Typed application state, populated once at startup and injected into routes via Depends().
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import Annotated

import networkx as nx
from fastapi import Depends, Request

from models import (
    Tender,
    Company,
    Director,
    PublicOfficial,
    Bid,
    RiskScore,
)
from graph.communities import Cluster


@dataclass
class AppState:
    """Fully typed container for startup-cached data."""

    tenders: dict[str, Tender] = field(default_factory=dict)
    companies: dict[str, Company] = field(default_factory=dict)
    directors: dict[str, Director] = field(default_factory=dict)
    officials: dict[str, PublicOfficial] = field(default_factory=dict)
    bids: list[Bid] = field(default_factory=list)
    bids_by_tender: dict[str, list[Bid]] = field(default_factory=dict)
    graph: nx.Graph = field(default_factory=nx.Graph)
    graph_loaded: bool = False
    graph_source: str | None = None
    risk_scores: dict[str, RiskScore] = field(default_factory=dict)
    communities: list[Cluster] = field(default_factory=list)
    analysis_run_id: str | None = None
    analysis_status: str | None = None
    analysis_model_version: str | None = None
    analysis_created_at: datetime | None = None
    snapshot_source: str | None = None
    analysis_summary: dict[str, int] = field(default_factory=dict)
    company_graph_features: dict[str, dict[str, int]] = field(default_factory=dict)


def get_state(request: Request) -> AppState:
    """FastAPI dependency — returns the typed singleton populated at startup."""
    return request.app.state.app_state


State = Annotated[AppState, Depends(get_state)]
