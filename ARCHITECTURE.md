# Sentinel Architecture & Design Decisions

Living document capturing key design decisions, trade-offs, and rationale for the intelligence pipeline. Updated as the system evolves through milestones.

---

## ML Pipeline

### Feature Engineering (`ml/features.py`)

**12 features**, all category-agnostic by design:

| Feature               | Type    | Notes                                               |
| --------------------- | ------- | --------------------------------------------------- |
| `price_ratio`         | Ratio   | awarded / estimated — self-normalizing              |
| `price_zscore`        | Z-score | Per-category z-score of awarded amount              |
| `timeline_days`       | Natural | Submission window in days                           |
| `bidder_count`        | Natural | Number of bids on the tender                        |
| `bid_spread_ratio`    | Ratio   | (max bid - min bid) / estimated_value               |
| `winner_margin_ratio` | Ratio   | (2nd place - winner) / estimated_value              |
| `company_age_days`    | Natural | Winner's age at tender deadline                     |
| `win_rate`            | Ratio   | Winner's historical win rate                        |
| `graph_degree`        | Natural | Winner's degree in the shadow graph                 |
| `suspicious_edges`    | Natural | Count of suspicious edges (shared address/phone)    |
| `official_distance`   | Natural | Shortest path to any public official (capped at 10) |
| `community_size`      | Natural | COMPANY-type nodes within 2 hops                    |

**Key decision: ratio features instead of absolute KES values.**
`bid_spread` and `winner_margin` were originally in absolute KES. A road construction tender's spread (~10M KES) vs office supplies (~600K KES) caused the Isolation Forest to flag category differences rather than within-category anomalies. Converting to ratios of `estimated_value` makes them dimensionless and domain-agnostic. This is critical for a system spanning Kenyan procurement domains (roads, medical, IT, security, etc.).

**Key decision: single model, not per-category.**
With current data volumes (~20-50 tenders across ~5 categories), per-category models would have insufficient samples. The ratio-based feature design makes a single model work across categories. When data volume grows (hundreds per category), per-category models become a clean migration path since features are already category-agnostic.

**Key decision: `community_size` counts only COMPANY nodes.**
The 2-hop neighborhood in a heterogeneous graph includes tenders, officials, and directors. Counting all node types conflated graph structure with community membership. Filtering to COMPANY nodes makes this feature measure actual vendor clustering.

**Key decision: `official_distance` via multi-source BFS.**
Instead of computing shortest path from each company to every official (O(officials × shortest_path) per tender), we run BFS from all official nodes once and look up distances. O(V + E) total.

### Anomaly Detection (`ml/anomaly_detector.py`)

- **Algorithm**: Isolation Forest (100 estimators, 15% contamination)
- **Scaling**: StandardScaler before fitting
- **Explainability**: SHAP TreeExplainer for exact per-sample feature attributions (falls back to deviation proxy if SHAP unavailable)

**Key decision: sigmoid normalization instead of min-max.**
The original min-max normalization was relative to the current batch — adding one tender reshuffled all scores. For incremental ingestion (Milestone 1), this is unstable. The sigmoid mapping is anchored to the training distribution:

```
z = (raw_score - train_mean) / train_std
normalized = 100 / (1 + exp(2z))
```

- Training mean → ~50/100
- 1 std below mean → ~73/100 (suspicious)
- 2 std below mean → ~88/100 (very suspicious)
- Stable regardless of batch composition

**Key decision: SHAP over deviation proxy.**
The original feature importance used absolute deviation from scaled mean — a crude proxy that ignores feature interactions and tree structure. SHAP TreeExplainer gives exact, additive, signed attributions. This feeds directly into evidence packs and LLM explanations with grounded feature contributions like "flagged primarily because `official_distance` (+0.23)".

### Hybrid Scoring (`ml/hybrid_scorer.py`)

- **Weight split**: 60% rule-based, 40% ML
- **ML factor type**: `ML_ANOMALY` (distinct from rule-based `PRICE_ANOMALY`)
- **Threshold**: ML factor added when anomaly score ≥ 50

**Key decision: dedicated `ML_ANOMALY` risk factor type.**
ML detections were previously tagged as `PRICE_ANOMALY`, but the model uses all 12 features (graph, timing, vendor maturity, etc.). A dedicated type lets the UI and LLM distinguish rule-detected price anomalies from ML-detected multi-signal anomalies.

