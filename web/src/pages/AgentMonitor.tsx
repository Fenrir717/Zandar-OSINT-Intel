import { useEffect, useRef, useState } from "react";
import { api, streamAgentEvents, type AgentEvent, type AgentRun } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, Tile } from "../components/ui";
import { Icon } from "../components/icons";

type Live = { status: string; node?: string; detail?: string; at: number };
type FeedItem = AgentEvent & { at: number };

const TONE: Record<string, "ok" | "crit" | "warn" | "accent" | "muted"> = {
  done: "ok", failed: "crit", rejected: "crit", running: "warn",
  queued: "warn", awaiting_approval: "accent",
};
const GRAPH_LABEL: Record<string, string> = { analysis: "Graph C · Narasi", planner: "Graph A · Planner" };

export function AgentMonitor({ headerSlot }: { headerSlot: (node: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [live, setLive] = useState<Record<string, Live>>({});
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const selRef = useRef(selected);
  selRef.current = selected;

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) api.agentRuns(selected).then(setRuns).catch(() => setRuns([])); }, [selected]);

  useEffect(() => {
    const ctrl = new AbortController();
    let stop = false;
    function onEvent(e: AgentEvent) {
      setLive((m) => ({ ...m, [e.id]: { status: e.status, node: e.node, detail: e.detail, at: Date.now() } }));
      if (!e.investigation_id || e.investigation_id === selRef.current) {
        setFeed((f) => [{ ...e, at: Date.now() }, ...f].slice(0, 30));
      }
      if (e.node === "start" || ["done", "rejected", "failed"].includes(e.status)) {
        api.agentRuns(selRef.current).then(setRuns).catch(() => {});
      }
    }
    (async function loop() {
      while (!stop) {
        try { setConnected(true); await streamAgentEvents(onEvent, ctrl.signal); }
        catch { /* putus */ }
        if (stop) return;
        setConnected(false);
        await new Promise((r) => setTimeout(r, 3000));
      }
    })();
    return () => { stop = true; ctrl.abort(); };
  }, []);

  async function build() {
    if (!selected || busy) return;
    setBusy(true); setNote("");
    try { await api.buildNarratives(selected); setNote("Analisis diantrekan — pantau progres node di feed live."); }
    catch { setNote("Gagal memicu analisis."); }
    finally { setBusy(false); }
  }

  const eff = (r: AgentRun) => live[r.id]?.status ?? r.status;
  const running = runs.filter((r) => ["running", "queued", "awaiting_approval"].includes(eff(r))).length;
  const tokens = runs.reduce((s, r) => s + r.tokens_in + r.tokens_out, 0);

  return (
    <div>
      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Total run" value={runs.length || "–"} icon="agents" /></div>
        <div className="rise rise-2"><Tile label="Sedang berjalan" value={running || "0"} icon="spark" tone={running ? "warn" : undefined} /></div>
        <div className="rise rise-3"><Tile label="Token dipakai" value={tokens.toLocaleString("id")} icon="analysis" /></div>
        <div className="rise rise-4"><Tile label="Koneksi live" value={connected ? "tersambung" : "terputus"} icon="refresh" tone={connected ? undefined : "warn"} /></div>
      </div>

      <Card className="rise rise-2" style={{ padding: 16, marginBottom: 16, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <span style={{ width: 42, height: 42, borderRadius: 12, background: "var(--accent-soft)", color: "var(--accent-ink)", display: "grid", placeItems: "center", flexShrink: 0 }}>
          <Icon name="analysis" size={22} />
        </span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <b style={{ fontSize: 14 }}>Analisis Narasi (Graph C)</b>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>Kelompokkan komentar ter-embed → narasi → skor risiko. Progres tiap node tampil live.</div>
          {note && <div style={{ fontSize: 12, color: "var(--accent-ink)", marginTop: 6 }}>{note}</div>}
        </div>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
          <span className={connected ? "live-dot" : ""} style={!connected ? { width: 8, height: 8, borderRadius: "50%", background: "var(--muted)" } : undefined} />
          {connected ? "LIVE" : "offline"}
        </span>
        <Button onClick={build} icon="spark" disabled={busy}>{busy ? "Menjalankan…" : "Jalankan analisis"}</Button>
      </Card>

      <div className="grid-split rise rise-3" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 16, alignItems: "start" }}>
        <RunsTable runs={runs} live={live} />
        <FeedPanel feed={feed} />
      </div>
    </div>
  );
}

