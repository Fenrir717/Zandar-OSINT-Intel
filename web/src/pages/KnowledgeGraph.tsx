import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type GraphEdge, type GraphNode, type KnowledgeGraph as KG } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, IconButton, Pill, Spinner } from "../components/ui";
import { Icon } from "../components/icons";

const W = 900, H = 620;
const TYPE: Record<string, { c: string; label: string }> = {
  person: { c: "var(--info)", label: "Orang" },
  organization: { c: "var(--accent)", label: "Organisasi" },
  location: { c: "var(--violet)", label: "Lokasi" },
};
const color = (t: string) => TYPE[t]?.c ?? "var(--muted)";
const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

function layout(nodes: GraphNode[], edges: GraphEdge[]): Record<string, { x: number; y: number }> {
  const N = nodes.length || 1;
  const p: Record<string, { x: number; y: number; vx: number; vy: number }> = {};
  nodes.forEach((n, i) => {
    const a = (i / N) * Math.PI * 2;
    p[n.id] = { x: W / 2 + Math.cos(a) * W * 0.3, y: H / 2 + Math.sin(a) * H * 0.3, vx: 0, vy: 0 };
  });
  const adj = edges.filter((e) => p[e.source] && p[e.target]);
  const k = 150;
  for (let it = 0; it < 180; it++) {
    for (let i = 0; i < nodes.length; i++)
      for (let j = i + 1; j < nodes.length; j++) {
        const a = p[nodes[i].id], b = p[nodes[j].id];
        let dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const rep = (k * k) / d / 10;
        dx /= d; dy /= d;
        a.vx += dx * rep; a.vy += dy * rep; b.vx -= dx * rep; b.vy -= dy * rep;
      }
    for (const e of adj) {
      const a = p[e.source], b = p[e.target];
      let dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.hypot(dx, dy) || 0.01;
      const att = ((d * d) / k / 36) * Math.min(3, e.weight);
      dx /= d; dy /= d;
      a.vx += dx * att; a.vy += dy * att; b.vx -= dx * att; b.vy -= dy * att;
    }
    for (const n of nodes) {
      const q = p[n.id];
      q.vx += (W / 2 - q.x) * 0.012; q.vy += (H / 2 - q.y) * 0.012;
      q.x += Math.max(-20, Math.min(20, q.vx)); q.y += Math.max(-20, Math.min(20, q.vy));
      q.vx *= 0.86; q.vy *= 0.86;
      q.x = Math.max(40, Math.min(W - 40, q.x)); q.y = Math.max(44, Math.min(H - 32, q.y));
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
  const [q, setQ] = useState("");
  const [typeF, setTypeF] = useState("all");
  const [sel, setSel] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [expanded, setExpanded] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ mx: number; my: number; px: number; py: number; moved: boolean } | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, [selected]);
  useEffect(() => { setSel(null); setPan({ x: 0, y: 0 }); setZoom(1); }, [data]);

  // wheel-zoom (non-passive agar bisa cegah scroll halaman)
  useEffect(() => {
    const el = svgRef.current; if (!el) return;
    const onWheel = (e: WheelEvent) => { e.preventDefault(); setZoom((z) => Math.max(0.4, Math.min(3, z * (e.deltaY < 0 ? 1.12 : 0.89)))); };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [data]);
  useEffect(() => {  // ESC keluar dari mode perbesar
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setExpanded(false); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

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
        if (g && g.nodes.length > 0) { setData(g); setNote(""); setBusy(false); stopPoll(); }
        else if (tries > 30) { setNote("Masih memproses / tak ada entitas ditemukan."); setBusy(false); stopPoll(); }
      }, 3000);
    } catch { setNote("Gagal memicu pembangunan graf."); setBusy(false); }
  }
  function stopPoll() { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } }

  const pos = useMemo(() => (data ? layout(data.nodes, data.edges) : {}), [data]);
  const maxM = useMemo(() => Math.max(1, ...(data?.nodes || []).map((n) => n.mentions)), [data]);
  const byId = useMemo(() => Object.fromEntries((data?.nodes || []).map((n) => [n.id, n])), [data]);
  const neighbors = useMemo(() => {
    if (!sel || !data) return null;
    const s = new Set<string>([sel]);
    for (const e of data.edges) { if (e.source === sel) s.add(e.target); if (e.target === sel) s.add(e.source); }
    return s;
  }, [sel, data]);
  const emph = useMemo(() => {
    const s = new Set<string>();
    if (!data) return s;
    if (sel) { neighbors?.forEach((id) => s.add(id)); return s; }
    const qq = q.trim().toLowerCase();
    for (const n of data.nodes)
      if ((typeF === "all" || n.type === typeF) && (!qq || n.label.toLowerCase().includes(qq))) s.add(n.id);
    return s;
  }, [data, sel, neighbors, q, typeF]);
  const filtering = Boolean(sel || q.trim() || typeF !== "all");

  function onDown(e: React.PointerEvent) {
    drag.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y, moved: false };
  }
  function onMove(e: React.PointerEvent) {
    if (!drag.current || !svgRef.current) return;
    const dx = e.clientX - drag.current.mx, dy = e.clientY - drag.current.my;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.current.moved = true;
    const rect = svgRef.current.getBoundingClientRect();
    const s = W / rect.width;
    setPan({ x: drag.current.px + dx * s, y: drag.current.py + dy * s });
  }
  function onUp() {
    const moved = drag.current?.moved; drag.current = null;
    if (!moved) setSel(null); // klik latar → lepas pilihan
  }
  const toggleExpand = () => setExpanded((v) => !v);
  const selNode = sel ? byId[sel] : null;
  const selDeg = sel && data ? data.edges.filter((e) => e.source === sel || e.target === sel).length : 0;

  const content = loading ? (
    <div style={{ flex: 1, display: "grid", placeItems: "center", minHeight: 400 }}><Spinner size={26} /></div>
  ) : !data || data.nodes.length === 0 ? (
    <div style={{ flex: 1, display: "grid", placeItems: "center", padding: 24, minHeight: 400 }}>
      <Empty icon="graph">Graf belum dibangun. Klik <b>Bangun graf</b> — NER lokal mengekstrak entitas lalu menyusunnya di Neo4j.</Empty>
    </div>
  ) : (
    <>
      <div style={{ position: "relative", flex: 1, minHeight: 0 }}>
        <div style={{ position: "absolute", top: 12, right: 12, display: "flex", flexDirection: "column", gap: 6, zIndex: 2 }}>
          <IconButton icon="plus" title="Zoom in" onClick={() => setZoom((z) => Math.min(3, z + 0.25))} />
          <div className="tnum" style={{ textAlign: "center", fontSize: 10, color: "var(--muted)" }}>{Math.round(zoom * 100)}%</div>
          <IconButton icon="minus" title="Zoom out" onClick={() => setZoom((z) => Math.max(0.4, z - 0.25))} />
          <IconButton icon="reset" title="Reset tampilan" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} />
          <IconButton icon={expanded ? "x" : "expand"} title={expanded ? "Tutup (Esc)" : "Layar penuh"} onClick={toggleExpand} />
        </div>
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet"
          style={{ width: "100%", height: "100%", display: "block", cursor: drag.current ? "grabbing" : "grab", touchAction: "none" }}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}
          role="img" aria-label="Knowledge graph entitas">
          <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
            {(data?.edges || []).map((e, i) => {
              const a = pos[e.source], b = pos[e.target]; if (!a || !b) return null;
              const touch = sel && (e.source === sel || e.target === sel);
              const on = emph.has(e.source) && emph.has(e.target);
              const op = sel ? (touch ? 0.85 : 0.06) : (filtering ? (on ? 0.5 : 0.08) : 0.5);
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={touch ? "var(--accent)" : "var(--line)"} strokeWidth={Math.min(3.5, 0.8 + e.weight * 0.5)} opacity={op} />;
            })}
            {(data?.nodes || []).map((n) => {
              const p = pos[n.id]; if (!p) return null;
              const r = 15 + (n.mentions / maxM) * 22;
              const c = color(n.type);
              const on = emph.has(n.id);
              const isSel = sel === n.id;
              return (
                <g key={n.id} opacity={on ? 1 : 0.16} style={{ transition: "opacity .2s", cursor: "pointer" }}
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => { e.stopPropagation(); setSel(isSel ? null : n.id); }}>
                  {isSel && <circle cx={p.x} cy={p.y} r={r + 6} fill="none" stroke={c} strokeOpacity={0.35} strokeWidth={2.5} />}
                  <circle cx={p.x} cy={p.y} r={r} fill={c} fillOpacity={0.16} stroke={c} strokeWidth={isSel ? 3 : 2} />
                  <text x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central" fontSize={Math.min(15, r * 0.85)} fontWeight={700} fill={c} style={{ pointerEvents: "none" }}>{n.mentions}</text>
                  <text x={p.x} y={p.y + r + 13} textAnchor="middle" fontSize={11} fill="var(--ink-2)" style={{ pointerEvents: "none", fontWeight: isSel ? 700 : 400 }}>{trunc(n.label, 20)}</text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <div style={{ padding: "9px 14px", borderTop: "1px solid var(--line)", background: "var(--surface)", fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <Icon name="spark" size={12} style={{ color: "var(--accent)" }} />
        Klik node untuk fokus · seret untuk menggeser · scroll / tombol untuk zoom · <b className="tnum" style={{ color: "var(--ink-2)" }}>{data?.nodes.length}</b> node teratas
      </div>
    </>
  );

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {note && <span style={{ fontSize: 12, color: "var(--accent-ink)", alignSelf: "center", marginRight: "auto" }}>{note}</span>}
        <Button variant="ghost" icon="refresh" onClick={load}>Muat ulang</Button>
        <Button icon="spark" onClick={build} disabled={busy}>{busy ? "Membangun…" : data && data.nodes.length ? "Bangun ulang" : "Bangun graf"}</Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16, alignItems: "start" }} className="grid-2">
        {/* Panel kiri */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Card style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ position: "relative" }}>
              <Icon name="search" size={15} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--faint)" }} />
              <input className="input" placeholder="Cari entitas…" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingLeft: 32 }} />
            </div>
            <select className="select" value={typeF} onChange={(e) => setTypeF(e.target.value)}>
              <option value="all">Semua tipe</option>
              <option value="person">Orang</option>
              <option value="organization">Organisasi</option>
              <option value="location">Lokasi</option>
            </select>
          </Card>

          {selNode ? (
            <Card style={{ padding: 14 }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700, marginBottom: 8 }}>Entitas terpilih</div>
              <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 8 }}>
                <span style={{ width: 12, height: 12, borderRadius: "50%", background: color(selNode.type), flexShrink: 0 }} />
                <b style={{ fontSize: 14 }}>{selNode.label}</b>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Pill tone="muted">{TYPE[selNode.type]?.label ?? selNode.type}</Pill>
                <Pill tone="accent">{selNode.mentions} sebutan</Pill>
                <Pill tone="info">{selDeg} koneksi</Pill>
              </div>
              <button className="btn btn-ghost" style={{ marginTop: 10, width: "100%" }} onClick={() => setSel(null)}>Lepas pilihan</button>
            </Card>
          ) : (
            <Card style={{ padding: 14 }}>
              <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", fontWeight: 700, marginBottom: 10 }}>Legenda</div>
              {["person", "organization", "location"].map((t) => (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 12.5, padding: "3px 0" }}>
                  <span style={{ width: 10, height: 10, borderRadius: "50%", background: TYPE[t].c }} /> {TYPE[t].label}
                </div>
              ))}
            </Card>
          )}

          <Card style={{ padding: 14, display: "flex", gap: 22 }}>
            <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: "var(--accent-ink)" }}>{data?.stats.entities ?? 0}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>entitas</div></div>
            <div><div className="tnum" style={{ fontSize: 22, fontWeight: 800, color: "var(--accent-ink)" }}>{data?.stats.relations ?? 0}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>relasi</div></div>
          </Card>
          <div style={{ fontSize: 11, color: "var(--faint)", lineHeight: 1.5, padding: "0 2px" }}>
            Data NYATA: entitas NER lokal (sudah diresolusi/digabung) + ko-okurensi. Deteksi komunitas (CIB) = lanjutan Fase 3.
          </div>
        </div>

        {/* Kanvas graf */}
        <Card style={{ padding: 0, overflow: "hidden" }}>
          {expanded ? (
            <div style={{ height: 540, display: "grid", placeItems: "center", color: "var(--muted)", fontSize: 12.5, textAlign: "center", padding: 20 }}>
              Grafik dibuka layar penuh.<br />Tekan <b>×</b> atau <b>Esc</b> untuk kembali.
            </div>
          ) : (
            <div ref={wrapRef} style={{ position: "relative", display: "flex", flexDirection: "column", height: 540, background: "var(--surface)" }}>{content}</div>
          )}
        </Card>
      </div>

      {expanded && createPortal(
        <div ref={wrapRef} style={{ position: "fixed", inset: 0, zIndex: 200, background: "var(--bg)", display: "flex", flexDirection: "column" }}>{content}</div>,
        document.body,
      )}
    </div>
  );
}
