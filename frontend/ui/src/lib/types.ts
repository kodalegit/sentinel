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
  | "RUSHED_TIMELINE"
  | "ML_ANOMALY";
export type NodeType = "COMPANY" | "DIRECTOR" | "OFFICIAL" | "TENDER";
export type EdgeType =
  | "DIRECTOR_OF"
  | "BID_ON"
  | "WON"
  | "AWARDED_BY"
  | "RELATED_TO"
  | "SHARES_ADDRESS"
  | "SHARES_PHONE"
  | "SHARES_EMAIL";

// Core entities
export interface Tender {
  id: string;
  reference_number: string;
  title: string;
  description: string;
  procuring_entity: string;
  category: string;
  estimated_value: number | null;
  published_date: string | null;
  deadline: string | null;
  status: TenderStatus;
  awarded_to: string | null;
  awarded_amount: number | null;
  procurement_officer_id: string | null;
  procurement_method: string | null;
  procurement_category: string | null;
  pe_type: string | null;
  currency: string;
  source_system: string | null;
}

export interface Company {
  id: string;
  name: string;
  registration_number: string;
  registration_date: string | null;
  address: string | null;
  phone: string | null;
  director_ids: string[];
  supplier_type: string | null;
  brs_number: string | null;
  contact_email: string | null;
  physical_address: string | null;
  postal_address: string | null;
  postal_code: string | null;
  source_system: string | null;
  data_quality_flags: Record<string, unknown> | null;
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
  assigned_to_id: string | null;
  created_by: string;
  created_by_id: string | null;
  summary: string | null;
  decision: string | null;
  decision_type: string | null;
  finding: string | null;
  closed_at: string | null;
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

// M3: Case Events & Timeline
export type EventType =
  | "CASE_OPENED"
  | "STATUS_CHANGE"
  | "ASSIGNMENT"
  | "NOTE_ADDED"
  | "PRIORITY_CHANGE"
  | "DECISION_RECORDED"
  | "EVIDENCE_LINKED"
  | "EVIDENCE_UNLINKED";

export interface CaseEvent {
  id: string;
  case_id: string;
  event_type: EventType;
  actor: string;
  actor_id: string;
  old_value: string | null;
  new_value: string | null;
  event_metadata: Record<string, unknown> | null;
  created_at: string;
}

// M3: Evidence Links
export type EvidenceType = "TENDER" | "RISK_FACTOR" | "GRAPH_PATH" | "DOCUMENT";

export interface CaseEvidenceLink {
  id: string;
  case_id: string;
  evidence_type: EvidenceType;
  reference_id: string;
  label: string;
  link_metadata: Record<string, unknown> | null;
  added_by: string;
  added_by_id: string;
  created_at: string;
}

// M3: Structured Decisions
export type DecisionType =
  | "SUBSTANTIATED"
  | "UNSUBSTANTIATED"
  | "REFERRED"
  | "INCONCLUSIVE";

// M3: Notifications
export interface CaseNotification {
  id: string;
  case_id: string;
  case_title: string | null;
  message: string;
  is_read: boolean;
  created_at: string;
}

// M3: Supervisor Workload
export interface WorkloadItem {
  user_id: string | null;
  username: string;
  full_name: string;
  role: string | null;
  open: number;
  investigating: number;
  escalated: number;
  total_active: number;
}

// Ingestion
export interface IngestionResponse {
  status: string;
  message: string;
  counts: Record<string, number>;
}

export interface RecomputeResponse {
  status: string;
  stats: {
    tenders: number;
    companies: number;
    nodes: number;
    edges: number;
    communities: number;
    risk_scores: number;
  };
}

// =============================================================================
// M5: Knowledge Base, Chat, and Agent Settings
// =============================================================================

export type KnowledgeDocumentCategory =
  | "LAW"
  | "CASE_LAW"
  | "REGULATION"
  | "GUIDELINE";

export interface KnowledgeDocument {
  id: string;
  title: string;
  description: string | null;
  category: KnowledgeDocumentCategory;
  source_url: string | null;
  file_name: string | null;
  chunk_count: number;
  uploaded_by: string | null;
  created_at: string;
}

export interface KnowledgeChunk {
  id: string;
  document_id: string;
  content: string;
  chunk_index: number;
  page_number: number | null;
  chunk_metadata: Record<string, unknown> | null;
}

export interface KnowledgeStats {
  total_documents: number;
  total_chunks: number;
  by_category: Record<string, number>;
}

export interface ChatThread {
  id: string;
  case_id: string;
  user_id: string;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  events: ChatStreamEvent[] | null;
  created_at: string;
}

export interface Citation {
  marker: number;
  doc_id: string;
  title: string;
  source_url: string | null;
  category: string;
  excerpt: string;
  page: number | null;
  chunk_id: string;
}

export type ChatStreamEventType =
  | "token"
  | "reasoning"
  | "tool_start"
  | "tool_end"
  | "citation"
  | "done"
  | "error";

export interface ChatStreamEvent {
  type: ChatStreamEventType;
  // token
  delta?: string;
  // reasoning
  content?: string;
  step?: number;
  // tool_start / tool_end
  tool?: string;
  tool_call_id?: string;
  input?: Record<string, unknown>;
  summary?: string;
  // citation
  marker?: number;
  doc_id?: string;
  title?: string;
  source_url?: string | null;
  category?: string;
  excerpt?: string;
  page?: number | null;
  chunk_id?: string;
  // done
  citations?: Citation[];
  thread_id?: string;
  // error
  message?: string;
  code?: string;
  recoverable?: boolean;
}

export type ChatAction = "chat" | "summary" | "next_steps" | "risk_analysis";

export interface AgentSettings {
  llm_provider: string | null;
  llm_model: string | null;
  llm_api_key_set: boolean;
  llm_base_url: string | null;
  llm_temperature: number | null;
  embedding_provider: string | null;
  embedding_model: string | null;
}

export interface AgentSettingsUpdate {
  llm_provider?: string;
  llm_model?: string;
  llm_api_key?: string;
  llm_base_url?: string;
  llm_temperature?: number;
  embedding_provider?: string;
  embedding_model?: string;
}