function RunsTable({ runs, live }: { runs: AgentRun[]; live: Record<string, Live> }) {
  if (runs.length === 0) return <Empty icon="agents">Belum ada agent run. Jalankan analisis di atas untuk melihatnya di sini.</Empty>;
  return (
    <Card style={{ padding: 0, overflow: "hidden" }}>
      <div className="scroll-x">
        <table className="tbl">
          <thead><tr><th>Graph</th><th>Status</th><th>Token</th><th>Mulai</th><th>Durasi</th></tr></thead>
          <tbody>
            {runs.map((r) => {
              const lv = live[r.id];
              const status = lv?.status ?? r.status;
              return (
                <tr key={r.id}>
                  <td style={{ fontWeight: 600 }}>{GRAPH_LABEL[r.graph_name] ?? r.graph_name}</td>
                  <td>
                    <Pill tone={TONE[status] ?? "muted"} dot>{status}</Pill>
                    {lv?.node && ["running", "queued"].includes(status) &&
                      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 5, fontFamily: "var(--font-mono)", display: "flex", alignItems: "center", gap: 5 }}>
                        <Icon name="chevronR" size={11} stroke={2.4} style={{ color: "var(--accent)" }} />{lv.node}: {lv.detail}</div>}
                  </td>
                  <td className="tnum">{(r.tokens_in + r.tokens_out).toLocaleString("id")}</td>
                  <td style={{ color: "var(--muted)" }}>{fmt(r.started_at)}</td>
                  <td className="tnum">{dur(r.started_at, r.ended_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function FeedPanel({ feed }: { feed: FeedItem[] }) {
  return (
    <Card style={{ padding: 16, maxHeight: 470, overflowY: "auto" }}>
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".07em", color: "var(--muted)", fontWeight: 700, marginBottom: 12, display: "flex", alignItems: "center", gap: 7 }}>
        <Icon name="spark" size={13} /> Aktivitas Live
      </div>
      {feed.length === 0 ? <div style={{ fontSize: 12.5, color: "var(--muted)", lineHeight: 1.6 }}>Menunggu event… jalankan analisis untuk melihat progres node secara real-time.</div>
        : <div style={{ position: "relative" }}>
            <span aria-hidden style={{ position: "absolute", left: 4, top: 6, bottom: 6, width: 2, background: "var(--line)" }} />
            {feed.map((e, i) => (
              <div key={i} className="rise" style={{ display: "flex", gap: 12, paddingBottom: 14, position: "relative" }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", marginTop: 3, flexShrink: 0, zIndex: 1, border: "2px solid var(--surface)",
                  background: e.status === "done" ? "var(--ok)" : e.status === "rejected" || e.status === "failed" ? "var(--crit)" : "var(--accent)" }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12.5 }}><b>{e.node ?? e.status}</b> <span style={{ color: "var(--muted)" }}>{e.detail ?? ""}</span></div>
                  <div style={{ fontSize: 10.5, color: "var(--faint)", fontFamily: "var(--font-mono)", marginTop: 1 }}>
                    {GRAPH_LABEL[e.graph] ?? e.graph} · {new Date(e.at).toLocaleTimeString("id")}
                  </div>
                </div>
              </div>
            ))}
          </div>}
    </Card>
  );
}

const fmt = (t: string | null) => (t ? new Date(t).toLocaleString("id", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "–");
function dur(a: string | null, b: string | null): string {
  if (!a) return "–";
  const end = b ? new Date(b).getTime() : Date.now();
  const s = Math.max(0, Math.round((end - new Date(a).getTime()) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}