---

## Graph Analytics

### Hybrid Architecture: PostgreSQL + Neo4j

**Key decision: Hybrid graph architecture with PostgreSQL as source of truth and Neo4j for analytics.**

The system uses a dual-database approach:

1. **PostgreSQL**: Source of truth for all entities (companies, tenders, bids, cases)
2. **Neo4j**: Optimized graph analytics (community detection, pathfinding, centrality)

This provides:

- **Performance**: Neo4j's index-free adjacency enables sub-millisecond traversals
- **Accuracy**: Neo4j GDS provides best-in-class algorithms (Louvain, PageRank)
- **Robustness**: PostgreSQL remains authoritative; Neo4j can be rebuilt from PG
- **Graceful fallback**: System works with NetworkX if Neo4j is unavailable

### Shadow Graph (`graph/builder.py`)

Heterogeneous NetworkX graph with:

- **Node types**: COMPANY, DIRECTOR, OFFICIAL, TENDER
- **Edge types**: DIRECTOR_OF, BID_ON, WON, AWARDED_BY, RELATED_TO, SHARES_ADDRESS, SHARES_PHONE, SHARES_EMAIL
- Suspicious edges flagged for: family connections, shared addresses (plot number matching), shared phone numbers, shared emails

**Key decision: Hash-based shared attribute detection (O(n) instead of O(n²)).**
The original pairwise comparison of all companies for shared attributes caused edge explosion (22M edges for 10K tenders). Hash-based grouping by normalized attribute keys reduces complexity to O(n) and limits edges per company to 50.

### Neo4j Sync (`graph/neo4j_sync.py`)

Syncs PostgreSQL entities to Neo4j on recomputation:

```
PostgreSQL → sync_graph_to_neo4j()
  → Create Company, Director, Official, Tender nodes
  → Create DIRECTED_BY, BID_ON, RELATED_TO edges
  → Create SHARES_ADDRESS, SHARES_PHONE, SHARES_EMAIL, SHARES_DIRECTOR edges
```

### Community Detection (`graph/neo4j_communities.py`)

**Key decision: Neo4j GDS Louvain with NetworkX fallback.**

When Neo4j GDS is available:

- Uses `gds.louvain.stream()` for community detection
- Provides better quality communities than NetworkX implementation
- Enables future algorithms (PageRank, centrality, triangle count)

When Neo4j is unavailable:

- Falls back to NetworkX Louvain implementation
- Same interface, slightly lower performance

**Key decision: communities cached at startup.**
Communities are computed once in `lifespan` alongside risk scores and stored in `AppState.communities`. Routes serve cached data.

The `get_cartel_sets()` helper extracts simple `list[set[str]]` from Louvain clusters for the rule engine's cartel check, maintaining the same interface.

### Suspicion Scoring

Cluster suspicion score (0-100) based on:

- Shared attributes: addresses (up to 15pts), phones (up to 10pts), directors (up to 5pts)
- Co-bidding frequency: up to 30pts
- Suspicious edges in main graph: up to 20pts
- Cluster size bonus: up to 20pts

---

## Risk Scoring (`risk/engine.py`)

5 rule-based checks + 1 ML factor:

| Factor               | Weight   | Trigger                                                   |
| -------------------- | -------- | --------------------------------------------------------- |
| Conflict of Interest | 30       | Graph path between winner and procurement officer ≤3 hops |
| Cartel Pattern       | 25       | ≥3 Louvain community members bid on same tender           |
| Shell Company        | 20/10    | Winner registered <30 / <90 days before deadline          |
| Price Anomaly        | 15       | Awarded amount >150% of estimate                          |
| Rushed Timeline      | 10/5     | Submission window ≤5 / ≤7 days                            |
| ML Anomaly           | variable | Isolation Forest score ≥50/100                            |

Categories: HIGH (≥50), MEDIUM (≥25), LOW (<25)

### Multi-Signal Shell Company Detection

Shell company risk is computed as a composite of multiple signals, each with independent weights:

| Signal                        | Weight | Rationale                                    |
| ----------------------------- | ------ | -------------------------------------------- |
| Company age < 30 days         | 25     | Classic shell indicator                      |
| Company age < 90 days         | 15     | Recent registration                          |
| Missing registration date     | 10     | Unverifiable entity age                      |
| Address quality = PLACEHOLDER | 15     | "PO Box 123" default in e-GP data            |
| Address quality = VAGUE       | 8      | "MOI AVENUE" — not specific enough to verify |
| Zero directors listed         | 12     | Missing director info = opacity              |
| Generic email domain          | 5      | Gmail/yahoo instead of business domain       |
| Large contract + new company  | 20     | Disproportionate award to new entity         |

