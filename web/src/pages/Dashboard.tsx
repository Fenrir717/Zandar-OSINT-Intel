import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type AgentRun, type Investigation } from "../lib/api";
import { Button, Card, Empty, Pill, ProgressBar, Spinner, Tile } from "../components/ui";
import { Icon, type IconName } from "../components/icons";

type Tone = "accent" | "ok" | "warn" | "crit" | "muted" | "info" | "violet";

const STATUS_ORDER = ["planning", "collecting", "analyzing", "verifying", "done"];
const STATUS_LABEL: Record<string, string> = {
  planning: "Perencanaan", collecting: "Pengumpulan", analyzing: "Analisis", verifying: "Verifikasi", done: "Selesai",
};
const STATUS_TONE: Record<string, Tone> = {
  planning: "muted", collecting: "info", analyzing: "warn", verifying: "violet", done: "ok",
};
const STATUS_COLOR: Record<string, string> = {
  planning: "var(--muted)", collecting: "var(--info)", analyzing: "var(--warn)", verifying: "var(--violet)", done: "var(--ok)",
};

const PRIORITY_LABEL: Record<string, string> = { low: "Rendah", medium: "Sedang", high: "Tinggi", critical: "Kritis" };
const PRIORITY_TONE: Record<string, Tone> = { low: "muted", medium: "info", high: "warn", critical: "crit" };

const RUN_STATUS_ORDER = ["queued", "running", "awaiting_approval", "done", "failed", "rejected"];
const RUN_TONE: Record<string, Tone> = {
  done: "ok", failed: "crit", rejected: "crit", running: "warn", queued: "warn", awaiting_approval: "accent",
};
const RUN_COLOR: Record<string, string> = {
  done: "var(--ok)", failed: "var(--crit)", rejected: "var(--crit)", running: "var(--warn)", queued: "var(--warn)", awaiting_approval: "var(--accent)",
};
const GRAPH_LABEL: Record<string, string> = { planner: "Graph A · Planner", analysis: "Graph C · Narasi" };

const tip = { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)", boxShadow: "var(--sh-md)" };

function countBy<T>(items: T[], key: (t: T) => string, order: string[]): { name: string; value: number }[] {
  const counts: Record<string, number> = {};
  items.forEach((it) => { const k = key(it); counts[k] = (counts[k] || 0) + 1; });
  const ordered = order.filter((k) => counts[k]).map((k) => ({ name: k, value: counts[k] }));
  const extra = Object.keys(counts).filter((k) => !order.includes(k)).map((k) => ({ name: k, value: counts[k] }));
  return ordered.concat(extra);
}

export function Dashboard({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const nav = useNavigate();
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => { headerSlot(null); }, []);
  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true); setError("");
    try {
      const [inv, runs] = await Promise.all([api.investigations(), api.agentRuns()]);
      setInvestigations(inv); setAgentRuns(runs);
    } catch {
      setError("Gagal memuat data dashboard.");
    } finally {
      setLoading(false);
    }
  }

  const activeCount = investigations.filter((i) => i.status !== "done").length;
  const totalTokens = agentRuns.reduce((s, r) => s + r.tokens_in + r.tokens_out, 0);
  const doneRuns = agentRuns.filter((r) => r.status === "done").length;

  const statusData = countBy(investigations, (i) => i.status, STATUS_ORDER);
  const runStatusData = countBy(agentRuns, (r) => r.status, RUN_STATUS_ORDER);

  const recentInvestigations = investigations.slice(0, 6);
  const recentRuns = [...agentRuns]
    .sort((a, b) => (b.started_at ? new Date(b.started_at).getTime() : 0) - (a.started_at ? new Date(a.started_at).getTime() : 0))
    .slice(0, 6);

  if (loading && investigations.length === 0 && agentRuns.length === 0) {
    return <div style={{ display: "grid", placeItems: "center", padding: "80px 0" }}><Spinner size={28} /></div>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14 }}>
        {error && <span style={{ fontSize: 12, color: "var(--crit-ink)", alignSelf: "center", marginRight: "auto" }}>{error}</span>}
        <Button icon="target" onClick={() => nav("/scan")}>Scan topik baru</Button>
        <Button variant="ghost" icon="refresh" onClick={load}>Segarkan</Button>
      </div>

      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Investigasi" value={investigations.length} icon="search" /></div>
        <div className="rise rise-2"><Tile label="Investigasi aktif" value={activeCount} icon="spark" /></div>
        <div className="rise rise-3"><Tile label="Agent run" value={agentRuns.length} icon="agents" /></div>
        <div className="rise rise-4"><Tile label="Token LLM" value={<span className="tnum">{totalTokens.toLocaleString("id")}</span>} icon="analysis" /></div>
        <div className="rise rise-4"><Tile label="Run selesai" value={doneRuns} icon="reports" /></div>
      </div>

      {investigations.length === 0 ? (
        <Empty icon="search">Belum ada investigasi. Buat investigasi baru untuk mulai mengumpulkan data.</Empty>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <ChartCard title="Investigasi per Status" icon="target">
              {statusData.length === 0 ? <Mini /> : (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ResponsiveContainer width="55%" height={190}>
                    <PieChart>
                      <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="var(--surface)" strokeWidth={2}>
                        {statusData.map((s) => <Cell key={s.name} fill={STATUS_COLOR[s.name] || "var(--muted)"} />)}
                      </Pie>
                      <Tooltip contentStyle={tip} formatter={(v: number, n: string) => [v, STATUS_LABEL[n] || n]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <Legend items={statusData.map((s) => ({ label: STATUS_LABEL[s.name] || s.name, value: s.value, color: STATUS_COLOR[s.name] || "var(--muted)" }))} />
                </div>
              )}
            </ChartCard>

            <ChartCard title="Aktivitas Agen" icon="agents">
              {runStatusData.length === 0 ? <Mini /> : (
                <ResponsiveContainer width="100%" height={190}>
                  <BarChart data={runStatusData} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                    <XAxis dataKey="name" tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={0} angle={-18} textAnchor="end" height={44} />
                    <YAxis tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={tip} cursor={{ fill: "var(--surface-2)" }} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={34}>
                      {runStatusData.map((s) => <Cell key={s.name} fill={RUN_COLOR[s.name] || "var(--muted)"} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          <div className="grid-split" style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, alignItems: "start" }}>
            <RecentInvestigations items={recentInvestigations} />
            <RecentRuns items={recentRuns} />
          </div>
        </div>
      )}
    </div>
  );
}

function ChartCard({ title, icon, children }: { title: string; icon: IconName; children: React.ReactNode }) {
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name={icon} size={16} /></span>{title}
      </div>
      {children}
    </Card>
  );
}

