"""
Pydantic models for Sentinel MVP.
Represents the procurement domain entities and risk assessment structures.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# Enums
class RiskCategory(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TenderStatus(str, Enum):
    OPEN = "OPEN"
    EVALUATION = "EVALUATION"
    AWARDED = "AWARDED"
    CANCELLED = "CANCELLED"


class AddressQuality(str, Enum):
    SPECIFIC = "SPECIFIC"
    VAGUE = "VAGUE"
    PLACEHOLDER = "PLACEHOLDER"
    UNKNOWN = "UNKNOWN"


class SourceSystem(str, Enum):
    PPIP = "ppip"
    EGP = "egp"
    MANUAL = "manual"
    SYNTHETIC = "synthetic"


class RiskFactorType(str, Enum):
    CARTEL_PATTERN = "CARTEL_PATTERN"
    SHELL_COMPANY = "SHELL_COMPANY"
    CONFLICT_OF_INTEREST = "CONFLICT_OF_INTEREST"
    PRICE_ANOMALY = "PRICE_ANOMALY"
    RUSHED_TIMELINE = "RUSHED_TIMELINE"
    ML_ANOMALY = "ML_ANOMALY"


class NodeType(str, Enum):
    COMPANY = "COMPANY"
    DIRECTOR = "DIRECTOR"
    OFFICIAL = "OFFICIAL"
    TENDER = "TENDER"


class EdgeType(str, Enum):
    DIRECTOR_OF = "DIRECTOR_OF"
    DIRECTED_BY = "DIRECTED_BY"
    BID_ON = "BID_ON"
    CO_BID = "CO_BID"
    WON = "WON"
    AWARDED_BY = "AWARDED_BY"
    RELATED_TO = "RELATED_TO"
    SHARES_ADDRESS = "SHARES_ADDRESS"
    SHARES_PHONE = "SHARES_PHONE"
    SHARES_EMAIL = "SHARES_EMAIL"


class RelationshipType(str, Enum):
    SIBLING = "SIBLING"
    SPOUSE = "SPOUSE"
    PARENT_CHILD = "PARENT_CHILD"
    BUSINESS_PARTNER = "BUSINESS_PARTNER"


class UserRole(str, Enum):
    AUDITOR = "auditor"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    SYSTEM = "system"


# User & Authentication Models
class User(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    role: UserRole = UserRole.AUDITOR


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    username: str
    password: str


# Core Domain Entities
class Director(BaseModel):
    id: str
    name: str
    national_id: Optional[str] = None
    company_ids: list[str] = Field(default_factory=list)


class PublicOfficial(BaseModel):
    id: str
    name: str
    department: str
    position: str
    related_persons: dict[str, RelationshipType] = Field(
        default_factory=dict
    )  # person_id -> relationship


class Company(BaseModel):
    id: str
    name: str
    registration_number: str
    registration_date: Optional[date] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    director_ids: list[str] = Field(default_factory=list)

    # Kenya-specific fields
    supplier_type: Optional[str] = None
    brs_number: Optional[str] = None
    egp_registration_number: Optional[str] = None
    contact_email: Optional[str] = None
    physical_address: Optional[str] = None
    postal_address: Optional[str] = None
    postal_code: Optional[str] = None

    # Provenance
    source_system: Optional[str] = None
    source_record_id: Optional[str] = None
    data_quality_flags: Optional[dict] = None


class Bid(BaseModel):
    id: str
    tender_id: str
    company_id: str
    amount: Optional[float] = None
    submission_date: datetime
    technical_score: Optional[float] = None


class Tender(BaseModel):
    id: str
    reference_number: str
    title: str
    description: Optional[str] = None
    procuring_entity: str
    category: Optional[str] = None
    estimated_value: Optional[float] = None  # KES
    published_date: Optional[date] = None
    deadline: Optional[date] = None
    status: TenderStatus = TenderStatus.OPEN
    awarded_to: Optional[str] = None  # company_id
    awarded_amount: Optional[float] = None
    procurement_officer_id: Optional[str] = None

    # Kenya-specific fields
    procurement_method: Optional[str] = None
    procurement_category: Optional[str] = None
    pe_type: Optional[str] = None
    currency: str = "KES"
    ocds_id: Optional[str] = None
    buyer_id: Optional[str] = None

    # Provenance
    source_system: Optional[str] = None
    source_record_id: Optional[str] = None
    data_quality_flags: Optional[dict] = None


# Risk Assessment Models
class RiskFactor(BaseModel):
    type: RiskFactorType
    description: str
    weight: int  # Contribution to overall score
    evidence: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)


class RiskScore(BaseModel):
    overall: int = Field(ge=0, le=100)
    category: RiskCategory
    factors: list[RiskFactor] = Field(default_factory=list)
    recommendation: Optional[str] = None


class AnalysisSnapshotInfo(BaseModel):
    analysis_run_id: Optional[str] = None
    status: Optional[str] = None
    snapshot_source: Optional[str] = None
    graph_source: Optional[str] = None
    graph_loaded: bool = False
    model_version: Optional[str] = None
    created_at: Optional[datetime] = None
    tender_count: int = 0
    company_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    community_count: int = 0
    risk_score_count: int = 0
    company_feature_count: int = 0


class TenderWithRisk(BaseModel):
    """Tender with computed risk score for API responses."""

    tender: Tender
    risk: RiskScore
    bidder_count: int = 0


class TenderBidStats(BaseModel):
    bidder_count: int = 0
    priced_bid_count: int = 0
    participation_only_count: int = 0


class PaginatedTenderResults(BaseModel):
    items: list[TenderWithRisk] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 50
    has_more: bool = False


class TenderDetail(BaseModel):
    """Full tender details including bids and risk breakdown."""

    tender: Tender
    risk: RiskScore
    bids: list[Bid] = Field(default_factory=list)
    winning_company: Optional[Company] = None


# Graph Models for Frontend
class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    risk_level: Optional[RiskCategory] = None
    metadata: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: EdgeType
    suspicious: bool = False
    label: Optional[str] = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphSearchResult(BaseModel):
    id: str
    type: NodeType
    label: str
    risk_level: Optional[RiskCategory] = None
    subtitle: Optional[str] = None


# Case Management
class CaseStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class NoteType(str, Enum):
    OBSERVATION = "OBSERVATION"
    EVIDENCE = "EVIDENCE"
    DECISION = "DECISION"
    ACTION = "ACTION"


class CaseNote(BaseModel):
    id: str
    case_id: str
    author: str  # Display name
    author_id: Optional[str] = None  # User UUID
    content: str
    note_type: NoteType
    created_at: datetime


class Case(BaseModel):
    id: str
    tender_id: str
    title: str
    status: CaseStatus
    priority: RiskCategory
    assigned_to: Optional[str] = None  # Display name
    assigned_to_id: Optional[str] = None  # User UUID
    created_by: str  # Display name
    created_by_id: Optional[str] = None  # User UUID
    summary: Optional[str] = None
    decision: Optional[str] = None  # Legacy recommendation field
    # M3: Structured decision fields
    decision_type: Optional[str] = None
    finding: Optional[str] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    notes: list[CaseNote] = Field(default_factory=list)


class CaseWithTender(BaseModel):
    """Case with associated tender info for list views."""

    case: Case
    tender_title: str
    risk_score: int
    risk_category: RiskCategory


class CaseCreate(BaseModel):
    tender_id: str
    title: str
    priority: Optional[RiskCategory] = None
    assigned_to_id: Optional[str] = None  # User UUID to assign to
    summary: Optional[str] = None


class CaseUpdate(BaseModel):
    status: Optional[CaseStatus] = None
    priority: Optional[RiskCategory] = None
    assigned_to_id: Optional[str] = None  # User UUID to assign to
    summary: Optional[str] = None
    decision: Optional[str] = None


class CaseNoteCreate(BaseModel):
    content: str
    note_type: NoteType = NoteType.OBSERVATION


# M3: Case Events & Timeline
class EventType(str, Enum):
    CASE_OPENED = "CASE_OPENED"
    STATUS_CHANGE = "STATUS_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"
    NOTE_ADDED = "NOTE_ADDED"
    PRIORITY_CHANGE = "PRIORITY_CHANGE"
    DECISION_RECORDED = "DECISION_RECORDED"
    EVIDENCE_LINKED = "EVIDENCE_LINKED"
    EVIDENCE_UNLINKED = "EVIDENCE_UNLINKED"


class CaseEvent(BaseModel):
    id: str
    case_id: str
    event_type: EventType
    actor: str  # Display name
    actor_id: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    event_metadata: Optional[dict] = None
    created_at: datetime


# M3: Evidence Links
class EvidenceType(str, Enum):
    TENDER = "TENDER"
    RISK_FACTOR = "RISK_FACTOR"
    GRAPH_PATH = "GRAPH_PATH"
    DOCUMENT = "DOCUMENT"


class CaseEvidenceLink(BaseModel):
    id: str
    case_id: str
    evidence_type: EvidenceType
    reference_id: str
    label: str
    link_metadata: Optional[dict] = None
    added_by: str  # Display name
    added_by_id: str
    created_at: datetime


class CaseEvidenceLinkCreate(BaseModel):
    evidence_type: EvidenceType
    reference_id: str
    label: str
    link_metadata: Optional[dict] = None


# M3: Structured Decisions
class DecisionType(str, Enum):
    SUBSTANTIATED = "SUBSTANTIATED"
    UNSUBSTANTIATED = "UNSUBSTANTIATED"
    REFERRED = "REFERRED"
    INCONCLUSIVE = "INCONCLUSIVE"


class CaseDecision(BaseModel):
    decision_type: DecisionType
    finding: str
    recommendation: Optional[str] = None
    evidence_references: list[str] = Field(default_factory=list)  # Evidence link IDs


# M3: Notifications
class CaseNotification(BaseModel):
    id: str
    case_id: str
    case_title: Optional[str] = None
    message: str
    is_read: bool
    created_at: datetime


# M3: Supervisor Workload
class WorkloadItem(BaseModel):
    user_id: Optional[str] = None
    username: str
    full_name: str
    role: Optional[str] = None
    open: int
    investigating: int
    escalated: int
    total_active: int


# Contract model (Kenya e-GP)
class Contract(BaseModel):
    id: str
    tender_id: Optional[str] = None
    company_id: Optional[str] = None
    contract_number: str
    title: Optional[str] = None
    description: Optional[str] = None
    contract_amount: Optional[float] = None
    currency: str = "KES"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    effective_date: Optional[date] = None
    status: Optional[str] = None
    procurement_method: Optional[str] = None
    procurement_category: Optional[str] = None
    agpo_group: Optional[str] = None
    reservation_group: Optional[str] = None
    is_agpo_reserved: Optional[bool] = None
    pe_name: Optional[str] = None
    pe_type: Optional[str] = None
    source_system: Optional[str] = None
    source_record_id: Optional[str] = None


# Ownership model (Kenya e-GP)
class Ownership(BaseModel):
    id: str
    company_id: str
    owner_name: str
    nationality: Optional[str] = None
    postal_address: Optional[str] = None


# Dashboard Stats
class DashboardStats(BaseModel):
    total_tenders: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    pending_review: int
    total_value: float  # KES
    flagged_today: int


# =============================================================================
# M5: Knowledge Base, Chat, and Agent Settings
# =============================================================================


class KnowledgeDocumentCategory(str, Enum):
    LAW = "LAW"
    CASE_LAW = "CASE_LAW"
    REGULATION = "REGULATION"
    GUIDELINE = "GUIDELINE"


class KnowledgeDocument(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    category: KnowledgeDocumentCategory
    source_url: Optional[str] = None
    file_name: Optional[str] = None
    chunk_count: int = 0
    uploaded_by: Optional[str] = None
    created_at: datetime


class KnowledgeDocumentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: KnowledgeDocumentCategory
    source_url: Optional[str] = None


class KnowledgeDocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[KnowledgeDocumentCategory] = None
    source_url: Optional[str] = None


class KnowledgeChunk(BaseModel):
    id: str
    document_id: str
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    chunk_metadata: Optional[dict] = None


class KnowledgeStats(BaseModel):
    total_documents: int
    total_chunks: int
    by_category: dict[str, int]


class ChatThread(BaseModel):
    id: str
    case_id: str
    user_id: str
    title: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    citations: Optional[list[dict]] = None
    events: Optional[list[dict]] = None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class AgentSetting(BaseModel):
    key: str
    value: str
    updated_by: Optional[str] = None
    updated_at: datetime


class AgentSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_temperature: Optional[float] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None


class AgentSettingsResponse(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_set: bool = False
    llm_base_url: Optional[str] = None
    llm_temperature: Optional[float] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None


class LLMModelCatalogEntry(BaseModel):
    value: str
    label: str
    description: Optional[str] = None
    recommended: bool = False
    deprecated: bool = False


class LLMProviderCatalog(BaseModel):
    value: str
    label: str
    description: Optional[str] = None
    requires_api_key: bool = True
    supports_base_url: bool = False
    supports_custom_model: bool = False
    models: list[LLMModelCatalogEntry] = Field(default_factory=list)


class LLMModelCatalogResponse(BaseModel):
    providers: list[LLMProviderCatalog] = Field(default_factory=list)
