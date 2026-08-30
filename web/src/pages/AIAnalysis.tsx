import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api, type AnalysisStats, type Narrative } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, Tile } from "../components/ui";
import { Icon } from "../components/icons";

const SENT_COLOR: Record<string, string> = {
  pos: "var(--ok)", positive: "var(--ok)", neg: "var(--crit)", negative: "var(--crit)",
  neu: "var(--muted)", neutral: "var(--muted)", mixed: "var(--violet)", "?": "var(--line)",
};
const SENT_LABEL: Record<string, string> = { pos: "Positif", neg: "Negatif", neu: "Netral", mixed: "Campuran", "?": "?" };
const tip = { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)", boxShadow: "var(--sh-md)" };

function arr(d: Record<string, number> | undefined) {
  return Object.entries(d || {}).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
}

export function AIAnalysis({ headerSlot }: { headerSlot: (node: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [stats, setStats] = useState<AnalysisStats | null>(null);
  const [nars, setNars] = useState<Narrative[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try {
      const [s, n] = await Promise.all([api.analysisStats(selected), api.narratives(selected).catch(() => [])]);
      setStats(s); setNars(n);
    } catch { setStats(null); setNars([]); }
    finally { setLoading(false); }
  }
  async function run() {
    if (!selected || busy) return;
    setBusy(true); setNote("");
    try { await api.runAnalysis(selected); setNote("Klasifikasi diantrekan — klik Segarkan beberapa detik lagi."); }
    catch { setNote("Gagal memicu analisis."); }
    finally { setBusy(false); }
  }

  const sent = arr(stats?.sentiment);
  const emo = arr(stats?.emotion);
  const intent = arr(stats?.intent);
  const trend = (stats?.sentiment_trend || []).map((t) => ({ ...t, label: t.day.slice(5) }));
  const covered = stats ? Math.round(stats.coverage * 100) : 0;
  const empty = !loading && (!stats || stats.analyzed === 0);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14 }}>
        {note && <span style={{ fontSize: 12, color: "var(--accent-ink)", alignSelf: "center", marginRight: "auto" }}>{note}</span>}
        <Button variant="ghost" icon="refresh" onClick={load}>Segarkan</Button>
        <Button icon="spark" onClick={run} disabled={busy}>{busy ? "Menjalankan…" : "Jalankan Analisis"}</Button>
      </div>

      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Total komentar" value={stats ? stats.total.toLocaleString("id") : "–"} icon="comment" /></div>
        <div className="rise rise-2"><Tile label="Dianalisis" value={stats ? stats.analyzed.toLocaleString("id") : "–"} icon="analysis" sub={stats ? `${covered}% cakupan` : undefined} /></div>
        <div className="rise rise-3"><Tile label="Rerata sentimen" value={stats?.avg_sentiment != null ? stats.avg_sentiment.toFixed(2) : "–"} icon="spark" tone={stats && stats.avg_sentiment != null && stats.avg_sentiment < -0.1 ? "crit" : undefined} /></div>
        <div className="rise rise-4"><Tile label="Tersangka bot" value={stats ? stats.bot_suspect : "–"} icon="agents" tone={stats && stats.bot_suspect > 0 ? "warn" : undefined} /></div>
        <div className="rise rise-4"><Tile label="Narasi" value={nars.length || "–"} icon="graph" /></div>
      </div>

      {empty ? (
        <Empty icon="analysis">Belum ada hasil analisis untuk investigasi ini. Klik <b>Jalankan Analisis</b> untuk mengklasifikasi komentar.</Empty>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <ChartCard title="Distribusi Sentimen" icon="comment">
              {sent.length === 0 ? <Mini /> : (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ResponsiveContainer width="55%" height={190}>
                    <PieChart>
                      <Pie data={sent} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="var(--surface)" strokeWidth={2}>
                        {sent.map((s) => <Cell key={s.name} fill={SENT_COLOR[s.name] || "var(--muted)"} />)}
                      </Pie>
                      <Tooltip contentStyle={tip} formatter={(v: number, n: string) => [v, SENT_LABEL[n] || n]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <Legend items={sent.map((s) => ({ label: SENT_LABEL[s.name] || s.name, value: s.value, color: SENT_COLOR[s.name] || "var(--muted)" }))} />
                </div>
              )}
            </ChartCard>

            <ChartCard title="Rincian Emosi" icon="spark">
              {emo.length === 0 ? <Mini /> : (
                <ResponsiveContainer width="100%" height={190}>
                  <BarChart data={emo} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                    <XAxis dataKey="name" tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={0} angle={-18} textAnchor="end" height={44} />
                    <YAxis tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={tip} cursor={{ fill: "var(--surface-2)" }} />
                    <Bar dataKey="value" fill="var(--violet)" radius={[4, 4, 0, 0]} maxBarSize={34} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          <div className="grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <ChartCard title="Klasifikasi Intent" icon="analysis">
              {intent.length === 0 ? <Mini /> : (
                <ResponsiveContainer width="100%" height={Math.max(150, intent.length * 34)}>
                  <BarChart data={intent} layout="vertical" margin={{ top: 0, right: 16, left: 6, bottom: 0 }}>
                    <XAxis type="number" hide allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={92} tick={{ fill: "var(--ink-2)", fontSize: 11 }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={tip} cursor={{ fill: "var(--surface-2)" }} />
                    <Bar dataKey="value" fill="var(--accent)" radius={[0, 5, 5, 0]} maxBarSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title="Tren Sentimen Harian" icon="timeline">
              {trend.length === 0 ? <Mini msg="Tak ada data bertanggal." /> : (
                <ResponsiveContainer width="100%" height={190}>
                  <AreaChart data={trend} margin={{ top: 8, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gTrend" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.32} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} minTickGap={16} />
                    <YAxis domain={[-1, 1]} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={tip} formatter={(v: number) => [Number(v).toFixed(2), "rerata"]} />
                    <Area type="monotone" dataKey="avg" stroke="var(--accent)" strokeWidth={2} fill="url(#gTrend)" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          <NarrativesCard nars={nars} />
        </div>
      )}
    </div>
  );
}

function ChartCard({ title, icon, children }: { title: string; icon: "comment" | "spark" | "analysis" | "timeline" | "graph"; children: React.ReactNode }) {
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
          <span className="tnum" style={{ fontWeight: 700 }}>{Math.round((i.value / total) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function NarrativesCard({ nars }: { nars: Narrative[] }) {
  if (nars.length === 0) return null;
  const riskTone = (r: number | null) => (r == null ? "muted" : r >= 0.5 ? "crit" : r >= 0.35 ? "warn" : "ok") as "crit" | "warn" | "ok" | "muted";
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="graph" size={16} /></span>Narasi Teratas (Graph C)
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>{nars.length} narasi · skor risiko ABC+D</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {nars.slice(0, 8).map((n, i) => (
          <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: i < Math.min(8, nars.length) - 1 ? "1px solid var(--line-2)" : "none" }}>
            <span className="tnum" style={{ width: 20, fontSize: 12, color: "var(--faint)", fontWeight: 700 }}>{i + 1}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.label}</div>
              {n.summary && <div style={{ fontSize: 11.5, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.summary}</div>}
            </div>
            {n.assessment?.authenticity != null && (
              <span className="hide-sm tnum" title="Otentisitas (0 organik .. 1 terkoordinasi)" style={{ fontSize: 11, color: "var(--muted)" }}>
                koord {Math.round((n.assessment.authenticity || 0) * 100)}%
              </span>
            )}
            <span className="tnum" style={{ fontSize: 11, color: "var(--muted)" }}>{n.evidence_count} bukti</span>
            <Pill tone={riskTone(n.risk_score)} dot>risiko {n.risk_score != null ? n.risk_score.toFixed(2) : "–"}</Pill>
          </div>
        ))}
      </div>
    </Card>
  );
}

const Mini = ({ msg = "Tak ada data." }: { msg?: string }) => (
  <div style={{ height: 170, display: "grid", placeItems: "center", color: "var(--faint)", fontSize: 12.5 }}>{msg}</div>
);