function Legend({ items }: { items: { label: string; value: number; color: string }[] }) {
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
      {items.map((i) => (
        <div key={i.label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
          <span style={{ width: 9, height: 9, borderRadius: 3, background: i.color, flexShrink: 0 }} />
          <span style={{ flex: 1, color: "var(--ink-2)" }}>{i.label}</span>
          <span className="tnum" style={{ fontWeight: 700 }}>{i.value}</span>
          <span className="tnum" style={{ color: "var(--muted)", fontSize: 11 }}>{Math.round((i.value / total) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function RecentInvestigations({ items }: { items: Investigation[] }) {
  return (
    <Card className="rise rise-2" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="projects" size={16} /></span>Investigasi Terbaru
      </div>
      {items.length === 0 ? <Mini /> : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {items.map((inv, i) => (
            <div key={inv.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: i < items.length - 1 ? "1px solid var(--line-2)" : "none" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{inv.title}</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ flex: 1, maxWidth: 90 }}><ProgressBar value={inv.progress} tone={STATUS_TONE[inv.status]} /></span>
                  <span className="tnum">{Math.round(inv.progress)}%</span>
                </div>
              </div>
              <Pill tone={PRIORITY_TONE[inv.priority] ?? "muted"}>{PRIORITY_LABEL[inv.priority] ?? inv.priority}</Pill>
              <Pill tone={STATUS_TONE[inv.status] ?? "muted"} dot>{STATUS_LABEL[inv.status] ?? inv.status}</Pill>
              <span className="hide-sm" style={{ fontSize: 11, color: "var(--faint)", whiteSpace: "nowrap" }}>
                {new Date(inv.created_at).toLocaleDateString("id", { day: "2-digit", month: "short", year: "numeric" })}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function RecentRuns({ items }: { items: AgentRun[] }) {
  return (
    <Card className="rise rise-3" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="agents" size={16} /></span>Aktivitas Agen Terakhir
      </div>
      {items.length === 0 ? <Mini /> : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {items.map((r, i) => (
            <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 0", borderBottom: i < items.length - 1 ? "1px solid var(--line-2)" : "none" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {GRAPH_LABEL[r.graph_name] ?? r.graph_name}
                </div>
                <div style={{ fontSize: 11, color: "var(--faint)", marginTop: 2 }}>{fmt(r.started_at)}</div>
              </div>
              <span className="tnum" style={{ fontSize: 11, color: "var(--muted)" }}>{(r.tokens_in + r.tokens_out).toLocaleString("id")}</span>
              <Pill tone={RUN_TONE[r.status] ?? "muted"} dot>{r.status}</Pill>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

const fmt = (t: string | null) => (t ? new Date(t).toLocaleDateString("id", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "–");

const Mini = ({ msg = "Tak ada data." }: { msg?: string }) => (
  <div style={{ height: 170, display: "grid", placeItems: "center", color: "var(--faint)", fontSize: 12.5 }}>{msg}</div>
);
