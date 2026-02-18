# Sentinel: Development Milestones

**Project**: AI-Powered Public Procurement Oversight System  
**Track**: Governance & Public Policy  
**Owner**: Victor Kimani  
**Current Week**: 3 of 9  
**Last Updated**: February 2026

---

## Status Legend

| Priority     | Meaning                                       |
| ------------ | --------------------------------------------- |
| **CRITICAL** | Must-have for a functional demo and judging   |
| **HIGH**     | Strongly expected for a credible submission   |
| **MEDIUM**   | Adds significant value; pursue if time allows |
| **LOW**      | Nice-to-have polish and future-proofing       |

---

## Milestone 1: Kenya Data Onramp & Schema Evolution

**Priority**: CRITICAL  
**Timeline**: Week 3 (1 week)  
**Status**: In Progress

### Description

Ground the system in real Kenyan procurement data. The current schema was designed around synthetic patterns; real data from PPIP (OCDS) and e-GP reveals critical gaps: no provenance tracking, no AGPO/reservation fields, no contract lifecycle model, no BRS/e-GP identifiers, and address matching that fails on Kenya's sparse/generic addresses. This milestone evolves the data model to match real government platform outputs, adds connectors for both PPIP and e-GP, and upgrades entity detection for the Kenyan data reality.

### Deliverables

#### Schema Evolution (Kenya-grounded)

- **Provenance fields** on all core entities: `source_system` (ppip/egp/manual/synthetic), `source_record_id`, `ingested_at`, `data_quality_flags` (JSON)
- **Company model expansion**: `supplier_type` (Local Company, Sole Proprietorship, etc.), `brs_number`, `egp_registration_number`, `contact_email`, `physical_address`, `postal_address` (split from single `address`), `postal_code`
- **Tender model expansion**: `procurement_method` (Open, Selective, Direct, RFQ), `procurement_category` (Goods, Works, Services, Non Consultancy Services), `pe_type` (National Government, County Government, State Corporation), `currency` (default KES), `ocds_id`
- **Contract model** (new): Links tender → supplier with `contract_number`, `contract_amount`, `start_date`, `end_date`, `effective_date`, `status`, AGPO fields (`agpo_group`, `reservation_group`, `is_agpo_reserved`)
- **Ownership model** (new): `company_id` → `owner_name`, `nationality`, `postal_address` — captures e-GP ownership info distinct from directors
- **Alembic migration** for all schema changes

#### Data Source Connectors

- **PPIP OCDS connector** (`connectors/ppip.py`): Fetch OCDS 1.1 releases from `tenders.go.ke/api/ocds/tenders?fy=YYYY-YYYY`, normalize to internal schema, handle both `"tender"` and `"contract"` tagged releases, extract parties with supplier roles
- **e-GP ingestion adapters** (`connectors/egp.py`): Accept e-GP tender list payloads and contract detail payloads (including `contractmaindata`, `contractmoredetails`, `supplierdetails` with director/ownership info), normalize dates (DD/MM/YYYY → ISO), map AGPO fields
- **Ingestion API** (`routes/ingest.py`): POST endpoints for PPIP sync (by FY) and e-GP payload ingestion; triggers async recomputation

#### Multi-Signal Entity Detection (Kenyan data reality)

- **Address quality classifier**: Score addresses as SPECIFIC (plot/building/LR number), VAGUE (road/area name only), or PLACEHOLDER ("PO Box 123" default pattern)
- **Enhanced shared-attribute detection**: Exact email match, shared BRS prefix patterns, shared postal code + vague address combo, same-person ownership across multiple bidding companies
- **Data completeness scoring**: Per-entity quality score based on field coverage (directors listed? ownership info? valid address? contact details?)
- **"Missing data as signal"**: Companies with no directors, placeholder addresses, and null nationality flagged as elevated shell risk

#### Infrastructure

- **Manual recomputation workflow**: User triggers recomputation via Data Sources page after ingestion
- **POST /api/recompute endpoint**: In-process recomputation (graph rebuild, community detection, risk scoring)
- **Configurable synthetic data generator** with realistic Kenyan patterns
- **Automated startup pipeline**: migrations, seeding, health checks in Docker

