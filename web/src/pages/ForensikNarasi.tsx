// Forensik Narasi — peta koordinasi × risiko (ABC+D nyata dari Graph C).
// Sumbu Kebenaran (veracity) & kuadran final ditunda ke Fase 5 (verifikasi klaim).
import { useEffect, useState } from "react";
import type { TooltipProps } from "recharts";
import {
  Cell, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { api, type Evidence, type Narrative } from "../lib/api";
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
          <QuadrantChart nars={nars} />

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
              Sumbu Otentisitas×Kebenaran ada di kartu <b>Kuadran</b> di atas — jalankan <b>Verifikasi Klaim</b> untuk mengisinya.
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

type Quad = "healthy" | "agenda" | "rumor" | "operation";
const QUAD: Record<Quad, { label: string; color: string }> = {
  healthy: { label: "Sehat · organik + benar", color: "var(--ok)" },
  agenda: { label: "Agenda · terkoordinasi + benar", color: "var(--info)" },
  rumor: { label: "Rumor · organik + salah", color: "var(--warn)" },
  operation: { label: "Operasi · terkoordinasi + salah", color: "var(--crit)" },
};
function quadOf(x: number, y: number): Quad {
  const coord = x >= 0.5, tru = y >= 0.5;
  return !coord && tru ? "healthy" : !coord && !tru ? "rumor" : coord && tru ? "agenda" : "operation";
}
interface QuadPoint { x: number; y: number; z: number; label: string; q: Quad }

function QuadrantChart({ nars }: { nars: Narrative[] }) {
  const pts: QuadPoint[] = nars
    .filter((n) => n.assessment?.authenticity != null && n.assessment?.veracity != null)
    .map((n) => {
      const x = n.assessment!.authenticity as number;
      const y = n.assessment!.veracity as number;
      return { x, y, z: n.evidence_count, label: n.label, q: (n.assessment!.quadrant as Quad) || quadOf(x, y) };
    });
  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="target" size={16} /></span>Kuadran Otentisitas × Kebenaran
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>{pts.length} narasi terverifikasi</span>
      </div>
      {pts.length === 0 ? (
        <div style={{ height: 200, display: "grid", placeItems: "center", textAlign: "center", color: "var(--faint)", fontSize: 12.5, padding: "0 24px" }}>
          Sumbu Kebenaran belum terisi. Buka halaman <b style={{ color: "var(--muted)" }}>Verifikasi Klaim</b> lalu jalankan verifikasi untuk menempatkan narasi ke kuadran.
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart margin={{ top: 10, right: 16, left: -6, bottom: 4 }}>
              <ReferenceArea x1={0} x2={0.5} y1={0.5} y2={1} fill="var(--ok)" fillOpacity={0.05} />
              <ReferenceArea x1={0.5} x2={1} y1={0.5} y2={1} fill="var(--info)" fillOpacity={0.05} />
              <ReferenceArea x1={0} x2={0.5} y1={0} y2={0.5} fill="var(--warn)" fillOpacity={0.05} />
              <ReferenceArea x1={0.5} x2={1} y1={0} y2={0.5} fill="var(--crit)" fillOpacity={0.06} />
              <XAxis type="number" dataKey="x" domain={[0, 1]} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
              <YAxis type="number" dataKey="y" domain={[0, 1]} tick={{ fill: "var(--muted)", fontSize: 10 }} tickLine={false} axisLine={false} />
              <ZAxis type="number" dataKey="z" range={[60, 300]} />
              <ReferenceLine x={0.5} stroke="var(--line)" strokeDasharray="4 4" />
              <ReferenceLine y={0.5} stroke="var(--line)" strokeDasharray="4 4" />
              <Tooltip cursor={{ strokeDasharray: "3 3", stroke: "var(--line)" }} content={QuadTip} />
              <Scatter data={pts} isAnimationActive={false}>
                {pts.map((d, i) => <Cell key={i} fill={QUAD[d.q].color} />)}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--faint)", marginTop: 2 }}>
            <span>← Organik</span><span>Otentisitas</span><span>Terkoordinasi →</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 14px", marginTop: 10, borderTop: "1px solid var(--line-2)", paddingTop: 10 }}>
            {(Object.keys(QUAD) as Quad[]).map((k) => (
              <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)" }}>
                <span style={{ width: 9, height: 9, borderRadius: 3, background: QUAD[k].color }} />{QUAD[k].label}
              </span>
            ))}
          </div>
          <div style={{ fontSize: 10.5, color: "var(--faint)", marginTop: 6 }}>Sumbu tegak: Kebenaran (bawah salah · atas benar). Verdict = penilaian AI draf.</div>
        </>
      )}
    </Card>
  );
}

