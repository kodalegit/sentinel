# Sentinel MVP: 9-Week Technical Roadmap

**Project**: AI-Powered Public Procurement Oversight System  
**Track**: Governance & Public Policy  
**Target**: Production-ready MVP for Kenya procurement agencies  
**Current Week**: 3 of 9

---

## Roadmap Overview

| Phase                      | Weeks | Focus                                                          | Priority | Status      |
| -------------------------- | ----- | -------------------------------------------------------------- | -------- | ----------- |
| **Foundation**             | 1–2   | DB, ML, Graph, LLM, Cases, UI, Infra                           | —        | ✅ Complete |
| **Kenya Data & Detection** | 3     | Schema evolution, PPIP/e-GP connectors, multi-signal detection | CRITICAL | ✅ COMPLETE |
| **Auth & Workflow**        | 3–4   | JWT auth, roles, investigation hardening                       | HIGH     | Planned     |
| **Ingestion & LLM**        | 5–6   | CSV/PDF ingestion, LLM case analysis                           | MEDIUM   | Planned     |
| **Graph & Detection**      | 6–7   | Graph UX, fuzzy detection, search                              | MEDIUM   | Planned     |
| **Polish & Demo**          | 8–9   | Export, performance, demo prep                                 | LOW      | Planned     |

---

## Weeks 1–2: Foundation (✅ COMPLETE)

**Goal**: Full working system — DB, ML, graph, LLM, case management, UI, deployment

### What Was Delivered

- [x] **PostgreSQL + async SQLAlchemy** — 8 tables, Alembic migrations, CRUD repository, seed script
- [x] **Hybrid risk engine** — 12 features, Isolation Forest + rules (60/40 fusion), risk persistence
- [x] **Graph analytics** — Louvain community detection, cluster/path/entity APIs
- [x] **LLM intelligence** — LangGraph agent, evidence packs, template fallback, provider-agnostic
- [x] **Case management** — 5-state workflow, typed notes, 7 API endpoints, frontend page
- [x] **UI overhaul** — shadcn/ui components, dashboard, graph explorer, case management
- [x] **Infrastructure** — Docker Compose, Dockerfiles, Railway configs
- [x] **Backend refactor** — Pydantic settings, modular routes, typed AppState dependency injection

---

## Week 3: Kenya Data Onramp & Schema Evolution

**Goal**: Ground the system in real Kenyan procurement data from PPIP and e-GP; evolve schema for Kenya's data reality

### Deliverables

- [x] **Schema Evolution (Kenya-grounded)**
  - [x] Provenance fields on core entities: `source_system`, `source_record_id`, `ingested_at`, `data_quality_flags`
  - [x] Company expansion: `supplier_type`, `brs_number`, `egp_registration_number`, `contact_email`, split `physical_address`/`postal_address`/`postal_code`
  - [x] Tender expansion: `procurement_method`, `procurement_category`, `pe_type`, `currency`, `ocds_id`
  - [x] New Contract model: `contract_number`, `contract_amount`, `start_date`, `end_date`, AGPO fields
  - [x] New Ownership model: `company_id` → `owner_name`, `nationality`, `postal_address`
  - [x] Alembic migration for all schema changes
- [x] **PPIP OCDS Connector** (`connectors/ppip.py`)
  - [x] Fetch OCDS 1.1 releases from `tenders.go.ke/api/ocds/tenders?fy=YYYY-YYYY`
  - [x] Normalize both `"tender"` and `"contract"` tagged releases
  - [x] Extract parties → companies, map buyer → procuring entity
  - [x] Persist with `source_system=ppip` provenance
- [x] **e-GP Ingestion Adapters** (`connectors/egp.py`)
  - [x] Accept e-GP tender list and contract detail payloads
  - [x] Normalize dates (DD/MM/YYYY → ISO), map AGPO fields
  - [x] Extract `supplierdetails` including director/ownership info
  - [x] Persist with `source_system=egp` provenance
- [x] **Ingestion API** (`routes/ingest.py`)
  - [x] POST `/api/ingest/ppip/sync` — sync PPIP tenders by fiscal year
  - [x] POST `/api/ingest/egp/tenders` — accept e-GP tender payload
  - [x] POST `/api/ingest/egp/contracts` — accept e-GP contract payload
  - [x] POST `/api/recompute` — manual recomputation trigger
