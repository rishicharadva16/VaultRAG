export type Role = 'employee' | 'manager' | 'hr_admin' | 'finance_admin' | 'admin';

export interface User {
  id: string;
  name: string;
  email: string;
  roles: Role[];
  employee_id: string | null;
  department: string | null;
  external_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface HighlightOut {
  start: number;
  end: number;
}

// Map to TypeScript number
export interface HighlightSpan {
  start: number;
  end: number;
}

export interface CitationItem {
  id: number;
  chunk_id: string;
  source_id: string;
  file: string;
  page: number | null;
  row_id?: string | null;
  snippet: string;
  highlights: HighlightSpan[];
  highlight_text: string;
}

export interface AskResponse {
  answer: string;
  refused: boolean;
  verified: boolean;
  citations: CitationItem[];
}

export interface SearchResultItem {
  chunk_id: string;
  source_id: string;
  file: string;
  page: number | null;
  row_id?: string | null;
  text: string;
  score: number;
}

export interface SearchResponse {
  results: SearchResultItem[];
  count: number;
  message?: string | null;
}

export interface ChunkResponse {
  chunk_id: string;
  source_id: string;
  file: string;
  page: number | null;
  row_id?: string | null;
  text: string;
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface SourceViewResponse {
  kind: 'pdf_text' | 'image' | 'db_row' | 'text';
  file: string;
  page: number | null;
  row_id?: string | null;
  page_width?: number | null;
  page_height?: number | null;
  rects: Rect[];
  match: 'exact' | 'partial' | 'none';
  text: string;
  page_image_url?: string | null;
}

export interface SourcePagesResponse {
  page_count: number;
  readable_pages: number[];
}

export interface HealthResponse {
  postgres: { status: string; detail?: string };
  qdrant: { status: string };
  llm: { status: string };
}

// ── Admin User Management Types ─────────────────────────

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  department: string | null;
  employee_id: string | null;
  is_active: boolean;
  shown_in_demo: boolean;
  is_admin: boolean;
  roles: string[];
}

export interface CreateAdminUserPayload {
  name: string;
  email: string;
  password: string;
  department?: string | null;
  employee_id?: string | null;
  roles?: string[];
  external_id?: string | null;
}

export interface PatchAdminUserPayload {
  name?: string | null;
  department?: string | null;
  is_active?: boolean | null;
  shown_in_demo?: boolean | null;
  password?: string | null;
}


// ── Step 6 Document & Sharing Types ─────────────────────────

export type DocumentKind = 'pdf' | 'image' | 'csv' | 'text';
export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed';

export interface DocumentOwner {
  id: string;
  name: string;
}

export interface DocumentItem {
  id: string;
  filename: string;
  kind: DocumentKind;
  status: DocumentStatus;
  reason_code: string | null;
  size_bytes: number;
  created_at: string;
  owner: DocumentOwner;
  shared_with_count: number | null;
  can_manage: boolean;
}

export interface DocumentDetail extends DocumentItem {
  chunk_count: number;
}

export interface DocumentUploadResponse {
  id: string;
  status: DocumentStatus;
  isDuplicate?: boolean;
}

export type GranteeType = 'user' | 'role' | 'department';

export interface DocumentShare {
  id: string;
  grantee_type: GranteeType;
  grantee_value: string;
  include_sensitive: boolean;
  created_at: string;
  granted_by: string;
}

export interface CreateSharePayload {
  grantee_type: GranteeType;
  value: string;
  include_sensitive?: boolean;
}

export interface SharingTargetUser {
  id: string;
  name: string;
  department: string;
}

export interface SharingTargets {
  users: SharingTargetUser[];
  roles: string[];
  departments: string[];
}

// ── Step 6 Admin Monitoring Types ───────────────────────────

export interface AuditTotals {
  asks: number;
  searches: number;
  refusals: number;
  refusal_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  uploads: number;
  active_users: number;
}

export interface AuditDailySeries {
  date: string;
  asks: number;
  searches: number;
  refusals: number;
  uploads: number;
}

export interface AuditTopUser {
  name: string;
  count: number;
}

export interface AuditSummary {
  days: number;
  totals: AuditTotals;
  per_day_series: AuditDailySeries[];
  counts_by_reason_code: Record<string, number>;
  top_users: AuditTopUser[];
}

export interface AdminQueryLog {
  time: string;
  user_name: string;
  event_type: string;
  refused: boolean | null;
  reason_code: string | null;
  latency_ms: number | null;
  chunk_count: number | null;
  admin_access: boolean;
  question_hash: string | null;
  question_length: number | null;
}

export interface AdminUploadItem {
  id: string;
  filename: string;
  kind: DocumentKind;
  status: DocumentStatus;
  size_bytes: number;
  owner: DocumentOwner;
  shared_with_count: number;
  deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface HistoryItem {
  id: string;
  question: string;
  created_at: string;
  outcome: 'answered' | 'refused';
  source_count: number;
  user_name?: string | null;
  department?: string | null;
}

export interface HistoryResponse {
  items: HistoryItem[];
  total: number;
}

