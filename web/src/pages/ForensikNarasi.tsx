// Forensik Narasi — peta koordinasi × risiko (ABC+D nyata dari Graph C).
// Sumbu Kebenaran (veracity) & kuadran final ditunda ke Fase 5 (verifikasi klaim).
import { useEffect, useState } from "react";
import type { TooltipProps } from "recharts";
import {
  Cell, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { api, type Narrative } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Card, Empty, Pill, ProgressBar, Spinner, Tile } from "../components/ui";
import { Icon } from "../components/icons";

type RiskTone = "crit" | "warn" | "ok" | "muted";
type BarTone = "info" | "violet" | "crit" | "accent";

const tip = { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)", boxShadow: "var(--sh-md)" };

function riskTone(r: number | null): RiskTone {
  if (r == null) return "muted";
  return r >= 0.5 ? "crit" : r >= 0.35 ? "warn" : "ok";
}
function riskColor(r: number | null): string {
  if (r == null) return "var(--muted)";
  return r >= 0.5 ? "var(--crit)" : r >= 0.35 ? "var(--warn)" : "var(--ok)";
}

interface ScatterPoint { x: number; y: number; z: number; label: string }

export function ForensikNarasi({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [nars, setNars] = useState<Narrative[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try { setNars(await api.narratives(selected)); }
    catch { setNars([]); }
    finally { setLoading(false); }
  }

  const withAuth = nars.filter((n) => n.assessment?.authenticity != null);
  const coordinated = withAuth.filter((n) => (n.assessment?.authenticity ?? 0) >= 0.6).length;
  const avgAuth = withAuth.length
    ? withAuth.reduce((s, n) => s + (n.assessment?.authenticity ?? 0), 0) / withAuth.length
    : null;
  const totalEvidence = nars.reduce((s, n) => s + n.evidence_count, 0);

  const scatterData: ScatterPoint[] = nars
    .filter((n) => n.assessment?.authenticity != null && n.risk_score != null)
    .map((n) => ({
      x: n.assessment?.authenticity as number,
      y: n.risk_score as number,
      z: n.evidence_count,
      label: n.label,
    }));

  const sorted = [...nars].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));
  const empty = !loading && nars.length === 0;

  return (
    <div>
      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Narasi" value={nars.length || "–"} icon="graph" /></div>
        <div className="rise rise-2"><Tile label="Terkoordinasi tinggi" value={coordinated || "0"} icon="spark" tone={coordinated ? "warn" : undefined} /></div>
        <div className="rise rise-3"><Tile label="Rerata otentisitas" value={avgAuth != null ? avgAuth.toFixed(2) : "–"} icon="analysis" /></div>
        <div className="rise rise-4"><Tile label="Total bukti" value={totalEvidence.toLocaleString("id")} icon="comment" /></div>
      </div>

      {loading ? (
        <div style={{ display: "grid", placeItems: "center", padding: 60 }}><Spinner size={28} /></div>
      ) : empty ? (
        <Empty icon="graph">Belum ada narasi. Bangun narasi via Agent Monitor (Jalankan analisis) dulu.</Empty>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card className="rise" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, fontWeight: 600 }}>
              <span style={{ color: "var(--accent)" }}><Icon name="graph" size={16} /></span>Peta Koordinasi × Risiko
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>{scatterData.length} narasi terpetakan</span>
            </div>
            {scatterData.length === 0 ? (
              <div style={{ height: 220, display: "grid", placeItems: "center", color: "var(--faint)", fontSize: 12.5 }}>Tak ada data otentisitas/risiko untuk dipetakan.</div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={290}>
                  <ScatterChart margin={{ top: 10, right: 20, left: -10, bottom: 4 }}>
                    <XAxis type="number" dataKey="x" domain={[0, 1]} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
                    <YAxis type="number" dataKey="y" domain={[0, 1]} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <ZAxis type="number" dataKey="z" range={[60, 320]} />
                    <ReferenceLine x={0.5} stroke="var(--line)" strokeDasharray="4 4" />
                    <ReferenceLine y={0.5} stroke="var(--line)" strokeDasharray="4 4" />
                    <Tooltip cursor={{ strokeDasharray: "3 3", stroke: "var(--line)" }} content={ScatterTip} />
                    <Scatter data={scatterData} isAnimationActive={false}>
                      {scatterData.map((d, i) => <Cell key={i} fill={riskColor(d.y)} />)}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
                <div style={{ textAlign: "center", fontSize: 11, color: "var(--muted)", marginTop: 2 }}>← Organik   ·   Terkoordinasi →</div>
              </>
            )}
            <div style={{ fontSize: 11, color: "var(--faint)", marginTop: 10, borderTop: "1px solid var(--line-2)", paddingTop: 10 }}>
              Sumbu Kebenaran (veracity) &amp; kuadran final Otentisitas×Kebenaran → Fase 5 (verifikasi klaim).
            </div>
          </Card>

          <NarrativeList nars={sorted} />
        </div>
      )}
    </div>
  );
}

