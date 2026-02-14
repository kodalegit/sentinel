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
    BID_ON = "BID_ON"
    WON = "WON"
    AWARDED_BY = "AWARDED_BY"
    RELATED_TO = "RELATED_TO"
    SHARES_ADDRESS = "SHARES_ADDRESS"
    SHARES_PHONE = "SHARES_PHONE"


class RelationshipType(str, Enum):
    SIBLING = "SIBLING"
    SPOUSE = "SPOUSE"
    PARENT_CHILD = "PARENT_CHILD"
    BUSINESS_PARTNER = "BUSINESS_PARTNER"


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
    amount: float  # KES
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


class TenderWithRisk(BaseModel):
    """Tender with computed risk score for API responses."""

    tender: Tender
    risk: RiskScore
    bidder_count: int = 0


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
    author: str
    content: str
    note_type: NoteType
    created_at: datetime


class Case(BaseModel):
    id: str
    tender_id: str
    title: str
    status: CaseStatus
    priority: RiskCategory
    assigned_to: Optional[str] = None
    created_by: str
    summary: Optional[str] = None
    decision: Optional[str] = None
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
    assigned_to: Optional[str] = None
    summary: Optional[str] = None
    created_by: str = "auditor"


class CaseUpdate(BaseModel):
    status: Optional[CaseStatus] = None
    priority: Optional[RiskCategory] = None
    assigned_to: Optional[str] = None
    summary: Optional[str] = None
    decision: Optional[str] = None


class CaseNoteCreate(BaseModel):
    content: str
    author: str = "auditor"
    note_type: NoteType = NoteType.OBSERVATION


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