- [x] **Multi-Signal Entity Detection**
  - [x] Address quality classifier: SPECIFIC / VAGUE / PLACEHOLDER
  - [x] Enhanced shared-attribute detection (email, BRS prefix, ownership overlap)
  - [x] Data completeness scoring per entity
  - [x] Composite shell-risk scoring (age + address quality + director count + ownership)
- [x] **Infrastructure**
  - [x] Automated migrations + seeding in Docker entrypoint
  - [x] Health check endpoint: `/api/health`
  - [x] In-process recomputation via `POST /api/recompute`
  - [x] Frontend Data Sources page (`/sources`) with ingestion UI

### Success Criteria

- [x] Schema handles real PPIP OCDS releases and e-GP contract payloads without data loss
- [x] PPIP sync ingests 50+ real releases for FY 2025-2026
- [x] e-GP contract ingestion stores AGPO metadata and supplier ownership
- [x] Shell detection flags companies with placeholder addresses + recent registration + missing directors
- [x] `docker compose up` → healthy stack with zero manual intervention
- [x] Manual recomputation workflow allows batching ingestions before re-analyzing

### Mentor Review Checkpoint

- **Demo**: Ingest real PPIP tenders → show them in dashboard with provenance
- **Demo**: Show multi-signal shell detection working on sparse e-GP data
- **Discussion**: Address quality approach, dual-source reconciliation strategy
- **Blockers**: _[Document any issues here]_

---

## Weeks 3–4: Authentication & User Management

**Goal**: JWT auth with role-based access, user-attributed actions

### Deliverables

- [ ] **User Model & Auth**
  - [ ] User table: username, email, hashed_password, role, is_active
  - [ ] Alembic migration for users table
  - [ ] JWT tokens (access + refresh) via `python-jose` + `passlib`
  - [ ] Login endpoint: POST `/api/auth/login`
  - [ ] Token refresh endpoint: POST `/api/auth/refresh`
- [ ] **Role-Based Access Control**
  - [ ] Roles: `auditor`, `supervisor`, `admin`
  - [ ] Route protection via FastAPI `Depends()` — typed dependency (fits existing pattern)
  - [ ] Auditors: view, investigate, add notes
  - [ ] Supervisors: + assign, escalate, dismiss, resolve cases
  - [ ] Admins: + manage users
- [ ] **User Attribution**
  - [ ] Case actions attributed to logged-in user
  - [ ] Audit log entries include user identity
- [ ] **Login UI**
  - [ ] Login page with JWT token management
  - [ ] Protected routes in frontend

### Success Criteria

- Auditor can log in and investigate but cannot dismiss/escalate
- Supervisor can escalate, resolve, dismiss, and reassign cases
- All case actions are attributed to the logged-in user in audit trail

### Mentor Review Checkpoint

- **Demo**: Login as auditor vs supervisor, show permission differences
- **Discussion**: Auth security, token management, production migration to OAuth2
- **Blockers**: _[Document any issues here]_

---

## Weeks 4–5: Investigation Workflow Hardening

**Goal**: Realistic audit workflow with assignment, oversight, and decision recording

### Deliverables

- [ ] **Hybrid Case Assignment**
  - [ ] Supervisors assign cases to specific auditors
  - [ ] Auditors self-assign from unassigned case queue
  - [ ] Reassignment capability
- [ ] **Supervisor Dashboard**
  - [ ] View all open/escalated cases
  - [ ] Filter by assignee, priority, status
  - [ ] Case workload overview
- [ ] **Investigation Experience**
  - [ ] Case timeline: full history of status changes, notes, assignments
  - [ ] Decision recording: structured finding, recommendation, evidence references
  - [ ] Notification hooks (placeholder): log/in-app indicator on escalation or assignment

### Success Criteria

- Supervisor can assign and reassign cases; auditor can pick up unassigned cases
- Case timeline shows full investigation history
- Decisions are recorded with structured evidence references

### Mentor Review Checkpoint

- **Demo**: Full investigation workflow — assign → investigate → decide → escalate
- **Discussion**: Real-world auditor workflow requirements
- **Blockers**: _[Document any issues here]_

---

## Weeks 5–6: Data Ingestion & LLM Deepening

**Goal**: Richer data input (CSV, PDF PoC) and deeper LLM integration for case analysis

### Deliverables

- [ ] **CSV/Excel Batch Upload**
  - [ ] Upload endpoint with validation and error reporting
  - [ ] Batch processing via ARQ background job
  - [ ] Ingestion status feedback (job status polling)
