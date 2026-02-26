const BASE = '/api';

function getHeaders(): HeadersInit {
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...getHeaders(), ...options?.headers },
  });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: async <T>(path: string, formData: FormData): Promise<T> => {
    const headers: HeadersInit = {};
    const token = localStorage.getItem('token');
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: formData });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },
};

// Auth
export const authApi = {
  getMode: () => api.get<{ auth_mode: string }>('/auth/mode'),
  login: (username: string, password: string) =>
    api.post<{ access_token: string }>('/auth/login', { username, password }),
  me: () => api.get<User>('/auth/me'),
  listUsers: () => api.get<User[]>('/auth/users'),
  createUser: (data: { username: string; password: string; display_name?: string; role?: string }) =>
    api.post<User>('/auth/users', data),
  updateUser: (id: string, data: { display_name?: string; role?: string; is_active?: boolean }) =>
    api.put<User>(`/auth/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/auth/users/${id}`),
};

// Tags
export const tagApi = {
  listTree: () => api.get<TagTree[]>('/tags/tree'),
  createTree: (data: { name: string; parent_id?: string; icon?: string }) =>
    api.post<TagTree>('/tags/tree', data),
  updateTree: (id: string, data: { name?: string; parent_id?: string; icon?: string }) =>
    api.put<TagTree>(`/tags/tree/${id}`, data),
  deleteTree: (id: string) => api.delete(`/tags/tree/${id}`),
  listContent: () => api.get<ContentTag[]>('/tags/content'),
  createContent: (data: { name: string; color?: string }) => api.post<ContentTag>('/tags/content', data),
  updateContent: (id: string, data: { name?: string; color?: string }) =>
    api.put<ContentTag>(`/tags/content/${id}`, data),
  deleteContent: (id: string) => api.delete(`/tags/content/${id}`),
  listStatus: () => api.get<StatusDimension[]>('/tags/status'),
  createStatus: (data: { key: string; display_name?: string; options: string[]; default_value?: string }) =>
    api.post<StatusDimension>('/tags/status', data),
  deleteStatus: (id: string) => api.delete(`/tags/status/${id}`),
};

// Entities
export const entityApi = {
  list: (params?: { page?: number; source?: string }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set('page', String(params.page));
    if (params?.source) q.set('source', params.source);
    return api.get<Entity[]>(`/entities?${q}`);
  },
  get: (id: string) => api.get<Entity>(`/entities/${id}`),
  create: (data: { title: string; content?: string; source?: string }) => api.post<Entity>('/entities', data),
  update: (id: string, data: { title?: string; content?: string }) => api.put<Entity>(`/entities/${id}`, data),
  delete: (id: string) => api.delete(`/entities/${id}`),
  versions: (id: string) => api.get<EntityVersion[]>(`/entities/${id}/versions`),
};

// Review Queue
export const reviewApi = {
  list: (status = 'all', page = 1) =>
    api.get<ReviewListResponse>(`/review/list?status=${status}&page=${page}`),
  listPending: (page = 1) => api.get<ReviewItem[]>(`/review/pending?page=${page}`),
  getCount: () => api.get<{ count: number }>('/review/count'),
  getStats: () => api.get<ReviewStats>('/review/stats'),
  approve: (id: string, modifications?: Record<string, unknown>) =>
    api.post(`/review/${id}/approve`, { modifications: modifications || null }),
  reject: (id: string, reason = '') => api.post(`/review/${id}/reject`, { reason }),
  manualTag: (id: string, tags: { folder_tags: string[]; content_tags: string[]; status: Record<string, string> }) =>
    api.post(`/review/${id}/manual-tag`, tags),
  batchApprove: (ids: string[]) => api.post('/review/batch-approve', { review_ids: ids }),
};

// Sync
export interface SyncTriggerOptions {
  limit?: number;
  order?: 'newest' | 'oldest';
  folder_whitelist?: string[];
  days_back?: number;
  days_forward?: number;
  list_names?: string[];
  due_after?: string;
  due_before?: string;
}