**Threshold**: Composite score ≥ 40 triggers shell company flag.

**Key decision: multi-signal over single-field.**
Kenyan e-GP data frequently has placeholder addresses ("PO Box 123") or vague addresses ("MOI AVENUE"). Relying on a single field like address quality would produce false positives. The composite approach requires multiple signals to accumulate, reducing false positives while catching genuine shell entities.

### Handling Incomplete Data

**Null-safe operations throughout the pipeline:**

1. **ML features** (`ml/features.py`): `estimated_value` can be `None` for tenders without published estimates. All ratio features use `est = tender.estimated_value or 0.0` to avoid division errors.

2. **Stats calculation** (`routes/stats.py`): `total_value = sum((t.estimated_value or 0) for t in state.tenders.values())` prevents `TypeError` when aggregating.

3. **Shell company detection** (`risk/engine.py`): All optional fields (`winner.registration_date`, `winner.contact_email`, `tender.awarded_amount`) are checked before use. Missing data is treated as a signal (e.g., "missing_registration" adds 10 points) rather than causing analysis failure.

4. **Data quality flags**: Companies have a `data_quality_flags` JSON field with `quality_score` (0-100) based on field coverage (directors listed? ownership info? valid address? contact details?). Low-quality companies are flagged for elevated shell risk but not excluded from analysis.

**Key design principle: "Missing data as signal, not failure."**
Sparse Kenyan procurement data is a reality. The system uses explicit data-quality flags and multi-signal scoring instead of failing when critical attributes are missing. This allows Sentinel to work with real-world data while still producing reliable risk assessments.

---

## Intelligence (`intelligence/`)

- **LangGraph agent** with configurable LLM (OpenAI, Anthropic, Google, Ollama)
- **Evidence packs** structure all tender data for LLM grounding (prevents hallucination)
- **Template fallback** if LLM unavailable — system remains functional
- **System prompt** enforces advisory language and evidence citation

---

## Data Flow (Startup & Recomputation)

```
PostgreSQL → load_data_from_db()
  → build_procurement_graph()
  → detect_communities()           ← cached in AppState
  → HybridRiskScorer.score_all()   ← uses cached communities
    → extract_tender_features()    ← uses pre-computed bids_by_tender
    → AnomalyDetector.fit/score()  ← SHAP + sigmoid normalization
    → compute_risk_score() per tender (rules)
    → fuse scores (60/40)
  → persist_risk_scores() → PostgreSQL
  → AppState (in-memory singleton)
```

### Manual Recomputation Workflow

**Key decision: Manual recomputation instead of async background jobs.**

The original design used Redis + ARQ worker for async recomputation after data ingestion. This was replaced with a manual workflow:

1. **Ingestion endpoints** (`/api/ingest/ppip/sync`, `/api/ingest/egp/tenders`, `/api/ingest/egp/contracts`) persist data to PostgreSQL and return immediately.
2. **User triggers recomputation** via the Data Sources page (`/sources`) by clicking "Recompute Analysis".
3. **POST /api/recompute** returns `202 Accepted` immediately with a `job_id` and fires a background task which:
   - Reloads all data from PostgreSQL
   - Rebuilds the procurement graph
   - Detects communities
   - Computes risk scores
   - Syncs the updated graph state to Neo4j
   - Updates the in-memory `AppState` singleton
4. **Polling endpoints**: Clients poll `GET /api/recompute/status/{job_id}` for completion.

**Rationale:**

- **Batching**: Users can ingest multiple datasets before recomputing, avoiding expensive analysis on every small ingestion.
- **Control**: Users decide when recomputation runs (e.g., after business hours).
- **Non-blocking UX**: Recomputation runs as an async background job with status polling, preventing HTTP timeouts on large datasets.
- **Transparency**: Activity log shows recomputation history and stats.

### Testing Strategy

- **Core Logic Unit Tests**: `tests/test_risk_engine.py` and `tests/test_ml_features.py` isolate the critical path logic (risk rules, ML feature extraction). They use deterministic Pydantic fixtures and NetworkX graphs to verify calculations with zero database or network dependencies.