function ScatterTip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload as ScatterPoint;
  return (
    <div style={{ ...tip, padding: "8px 11px" }}>
      <div style={{ fontWeight: 700, marginBottom: 4, maxWidth: 200, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{d.label}</div>
      <div>Otentisitas: <b className="tnum">{d.x.toFixed(2)}</b></div>
      <div>Risiko: <b className="tnum">{d.y.toFixed(2)}</b></div>
      <div style={{ color: "var(--muted)" }}>{d.z} bukti</div>
    </div>
  );
}

function NarrativeList({ nars }: { nars: Narrative[] }) {
  if (nars.length === 0) return null;
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="audit" size={16} /></span>Rincian Narasi (ABC+D)
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>{nars.length} narasi · diurutkan risiko</span>
      </div>
      <div className="scroll-x">
        <div style={{ minWidth: 720, display: "flex", flexDirection: "column" }}>
          {nars.map((n, i) => {
            const a = n.assessment;
            return (
              <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 0", borderBottom: i < nars.length - 1 ? "1px solid var(--line-2)" : "none" }}>
                <span className="tnum" style={{ width: 20, fontSize: 12, color: "var(--faint)", fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                <div style={{ flex: "1 1 220px", minWidth: 160 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.label}</div>
                  {n.summary && <div style={{ fontSize: 11.5, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.summary}</div>}
                </div>
                <MiniBar label="A" value={a?.actors ?? null} tone="info" />
                <MiniBar label="B" value={a?.behavior ?? null} tone="violet" />
                <MiniBar label="C" value={a?.content ?? null} tone="crit" />
                <MiniBar label="D" value={a?.distribution ?? null} tone="accent" />
                <span className="hide-sm tnum" title="Otentisitas (0 organik .. 1 terkoordinasi)" style={{ fontSize: 11, color: "var(--muted)", width: 68, textAlign: "right", flexShrink: 0 }}>
                  koord {a?.authenticity != null ? Math.round(a.authenticity * 100) : "–"}%
                </span>
                <span className="tnum" style={{ fontSize: 11, color: "var(--muted)", width: 58, textAlign: "right", flexShrink: 0 }}>{n.evidence_count} bukti</span>
                <Pill tone={riskTone(n.risk_score)} dot>risiko {n.risk_score != null ? n.risk_score.toFixed(2) : "–"}</Pill>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

function MiniBar({ label, value, tone }: { label: string; value: number | null; tone: BarTone }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5, flexShrink: 0 }} title={label}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", width: 9 }}>{label}</span>
      <div style={{ width: 60 }}><ProgressBar value={value != null ? value * 100 : 0} tone={tone} /></div>
      <span className="tnum" style={{ fontSize: 10.5, color: "var(--muted)", width: 30, textAlign: "right" }}>{value != null ? `${Math.round(value * 100)}%` : "–"}</span>
    </div>
  );
}