- [ ] **PDF Ingestion Proof-of-Concept**
  - [ ] Upload PDF tender document
  - [ ] LLM-assisted field extraction (LlamaIndex or similar)
  - [ ] Review UI: auditor sees extracted fields, corrects/confirms
  - [ ] Commit to DB on approval → triggers async recomputation
- [ ] **Entity Resolution**
  - [ ] Fuzzy matching on company names
  - [ ] Director deduplication
- [ ] **LLM Case Analysis**
  - [ ] Case-level AI summary: synthesize linked tenders, risk factors, and notes
  - [ ] "Suggest next steps" based on case status and evidence
  - [ ] Conversational investigation assistant (ask questions about evidence)
  - [ ] Improved prompt engineering: advisory, non-accusatory language
  - [ ] Graceful fallback to template-based output when no API key

### Success Criteria

- CSV of 50+ tenders uploads and processes successfully
- PDF uploaded → fields extracted → reviewed → committed
- Duplicate companies detected and merged
- Case summary references specific evidence items

### Mentor Review Checkpoint

- **Demo**: CSV batch upload + PDF extraction review flow
- **Demo**: AI case summary for a complex multi-tender case
- **Discussion**: Entity resolution quality, LLM grounding reliability
- **Blockers**: _[Document any issues here]_

---

## Weeks 6–7: Graph UX & Detection Improvements

**Goal**: Better detection quality and more intuitive graph exploration

### Deliverables

- [ ] **Detection Improvements**
  - [ ] Fuzzy/normalized address matching (handle variations)
  - [ ] Fuzzy phone number matching
  - [ ] Performance evaluation of community detection at scale (document findings)
- [ ] **Graph UX Enhancements**
  - [ ] Entity search: find any entity by name
  - [ ] Better node labeling and edge annotations
  - [ ] Risk-colored nodes in graph view
  - [ ] Click risk factor → highlight relevant graph path

### Success Criteria

- Shared address detection catches variations ("P.O. Box 123" vs "PO Box 123, Nairobi")
- Investigator can search for an entity and see its neighborhood
- Risk-relevant paths are visually highlighted

### Mentor Review Checkpoint

- **Demo**: Fuzzy detection catching previously missed patterns
- **UX Feedback**: Graph usability and investigation flow
- **Discussion**: Scale evaluation results, Neo4j migration considerations
- **Blockers**: _[Document any issues here]_

---

## Weeks 8–9: Polish, Export & Demo Readiness

**Goal**: Deployable, demonstrable, defensible system

### Deliverables

- [ ] **Export Features**
  - [ ] PDF risk report per tender (evidence, graph snapshot, recommendation)
  - [ ] CSV bulk export of risk scores
- [ ] **Performance & Quality**
  - [ ] Test with 100–500 tender dataset from configurable generator
  - [ ] Database index optimization
  - [ ] Frontend lazy loading and responsiveness
- [ ] **Documentation**
  - [ ] Updated architecture documentation
  - [ ] User guide: auditor workflows
  - [ ] Multi-tenancy architecture documented (deployment-per-client model)
  - [ ] API documentation (Swagger/OpenAPI — already auto-generated)
- [ ] **Demo Preparation**
  - [ ] Demo script: 3 scenarios (cartel, shell company, conflict of interest)
  - [ ] Backup: recorded demo video
  - [ ] "Under questioning" prep: FAQs, technical deep-dives
  - [ ] Pitch deck: problem, solution, impact, tech

### Success Criteria

- PDF risk report downloadable for any tender
- System handles 500 tenders without noticeable degradation
- Demo runs end-to-end without errors across all 3 scenarios
- Team can answer technical questions confidently

### Mentor Review Checkpoint

- **Demo Dry Run**: Full presentation with Q&A
- **Technical Review**: Code quality, architecture soundness
- **Deployment Test**: Deploy on fresh machine, verify works
- **Blockers**: _[Document any issues here]_

---

## Risk Register

