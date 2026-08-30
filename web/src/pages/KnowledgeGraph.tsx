import { useEffect, useState } from "react";
import { Card, IconButton, Pill, PreviewBanner, SectionTitle } from "../components/ui";

type EntityType = "person" | "org" | "platform" | "topic" | "narrative" | "account";

interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  x: number;
  y: number;
  r: number;
}

interface GraphEdge {
  from: string;
  to: string;
}

const TYPE_COLOR: Record<EntityType, string> = {
  person: "var(--info)",
  org: "var(--accent)",
  platform: "var(--violet)",
  topic: "var(--warn)",
  narrative: "var(--ok)",
  account: "var(--crit)",
};

const TYPE_LABEL: Record<EntityType, string> = {
  person: "Person",
  org: "Organization",
  platform: "Platform",
  topic: "Topic",
  narrative: "Narrative",
  account: "Account/Community",
};

const TYPE_ORDER: EntityType[] = ["person", "org", "platform", "topic", "narrative", "account"];

// Tata letak statis prakomputasi (contoh) — tema OSINT Indonesia. Bukan data nyata;
// Fase 3 akan mengganti ini dengan graf Neo4j GDS interaktif sungguhan.
const NODES: GraphNode[] = [
  { id: "prabowo", label: "Prabowo", type: "person", x: 420, y: 50, r: 20 },
  { id: "kemenko", label: "Kemenko Perekonomian", type: "org", x: 220, y: 120, r: 18 },
  { id: "kemenkeu", label: "Kementerian Keuangan", type: "org", x: 610, y: 120, r: 18 },
  { id: "bansos", label: "bansos", type: "topic", x: 140, y: 240, r: 15 },
  { id: "ikn", label: "IKN", type: "topic", x: 690, y: 230, r: 15 },
  { id: "narasi_ekonomi", label: "narasi: ekonomi kuat", type: "narrative", x: 420, y: 220, r: 17 },
  { id: "narasi_bansos", label: "narasi: bansos diselewengkan", type: "narrative", x: 230, y: 350, r: 17 },
  { id: "reddit", label: "Reddit", type: "platform", x: 90, y: 460, r: 15 },
  { id: "youtube", label: "YouTube", type: "platform", x: 340, y: 480, r: 15 },
  { id: "x_twitter", label: "X (Twitter)", type: "platform", x: 540, y: 460, r: 15 },
  { id: "akun_ekonom", label: "akun @ekonom_id", type: "account", x: 630, y: 350, r: 14 },
  { id: "komunitas", label: "komunitas koordinasi", type: "account", x: 720, y: 460, r: 14 },
];

const EDGES: GraphEdge[] = [
  { from: "prabowo", to: "kemenko" },
  { from: "prabowo", to: "kemenkeu" },
  { from: "prabowo", to: "narasi_ekonomi" },
  { from: "kemenko", to: "kemenkeu" },
  { from: "kemenko", to: "bansos" },
  { from: "kemenko", to: "ikn" },
  { from: "kemenkeu", to: "bansos" },
  { from: "bansos", to: "narasi_bansos" },
  { from: "ikn", to: "narasi_ekonomi" },
  { from: "narasi_ekonomi", to: "youtube" },
  { from: "narasi_ekonomi", to: "x_twitter" },
  { from: "narasi_bansos", to: "reddit" },
  { from: "narasi_bansos", to: "akun_ekonom" },
  { from: "akun_ekonom", to: "komunitas" },
  { from: "komunitas", to: "narasi_bansos" },
  { from: "reddit", to: "youtube" },
];

const NODE_BY_ID: Record<string, GraphNode> = Object.fromEntries(NODES.map((n) => [n.id, n]));

const ZOOM_MIN = 0.6;
const ZOOM_MAX = 1.8;
const ZOOM_STEP = 0.15;

