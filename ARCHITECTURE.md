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
| `bidder_count`        | Natural | Number of known participants on the tender          |
| `bid_spread_ratio`    | Ratio   | (max disclosed bid - min disclosed bid) / estimate  |
| `winner_margin_ratio` | Ratio   | (best losing disclosed bid - winner) / estimate     |
| `company_age_days`    | Natural | Winner's age at tender deadline                     |
| `win_rate`            | Ratio   | Winner's historical win rate                        |
| `graph_degree`        | Natural | Winner's degree in the shadow graph                 |
| `suspicious_edges`    | Natural | Count of suspicious edges (shared address/phone)    |
| `official_distance`   | Natural | Shortest path to any public official (capped at 10) |
| `community_size`      | Natural | COMPANY-type nodes within 2 hops                    |

**Key decision: ratio features instead of absolute KES values.**
`bid_spread` and `winner_margin` were originally in absolute KES. A road construction tender's spread (~10M KES) vs office supplies (~600K KES) caused the Isolation Forest to flag category differences rather than within-category anomalies. Converting to ratios of `estimated_value` makes them dimensionless and domain-agnostic. This is critical for a system spanning Kenyan procurement domains (roads, medical, IT, security, etc.).

**Key decision: bidder participation is distinct from priced bidding.**
Real procurement feeds do not always publish full bid-price ladders. The canonical `Bid` model now allows `amount = NULL` so the system can preserve bidder participation without fabricating prices. `bidder_count` always reflects known participants, while `bid_spread_ratio` and `winner_margin_ratio` activate only when real disclosed bid amounts exist.

**Key decision: synthetic data trains the pattern vocabulary; sparse real data calibrates production behavior.**
Sentinel should not be trained only on synthetic data or only on sparse production data. Synthetic data is useful for development because it provides complete attribute coverage and controllable examples of Kenyan procurement risk patterns such as shell entities, cartel-style overlap, rushed tenders, and conflict signals. But real PPIP/e-GP style data contains the missingness patterns, disclosure gaps, and source-specific sparsity that the system must survive in production. The practical approach is:

- use synthetic data to develop the feature pipeline, benchmark fraud-pattern detection, and demonstrate intended behavior
- use sparse real data to calibrate thresholds, review false positives, and verify graceful degradation under incomplete evidence
- include source-aware features such as pricing coverage, bidder participation known, and evidence-quality scores so the model learns the difference between suspicious patterns and low-information records

This supports a key Sentinel principle: low evidence coverage is not automatically evidence of wrongdoing.

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
- bidder edges preserve participation even when pricing is undisclosed via `has_pricing`
- suspicious edges flagged for: family connections, specific shared addresses, non-generic shared phone numbers, and non-generic shared emails

**Key decision: Hash-based shared attribute detection (O(n) instead of O(n²)).**
The original pairwise comparison of all companies for shared attributes caused edge explosion (22M edges for 10K tenders). Hash-based grouping by normalized attribute keys reduces complexity to O(n) and limits edges per company to 50.

**Key decision: strict filtering before shared-attribute edges are created.**
Recompute still uses a NetworkX analysis graph, so noisy shared attributes directly affect ML features and rule evaluation. To keep the analysis graph compact and meaningful:

- `SHARES_ADDRESS` edges are created only for `AddressQuality.SPECIFIC` addresses
- generic or obviously synthetic phone numbers are excluded from `SHARES_PHONE`
- generic emails are excluded from `SHARES_EMAIL`
- the same filtering rules are applied in Neo4j sync and community shared-attribute summaries

### Neo4j Sync (`graph/neo4j_sync.py`)

Syncs PostgreSQL entities to Neo4j on recomputation:

```
PostgreSQL → sync_graph_to_neo4j()
  → Create Company, Director, Official, Tender nodes
  → Create DIRECTED_BY, BID_ON, AWARDED_BY, RELATED_TO edges
  → Create SHARES_ADDRESS, SHARES_PHONE, SHARES_EMAIL, SHARES_DIRECTOR, CO_BID edges
```

Neo4j shared-attribute edges use the same normalization and filtering rules as the NetworkX analysis graph so recompute output and graph exploration stay aligned.

**Key decision: incremental Neo4j refresh by default for normal recompute paths.**
The scalable sync pattern is now:

- upsert nodes with `MERGE`
- prune stale nodes that no longer exist in PostgreSQL
- delete only relationships fully managed by the sync layer
- rebuild managed relationships from the latest canonical data

This avoids a full `MATCH (n) DETACH DELETE n` rebuild during normal recompute while preserving graph parity for graph exploration and analytics.

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

**Design decision: NetworkX is the canonical community source for risk until Neo4j semantics match.**

