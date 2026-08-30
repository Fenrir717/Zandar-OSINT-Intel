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
export interface Project {
  id: string; name: string; created_at: string | null; investigation_count: number;
}
export interface SystemService {
  name: string; kind: string; status: "connected" | "down" | "configured" | "not_configured"; detail: string;
}
export interface SystemUser {
  id: string; name: string; email: string; role: string; created_at: string | null;
}
export interface GraphNode { id: string; label: string; type: string; mentions: number; community: number; }
export interface GraphEdge { source: string; target: string; weight: number; }
export interface KnowledgeGraph {
  nodes: GraphNode[]; edges: GraphEdge[]; stats: { entities: number; relations: number };
}
export interface AgentRun {
  id: string; graph_name: string; status: string; tokens_in: number;
  tokens_out: number; cost_usd: number; started_at: string | null; ended_at: string | null;
}
export interface AgentEvent {
  type: string; id: string; investigation_id?: string; graph: string;
  status: string; node?: string; detail?: string;
  narratives?: number; tokens_in?: number; tokens_out?: number;
}
export interface NarrativeAssessment {
  actors: number | null; behavior: number | null; content: number | null;
  distribution: number | null; authenticity: number | null;
  veracity: number | null; quadrant: string | null; confidence: number | null;
}
export interface Narrative {
  id: string; label: string; summary: string | null; risk_score: number | null;
  risk_breakdown: Record<string, unknown> | null; evidence_count: number;
  first_seen: string | null; last_seen: string | null;
  assessment: NarrativeAssessment | null;
}
export interface Evidence {
  id: string; platform: string; author_hash: string; content: string;
  url: string | null; lang: string | null; published_at: string | null;
}
export interface AnalysisStats {
  total: number; analyzed: number; coverage: number;
  sentiment: Record<string, number>; emotion: Record<string, number>;
  intent: Record<string, number>; avg_sentiment: number | null;
  bot_suspect: number; sentiment_trend: { day: string; avg: number; count: number }[];
}
export interface ReportMeta {
  id: string; title: string; status: string; classification: string;
  created_at: string | null; generated_by_run: string | null;
}
export interface ReportCitation {
  n: number; url: string | null; platform: string | null;
  published_at: string | null; snippet: string | null;
}
export interface ReportDoc {
  title: string; sections: { heading: string; body: string }[];
  citations: ReportCitation[]; meta: Record<string, number>;
}
export interface ReportContent {
  id: string; title: string; status: string; classification: string;
  created_at: string | null; content: ReportDoc | null;
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
  createInvestigation: (body: {
    title: string; description?: string; priority?: string;
    data_policy?: string; budget_cap_usd?: number | null; project_id?: string;
  }) =>
    req<Investigation>("/investigations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  projects: () => req<Project[]>("/projects"),
  createProject: (name: string) =>
    req<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  createCollection: (body: {
    investigation_id: string; platform: string;
    query: Record<string, unknown>; schedule_cron?: string | null;
  }) =>
    req<Collection>("/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  runCollection: (col: string) =>
    req<Run>(`/collections/${col}/run`, { method: "POST" }),
  commentStats: (inv: string) => req<CommentStats>(`/comments/stats?investigation_id=${inv}`),
  searchComments: (params: Record<string, string>) =>
    req<Comment[]>("/comments/search?" + new URLSearchParams(params).toString()),
  collections: (inv: string) => req<Collection[]>(`/collections?investigation_id=${inv}`),
  runs: (col: string) => req<Run[]>(`/collections/${col}/runs`),
  adapters: () => req<AdapterInfo[]>("/sources/adapters"),
  agentRuns: (inv?: string) =>
    req<AgentRun[]>("/agent-runs" + (inv ? `?investigation_id=${inv}` : "")),
  buildNarratives: (inv: string, threshold = 0.86, minSize = 2) =>
    req<{ task_id: string; status: string }>(`/investigations/${inv}/narratives/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ threshold, min_size: minSize }),
    }),
  narratives: (inv: string) => req<Narrative[]>(`/investigations/${inv}/narratives`),
  narrativeEvidence: (narrativeId: string) => req<Evidence[]>(`/narratives/${narrativeId}/evidence`),
  analysisStats: (inv: string) => req<AnalysisStats>(`/analysis/${inv}/stats`),
  systemStatus: () => req<SystemService[]>("/system/status"),
  systemUsers: () => req<SystemUser[]>("/system/users"),
  graphData: (inv: string) => req<KnowledgeGraph>(`/investigations/${inv}/graph`),
  buildGraph: (inv: string) =>
    req<{ task_id: string; status: string }>(`/investigations/${inv}/graph/build`, { method: "POST" }),
  runAnalysis: (inv: string) =>
    req<{ task_id: string; status: string }>(`/analysis/${inv}/run`, { method: "POST" }),
  reports: (inv: string) => req<ReportMeta[]>(`/investigations/${inv}/reports`),
  report: (id: string) => req<ReportContent>(`/reports/${id}`),
  buildReport: (inv: string) =>
    req<{ report_id: string; cited_sources: number; sections: number }>(
      `/investigations/${inv}/reports/build`, { method: "POST" },
    ),
};

// SSE agent-run live — pakai fetch streaming (bukan EventSource) agar bisa kirim
// header Authorization; parse blok "data: {...}\n\n", lewati heartbeat ": ping".
export async function streamAgentEvents(
  onEvent: (e: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/agent-runs/stream`, {
    headers: { ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}) },
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, "Stream gagal");
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const part of parts) {
      const dataLine = part.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const payload = dataLine.slice(5).trim();
      if (!payload) continue;
      try {
        const e = JSON.parse(payload) as AgentEvent;
        if (e.type === "run") onEvent(e);
      } catch { /* abaikan baris tak valid */ }
    }
  }
}
