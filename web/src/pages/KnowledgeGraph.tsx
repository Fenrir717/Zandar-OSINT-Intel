import { useEffect, useMemo, useRef, useState } from "react";
import { api, type GraphEdge, type GraphNode, type KnowledgeGraph as KG } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, IconButton, Pill, Spinner } from "../components/ui";
import { Icon } from "../components/icons";

const W = 820, H = 560;
const TYPE: Record<string, { c: string; label: string }> = {
  person: { c: "var(--info)", label: "Orang" },
  organization: { c: "var(--accent)", label: "Organisasi" },
  location: { c: "var(--violet)", label: "Lokasi" },
};
const color = (t: string) => TYPE[t]?.c ?? "var(--muted)";

function layout(nodes: GraphNode[], edges: GraphEdge[]): Record<string, { x: number; y: number }> {
  const N = nodes.length || 1;
  const p: Record<string, { x: number; y: number; vx: number; vy: number }> = {};
  nodes.forEach((n, i) => {
    const a = (i / N) * Math.PI * 2;
    p[n.id] = { x: W / 2 + Math.cos(a) * W * 0.28, y: H / 2 + Math.sin(a) * H * 0.28, vx: 0, vy: 0 };
  });
  const adj = edges.filter((e) => p[e.source] && p[e.target]);
  const k = 130;
  for (let it = 0; it < 170; it++) {
    for (let i = 0; i < nodes.length; i++)
      for (let j = i + 1; j < nodes.length; j++) {
        const a = p[nodes[i].id], b = p[nodes[j].id];
        let dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const rep = (k * k) / d / 11;
        dx /= d; dy /= d;
        a.vx += dx * rep; a.vy += dy * rep; b.vx -= dx * rep; b.vy -= dy * rep;
      }
    for (const e of adj) {
      const a = p[e.source], b = p[e.target];
      let dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.hypot(dx, dy) || 0.01;
      const att = ((d * d) / k / 34) * Math.min(3, e.weight);
      dx /= d; dy /= d;
      a.vx += dx * att; a.vy += dy * att; b.vx -= dx * att; b.vy -= dy * att;
    }
    for (const n of nodes) {
      const q = p[n.id];
      q.vx += (W / 2 - q.x) * 0.012; q.vy += (H / 2 - q.y) * 0.012;
      q.x += Math.max(-18, Math.min(18, q.vx)); q.y += Math.max(-18, Math.min(18, q.vy));
      q.vx *= 0.86; q.vy *= 0.86;
      q.x = Math.max(28, Math.min(W - 28, q.x)); q.y = Math.max(34, Math.min(H - 24, q.y));
    }
  }
  return Object.fromEntries(nodes.map((n) => [n.id, { x: p[n.id].x, y: p[n.id].y }]));
}