- The recompute pipeline and rule-based cartel detection use the NetworkX communities built from the strict co-bid rule (edges require ≥2 shared tenders). This keeps the analysis snapshot, risk scoring, and UI summaries aligned.
- Neo4j remains the primary graph-exploration engine (pathfinding, neighborhoods) and can run community algorithms, but its current fallback groups one-off co-bidders and would drift from the stricter NetworkX signal. We keep NetworkX as the authoritative source until Neo4j community construction enforces the same co-bid and filtering rules.

### Request-Time Graph Serving

**Key decision: Neo4j-first on graph APIs, NetworkX only on failure.**

For large graphs, request-time graph APIs should not eagerly materialize the full NetworkX graph. The current preferred path is:

- `/api/graph/search` → Neo4j-backed entity search
- `/api/graph/path` → Neo4j shortest path
- `/api/graph/entity/{id}` and tender graph endpoints → Neo4j neighborhood queries
- evidence/explain graph paths → Neo4j-first resolution without forcing lazy NetworkX graph load

NetworkX remains a fallback if Neo4j query execution fails, not as the default preflight path.

**Key decision: debounce frontend graph search inputs.**
Because graph entity search now hits the backend database instead of an in-memory browser list, the Graph Explorer search input should not fire on every keystroke indefinitely. A small client-side debounce keeps the UI responsive while reducing avoidable request volume and query churn.

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

| Signal                        | Weight | Rationale                                     |
| ----------------------------- | ------ | --------------------------------------------- |
| Company age < 30 days         | 25     | Classic shell indicator                       |
| Company age < 90 days         | 15     | Recent registration                           |
| Missing registration date     | 10     | Unverifiable entity age                       |
| Address quality = PLACEHOLDER | 15     | "PO Box 123" default in e-GP data             |
| Address quality = VAGUE       | 8      | "MOI AVENUE" — not specific enough to verify  |
| Zero directors listed         | 12     | Missing director info where source expects it |
| Generic email domain          | 5      | Gmail/yahoo instead of business domain        |
| Large contract + new company  | 20     | Disproportionate award to new entity          |

**Threshold**: Composite score ≥ 40 triggers shell company flag.

**Key decision: multi-signal over single-field.**
Kenyan e-GP data frequently has placeholder addresses ("PO Box 123") or vague addresses ("MOI AVENUE"). Relying on a single field like address quality would produce false positives. The composite approach requires multiple signals to accumulate, reducing false positives while catching genuine shell entities.

### Handling Incomplete Data

**Null-safe operations throughout the pipeline:**

1. **ML features** (`ml/features.py`): `estimated_value` can be `None` for tenders without published estimates, and bidder records can exist without disclosed prices. All ratio features use `est = tender.estimated_value or 0.0` to avoid division errors, while price-spread features fall back to zero when priced bids are unavailable.

2. **Stats calculation** (`routes/stats.py`): `total_value = sum((t.estimated_value or 0) for t in state.tenders.values())` prevents `TypeError` when aggregating.

3. **Shell company detection** (`risk/engine.py`): All optional fields (`winner.registration_date`, `winner.contact_email`, `tender.awarded_amount`) are checked before use. Missing data is treated as a signal, but source-aware expectations prevent sparse PPIP/OCDS records from being penalized the same way as richer supplier-profile feeds.

4. **Data quality flags**: Companies have a `data_quality_flags` JSON field that now captures source-aware evidence quality. `completeness_score` measures how much structured evidence a source provided, `verification_score` measures how strongly the supplier identity can be verified, and `quality_score` blends the two. These flags inform shell-risk scoring and evidence presentation without excluding sparse records from analysis.

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
  → Neo4j-first recompute when enabled and healthy
    → sync_graph_to_neo4j(incremental=True)
    → detect_communities_neo4j()
    → materialize_company_graph_features_neo4j()
    → precompute_conflict_paths_neo4j()
    → HybridRiskScorer.score_all()
      → extract_tender_features()
      → AnomalyDetector.fit/score()  ← SHAP + sigmoid normalization
      → compute_risk_score() per tender (rules)
      → fuse scores (60/40)
  → fallback path: build_procurement_graph() + detect_communities() if Neo4j is unavailable or times out
  → persist_analysis_snapshot() → PostgreSQL
  → AppState (in-memory singleton + latest snapshot metadata)
