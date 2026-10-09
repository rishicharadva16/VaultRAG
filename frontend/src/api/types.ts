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

export interface HealthResponse {
  postgres: { status: string; detail?: string };
  qdrant: { status: string };
  llm: { status: string };
}

export interface DemoUser {
  externalId: string;
  name: string;
  email: string;
  role: Role;
  label: string;
}
