// Klien API terpusat — JWT di localStorage, tipe selaras model Pydantic backend.

const BASE = "/api/v1";
const TOKEN_KEY = "zandar_token";

export const auth = {
  get token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  },
  set(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      ...(opts.headers || {}),
      ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
    },
  });
  if (res.status === 401) {
    auth.clear();
    throw new ApiError(401, "Sesi berakhir");
  }
  if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  return res.status === 204 ? (null as T) : ((await res.json()) as T);
}

// ---- tipe ----
export interface User { id: string; email: string; name: string; role: string; }
export interface Investigation {
  id: string; title: string; description: string | null; status: string;
  priority: string; progress: number; data_policy: string;
  budget_cap_usd: number | null; created_at: string;
}
export interface Comment {
  id: string; investigation_id: string; platform: string; author_hash: string;
  content: string; lang: string | null; url: string | null; published_at: string | null;
}
export interface CommentStats {
  total: number; by_platform: Record<string, number>; by_lang: Record<string, number>;
}
export interface Collection {
  id: string; investigation_id: string; source_id: string;
  query: Record<string, unknown>; schedule_cron: string | null; last_run_at: string | null;
}
export interface Run {
  id: string; status: string; items_collected: number; error: string | null;
  started_at: string | null; finished_at: string | null;
}
export interface AdapterInfo {
  platform: string; tier: string; requires_credentials: boolean;
  rate_note: string; cost_note: string; legal_note: string;
}

// ---- endpoint ----
export const api = {
  async login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw new ApiError(res.status, "Email atau password salah");
    const j = (await res.json()) as { access_token: string };
    auth.set(j.access_token);
  },
  me: () => req<User>("/auth/me"),
  investigations: () => req<Investigation[]>("/investigations"),
  commentStats: (inv: string) => req<CommentStats>(`/comments/stats?investigation_id=${inv}`),
  searchComments: (params: Record<string, string>) =>
    req<Comment[]>("/comments/search?" + new URLSearchParams(params).toString()),
  collections: (inv: string) => req<Collection[]>(`/collections?investigation_id=${inv}`),
  runs: (col: string) => req<Run[]>(`/collections/${col}/runs`),
  adapters: () => req<AdapterInfo[]>("/sources/adapters"),
};