export const syncApi = {
  getStatus: () => api.get<SyncStatus>('/sync/status'),
  getNoteFolders: () => api.get<{ folders: string[] }>('/sync/apple/note-folders'),
  getReminderLists: () => api.get<{ lists: string[] }>('/sync/apple/reminder-lists'),
  trigger: (source: string, limit = 20, order = 'newest', options: SyncTriggerOptions = {}) => {
    const p = new URLSearchParams({ limit: String(limit), order });
    if (options.folder_whitelist?.length) p.set('folder_whitelist', options.folder_whitelist.join(','));
    if (options.days_back != null) p.set('days_back', String(options.days_back));
    if (options.days_forward != null) p.set('days_forward', String(options.days_forward));
    if (options.list_names?.length) p.set('list_names', options.list_names.join(','));
    if (options.due_after) p.set('due_after', options.due_after);
    if (options.due_before) p.set('due_before', options.due_before);
    return api.post<SyncResult>(`/sync/trigger/${source}?${p}`, {});
  },
  triggerAll: (limit = 20, order = 'newest') =>
    api.post<{ results: Record<string, unknown> }>(`/sync/trigger-all?limit=${limit}&order=${order}`, {}),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.upload<{ id: string; status: string; title: string }>('/sync/upload', fd);
  },
  createNote: (data: { title: string; body?: string; folder?: string }) =>
    api.post('/sync/create/note', data),
  createReminder: (data: { title: string; body?: string; list_name?: string; due_date?: string; priority?: number }) =>
    api.post('/sync/create/reminder', data),
  createEvent: (data: { title: string; start_date: string; end_date: string; description?: string; location?: string; calendar?: string; all_day?: boolean }) =>
    api.post('/sync/create/event', data),
  updateConfig: (config: Record<string, unknown>) => api.put('/sync/config', config),
};

// Search
export const searchApi = {
  search: (q: string, topK = 10, source?: string, mode = 'hybrid') => {
    const p = new URLSearchParams({ q, top_k: String(topK), mode });
    if (source) p.set('source', source);
    return api.get<SearchResponse>(`/search?${p}`);
  },
};

// Graph
export const graphApi = {
  stats: () => api.get<GraphStats>('/graph/stats'),
  entityGraph: (id: string, depth = 1) => api.get<GraphData>(`/graph/entity/${id}?depth=${depth}`),
  overview: (limit = 100) => api.get<GraphData>(`/graph/overview?limit=${limit}`),
};

// Chat
export const chatApi = {
  send: (message: string, conversationId?: string, mode: string = 'rag') =>
    api.post<ChatResponse>('/chat/send', { message, conversation_id: conversationId, mode }),
  sendStream: (message: string, conversationId?: string, mode: string = 'rag') =>
    fetch(`${BASE}/chat/send/stream`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ message, conversation_id: conversationId, stream: true, mode }),
    }),
  listConversations: (limit = 50) => api.get<Conversation[]>(`/chat/conversations?limit=${limit}`),
  getMessages: (id: string) => api.get<ChatMessage[]>(`/chat/conversations/${id}/messages`),
  createConversation: (title = '') => api.post<{ id: string }>('/chat/conversations', { title }),
  deleteConversation: (id: string) => api.delete(`/chat/conversations/${id}`),
};

// History
export const historyApi = {
  versions: (entityId: string) => api.get<EntityVersion[]>(`/history/${entityId}/versions`),
  version: (entityId: string, vnum: number) => api.get<EntityVersion>(`/history/${entityId}/versions/${vnum}`),
  diff: (entityId: string, a: number, b: number) =>
    api.get<VersionDiff>(`/history/${entityId}/diff?a=${a}&b=${b}`),
  timeline: (entityId: string) => api.get<TimelineItem[]>(`/history/${entityId}/timeline`),
};

// Version
export const versionApi = {
  get: () => api.get<VersionInfo>('/version'),
  check: () => api.get<UpdateCheck>('/version/check'),
};

// Version
export const versionApi = {
  getVersion: () => api.get<VersionInfo>('/version'),
  checkUpdate: () => api.get<UpdateCheck>('/version/check'),
};

// Settings
export const settingsApi = {
  getLLM: () => api.get<LLMConfigResponse>('/settings/llm'),
  updateLLM: (data: LLMConfigUpdate) => api.put<{ message: string }>('/settings/llm', data),
  getPaths: () => api.get<PathsConfigResponse>('/settings/paths'),
  updatePaths: (data: PathsConfigUpdate) => api.put<{ message: string }>('/settings/paths', data),
  getSystemInfo: () => api.get<SystemInfo>('/settings/system-info'),
};