### Success Criteria

- Schema handles real PPIP OCDS releases and e-GP contract payloads without data loss
- PPIP sync ingests 50+ real OCDS releases for FY 2025-2026 and persists normalized records
- e-GP contract ingestion accepts representative payloads including AGPO metadata and supplier ownership
- Shell company detection works under sparse data: flags companies with placeholder addresses + recent registration + missing directors
- Address quality classifier correctly distinguishes "Plot 45, Industrial Area" (specific) from "MOI AVENUE" (vague) from "PO Box 123" (placeholder)
- `docker compose up` brings full stack to healthy state
- Manual recomputation workflow allows users to batch ingestions before re-analyzing

---

## Milestone 2: User Management & Authentication

**Priority**: HIGH
**Timeline**: Weeks 3–4 (1–2 weeks)
**Status**: ✅ Complete

### Description

Cases currently have no real ownership — anyone can create, update, or dismiss them. This milestone introduces authentication and role-based access so that the investigation workflow has accountability. Users log in, and their actions are attributed and permission-gated.

### Deliverables

- ✅ User model with roles: **auditor**, **supervisor**, **admin**, **system**
- ✅ JWT-based authentication (login, token refresh)
- ✅ Role-based route protection (e.g., only supervisors can escalate/dismiss cases)
- ✅ User attribution on case actions, notes, and audit logs
- ✅ Basic login UI
- ✅ Admin user management page

### Success Criteria

- ✅ An auditor can log in, open and investigate cases, but cannot dismiss or escalate
- ✅ A supervisor can escalate, resolve, or dismiss cases
- ✅ All case actions are attributed to the logged-in user in the audit trail
- ✅ Admin can create, edit, and deactivate users

### Implementation Details

**Backend:**

- `UserDB` model with FK relationships to `CaseDB` and `CaseNoteDB`
- Alembic migration `a1b2c3d4e5f6` — adds `users` table, migrates string user fields to UUID FKs
- `auth/security.py` — bcrypt password hashing, JWT access (30min) + refresh (7 day) tokens
- `auth/dependencies.py` — `get_current_user`, `require_roles`, typed `CurrentUser`, `SupervisorOrAdmin`, `AdminOnly`
- `routes/auth.py` — `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me`
- `routes/users.py` — full CRUD at `/api/users` (admin only), `/api/users/assignable/list`
- All case routes protected with `CurrentUser`; dismiss/reassign gated to supervisor+
- Ingestion routes + `/api/recompute` protected with `SupervisorOrAdmin`
- Audit logs include `user_id` attribution
- Seed users: admin/admin123, supervisor/super123, auditor/audit123, system (no login)

**Frontend:**

- `AuthProvider` + `useAuth` hook — JWT stored in localStorage, auto-refresh on 401
- `/login` page with demo credentials hint
- `AuthGuard` component — wraps Dashboard, Cases, Graph pages; redirects to `/login` if unauthenticated
- Sidebar — shows logged-in user avatar + role, logout button, admin-only User Management link
- Cases page — DISMISS button hidden for auditors
- `/admin/users` — create, edit role/password, activate/deactivate users

**Default Credentials:**
| User | Password | Role |
|------|----------|------|
| `admin` | `admin123` | Admin |
| `supervisor` | `super123` | Supervisor |
| `auditor` | `audit123` | Auditor |

---

## Milestone 3: Investigation Workflow Hardening

**Priority**: HIGH  
**Timeline**: Week 4–5 (1–2 weeks)  
**Status**: Not Started

### Description

The case management system has the basic status machine (OPEN → INVESTIGATING → ESCALATED → RESOLVED/DISMISSED) but lacks the depth needed for a realistic audit workflow. This milestone fleshes out the investigation experience — assignment, handoff, decision recording, and supervisor oversight.

### Deliverables

- **Hybrid case assignment**: supervisors can assign cases to auditors; auditors can self-assign from an unassigned queue
- Supervisor dashboard: view all open/escalated cases, filter by assignee and priority
- Decision recording with structured fields (finding, recommendation, evidence references)
- Case timeline view showing full history of status changes, notes, and assignments
- Notification hooks (placeholder — e.g., log or in-app indicator when a case is escalated or assigned)

