import { useEffect, useState } from "react";
import { api, type Comment, type CommentStats } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Card, Empty, Pill, Tile } from "../components/ui";

export function CommentExplorer({ headerSlot }: { headerSlot: (node: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [tab, setTab] = useState<"comments" | "runs">("comments");
  const [stats, setStats] = useState<CommentStats | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [platform, setPlatform] = useState("");
  const [lang, setLang] = useState("");

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) { loadStats(); loadComments(); } }, [selected]);

  async function loadStats() {
    if (!selected) return;
    try { setStats(await api.commentStats(selected)); } catch { /* ignore */ }
  }
  async function loadComments() {
    if (!selected) return;
    setLoading(true);
    const params: Record<string, string> = { investigation_id: selected, limit: "100" };
    if (q) params.q = q;
    if (platform) params.platform = platform;
    if (lang) params.lang = lang;
    try { setComments(await api.searchComments(params)); }
    catch { setComments([]); }
    finally { setLoading(false); }
  }

  const platforms = stats ? Object.keys(stats.by_platform) : [];
  const langs = stats ? Object.keys(stats.by_lang) : [];

  return (
    <div>
      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Total komentar" value={stats ? stats.total.toLocaleString("id") : "–"} icon="comment" /></div>
        <div className="rise rise-2"><Tile label="Platform" value={platforms.length || "–"} icon="collections" /></div>
        <div className="rise rise-3"><Tile label="Bahasa terdeteksi" value={langs.length || "–"} icon="analysis" /></div>
        <div className="rise rise-4"><Tile label="Hasil terfilter" value={loading ? "…" : comments.length} icon="filter" /></div>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        {(["comments", "runs"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            fontSize: 13, padding: "7px 14px", borderRadius: 999, border: "1px solid",
            borderColor: tab === t ? "var(--accent)" : "var(--line)",
            background: tab === t ? "var(--accent-soft)" : "var(--surface)",
            color: tab === t ? "var(--accent-ink)" : "var(--muted)", fontWeight: tab === t ? 600 : 400,
          }}>{t === "comments" ? "Komentar" : "Riwayat Koleksi"}</button>
        ))}
      </div>

      {tab === "comments" ? (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && loadComments()}
              placeholder="Cari isi komentar…" className="input" style={{ flex: 1, minWidth: 200 }} />
            <select value={platform} onChange={(e) => { setPlatform(e.target.value); }} className="select" style={{ width: "auto" }}>
              <option value="">Semua platform</option>
              {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="select" style={{ width: "auto" }}>
              <option value="">Semua bahasa</option>
              {langs.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
            <button onClick={loadComments} className="btn btn-primary">Cari</button>
          </div>
          {loading ? <Empty>Memuat…</Empty>
            : comments.length === 0 ? <Empty>Tidak ada komentar cocok. Jalankan koleksi dulu, atau longgarkan filter.</Empty>
            : <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>{comments.map((c) => <CommentCard key={c.id} c={c} />)}</div>}
        </>
      ) : <RunsView inv={selected} />}
    </div>
  );
}

// Label intensitas dari |sentiment_score| (Tier 1): Sangat/Agak/Sedikit + arah.
function intensityLabel(c: Comment): { label: string; tone: "ok" | "crit" | "muted" | "violet" } | null {
  if (c.sentiment === "neu") return { label: "Netral", tone: "muted" };
  if (!c.sentiment || c.sentiment_score == null) return null;
  const mag = Math.abs(c.sentiment_score);
  const strength = mag >= 0.5 ? "Sangat" : mag >= 0.25 ? "Agak" : "Sedikit";
  if (c.sentiment === "pos") return { label: `${strength} Positif`, tone: "ok" };
  if (c.sentiment === "neg") return { label: `${strength} Negatif`, tone: "crit" };
  return { label: "Campuran", tone: "violet" };
}

function CommentCard({ c }: { c: Comment }) {
  const when = c.published_at ? new Date(c.published_at).toLocaleDateString("id") : "";
  const it = intensityLabel(c);
  return (
    <Card hover style={{ padding: "13px 15px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7, flexWrap: "wrap" }}>
        <span style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--surface-2)", display: "grid", placeItems: "center", fontSize: 10, fontWeight: 700, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
          {(c.author_hash || "?").slice(0, 2)}
        </span>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink)", fontWeight: 600 }}>{(c.author_hash || "").slice(0, 12)}…</span>{" "}
          <span style={{ opacity: .7 }}>(pseudonim)</span><br />{c.platform} · {when}
        </div>
        <div style={{ flex: 1 }} />
        {it && <Pill tone={it.tone} dot>{it.label}</Pill>}
        {c.is_sarcasm && <Pill tone="warn">sarkasme</Pill>}
        {c.lang && <Pill tone={c.lang === "id" ? "accent" : "muted"}>{c.lang}</Pill>}
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.5 }}>{c.content}</div>
      {c.url && <div style={{ marginTop: 7, fontSize: 11 }}><a href={c.url} target="_blank" rel="noopener noreferrer">sumber ↗</a></div>}
    </Card>
  );
}

function RunsView({ inv }: { inv: string }) {
  const [rows, setRows] = useState<{ query: string; cron: string | null; runs: import("../lib/api").Run[] }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const cols = await api.collections(inv);
        const out = await Promise.all(cols.map(async (col) => ({
          query: JSON.stringify(col.query).slice(0, 70),
          cron: col.schedule_cron,
          runs: await api.runs(col.id),
        })));
        if (alive) setRows(out);
      } catch { if (alive) setRows([]); }
      finally { if (alive) setLoading(false); }
    })();
    return () => { alive = false; };
  }, [inv]);

  if (loading) return <Empty>Memuat…</Empty>;
  if (rows.length === 0) return <Empty>Belum ada koleksi untuk investigasi ini.</Empty>;

  const stColor: Record<string, string> = { done: "var(--ok)", failed: "var(--crit)", running: "var(--warn)", queued: "var(--warn)" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {rows.map((r, i) => (
        <Card key={i} style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "13px 15px", borderBottom: "1px solid var(--line)" }}>
            <b>Koleksi</b><Pill>{r.query}…</Pill><div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>cron: {r.cron || "manual"}</span>
          </div>
          <div className="scroll-x">
            <table className="tbl">
              <thead><tr><th>Status</th><th>Item</th><th>Mulai</th><th>Selesai</th><th>Error</th></tr></thead>
              <tbody>
                {r.runs.length === 0 ? <tr><td style={{ color: "var(--muted)" }} colSpan={5}>belum ada run</td></tr>
                  : r.runs.map((run) => (
                    <tr key={run.id}>
                      <td style={{ color: stColor[run.status] || "var(--ink)", fontWeight: 600 }}>{run.status}</td>
                      <td className="tnum">{run.items_collected}</td>
                      <td style={{ color: "var(--muted)" }}>{fmt(run.started_at)}</td><td style={{ color: "var(--muted)" }}>{fmt(run.finished_at)}</td>
                      <td style={{ color: "var(--crit)" }}>{run.error || ""}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </div>
  );
}

const fmt = (t: string | null) => (t ? new Date(t).toLocaleString("id") : "–");