function QuadTip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload as QuadPoint;
  return (
    <div style={{ ...tip, padding: "8px 11px" }}>
      <div style={{ fontWeight: 700, marginBottom: 4, maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{d.label}</div>
      <div>Otentisitas: <b className="tnum">{d.x.toFixed(2)}</b></div>
      <div>Kebenaran: <b className="tnum">{d.y.toFixed(2)}</b></div>
      <div style={{ color: QUAD[d.q].color, fontWeight: 600, marginTop: 2 }}>{QUAD[d.q].label}</div>
    </div>
  );
}

const ABCD: { k: string; name: string; desc: string }[] = [
  { k: "A", name: "Aktor", desc: "Actors — seberapa terpusat/berulang pelaku di balik narasi" },
  { k: "B", name: "Perilaku", desc: "Behavior — pola penyebaran (ledakan/burst, sinkronisasi)" },
  { k: "C", name: "Konten", desc: "Content — muatan negatif/toksik/manipulatif" },
  { k: "D", name: "Distribusi", desc: "Distribution — jangkauan lintas platform/kanal" },
];

function NarrativeList({ nars }: { nars: Narrative[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const [ev, setEv] = useState<Record<string, Evidence[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  if (nars.length === 0) return null;

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

  return (
    <Card className="rise" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 13.5, fontWeight: 600 }}>
        <span style={{ color: "var(--accent)" }}><Icon name="audit" size={16} /></span>Rincian Narasi (ABC+D)
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>{nars.length} narasi · klik untuk bukti + sumber</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "5px 14px", marginBottom: 12 }}>
        {ABCD.map((x) => (
          <span key={x.k} title={x.desc} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--muted)", cursor: "help" }}>
            <b style={{ color: "var(--ink)" }}>{x.k}</b>{x.name}
          </span>
        ))}
      </div>
      <div className="scroll-x">
        <div style={{ minWidth: 720, display: "flex", flexDirection: "column" }}>
          {nars.map((n, i) => {
            const a = n.assessment;
            const isOpen = open === n.id;
            return (
              <div key={n.id} style={{ borderBottom: i < nars.length - 1 ? "1px solid var(--line-2)" : "none" }}>
                <button onClick={() => toggle(n.id)} style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 0", width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer", color: "var(--ink)" }}>
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
                  <Icon name={isOpen ? "chevronD" : "chevronR"} size={14} style={{ color: "var(--faint)", flexShrink: 0 }} />
                </button>
                {isOpen && (
                  <div style={{ padding: "2px 0 14px 34px" }}>
                    <SignalStrip breakdown={n.risk_breakdown} />
                    {busy === n.id ? <div style={{ fontSize: 12, color: "var(--muted)" }}>Memuat bukti…</div>
                      : (ev[n.id] || []).length === 0 ? <div style={{ fontSize: 12, color: "var(--muted)" }}>Tak ada bukti tertaut.</div>
                      : <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 10 }}>
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
            );
          })}
        </div>
      </div>
    </Card>
  );
}

// Sinyal forensik tambahan dari risk_breakdown Graph C (di luar ABC+D).
function SignalStrip({ breakdown }: { breakdown: Record<string, unknown> | null }) {
  const num = (k: string): number | null =>
    typeof breakdown?.[k] === "number" ? (breakdown[k] as number) : null;
  const platforms = Array.isArray(breakdown?.platforms) ? (breakdown!.platforms as string[]) : [];
  const items: { label: string; value: string; title: string }[] = [];
  const burst = num("burst");
  if (burst != null) items.push({ label: "Ledakan", value: burst.toFixed(2), title: "Burst — lonjakan volume dalam waktu singkat" });
  const tox = num("mean_toxicity");
  if (tox != null) items.push({ label: "Toksisitas", value: `${Math.round(tox * 100)}%`, title: "Rerata skor toksisitas bukti" });
  const cohesion = num("cohesion");
  if (cohesion != null) items.push({ label: "Kohesi", value: cohesion.toFixed(2), title: "Kemiripan semantik antar-bukti (0..1)" });
  const authors = num("unique_authors");
  if (authors != null) items.push({ label: "Penulis unik", value: String(authors), title: "Jumlah penulis berbeda" });
  const neg = num("neg_share");
  if (neg != null) items.push({ label: "Porsi negatif", value: `${Math.round(neg * 100)}%`, title: "Bagian bukti bersentimen negatif" });
  if (items.length === 0 && platforms.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
      {items.map((it) => (
        <span key={it.label} className="badge" title={it.title}
          style={{ color: "var(--muted)", borderColor: "var(--line)", background: "var(--surface-2)" }}>
          {it.label} <b className="tnum" style={{ color: "var(--ink)", marginLeft: 4 }}>{it.value}</b>
        </span>
      ))}
      {platforms.map((p) => <Pill key={p} tone="muted">{p}</Pill>)}
    </div>
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