### Success Criteria

- A supervisor can assign and reassign cases; an auditor can pick up unassigned cases
- A case's full investigation history is visible in a timeline
- Decisions are recorded with structured evidence references

---

## Milestone 4: Data Ingestion Pipeline (Extended)

**Priority**: MEDIUM  
**Timeline**: Weeks 5–6 (1–2 weeks)  
**Status**: Not Started

### Description

Building on Milestone 1's source connectors and normalized ingestion layer, this milestone adds richer data input — CSV batch upload, PDF document extraction with human-in-the-loop review, and deeper entity resolution. The goal is to improve completeness and linkage quality where Kenyan source systems are sparse or inconsistent.

### Deliverables

- CSV/Excel batch upload endpoint for tenders and bids (validated, with error reporting)
- **PDF ingestion proof-of-concept**: upload PDF → LLM-assisted field extraction → auditor reviews/corrects extracted fields → commit to system
- Entity resolution: fuzzy matching on company names, deduplication of directors
- Cross-source reconciliation: merge/link records referring to the same tender/supplier across e-GP and PPIP where identifiers differ
- Ingestion status/progress feedback to the user (job status polling or push)

### Success Criteria

- A CSV of 50+ tenders can be uploaded and processed into the system
- A PDF tender document can be uploaded, fields extracted and presented for review, then committed
- Duplicate companies are detected and merged rather than duplicated
- Cross-source duplicates (PPIP vs e-GP) can be linked with a confidence score

---

## Milestone 5: LLM Integration & Case Analysis

**Priority**: MEDIUM  
**Timeline**: Weeks 5–6 (1–2 weeks)  
**Status**: Not Started

### Description

The LLM explanation endpoint exists but is limited to single-tender risk explanation. This milestone deepens the LLM integration to support the investigation workflow — generating case summaries, suggesting next steps, and answering auditor questions about a case's evidence.

### Deliverables