### Kenya-Specific Schema Evolution

The schema was extended to handle real Kenyan procurement data from PPIP (OCDS) and e-GP platforms:

**Company fields:**

- `supplier_type`: Local Company, Sole Proprietorship, etc.
- `brs_number`: Business Registration Service identifier
- `egp_registration_number`: e-GP platform identifier
- `contact_email`: Primary contact email
- `physical_address`, `postal_address`, `postal_code`: Split from single `address` field
- `source_system`: `ppip`, `egp`, `manual`, or `synthetic`
- `source_record_id`: Original platform record ID
- `ingested_at`: Timestamp of ingestion
- `data_quality_flags`: JSON with `quality_score` (0-100) based on field coverage

**Tender fields:**

- `procurement_method`: Open, Selective, Direct, RFQ
- `procurement_category`: Goods, Works, Services, Non Consultancy Services
- `pe_type`: National Government, County Government, State Corporation
- `currency`: Default KES
- `ocds_id`: OCDS contract identifier
- `source_system`, `source_record_id`, `ingested_at`: Provenance tracking
- `estimated_value`: Now nullable (not all tenders have published estimates)

**New entities:**

- `ContractDB`: Links tender → supplier with contract metadata, AGPO fields
- `OwnershipDB`: Captures e-GP ownership info distinct from directors

All fields are nullable where appropriate to handle sparse Kenyan data.

---

## Technology Stack

| Layer          | Technology                                           |
| -------------- | ---------------------------------------------------- |
| Backend        | FastAPI, Python 3.12                                 |
| Database       | PostgreSQL (asyncpg + SQLAlchemy)                    |
| Graph Database | Neo4j 5 (GDS + APOC) with NetworkX fallback          |
| ML             | scikit-learn (Isolation Forest), SHAP, pandas, numpy |
| AI             | LangChain + LangGraph (configurable LLM)             |
| Frontend       | Next.js, TypeScript, Tailwind CSS, shadcn/ui         |
| Infrastructure | Docker Compose, Railway                              |

### Neo4j Configuration

```bash
# Environment variables
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=sentinel123
NEO4J_DATABASE=neo4j
NEO4J_ENABLED=true  # Set to false for NetworkX-only mode
```

**Docker Compose** includes Neo4j with GDS and APOC plugins pre-installed.

### Data Sources & Ingestion

**Connectors:**

- `connectors/ppip.py`: PPIP OCDS API connector (`tenders.go.ke/api/ocds`)
- `connectors/egp.py`: e-GP platform ingestion adapters

**API Endpoints:**

- `POST /api/ingest/ppip/sync`: Sync PPIP tenders by fiscal year
- `POST /api/ingest/egp/tenders`: Ingest e-GP tender payloads
- `POST /api/ingest/egp/contracts`: Ingest e-GP contract payloads
- `POST /api/recompute`: Manual recomputation trigger

**Frontend:**

- `/sources`: Data Sources page with ingestion UI
- PPIP sync by fiscal year
- e-GP tender/contract payload ingestion (JSON paste)
- Manual "Recompute Analysis" button
- Activity log and recomputation stats

---

## Design Principles

1. **Missing data as signal, not failure**: Sparse Kenyan procurement data is a reality. Use explicit data-quality flags and multi-signal scoring instead of failing when critical attributes are missing.

2. **Manual recomputation for control**: Users trigger recomputation after ingestion to batch multiple datasets and control when expensive analysis runs.

3. **Multi-signal over single-field**: Kenyan data frequently has placeholder or vague addresses. Composite scoring requires multiple signals to accumulate, reducing false positives.

4. **Ratio features for domain-agnostic ML**: Use ratios instead of absolute KES values to make features work across procurement domains (roads, medical, IT, etc.).

5. **Evidence-grounded intelligence**: LLM outputs are grounded in structured evidence packs to prevent hallucination. Template fallback ensures system works without LLM.

6. **Null-safe operations**: All optional fields are checked before use. Missing data is treated as a signal rather than causing analysis failure.

7. **Hybrid graph architecture**: PostgreSQL as source of truth, Neo4j for analytics. Graceful fallback to NetworkX if Neo4j unavailable.

8. **Hash-based edge detection**: O(n) complexity instead of O(n²) for shared attribute detection. Edge limits per entity prevent explosion.
