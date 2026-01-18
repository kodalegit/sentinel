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


class RiskFactorType(str, Enum):
    CARTEL_PATTERN = "CARTEL_PATTERN"
    SHELL_COMPANY = "SHELL_COMPANY"
    CONFLICT_OF_INTEREST = "CONFLICT_OF_INTEREST"
    PRICE_ANOMALY = "PRICE_ANOMALY"
    RUSHED_TIMELINE = "RUSHED_TIMELINE"


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
    related_persons: dict[str, RelationshipType] = Field(default_factory=dict)  # person_id -> relationship


class Company(BaseModel):
    id: str
    name: str
    registration_number: str
    registration_date: date
    address: str
    phone: str
    director_ids: list[str] = Field(default_factory=list)


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
    description: str
    procuring_entity: str
    category: str
    estimated_value: float  # KES
    published_date: date
    deadline: date
    status: TenderStatus
    awarded_to: Optional[str] = None  # company_id
    awarded_amount: Optional[float] = None
    procurement_officer_id: Optional[str] = None


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


# Dashboard Stats
class DashboardStats(BaseModel):
    total_tenders: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    pending_review: int
    total_value: float  # KES
    flagged_today: int