```

### Current Scale Bottlenecks

**Key decision: the next scale ceiling is Python-side analysis, not only graph traversal.**

Recent graph changes remove several avoidable bottlenecks, but at `10k–100k` tenders the main remaining constraints are:

1. **Python-side entity loading**
   - `load_data_from_db()` still hydrates the full working set into Python objects.
   - This increases startup/recompute memory pressure before graph analytics even begin.

2. **Batch scoring over all tenders**
   - `HybridRiskScorer.score_all()` still iterates the full tender set in Python.
   - Even after removing repeated category scans for price anomaly checks, the scorer remains O(number of tenders + feature extraction work).

3. **ML feature extraction**
   - `extract_tender_features()` still computes per-tender features in Python and depends on preloaded graph-derived or bid-derived context.
   - This is acceptable for current scale, but it will become a dominant cost before Neo4j traversal does.

4. **Model fitting and explainability**
   - Isolation Forest fitting and SHAP attribution are not free.
   - SHAP especially should be treated as a bounded or optional explainability cost as volumes grow.

5. **Persisted snapshot writes**
   - Persisting a full analysis run and linked risk assessments scales with the full tender set.
   - This is operationally correct, but it adds write amplification during recompute.

The practical near-term target is therefore a hybrid architecture: PostgreSQL as source of truth, Neo4j for graph analytics, and Python for bounded batch scoring plus ML.

### Persisted Analysis Snapshots

**Key decision: persist whole analysis runs, not only the latest in-memory scores.**

Each recomputation produces an analysis snapshot with:

- a distinct `analysis_run_id`
- snapshot status and created timestamp
- risk assessments linked directly to that analysis run
- summary metadata exposed to the UI

This makes startup more robust because the app can load the latest persisted analysis instead of requiring a fresh recompute before the dashboard becomes useful.

### Manual Recomputation Workflow

**Key decision: Manual recomputation instead of async background jobs.**

The original design used Redis + ARQ worker for async recomputation after data ingestion. This was replaced with a manual workflow:

1. **Ingestion endpoints** (`/api/ingest/ppip/sync`, `/api/ingest/egp/tenders`, `/api/ingest/egp/contracts`) persist data to PostgreSQL and return immediately.
2. **User triggers recomputation** via the Data Sources page (`/sources`) by clicking "Recompute Analysis".
3. **POST /api/recompute** returns `202 Accepted` immediately with a `job_id` and fires a background task which:
   - Reloads all data from PostgreSQL
   - Rebuilds the NetworkX analysis graph
   - Detects communities
   - Computes risk scores
   - Persists a new analysis snapshot and links risk assessments to that run
   - Syncs the updated graph state to Neo4j
   - Updates the in-memory `AppState` singleton and latest snapshot metadata
4. **Polling endpoints**: Clients poll `GET /api/recompute/status/{job_id}` for completion.

Related read endpoints:

- `GET /api/analysis/latest` exposes the latest persisted analysis snapshot metadata
- startup can load the latest persisted analysis snapshot into `AppState`

**Rationale:**

- **Batching**: Users can ingest multiple datasets before recomputing, avoiding expensive analysis on every small ingestion.
- **Control**: Users decide when recomputation runs (e.g., after business hours).
- **Non-blocking UX**: Recomputation runs as an async background job with status polling, preventing HTTP timeouts on large datasets.
- **Transparency**: Activity log shows recomputation history and stats.

### Testing Strategy

- **Core Logic Unit Tests**: `tests/test_risk_engine.py`, `tests/test_ml_features.py`, and `tests/test_graph_builder.py` isolate the critical path logic (risk rules, ML feature extraction, and shared-attribute graph filtering). They use deterministic Pydantic fixtures and NetworkX graphs to verify calculations with zero database or network dependencies.

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
- `data_quality_flags`: JSON with source-aware `completeness_score`, `verification_score`, and `quality_score`

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

**Bid semantics:**

- `BidDB.amount`: Nullable so the same canonical model can represent priced bids or participation-only bidder rosters
- bidder participation is preserved even when a source discloses only the roster and the award outcome
- downstream analytics distinguish between participant counts and priced-bid availability

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

Sentinel uses a source-agnostic canonical model. Connectors normalize source-specific payloads into shared domain entities, while provenance and source-aware evidence-quality flags preserve what each source actually proves.

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

5. **Source-aware evidence quality**: Preserve a stable canonical model, but interpret supplier evidence in the context of what each source is expected to publish.

6. **Evidence-grounded intelligence**: LLM outputs are grounded in structured evidence packs to prevent hallucination. Template fallback ensures system works without LLM.

7. **Null-safe operations**: All optional fields are checked before use. Missing data is treated as a signal rather than causing analysis failure.

8. **Hybrid graph architecture**: PostgreSQL as source of truth, Neo4j for analytics. Graceful fallback to NetworkX if Neo4j unavailable.

9. **Hash-based edge detection**: O(n) complexity instead of O(n²) for shared attribute detection. Edge limits per entity prevent explosion.
