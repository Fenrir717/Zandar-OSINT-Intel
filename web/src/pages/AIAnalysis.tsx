import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api, type AnalysisStats, type AspectsResult, type EarlyWarning, type EntitySentiment, type Evidence, type Narrative, type ReputationSummary } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, Spinner, Tile } from "../components/ui";
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

function AspectCard({ asp }: { asp: AspectsResult }) {
  return (
    <Card style={{ padding: 18, marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>Sentimen per Aspek <span style={{ color: "var(--faint)", fontWeight: 400, fontSize: 12 }}>· ABSA</span></h3>
        <Pill tone="muted">{asp.with_aspect.toLocaleString("id")} komentar ber-aspek</Pill>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
        {asp.aspects.map((a) => {
          const c = a.count || 1;
          const tone = a.sentiment === "positif" ? "ok" : a.sentiment === "negatif" ? "crit" : "muted";
          return (
            <div key={a.aspect}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12.5, marginBottom: 4 }}>
                <b>{a.label}</b>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Pill tone={tone as "ok" | "crit" | "muted"}>{a.sentiment} · {a.net_sentiment > 0 ? "+" : ""}{a.net_sentiment}</Pill>
                  <span className="tnum" style={{ color: "var(--faint)", minWidth: 34, textAlign: "right" }}>{a.count.toLocaleString("id")}</span>
                </span>
              </div>
              <div style={{ display: "flex", height: 10, borderRadius: 5, overflow: "hidden", background: "var(--surface-2)" }} title={`positif ${a.pos} · netral ${a.neu} · negatif ${a.neg}`}>
                <span style={{ width: `${(a.pos / c) * 100}%`, background: "var(--ok)" }} />
                <span style={{ width: `${(a.neu / c) * 100}%`, background: "var(--line)" }} />
                <span style={{ width: `${(a.neg / c) * 100}%`, background: "var(--crit)" }} />
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 11, fontSize: 11, color: "var(--faint)" }}>
        Aspek dideteksi via leksikon (produk · harga · pelayanan · pengiriman · aplikasi); sentimen agregat per-aspek.
      </div>
    </Card>
  );
}

function EarlyWarningCard({ ew }: { ew: EarlyWarning }) {
  const cfg = {
    spike: { tone: "crit", label: "SPIKE — Potensi Krisis" },
    elevated: { tone: "warn", label: "ELEVATED — Pantau Ketat" },
    calm: { tone: "ok", label: "Normal" },
  }[ew.level];
  const color = `var(--${cfg.tone})`;
  return (
    <Card style={{ padding: 16, marginBottom: 16, borderLeft: `4px solid ${color}` }}>
      <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ minWidth: 200, flex: "1 1 200px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, boxShadow: `0 0 0 4px color-mix(in srgb, ${color} 22%, transparent)` }} />
            <b style={{ fontSize: 14, color }}>Peringatan Dini · {cfg.label}</b>
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 5 }}>{ew.reason}</div>
        </div>
        <div style={{ display: "flex", gap: 18 }}>
          {[["Negatif/jam", ew.current, color], ["Baseline", ew.baseline, "var(--ink)"], ["Rasio", `${ew.ratio}×`, color]].map(([k, v, c]) => (
            <div key={k as string}>
              <div style={{ fontSize: 10.5, color: "var(--faint)", textTransform: "uppercase", letterSpacing: ".05em" }}>{k}</div>
              <div className="tnum" style={{ fontSize: 20, fontWeight: 800, color: c as string }}>{v}</div>
            </div>
          ))}
        </div>
        <div style={{ flex: "1 1 160px", minWidth: 140, height: 46 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={ew.series} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <Area type="monotone" dataKey="neg" stroke={color} fill={color} fillOpacity={0.16} strokeWidth={1.6} />
              <Tooltip contentStyle={tip} formatter={(v: number) => [v, "negatif"]} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}

function ReputationCard({ rep }: { rep: ReputationSummary }) {
  const idx = rep.reputation_index ?? 0;
  const tone = idx >= 66 ? "ok" : idx >= 40 ? "warn" : "crit";
  const color = `var(--${tone})`;
  const label = idx >= 66 ? "Baik" : idx >= 40 ? "Sedang" : "Buruk";
  const maxStar = Math.max(1, ...Object.values(rep.star_distribution));
  const rated = Object.entries(rep.by_platform).filter(([, v]) => v.rated > 0);
  return (
    <Card style={{ padding: 18, marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ textAlign: "center", minWidth: 128 }}>
          <div style={{ fontSize: 10.5, color: "var(--muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".07em" }}>Indeks Reputasi</div>
          <div className="tnum" style={{ fontSize: 46, fontWeight: 800, color, lineHeight: 1.1, letterSpacing: "-.02em" }}>
            {idx.toFixed(0)}<span style={{ fontSize: 17, color: "var(--faint)", fontWeight: 700 }}>/100</span>
          </div>
          <Pill tone={tone}>{label}</Pill>
        </div>
        <div style={{ minWidth: 132 }}>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>Rerata bintang</div>
          <div className="tnum" style={{ fontSize: 26, fontWeight: 800, marginTop: 2 }}>
            {rep.avg_rating != null ? <>{rep.avg_rating.toFixed(1)} <span style={{ color: "var(--warn)" }}>★</span></> : "–"}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--faint)" }}>{rep.rated_count.toLocaleString("id")} review ber-rating</div>
        </div>
        <div style={{ flex: 1, minWidth: 190 }}>
          {[5, 4, 3, 2, 1].map((s) => {
            const c = rep.star_distribution[String(s)] || 0;
            return (
              <div key={s} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, margin: "2.5px 0" }}>
                <span style={{ width: 20, color: "var(--muted)" }}>{s}★</span>
                <div style={{ flex: 1, height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
                  <span style={{ display: "block", width: `${Math.round((c / maxStar) * 100)}%`, height: "100%", background: s >= 4 ? "var(--ok)" : s === 3 ? "var(--warn)" : "var(--crit)" }} />
                </div>
                <span className="tnum" style={{ width: 42, textAlign: "right", color: "var(--faint)" }}>{c.toLocaleString("id")}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ marginTop: 11, paddingTop: 10, borderTop: "1px solid var(--line)", fontSize: 11, color: "var(--faint)" }}>
        Dasar: {rep.index_basis}. Rating: {rated.length ? rated.map(([k, v]) => `${k} ${v.avg_rating?.toFixed(1)}★`).join(" · ") : "belum ada review — indeks dari sentimen teks"}.
      </div>
    </Card>
  );
}

export function AIAnalysis({ headerSlot }: { headerSlot: (node: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [stats, setStats] = useState<AnalysisStats | null>(null);
  const [rep, setRep] = useState<ReputationSummary | null>(null);
  const [ew, setEw] = useState<EarlyWarning | null>(null);
  const [asp, setAsp] = useState<AspectsResult | null>(null);
  const [nars, setNars] = useState<Narrative[]>([]);
  const [ents, setEnts] = useState<EntitySentiment[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try {
      const [s, n, e, rp, w, ap] = await Promise.all([
        api.analysisStats(selected),
        api.narratives(selected).catch(() => []),
        api.entities(selected).catch(() => []),
        api.reputation(selected).catch(() => null),
        api.earlyWarning(selected).catch(() => null),
        api.aspects(selected).catch(() => null),
      ]);
      setStats(s); setNars(n); setEnts(e); setRep(rp); setEw(w); setAsp(ap);
    } catch { setStats(null); setNars([]); setEnts([]); setRep(null); setEw(null); setAsp(null); }
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

      {ew && (ew.level !== "calm" || ew.total_negative > 0) && <EarlyWarningCard ew={ew} />}

      {rep && rep.total > 0 && rep.reputation_index != null && <ReputationCard rep={rep} />}

      {asp && asp.aspects.length > 0 && <AspectCard asp={asp} />}

      <div className="grid-stats-6" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Total komentar" value={stats ? stats.total.toLocaleString("id") : "–"} icon="comment" /></div>
        <div className="rise rise-2"><Tile label="Dianalisis" value={stats ? stats.analyzed.toLocaleString("id") : "–"} icon="analysis" sub={stats ? `${covered}% cakupan` : undefined} /></div>
        <div className="rise rise-3"><Tile label="Rerata sentimen" value={stats?.avg_sentiment != null ? stats.avg_sentiment.toFixed(2) : "–"} icon="spark" tone={stats && stats.avg_sentiment != null && stats.avg_sentiment < -0.1 ? "crit" : undefined} /></div>
        <div className="rise rise-4"><Tile label="Tersangka bot" value={stats ? stats.bot_suspect : "–"} icon="agents" tone={stats && stats.bot_suspect > 0 ? "warn" : undefined} /></div>
        <div className="rise rise-1"><Tile label="Keyakinan model" value={stats?.avg_confidence != null ? `${Math.round(stats.avg_confidence * 100)}%` : "–"} icon="analysis" sub={stats && stats.low_confidence ? `${stats.low_confidence} perlu tinjau` : undefined} /></div>
        <div className="rise rise-2"><Tile label="Sarkasme terkoreksi" value={stats ? stats.sarcasm : "–"} icon="spark" tone={stats && stats.sarcasm > 0 ? "warn" : undefined} /></div>
      </div>

      {empty ? (
        <Empty icon="analysis">Belum ada hasil analisis untuk investigasi ini. Klik <b>Jalankan Analisis</b> untuk mengklasifikasi komentar.</Empty>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {selected && <ChatPanel inv={selected} />}

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

          <TargetSentiment ents={ents} />

          <NarrativesCard nars={nars} />
        </div>
      )}
    </div>
  );
}

const ETYPE_LABEL: Record<string, string> = {
  person: "Tokoh", organization: "Institusi", location: "Lokasi", misc: "Lainnya",
};
const EMO_LABEL: Record<string, string> = {
  anger: "Marah", fear: "Takut", joy: "Senang", sadness: "Sedih",
  trust: "Percaya", surprise: "Terkejut", disgust: "Jijik", neutral: "Netral",
};
const scoreTone = (s: number | null) =>
  (s == null ? "muted" : s > 0.1 ? "ok" : s < -0.1 ? "crit" : "muted") as "ok" | "crit" | "muted";

function TargetSentiment({ ents }: { ents: EntitySentiment[] }) {
  if (ents.length === 0) return null;
  const withSent = ents.filter((e) => e.pos + e.neg + e.neu > 0);
  const shown = withSent.slice(0, 12);
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="target" size={16} /></span>Sentimen per Target
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>
          {shown.length ? `${shown.length} entitas · dari knowledge graph` : "perlu bangun graph"}
        </span>
      </div>
      {withSent.length === 0 ? (
        <div style={{ fontSize: 12.5, color: "var(--muted)", lineHeight: 1.55, padding: "6px 0" }}>
          Entitas belum bermuatan sentimen. Buka <b>Knowledge Graph</b> lalu <b>bangun ulang</b> graph
          (setelah analisis) agar sentimen tiap komentar tertaut ke target yang disebutnya.
        </div>
      ) : (
        <div className="scroll-x">
          <div style={{ minWidth: 560, display: "flex", flexDirection: "column" }}>
            {shown.map((e, i) => {
              const total = e.pos + e.neg + e.neu || 1;
              const pp = (e.pos / total) * 100, up = (e.neu / total) * 100, npr = (e.neg / total) * 100;
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: i < shown.length - 1 ? "1px solid var(--line-2)" : "none" }}>
                  <div style={{ flex: "1 1 190px", minWidth: 150, display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{e.name}</span>
                    <Pill tone="muted">{ETYPE_LABEL[e.type] || e.type}</Pill>
                  </div>
                  <div title={`${e.pos} positif · ${e.neu} netral · ${e.neg} negatif`}
                    style={{ display: "flex", width: 150, height: 9, borderRadius: 5, overflow: "hidden", background: "var(--surface-2)", flexShrink: 0 }}>
                    <span style={{ width: `${pp}%`, background: "var(--ok)" }} />
                    <span style={{ width: `${up}%`, background: "var(--line)" }} />
                    <span style={{ width: `${npr}%`, background: "var(--crit)" }} />
                  </div>
                  <span className="hide-sm" style={{ fontSize: 11, color: "var(--muted)", width: 62, textAlign: "right", flexShrink: 0 }}>{e.emotion ? EMO_LABEL[e.emotion] || e.emotion : "–"}</span>
                  <span className="tnum" style={{ fontSize: 11, color: "var(--faint)", width: 56, textAlign: "right", flexShrink: 0 }}>{e.mentions} sebut</span>
                  <Pill tone={scoreTone(e.sent_score)} dot>{e.sent_score != null ? e.sent_score.toFixed(2) : "–"}</Pill>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

const CHAT_SUGGESTIONS = [
  "Ringkas temuan utama & beri satu rekomendasi",
  "Entitas mana paling menonjol dan bagaimana sentimennya?",
  "Narasi apa yang paling berisiko?",
  "Emosi dominan publik terhadap topik ini apa?",
];

function ChatPanel({ inv }: { inv: string }) {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setInput("");
    const history = messages.slice(-6);
    setMessages((m) => [...m, { role: "user", content: question }]);
    setBusy(true);
    try {
      const { answer } = await api.chatInvestigation(inv, question, history);
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Maaf, gagal menjawab. Coba lagi." }]);
    } finally { setBusy(false); }
  }

  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="spark" size={16} /></span>Asisten AI
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>ngobrol dengan data investigasi</span>
      </div>

      {messages.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 360, overflowY: "auto", marginBottom: 12, paddingRight: 2 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "90%" }}>
              <div style={{
                fontSize: 12.5, lineHeight: 1.6, whiteSpace: "pre-wrap", padding: "9px 12px", borderRadius: 12,
                background: m.role === "user" ? "var(--accent-soft)" : "var(--surface-2)",
                color: m.role === "user" ? "var(--accent-ink)" : "var(--ink)",
                border: m.role === "assistant" ? "1px solid var(--line)" : "none",
              }}>{m.content}</div>
            </div>
          ))}
          {busy && <div style={{ alignSelf: "flex-start", fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 7, padding: "4px 2px" }}><Spinner size={13} /> Asisten sedang menganalisis data…</div>}
        </div>
      )}

      {messages.length === 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
          {CHAT_SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} disabled={busy} className="badge"
              style={{ cursor: "pointer", color: "var(--ink-2)", borderColor: "var(--line)", background: "var(--surface)" }}>{s}</button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); send(input); }} style={{ display: "flex", gap: 8 }}>
        <input className="input" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Tanya apa saja tentang investigasi ini…" disabled={busy} style={{ flex: 1 }} />
        <Button type="submit" icon="spark" disabled={busy || !input.trim()}>{busy ? "…" : "Kirim"}</Button>
      </form>
      <div style={{ fontSize: 10.5, color: "var(--faint)", marginTop: 8 }}>Jawaban AI berbasis data investigasi (statistik, narasi, entitas-sentimen) — bisa keliru, verifikasi untuk keputusan penting.</div>
    </Card>
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
  const [open, setOpen] = useState<string | null>(null);
  const [ev, setEv] = useState<Record<string, Evidence[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  if (nars.length === 0) return null;
  const riskTone = (r: number | null) => (r == null ? "muted" : r >= 0.5 ? "crit" : r >= 0.35 ? "warn" : "ok") as "crit" | "warn" | "ok" | "muted";

  async function toggle(id: string) {
    if (open === id) { setOpen(null); return; }
    setOpen(id);
    if (!ev[id]) {
      setBusy(id);
      try { const e = await api.narrativeEvidence(id); setEv((m) => ({ ...m, [id]: e })); }
      catch { setEv((m) => ({ ...m, [id]: [] })); }
      finally { setBusy(null); }
    }
  }

  const top = nars.slice(0, 8);
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="graph" size={16} /></span>Narasi Teratas (Graph C)
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>klik untuk lihat bukti + sumber</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {top.map((n, i) => (
          <div key={n.id} style={{ borderBottom: i < top.length - 1 ? "1px solid var(--line-2)" : "none" }}>
            <button onClick={() => toggle(n.id)} style={{ display: "flex", alignItems: "center", gap: 12, width: "100%", textAlign: "left", padding: "11px 0", background: "none", border: "none", cursor: "pointer", color: "var(--ink)" }}>
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
              <Icon name={open === n.id ? "chevronD" : "chevronR"} size={14} style={{ color: "var(--faint)" }} />
            </button>
            {open === n.id && (
              <div style={{ padding: "2px 0 14px 32px" }}>
                {busy === n.id ? <div style={{ fontSize: 12, color: "var(--muted)" }}>Memuat bukti…</div>
                  : (ev[n.id] || []).length === 0 ? <div style={{ fontSize: 12, color: "var(--muted)" }}>Tak ada bukti tertaut.</div>
                  : <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
                      {(ev[n.id] || []).slice(0, 6).map((c) => (
                        <div key={c.id} style={{ borderLeft: "2px solid var(--line)", paddingLeft: 11 }}>
                          <div style={{ fontSize: 10.5, color: "var(--faint)", marginBottom: 2, display: "flex", gap: 6 }}>
                            <span style={{ fontWeight: 600, color: "var(--muted)" }}>{c.platform}</span>
                            {c.published_at && <span>· {new Date(c.published_at).toLocaleDateString("id")}</span>}
                          </div>
                          <div style={{ fontSize: 12, lineHeight: 1.45 }}>{c.content.slice(0, 200)}{c.content.length > 200 ? "…" : ""}</div>
                          {c.url && <a href={c.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 4, marginTop: 4 }}>buka sumber ↗</a>}
                        </div>
                      ))}
                      {(ev[n.id] || []).length > 6 && <div style={{ fontSize: 11, color: "var(--faint)" }}>+{(ev[n.id] || []).length - 6} bukti lain</div>}
                    </div>}
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

const Mini = ({ msg = "Tak ada data." }: { msg?: string }) => (
  <div style={{ height: 170, display: "grid", placeItems: "center", color: "var(--faint)", fontSize: 12.5 }}>{msg}</div>
);
