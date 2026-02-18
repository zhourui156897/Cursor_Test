/**
 * HTTP client for communicating with the dierdanao backend.
 */

import { requestUrl, RequestUrlParam } from "obsidian";

export interface PluginSettings {
  apiUrl: string;
  token: string;
  username: string;
  password: string;
  syncOnStartup: boolean;
  syncIntervalMinutes: number;
}

export const DEFAULT_SETTINGS: PluginSettings = {
  apiUrl: "http://localhost:8000",
  token: "",
  username: "admin",
  password: "changeme",
  syncOnStartup: true,
  syncIntervalMinutes: 30,
};

let _settings: PluginSettings = { ...DEFAULT_SETTINGS };

export function setApiSettings(s: PluginSettings) {
  _settings = s;
}

async function ensureToken(): Promise<string> {
  if (_settings.token) return _settings.token;
  const resp = await api.post("/api/auth/login", {
    username: _settings.username,
    password: _settings.password,
  });
  _settings.token = resp.access_token;
  return _settings.token;
}

function baseUrl(): string {
  return _settings.apiUrl.replace(/\/+$/, "");
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = await ensureToken();
  const params: RequestUrlParam = {
    url: `${baseUrl()}${path}`,
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  };
  if (body !== undefined) {
    params.body = JSON.stringify(body);
  }
  const resp = await requestUrl(params);
  if (resp.status === 401) {
    _settings.token = "";
    const newToken = await ensureToken();
    params.headers = { ...params.headers, Authorization: `Bearer ${newToken}` };
    const retry = await requestUrl(params);
    return retry.json as T;
  }
  return resp.json as T;
}

export const api = {
  get: <T>(path: string) => req<T>("GET", path),
  post: <T>(path: string, body: unknown) => req<T>("POST", path, body),
  put: <T>(path: string, body: unknown) => req<T>("PUT", path, body),
  del: <T>(path: string) => req<T>("DELETE", path),
};

// ─── Typed API helpers ───

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

export interface SearchResult {
  entity_id: string;
  title: string | null;
  content: string | null;
  source: string | null;
  distance: number | null;
  match_type: string;
}

export interface ChatResponse {
  conversation_id: string;
  answer: string;
  sources: { index: number; entity_id: string; title: string; source: string }[];
  tool_calls?: Record<string, unknown>[];
}

export interface TagTree {
  id: string;
  name: string;
  parent_id: string | null;
  path: string;
  children: TagTree[];
}

export interface ContentTag {
  id: string;
  name: string;
  color: string | null;
  usage_count: number;
}

export const reviewApi = {
  listPending: (page = 1) => api.get<ReviewItem[]>(`/api/review/pending?page=${page}`),
  getCount: () => api.get<{ count: number }>("/api/review/count"),
  approve: (id: string, mods?: Record<string, unknown>) =>
    api.post(`/api/review/${id}/approve`, { modifications: mods || null }),
  reject: (id: string, reason = "") =>
    api.post(`/api/review/${id}/reject`, { reason }),
};

export const searchApi = {
  search: (q: string, topK = 10, mode = "hybrid") =>
    api.get<{ query: string; results: SearchResult[]; total: number }>(
      `/api/search?q=${encodeURIComponent(q)}&top_k=${topK}&mode=${mode}`
    ),
};

export const chatApi = {
  send: (message: string, convId?: string, mode = "rag") =>
    api.post<ChatResponse>("/api/chat/send", {
      message,
      conversation_id: convId,
      mode,
    }),
  listConversations: (limit = 50) =>
    api.get<{ id: string; title: string; created_at: string }[]>(
      `/api/chat/conversations?limit=${limit}`
    ),
  getMessages: (id: string) =>
    api.get<{ role: string; content: string; sources: unknown[] | null }[]>(
      `/api/chat/conversations/${id}/messages`
    ),
  createConversation: (title = "") =>
    api.post<{ id: string }>("/api/chat/conversations", { title }),
  deleteConversation: (id: string) => api.del(`/api/chat/conversations/${id}`),
};

export const tagApi = {
  listTree: () => api.get<TagTree[]>("/api/tags/tree"),
  listContent: () => api.get<ContentTag[]>("/api/tags/content"),
};

export const healthApi = {
  check: () => api.get<{ status: string; version: string }>("/health"),
};
