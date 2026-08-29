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
  const select = { padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 6, background: "var(--surface)", color: "var(--ink)", fontSize: 13, fontFamily: "inherit" };

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
        <Tile label="Total komentar" value={stats ? stats.total.toLocaleString("id") : "–"} />
        <Tile label="Platform" value={platforms.length || "–"} />
        <Tile label="Bahasa terdeteksi" value={langs.length || "–"} />
        <Tile label="Hasil terfilter" value={loading ? "…" : comments.length} />
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
              placeholder="Cari isi komentar…" style={{ ...select, flex: 1, minWidth: 200 }} />
            <select value={platform} onChange={(e) => { setPlatform(e.target.value); }} style={select}>
              <option value="">Semua platform</option>
              {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={lang} onChange={(e) => setLang(e.target.value)} style={select}>
              <option value="">Semua bahasa</option>
              {langs.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
            <button onClick={loadComments} style={{ background: "var(--accent)", color: "#fff", border: "1px solid var(--accent-ink)", borderRadius: 6, padding: "8px 16px", fontWeight: 600, fontSize: 13 }}>Cari</button>
          </div>
          {loading ? <Empty>Memuat…</Empty>
            : comments.length === 0 ? <Empty>Tidak ada komentar cocok. Jalankan koleksi dulu, atau longgarkan filter.</Empty>
            : <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>{comments.map((c) => <CommentCard key={c.id} c={c} />)}</div>}
        </>
      ) : <RunsView inv={selected} />}
    </div>
  );
}

function CommentCard({ c }: { c: Comment }) {
  const when = c.published_at ? new Date(c.published_at).toLocaleDateString("id") : "";
  return (
    <Card style={{ padding: "13px 15px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 7 }}>
        <span style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--surface-2)", display: "grid", placeItems: "center", fontSize: 10, fontWeight: 700, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
          {(c.author_hash || "?").slice(0, 2)}
        </span>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink)", fontWeight: 600 }}>{(c.author_hash || "").slice(0, 12)}…</span>{" "}
          <span style={{ opacity: .7 }}>(pseudonim)</span><br />{c.platform} · {when}
        </div>
        <div style={{ flex: 1 }} />
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
  const th = { textAlign: "left" as const, fontSize: 10, textTransform: "uppercase" as const, letterSpacing: ".05em", color: "var(--muted)", padding: "9px 12px", background: "var(--surface-2)", borderBottom: "1px solid var(--line)" };
  const td = { padding: "9px 12px", borderBottom: "1px solid var(--line)", fontSize: 13 };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {rows.map((r, i) => (
        <Card key={i} style={{ padding: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <b>Koleksi</b><Pill>{r.query}…</Pill><div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>cron: {r.cron || "manual"}</span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>Status</th><th style={th}>Item</th><th style={th}>Mulai</th><th style={th}>Selesai</th><th style={th}>Error</th></tr></thead>
              <tbody>
                {r.runs.length === 0 ? <tr><td style={{ ...td, color: "var(--muted)" }} colSpan={5}>belum ada run</td></tr>
                  : r.runs.map((run) => (
                    <tr key={run.id}>
                      <td style={{ ...td, color: stColor[run.status] || "var(--ink)", fontWeight: 600 }}>{run.status}</td>
                      <td style={{ ...td, fontVariantNumeric: "tabular-nums" }}>{run.items_collected}</td>
                      <td style={td}>{fmt(run.started_at)}</td><td style={td}>{fmt(run.finished_at)}</td>
                      <td style={{ ...td, color: "var(--crit)" }}>{run.error || ""}</td>
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
