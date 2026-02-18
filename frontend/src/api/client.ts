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
  listPending: (page = 1) => api.get<ReviewItem[]>(`/review/pending?page=${page}`),
  getCount: () => api.get<{ count: number }>('/review/count'),
  approve: (id: string, modifications?: Record<string, unknown>) =>
    api.post(`/review/${id}/approve`, { modifications: modifications || null }),
  reject: (id: string, reason = '') => api.post(`/review/${id}/reject`, { reason }),
  batchApprove: (ids: string[]) => api.post('/review/batch-approve', { review_ids: ids }),
};

// Sync
export const syncApi = {
  getStatus: () => api.get<SyncStatus>('/sync/status'),
  trigger: (source: string) => api.post<SyncResult>(`/sync/trigger/${source}`, {}),
  triggerAll: () => api.post<{ results: Record<string, unknown> }>('/sync/trigger-all', {}),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return api.upload<{ id: string; status: string; title: string }>('/sync/upload', fd);
  },
  updateConfig: (config: Record<string, unknown>) => api.put('/sync/config', config),
};

// Types
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
  status: string;
  created_at: string | null;
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
