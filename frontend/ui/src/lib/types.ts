/**
 * TypeScript types for Sentinel frontend.
 */

// Enums
export type RiskCategory = "HIGH" | "MEDIUM" | "LOW";
export type TenderStatus = "OPEN" | "EVALUATION" | "AWARDED" | "CANCELLED";
export type RiskFactorType =
  | "CARTEL_PATTERN"
  | "SHELL_COMPANY"
  | "CONFLICT_OF_INTEREST"
  | "PRICE_ANOMALY"
  | "RUSHED_TIMELINE";
export type NodeType = "COMPANY" | "DIRECTOR" | "OFFICIAL" | "TENDER";
export type EdgeType =
  | "DIRECTOR_OF"
  | "BID_ON"
  | "WON"
  | "AWARDED_BY"
  | "RELATED_TO"
  | "SHARES_ADDRESS"
  | "SHARES_PHONE";

// Core entities
export interface Tender {
  id: string;
  reference_number: string;
  title: string;
  description: string;
  procuring_entity: string;
  category: string;
  estimated_value: number;
  published_date: string;
  deadline: string;
  status: TenderStatus;
  awarded_to: string | null;
  awarded_amount: number | null;
  procurement_officer_id: string | null;
}

export interface Company {
  id: string;
  name: string;
  registration_number: string;
  registration_date: string;
  address: string;
  phone: string;
  director_ids: string[];
}

export interface Director {
  id: string;
  name: string;
  national_id: string | null;
  company_ids: string[];
}

export interface Bid {
  id: string;
  tender_id: string;
  company_id: string;
  amount: number;
  submission_date: string;
  technical_score: number | null;
}

// Risk assessment
export interface RiskFactor {
  type: RiskFactorType;
  description: string;
  weight: number;
  evidence: string[];
  related_entity_ids: string[];
}

export interface RiskScore {
  overall: number;
  category: RiskCategory;
  factors: RiskFactor[];
  recommendation: string | null;
}

export interface TenderWithRisk {
  tender: Tender;
  risk: RiskScore;
  bidder_count: number;
}

export interface TenderDetail {
  tender: Tender;
  risk: RiskScore;
  bids: Bid[];
  winning_company: Company | null;
}

// Graph
export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  risk_level: RiskCategory | null;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: EdgeType;
  suspicious: boolean;
  label: string | null;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Dashboard
export interface DashboardStats {
  total_tenders: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  pending_review: number;
  total_value: number;
  flagged_today: number;
}

// Cartel response
export interface CartelCluster {
  company_ids: string[];
  company_names: string[];
  size: number;
}

export interface CartelsResponse {
  cartels: CartelCluster[];
  total: number;
}

// Community detection
export interface CommunityCluster {
  id: string;
  company_ids: string[];
  company_names: string[];
  size: number;
  suspicion_score: number;
  shared_attributes: {
    addresses: { address: string; companies: string[] }[];
    phones: { phone: string; companies: string[] }[];
    directors: { director_id: string; companies: string[] }[];
  };
  co_bid_count: number;
  win_pattern: {
    total_bids: number;
    bids_per_company: Record<string, number>;
  };
}

export interface CommunitiesResponse {
  clusters: CommunityCluster[];
  total: number;
}

// Case Management
export type CaseStatus =
  | "OPEN"
  | "INVESTIGATING"
  | "ESCALATED"
  | "RESOLVED"
  | "DISMISSED";

export type NoteType = "OBSERVATION" | "EVIDENCE" | "DECISION" | "ACTION";

export interface CaseNote {
  id: string;
  case_id: string;
  author: string;
  content: string;
  note_type: NoteType;
  created_at: string;
}

export interface Case {
  id: string;
  tender_id: string;
  title: string;
  status: CaseStatus;
  priority: RiskCategory;
  assigned_to: string | null;
  created_by: string;
  summary: string | null;
  decision: string | null;
  created_at: string;
  updated_at: string;
  notes: CaseNote[];
}

export interface CaseWithTender {
  case: Case;
  tender_title: string;
  risk_score: number;
  risk_category: RiskCategory;
}

export interface CaseStats {
  total: number;
  open: number;
  investigating: number;
  escalated: number;
  resolved: number;
  dismissed: number;
}