export function KnowledgeGraph({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [data, setData] = useState<KG | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [zoom, setZoom] = useState(1);
  const [q, setQ] = useState("");
  const pollRef = useRef<number | null>(null);

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try { setData(await api.graphData(selected)); } catch { setData(null); }
    finally { setLoading(false); }
  }
  async function build() {
    if (!selected || busy) return;
    setBusy(true); setNote("Ekstraksi entitas (NER) berjalan… biasanya <1 menit.");
    try {
      await api.buildGraph(selected);
      let tries = 0;
      pollRef.current = window.setInterval(async () => {
        tries++;
        const g = await api.graphData(selected).catch(() => null);
        if (g && g.nodes.length > 0) { setData(g); setNote(""); setBusy(false); stop(); }
        else if (tries > 30) { setNote("Masih memproses / tak ada entitas ditemukan."); setBusy(false); stop(); }
      }, 3000);
    } catch { setNote("Gagal memicu pembangunan graf."); setBusy(false); }
  }
  function stop() { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } }

  const pos = useMemo(() => (data ? layout(data.nodes, data.edges) : {}), [data]);
  const maxM = useMemo(() => Math.max(1, ...(data?.nodes || []).map((n) => n.mentions)), [data]);
  const types = useMemo(() => Array.from(new Set((data?.nodes || []).map((n) => n.type))), [data]);
  const match = (n: GraphNode) => q.trim() && n.label.toLowerCase().includes(q.toLowerCase().trim());
  const dim = q.trim().length > 0;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {note && <span style={{ fontSize: 12, color: "var(--accent-ink)", alignSelf: "center", marginRight: "auto" }}>{note}</span>}
        <Button variant="ghost" icon="refresh" onClick={load}>Muat ulang</Button>
        <Button icon="spark" onClick={build} disabled={busy}>{busy ? "Membangun…" : data && data.nodes.length ? "Bangun ulang" : "Bangun graf"}</Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "232px 1fr", gap: 16, alignItems: "start" }} className="grid-2">
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Card style={{ padding: 14 }}>
            <div style={{ position: "relative" }}>
              <Icon name="search" size={15} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--faint)" }} />
              <input className="input" placeholder="Cari entitas…" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingLeft: 32 }} />
            </div>
          </Card>
          <Card style={{ padding: 14 }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700, marginBottom: 10 }}>Legenda</div>
            {["person", "organization", "location"].map((t) => (
              <div key={t} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 12.5, padding: "3px 0", opacity: types.length && !types.includes(t) ? 0.4 : 1 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: TYPE[t].c }} /> {TYPE[t].label}
              </div>
            ))}
          </Card>
          <Card style={{ padding: 14, display: "flex", gap: 20 }}>
            <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: "var(--accent-ink)" }}>{data?.stats.entities ?? 0}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>entitas</div></div>
            <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: "var(--accent-ink)" }}>{data?.stats.relations ?? 0}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>relasi</div></div>
          </Card>
          <div style={{ fontSize: 11, color: "var(--faint)", lineHeight: 1.5, padding: "0 2px" }}>
            Data NYATA: entitas hasil NER lokal + ko-okurensi dalam komentar. Resolusi entitas & deteksi komunitas (CIB) = lanjutan Fase 3.
          </div>
        </div>

        <Card style={{ padding: 0, overflow: "hidden", position: "relative" }}>
          {loading ? <div style={{ height: 480, display: "grid", placeItems: "center" }}><Spinner size={26} /></div>
            : !data || data.nodes.length === 0 ? (
              <div style={{ height: 480, display: "grid", placeItems: "center", padding: 24 }}>
                <Empty icon="graph">Graf belum dibangun untuk investigasi ini. Klik <b>Bangun graf</b> — NER lokal mengekstrak entitas dari komentar lalu menyusunnya di Neo4j.</Empty>
              </div>
            ) : (
              <>
                <div style={{ position: "absolute", top: 12, right: 12, display: "flex", flexDirection: "column", gap: 6, zIndex: 2 }}>
                  <IconButton icon="plus" title="Perbesar" onClick={() => setZoom((z) => Math.min(2.4, z + 0.2))} />
                  <div style={{ textAlign: "center", fontSize: 10, color: "var(--muted)" }} className="tnum">{Math.round(zoom * 100)}%</div>
                  <IconButton icon="chevronD" title="Perkecil" onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))} />
                </div>
                <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block", background: "var(--surface)" }} role="img" aria-label="Knowledge graph entitas">
                  <g transform={`translate(${W / 2},${H / 2}) scale(${zoom}) translate(${-W / 2},${-H / 2})`}>
                    {data.edges.map((e, i) => {
                      const a = pos[e.source], b = pos[e.target];
                      if (!a || !b) return null;
                      return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--line)"
                        strokeWidth={Math.min(3, 0.6 + e.weight * 0.5)} opacity={dim ? 0.25 : 0.6} />;
                    })}
                    {data.nodes.map((n) => {
                      const p = pos[n.id]; if (!p) return null;
                      const r = 5 + (n.mentions / maxM) * 16;
                      const on = !dim || match(n);
                      return (
                        <g key={n.id} opacity={on ? 1 : 0.22} style={{ transition: "opacity .2s" }}>
                          <circle cx={p.x} cy={p.y} r={r} fill={color(n.type)} stroke="var(--surface)" strokeWidth={2} />
                          <text x={p.x} y={p.y + r + 11} textAnchor="middle" fontSize={11}
                            fill="var(--ink-2)" style={{ pointerEvents: "none", fontWeight: match(n) ? 700 : 400 }}>
                            {n.label.length > 20 ? n.label.slice(0, 19) + "…" : n.label}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </svg>
                <div style={{ position: "absolute", bottom: 10, left: 14, fontSize: 11, color: "var(--faint)" }}>
                  Ukuran node = frekuensi sebut · tebal garis = ko-okurensi · {data.nodes.length} node teratas
                </div>
              </>
            )}
        </Card>
      </div>

      {data && data.nodes.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <TopEntities nodes={data.nodes} />
        </div>
      )}
    </div>
  );
}

function TopEntities({ nodes }: { nodes: GraphNode[] }) {
  const top = [...nodes].sort((a, b) => b.mentions - a.mentions).slice(0, 12);
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="graph" size={16} /></span>Entitas Teratas
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {top.map((n) => (
          <span key={n.id} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, padding: "5px 11px", borderRadius: 999, border: "1px solid var(--line)", background: "var(--surface-2)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: color(n.type) }} />
            {n.label} <Pill tone="muted">{n.mentions}</Pill>
          </span>
        ))}
      </div>
    </Card>
  );
}