| Risk                       | Probability | Impact | Status        | Mitigation                                                                              |
| -------------------------- | ----------- | ------ | ------------- | --------------------------------------------------------------------------------------- |
| Timeline slippage          | Medium      | High   | 🟡 Monitoring | Weekly checkpoints, prioritize critical path (M1→M2→M3→M7)                              |
| LLM hallucination          | Medium      | High   | 🟢 Mitigated  | Evidence grounding, output validation, template fallback                                |
| Graph performance at scale | Medium      | Medium | 🟡 Monitoring | Scale evaluation in Week 6–7, Neo4j migration path documented                           |
| Sparse/generic addresses   | High        | High   | 🟡 Monitoring | Multi-signal detection; address quality classifier; don't rely on single-field matching |
| PPIP data completeness     | High        | Medium | 🟢 Accepted   | Many OCDS releases are tender-only (no awards/values); supplement with e-GP contracts   |
| Async job reliability      | Low         | Low    | � Removed     | Manual recomputation workflow eliminates async job complexity                           |
| Auth security              | Low         | High   | 🟢 Mitigated  | JWT best practices, production OAuth2 migration documented                              |
| PDF extraction quality     | Medium      | Low    | 🟢 Accepted   | Human-in-the-loop review before commit                                                  |

**Legend**: 🟢 Mitigated | 🟡 Monitoring | 🔴 Critical

---

## Success Metrics Tracking

### Stage 1: Execution Proof (Weeks 1–4)

- [x] End-to-end demo functional (risk → evidence → graph → case)
- [x] 5+ fraud patterns detectable (cartel, shell, conflict, pricing, timeline)
- [x] Working MVP with Docker deployment
- [ ] Auth + dynamic data ingestion operational

### Stage 2: Performance + Trust (Weeks 5–7)

- [ ] CSV/PDF ingestion working
- [ ] Case workflow with real user roles
- [ ] LLM case analysis with grounded summaries
- [ ] Graph UX improvements with fuzzy detection
- [ ] Latency: < 300ms per tender assessment

### Stage 3: Deployable Value (Weeks 8–9)

- [ ] Export: PDF reports, CSV bulk export
- [ ] Scale: 500-tender dataset tested
- [ ] Multi-tenancy architecture documented
- [ ] Polished demo across 3 scenarios

---

## Demo Scenario Checklist

### Scenario A: Cartel Detection

- [x] Setup: 4-company ring in dataset
- [x] Trigger: Cluster view flags co-bidding
- [x] Evidence: Graph shows shared address, rotation
- [x] Action: Create case, flag for investigation
- [ ] Script: < 2 min walkthrough (polish in Week 8–9)

### Scenario B: Shell Company

- [x] Setup: 4-day-old company, KES 78M win
- [x] Trigger: Isolation Forest + shell rule
- [x] Evidence: Registration vs deadline, no history
- [x] Explanation: LLM narrative (or template fallback)
- [ ] Action: Payment freeze recommendation via case workflow
- [ ] Script: < 2 min walkthrough (polish in Week 8–9)

### Scenario C: Conflict of Interest

- [x] Setup: Director-official sibling relationship
- [x] Trigger: Rule-based detection
- [x] Evidence: Graph path with RELATED_TO edge
- [x] Explanation: Relationship citation
- [ ] Action: Conflict declaration via case workflow
- [ ] Script: < 2 min walkthrough (polish in Week 8–9)

---

## Tech Debt & Future Work

### Known Tech Debt

1. NetworkX scalability limit (~10k nodes) → Future: Neo4j migration
2. ARQ worker → Future: Celery if scale demands it
3. JWT auth → Future: OAuth2/OIDC integration
4. PDF extraction PoC → Future: Full OCR + NLP pipeline
5. Startup-loaded AppState → Future: event-driven state updates

### Post-Hackathon Enhancements

- OAuth2/OIDC production auth
- Multi-tenancy (tenant_id column + middleware isolation)
- Real-time procurement portal integration (API polling/webhooks)
- Mobile app for field auditors
- ML retraining pipeline with new data
- pgvector for semantic search over evidence packs
- Advanced graph analytics (PageRank, betweenness centrality)
- Multi-language support (Swahili, French for regional)

---

## Key Contacts & Resources

**Mentors/Supervisors**:

- Name: **\*\***\_\_\_\_**\*\***
- Focus: **\*\***\_\_\_\_**\*\***
- Contact: **\*\***\_\_**\*\***

**Technical Support**:

- LLM API: OpenAI/Anthropic support
- Cloud: [Deployment platform]
- Database: PostgreSQL community

**Documentation**:

- OCDS Standard: https://standard.open-contracting.org/
- Kenya PPRA: https://ppra.go.ke/
- Hackathon Resources: [Link]

---

**Roadmap Version**: 2.0  
**Last Updated**: February 2026 (Week 2)  
**Next Review**: End of Week 3
