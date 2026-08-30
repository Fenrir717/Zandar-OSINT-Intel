import { useEffect, useRef, useState } from "react";
import { api, streamAgentEvents, type AgentEvent, type AgentRun } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, Tile } from "../components/ui";

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
  const [note, setNote] = useState<string>("");
  const selRef = useRef(selected);
  selRef.current = selected;

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) api.agentRuns(selected).then(setRuns).catch(() => setRuns([])); }, [selected]);

  // Koneksi SSE tunggal, auto-reconnect. Overlay event ke tabel + feed.
  useEffect(() => {
    const ctrl = new AbortController();
    let stop = false;
    function onEvent(e: AgentEvent) {
      setLive((m) => ({ ...m, [e.id]: { status: e.status, node: e.node, detail: e.detail, at: Date.now() } }));
      if (!e.investigation_id || e.investigation_id === selRef.current) {
        setFeed((f) => [{ ...e, at: Date.now() }, ...f].slice(0, 30));
      }
      // Segarkan snapshot saat run BARU mulai (agar muncul di tabel) & saat selesai
      if (e.node === "start" || ["done", "rejected", "failed"].includes(e.status)) {
        api.agentRuns(selRef.current).then(setRuns).catch(() => {});
      }
    }
    (async function loop() {
      while (!stop) {
        try {
          setConnected(true);
          await streamAgentEvents(onEvent, ctrl.signal);
        } catch { /* jaringan/putus */ }
        if (stop) return;
        setConnected(false);
        await new Promise((r) => setTimeout(r, 3000));  // reconnect
      }
    })();
    return () => { stop = true; ctrl.abort(); };
  }, []);

  async function build() {
    if (!selected || busy) return;
    setBusy(true); setNote("");
    try {
      await api.buildNarratives(selected);
      setNote("Analisis diantrekan — pantau progres di feed live di bawah.");
    } catch { setNote("Gagal memicu analisis."); }
    finally { setBusy(false); }
  }

  const eff = (r: AgentRun) => live[r.id]?.status ?? r.status;
  const running = runs.filter((r) => ["running", "queued", "awaiting_approval"].includes(eff(r))).length;
  const tokens = runs.reduce((s, r) => s + r.tokens_in + r.tokens_out, 0);

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
        <Tile label="Total run" value={runs.length || "–"} />
        <Tile label="Sedang berjalan" value={running || "0"} tone={running ? "warn" : undefined} />
        <Tile label="Token dipakai" value={tokens.toLocaleString("id")} />
        <Tile label="Koneksi live" value={connected ? "tersambung" : "putus"} tone={connected ? undefined : "warn"} />
      </div>

      <Card style={{ padding: 16, marginBottom: 16, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <b style={{ fontSize: 14 }}>Analisis Narasi (Graph C)</b>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
            Kelompokkan komentar ter-embed → narasi → skor risiko. Pantau tiap node secara live.
          </div>
          {note && <div style={{ fontSize: 12, color: "var(--accent-ink)", marginTop: 6 }}>{note}</div>}
        </div>
        <LiveDot on={connected} />
        <Button onClick={build}>{busy ? "Menjalankan…" : "Jalankan analisis"}</Button>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, alignItems: "start" }}>
        <RunsTable runs={runs} live={live} />
        <FeedPanel feed={feed} />
      </div>
    </div>
  );
}

function LiveDot({ on }: { on: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: on ? "var(--ok)" : "var(--muted)",
        boxShadow: on ? "0 0 0 3px var(--ok-soft)" : "none" }} />
      {on ? "LIVE" : "offline"}
    </span>
  );
}

function RunsTable({ runs, live }: { runs: AgentRun[]; live: Record<string, Live> }) {
  const th = { textAlign: "left" as const, fontSize: 10, textTransform: "uppercase" as const, letterSpacing: ".05em", color: "var(--muted)", padding: "9px 12px", background: "var(--surface-2)", borderBottom: "1px solid var(--line)" };
  const td = { padding: "9px 12px", borderBottom: "1px solid var(--line)", fontSize: 13, verticalAlign: "top" as const };
  if (runs.length === 0) return <Empty>Belum ada agent run. Jalankan analisis di atas.</Empty>;
  return (
    <Card style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr><th style={th}>Graph</th><th style={th}>Status</th><th style={th}>Token</th><th style={th}>Mulai</th><th style={th}>Durasi</th></tr></thead>
          <tbody>
            {runs.map((r) => {
              const lv = live[r.id];
              const status = lv?.status ?? r.status;
              return (
                <tr key={r.id}>
                  <td style={td}>{GRAPH_LABEL[r.graph_name] ?? r.graph_name}</td>
                  <td style={td}>
                    <Pill tone={TONE[status] ?? "muted"}>{status}</Pill>
                    {lv?.node && ["running", "queued"].includes(status) &&
                      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, fontFamily: "var(--font-mono)" }}>▸ {lv.node}: {lv.detail}</div>}
                  </td>
                  <td style={{ ...td, fontVariantNumeric: "tabular-nums" }}>{(r.tokens_in + r.tokens_out).toLocaleString("id")}</td>
                  <td style={td}>{fmt(r.started_at)}</td>
                  <td style={{ ...td, fontVariantNumeric: "tabular-nums" }}>{dur(r.started_at, r.ended_at)}</td>
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
    <Card style={{ padding: 14, maxHeight: 460, overflowY: "auto" }}>
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700, marginBottom: 10 }}>
        Aktivitas Live
      </div>
      {feed.length === 0 ? <div style={{ fontSize: 12, color: "var(--muted)" }}>Menunggu event… jalankan analisis untuk melihat progres node.</div>
        : <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {feed.map((e, i) => (
              <div key={i} style={{ display: "flex", gap: 9, padding: "7px 0", borderBottom: i < feed.length - 1 ? "1px solid var(--line)" : "none" }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", marginTop: 5, flexShrink: 0,
                  background: e.status === "done" ? "var(--ok)" : e.status === "rejected" || e.status === "failed" ? "var(--crit)" : "var(--accent)" }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12.5 }}>
                    <b>{e.node ?? e.status}</b> <span style={{ color: "var(--muted)" }}>{e.detail ?? ""}</span>
                  </div>
                  <div style={{ fontSize: 10.5, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
                    {GRAPH_LABEL[e.graph] ?? e.graph} · {new Date(e.at).toLocaleTimeString("id")}
                  </div>
                </div>
              </div>
            ))}
          </div>}
    </Card>
  );
}

const fmt = (t: string | null) => (t ? new Date(t).toLocaleString("id") : "–");
function dur(a: string | null, b: string | null): string {
  if (!a) return "–";
  const end = b ? new Date(b).getTime() : Date.now();
  const s = Math.max(0, Math.round((end - new Date(a).getTime()) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}