// Types
export interface LLMConfigResponse {
  api_url: string;
  api_key_masked: string;
  has_api_key: boolean;
  model: string;
  embedding_model: string;
  embedding_dim: number;
  status: 'connected' | 'disconnected';
}
export interface LLMConfigUpdate {
  api_url?: string;
  api_key?: string;
  model?: string;
  embedding_model?: string;
  embedding_dim?: number;
}
export interface PathsConfigResponse {
  obsidian_vault_path: string;
  data_dir: string;
  resolved_vault_path: string;
  resolved_data_dir: string;
}
export interface PathsConfigUpdate {
  obsidian_vault_path?: string;
  data_dir?: string;
}
export interface SystemInfo {
  version: string;
  phase: string;
  auth_mode: string;
  vector_db_mode: string;
  services: {
    llm: { status: string; url: string };
    milvus: Record<string, unknown>;
    neo4j: Record<string, unknown>;
  };
  data: {
    entities: number;
    pending_reviews: number;
    conversations: number;
    milvus_vectors: number;
    neo4j_nodes: number;
  };
}

export interface VersionInfo { version: string }
export interface UpdateCheck { local: string; remote: string; has_update: boolean; error: string | null }

export interface VersionInfo {
  version: string;
}
export interface UpdateCheck {
  local: string;
  remote: string;
  has_update: boolean;
  error: string | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  message?: string;
}
export interface SearchResult {
  entity_id: string;
  title: string | null;
  content: string | null;
  source: string | null;
  obsidian_path: string | null;
  distance: number | null;
  match_type: string;
}
export interface GraphStats { available: boolean; node_count: number; relationship_count: number; error?: string }
export interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }
export interface GraphNode { id: string; title: string; source: string; labels: string[] }
export interface GraphEdge { source: string; target: string; type: string }
export interface ChatResponse { conversation_id: string; answer: string; sources: ChatSource[]; tool_calls?: Record<string, unknown>[] }
export interface ChatSource { index: number; entity_id: string; title: string; source: string }
export interface Conversation { id: string; title: string; created_at: string; updated_at: string; summary: string | null }
export interface ChatMessage { id: string; role: string; content: string; sources: ChatSource[] | null; created_at: string }
export interface VersionDiff { entity_id: string; version_a: EntityVersion; version_b: EntityVersion; title_changed: boolean; content_changed: boolean }
export interface TimelineItem { id: string; dimension: string; old_value: string | null; new_value: string | null; changed_by: string | null; changed_at: string; note: string | null }

export interface ReviewItem {
  id: string;
  entity_id: string;
  entity_title: string | null;
  entity_source: string | null;
  entity_content: string | null;
  suggested_folder_tags: string[] | null;
  suggested_content_tags: string[] | null;
  suggested_status: Record<string, string> | null;
  confidence_scores: Record<string, unknown> | null;
  reviewer_action: Record<string, unknown> | null;
  status: string;
  created_at: string | null;
  reviewed_at: string | null;
}

export interface ReviewListResponse {
  items: ReviewItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReviewStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  modified: number;
}

export interface SyncStatus {
  config: {
    enabled: boolean;
    auto_sync: boolean;
    interval_minutes: number;
    sources: Record<string, boolean>;
  };
  status: Record<string, { running: boolean; last_run: string | null; last_result: unknown }>;
}

export interface SyncResult {
  message: string;
  results: { total: number; created: number; updated: number; skipped: number };
}

export interface User {
  id: string;
  username: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TagTree {
  id: string;
  name: string;
  parent_id: string | null;
  path: string;
  icon: string | null;
  sort_order: number;
  children: TagTree[];
}

export interface ContentTag {
  id: string;
  name: string;
  color: string | null;
  usage_count: number;
}

export interface StatusDimension {
  id: string;
  key: string;
  display_name: string | null;
  options: string[];
  default_value: string | null;
}

export interface Entity {
  id: string;
  source: string;
  title: string | null;
  content: string | null;
  content_type: string;
  current_version: number;
  review_status: string;
  created_at: string;
  updated_at: string;
}

export interface EntityVersion {
  id: string;
  entity_id: string;
  version_number: number;
  title: string | null;
  content: string | null;
  change_source: string | null;
  change_summary: string | null;
  created_at: string;
}