- Case-level AI summary: synthesize all linked tenders, risk factors, and notes into an executive brief
- "Suggest next steps" generation based on case status and evidence
- Conversational investigation assistant (ask questions about a case's evidence pack)
- Improved prompt engineering for advisory, non-accusatory language
- Robust fallback: all LLM features degrade gracefully to template-based output

### Success Criteria

- An auditor can generate a case summary that references specific evidence items
- Suggested next steps are contextually relevant to the case's current status
- System works fully (with reduced richness) when no LLM API key is configured

---

## Milestone 6: Graph UX & Detection Improvements

**Priority**: MEDIUM  
**Timeline**: Weeks 6–7 (1–2 weeks)  
**Status**: Not Started

### Description

The graph explorer works but has room for improvement in both detection quality and user experience. Shared attribute detection (addresses, phones) is currently very literal, and the graph view could better guide investigators toward suspicious patterns.

### Deliverables

- Improved shared attribute detection: fuzzy/normalized address and phone matching
- Graph search: find any entity by name
- Visual improvements: better node labeling, edge annotations, risk-colored nodes
- Path highlighting: click a risk factor to highlight the relevant graph path
- Performance evaluation of community detection at larger scale; document findings and migration path if needed

### Success Criteria

- Shared address detection catches variations (e.g., "P.O. Box 123" vs "PO Box 123, Nairobi")
- An investigator can search for an entity and see its neighborhood in the graph
- Risk-relevant paths are visually highlighted when exploring a flagged tender

---

## Milestone 7: Polish, Export & Demo Readiness

**Priority**: LOW  
**Timeline**: Weeks 8–9 (1–2 weeks)  
**Status**: Not Started

### Description

Final hardening pass — export capabilities, performance optimization, documentation, and demo preparation. The goal is a system that presents well under scrutiny and can be demonstrated confidently.

### Deliverables

- PDF risk report export for individual tenders (evidence, graph snapshot, recommendation)
- CSV bulk export of risk scores
- Performance testing with expanded dataset (100–500 tenders)
- Polished demo script covering 3 scenarios (cartel, shell company, conflict of interest)
- Updated architecture documentation and user guide
- Recorded backup demo video

### Success Criteria

- A risk report PDF can be generated and downloaded for any tender
- System handles 500 tenders without noticeable performance degradation
- Demo runs end-to-end without errors across all 3 scenarios

---

## Timeline Summary

| Week | Milestone                                | Priority |
| ---- | ---------------------------------------- | -------- |
| 3    | M1: Kenya Data Onramp & Schema Evolution | CRITICAL |
| 3–4  | M2: User Management & Authentication     | HIGH     |
| 4–5  | M3: Investigation Workflow Hardening     | HIGH     |
| 5–6  | M4: Data Ingestion Pipeline (Extended)   | MEDIUM   |
| 5–6  | M5: LLM Integration & Case Analysis      | MEDIUM   |
| 6–7  | M6: Graph UX & Detection Improvements    | MEDIUM   |
| 8–9  | M7: Polish, Export & Demo Readiness      | LOW      |

> Milestones 4–6 can be pursued in parallel or reordered based on progress and feedback. The critical path is M1 → M2 → M3 → M7.

---

## Resolved Questions

1. **Data ingestion scope**: Milestone 1 includes PPIP OCDS + e-GP JSON ingestion baseline; CSV remains minimum fallback; PDF/OCR remains upload → extract fields → manual review before commit.
2. **Auth depth**: JWT + roles (auditor, supervisor, admin) is sufficient for the hackathon. Production migration to a hardened framework (e.g., OAuth2/OIDC) documented as future work.
3. **Multi-tenancy**: Documented as an architecture decision only. The system will be deployed separately per client in production.
4. **Real data**: PPIP OCDS API confirmed live and returning real releases (FY 2025-2026). e-GP contract endpoint provides rich supplier/ownership data. Hybrid strategy: real PPIP/e-GP samples + synthetic augmentation for controllable fraud scenarios.
5. **Address quality**: Kenyan e-GP addresses are frequently vague ("MOI AVENUE") or placeholder ("PO Box 123"). Detection must use multi-signal scoring, not single-field address matching.
6. **AGPO handling**: AGPO reservation data (youth/women/PWD) available in e-GP contracts. Stored for analysis but treated as context, not a risk factor — AGPO fronting detection uses ownership/director overlap signals instead.

## Architectural Decisions (Week 3)

1. **Manual recomputation workflow**: After data ingestion, users trigger recomputation via Data Sources page (`POST /api/recompute`). This allows batching multiple ingestions before expensive analysis and provides control over when recomputation runs. Removed Redis + ARQ worker in favor of in-process recomputation.
2. **Dual-source ingestion**: PPIP (OCDS) provides tender metadata + some awards/contracts with party details. e-GP provides richer contract + supplier ownership data. Both normalized to the same internal schema with provenance tracking.
3. **Address quality as first-class concept**: Every company address classified as SPECIFIC/VAGUE/PLACEHOLDER. Vague addresses suppress shared-address edge confidence; placeholder addresses ("PO Box 123") are excluded from address matching entirely.
4. **Multi-signal shell detection**: Registration recency alone is insufficient. Shell risk is a composite of: (a) company age, (b) address quality, (c) director count, (d) ownership completeness, (e) email domain patterns, (f) BRS number recency. Each signal has independent weight; composite exceeding threshold triggers flag.
5. **Contract as first-class entity**: Separate from tender. A tender may have zero or many contracts. Contract carries award amount, AGPO status, supplier link, and dates — enabling contract-level analysis.
6. **Case assignment**: Hybrid model — supervisors can assign cases to auditors, and auditors can self-assign from an unassigned queue.
7. **Confidence-aware detection**: When critical supplier attributes are missing/generic, Sentinel uses explicit data-quality flags and multi-signal scoring instead of single-field conclusions.
8. **Nullable estimated_value**: Kenyan tenders may not have estimated_value. ML features and stats calculations handle None gracefully (defaulting to 0 for ratios).

---

**Version**: 2.0  
**Next Review**: End of Week 3