export function KnowledgeGraph({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  useEffect(() => { headerSlot(null); }, []);

  const [query, setQuery] = useState("");
  const [scale, setScale] = useState(1);

  const q = query.trim().toLowerCase();
  const isMatch = (n: GraphNode) => !q || n.label.toLowerCase().includes(q);

  function zoomIn() { setScale((s) => Math.min(ZOOM_MAX, +(s + ZOOM_STEP).toFixed(2))); }
  function zoomOut() { setScale((s) => Math.max(ZOOM_MIN, +(s - ZOOM_STEP).toFixed(2))); }

  return (
    <div>
      <PreviewBanner phase="Fase 3">Graf pengetahuan (Neo4j GDS) hadir di Fase 3 — tampilan ini memakai data contoh untuk pratinjau.</PreviewBanner>

      <div className="grid-split" style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, alignItems: "start" }}>
        <div className="rise rise-1" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card style={{ padding: 16 }}>
            <SectionTitle>Cari Entitas</SectionTitle>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter berdasarkan label…"
              className="input"
            />
          </Card>

          <Card style={{ padding: 16 }}>
            <SectionTitle>Legenda</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {TYPE_ORDER.map((t) => (
                <div key={t} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 12.5 }}>
                  <span style={{ width: 10, height: 10, borderRadius: "50%", background: TYPE_COLOR[t], flexShrink: 0 }} />
                  <span style={{ color: "var(--ink-2)" }}>{TYPE_LABEL[t]}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card style={{ padding: 16 }}>
            <SectionTitle>Statistik</SectionTitle>
            <div style={{ display: "flex", gap: 22 }}>
              <div>
                <div className="tnum" style={{ fontSize: 22, fontWeight: 800 }}>{NODES.length}</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>entitas</div>
              </div>
              <div>
                <div className="tnum" style={{ fontSize: 22, fontWeight: 800 }}>{EDGES.length}</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>relasi</div>
              </div>
            </div>
          </Card>
        </div>

        <Card className="rise rise-2" style={{ padding: 0, overflow: "hidden", position: "relative" }}>
          <div style={{ position: "absolute", top: 12, left: 12, zIndex: 2 }}>
            <Pill tone="warn" dot>data contoh</Pill>
          </div>

          <div style={{ position: "absolute", top: 12, right: 12, zIndex: 2, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
            <IconButton icon="plus" title="Perbesar" onClick={zoomIn} />
            <span className="tnum" style={{ fontSize: 10.5, color: "var(--muted)", fontWeight: 700 }}>{Math.round(scale * 100)}%</span>
            <button
              className="icon-btn"
              type="button"
              title="Perkecil"
              aria-label="Perkecil"
              onClick={zoomOut}
              style={{ fontSize: 18, fontWeight: 700, lineHeight: 1 }}
            >
              –
            </button>
          </div>

          <div style={{ width: "100%", height: 560, overflow: "hidden", background: "var(--surface-2)", display: "grid", placeItems: "center" }}>
            <svg
              viewBox="0 0 800 520"
              width="100%"
              height="100%"
              style={{ transform: `scale(${scale})`, transition: "transform var(--dur) var(--ease-out)" }}
            >
              <g>
                {EDGES.map((e, i) => {
                  const a = NODE_BY_ID[e.from];
                  const b = NODE_BY_ID[e.to];
                  const dim = q !== "" && !isMatch(a) && !isMatch(b);
                  return (
                    <line
                      key={i}
                      x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                      stroke="var(--line)" strokeWidth={1.4}
                      opacity={dim ? 0.15 : 0.55}
                    />
                  );
                })}
              </g>
              <g>
                {NODES.map((n) => {
                  const dim = q !== "" && !isMatch(n);
                  const highlight = q !== "" && !dim;
                  const color = TYPE_COLOR[n.type];
                  return (
                    <g key={n.id} opacity={dim ? 0.25 : 1}>
                      <circle cx={n.x} cy={n.y} r={n.r} fill={color} fillOpacity={0.16} stroke={color} strokeWidth={highlight ? 3 : 2} />
                      <circle cx={n.x} cy={n.y} r={3} fill={color} />
                      <text
                        x={n.x} y={n.y + n.r + 15}
                        textAnchor="middle"
                        fontSize={10.5}
                        fontFamily="var(--font-ui)"
                        fontWeight={highlight ? 700 : 500}
                        fill={highlight ? "var(--ink)" : "var(--ink-2)"}
                      >
                        {n.label}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
        </Card>
      </div>
    </div>
  );
}
