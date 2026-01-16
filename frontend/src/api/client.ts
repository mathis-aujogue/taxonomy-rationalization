/** API client for taxonomy matching backend. */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface ColumnMapping {
  l1?: string | null;
  l2?: string | null;
  l3: string;
  definition?: string | null;
}

export interface JobInfo {
  id: number;
  target_id: string;
  filename: string;
  status: string;
  column_mapping: ColumnMapping;
  created_at: string;
  updated_at: string;
  error_message?: string | null;
}

export interface CandidateMatch {
  l1: string;
  l2: string;
  l3: string;
  score: number;
  definition?: string;
}

export interface MatchResult {
  target_l1: string;
  target_l2: string;
  target_l3: string;
  matched_l1: string;
  matched_l2: string;
  matched_l3: string;
  confidence: number;
  reasoning?: string;
  top_3_candidates: CandidateMatch[];
  status: string;
}

export interface MatchResponse {
  results: MatchResult[];
  total: number;
  matched: number;
  unmatched: number;
  average_confidence: number;
}

export interface TaxonomyNode {
  l1?: string | null;
  l2?: string | null;
  l3: string;
  definition?: string | null;
  children: TaxonomyNode[];
}

// API functions
export const uploadTaxonomy = async (
  file: File,
  targetId: string,
  columnMapping: ColumnMapping
) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('target_id', targetId);
  if (columnMapping.l1) formData.append('l1_column', columnMapping.l1);
  if (columnMapping.l2) formData.append('l2_column', columnMapping.l2);
  formData.append('l3_column', columnMapping.l3);
  if (columnMapping.definition) formData.append('definition_column', columnMapping.definition);

  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const ingestTaxonomy = async (targetId: string, clearExisting: boolean = false) => {
  const response = await api.post('/ingest', {
    target_id: targetId,
    clear_existing: clearExisting,
  });
  return response.data;
};

export const augmentTaxonomy = async (
  targetId: string,
  promptTemplate?: string,
  llmModel?: string
) => {
  const response = await api.post('/augment', {
    target_id: targetId,
    prompt_template: promptTemplate,
    llm_model: llmModel,
  });
  return response.data;
};

export const matchTaxonomy = async (
  ourTargetId: string,
  clientTargetId: string,
  threshold?: number,
  weights?: any,
  limit?: number
): Promise<MatchResponse> => {
  const response = await api.post('/match', {
    our_target_id: ourTargetId,
    client_target_id: clientTargetId,
    threshold,
    weights,
    limit,
  });
  return response.data;
};

export const getJobs = async (): Promise<{ jobs: JobInfo[] }> => {
  const response = await api.get('/jobs');
  return response.data;
};

export const getJob = async (targetId: string): Promise<JobInfo> => {
  const response = await api.get(`/jobs/${targetId}`);
  return response.data;
};

export const getOurTaxonomy = async (targetId: string): Promise<{
  target_id: string;
  nodes: TaxonomyNode[];
}> => {
  const response = await api.get(`/our-taxonomy/${targetId}`);
  return response.data;
};

export const exportTaxonomy = async (targetId: string, format: 'csv' | 'excel' = 'csv') => {
  const response = await api.post(
    '/export',
    { target_id: targetId, format },
    { responseType: 'blob' }
  );
  return response.data;
};

export interface VectorStatus {
  table_name: string;
  has_target_id_column: boolean;
  targets: Record<string, {
    total_records: number;
    num_categories: number;
    components: Record<string, number>;
    has_required_components: {
      l1: boolean;
      l2: boolean;
      l3: boolean;
      full: boolean;
      desc: boolean;
    };
    completeness_ratio: number;
    ready_for_hybrid_matching: boolean;
    original_indices: number[];
    total_indices: number;
  }>;
}

export const getVectorStatus = async (targetId?: string): Promise<VectorStatus> => {
  const params = targetId ? { target_id: targetId } : {};
  const response = await api.get('/vector-status', { params });
  return response.data;
};

export interface TargetIdInfo {
  target_id: string;
  ready_for_hybrid_matching: boolean;
  num_categories: number;
}

export interface TargetIdsResponse {
  target_ids: TargetIdInfo[];
}

export const getTargetIds = async (): Promise<TargetIdsResponse> => {
  const response = await api.get('/target-ids');
  return response.data;
};

export interface MatchSessionCreate {
  our_target_id: string;
  client_target_id: string;
  threshold?: number;
  results: MatchResult[];
}

export interface MatchSessionUpdate {
  validation_states: Record<string, string>;
}

export interface MatchSessionResponse {
  id: number;
  our_target_id: string;
  client_target_id: string;
  threshold?: number;
  results: MatchResult[];
  validation_states: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export const createMatchSession = async (data: MatchSessionCreate): Promise<MatchSessionResponse> => {
  const response = await api.post('/match-sessions', data);
  return response.data;
};

export const getMatchSession = async (sessionId: number): Promise<MatchSessionResponse> => {
  const response = await api.get(`/match-sessions/${sessionId}`);
  return response.data;
};

export const updateMatchSession = async (
  sessionId: number,
  data: MatchSessionUpdate
): Promise<MatchSessionResponse> => {
  const response = await api.patch(`/match-sessions/${sessionId}`, data);
  return response.data;
};

export const exportMatchSession = async (sessionId: number): Promise<Blob> => {
  const response = await api.get(`/match-sessions/${sessionId}/export`, {
    responseType: 'blob',
  });
  return response.data;
};
