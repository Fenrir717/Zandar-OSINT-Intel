import { useEffect, useState } from "react";
import { api, type AnalysisStats, type Narrative } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, PreviewBanner, ProgressBar, SectionTitle, Spinner, Tile } from "../components/ui";
import { Icon, type IconName } from "../components/icons";

const SENT_LABEL: Record<string, string> = { pos: "Positif", positive: "Positif", neg: "Negatif", negative: "Negatif", neu: "Netral", neutral: "Netral", mixed: "Campuran", "?": "?" };
const SENT_TONE: Record<string, "ok" | "crit" | "muted" | "violet"> = {
  pos: "ok", positive: "ok", neg: "crit", negative: "crit", neu: "muted", neutral: "muted", mixed: "violet",
};

function arr(d: Record<string, number> | undefined) {
  return Object.entries(d || {}).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
}

const riskTone = (r: number | null) => (r == null ? "muted" : r >= 0.5 ? "crit" : r >= 0.35 ? "warn" : "ok") as "crit" | "warn" | "ok" | "muted";

type SectionId = "exec" | "risk" | "sentiment";
const SECTIONS: { id: SectionId; label: string; icon: IconName }[] = [
  { id: "exec", label: "Ringkasan Eksekutif", icon: "reports" },
  { id: "risk", label: "Narasi Berisiko", icon: "target" },
  { id: "sentiment", label: "Sentimen", icon: "comment" },
];

export function Reports({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [stats, setStats] = useState<AnalysisStats | null>(null);
  const [nars, setNars] = useState<Narrative[]>([]);
  const [loading, setLoading] = useState(false);
  const [section, setSection] = useState<SectionId>("exec");

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try {
      const [s, n] = await Promise.all([api.analysisStats(selected), api.narratives(selected).catch(() => [])]);
      setStats(s); setNars(n);
    } catch { setStats(null); setNars([]); }
    finally { setLoading(false); }
  }

  const investigation = list.find((i) => i.id === selected);
  const empty = !loading && (!stats || stats.analyzed === 0) && nars.length === 0;
  const activeSection = SECTIONS.find((s) => s.id === section);

  return (
    <div>
      <PreviewBanner phase="Fase 4">Laporan penuh (Graph D: sitasi + ekspor PDF) menyusul di Fase 4. Di bawah ini ringkasan otomatis dari NARASI & ANALISIS nyata.</PreviewBanner>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14 }}>
        <Button variant="ghost" icon="refresh" onClick={load}>Segarkan</Button>
        <button className="btn btn-ghost" type="button" disabled title="Fase 4">
          <Icon name="download" size={16} /> Ekspor
        </button>
      </div>

      {loading && !stats ? (
        <div style={{ display: "grid", placeItems: "center", padding: "80px 0" }}><Spinner size={28} /></div>
      ) : empty ? (
        <Empty icon="reports">Jalankan analisis &amp; bangun narasi dulu.</Empty>
      ) : (
        <div className="grid-split" style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 16, alignItems: "start" }}>
          <Card className="rise rise-1" style={{ padding: 8 }}>
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSection(s.id)}
                className={`nav-item${section === s.id ? " active" : ""}`}
                style={{
                  display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left",
                  fontSize: 13, padding: "9px 12px", borderRadius: 9, border: "none", background: "transparent", cursor: "pointer",
                }}
              >
                <Icon name={s.icon} size={15} />{s.label}
              </button>
            ))}
          </Card>

          <Card className="rise rise-2" style={{ padding: 18 }}>
            <SectionTitle right={investigation ? <span style={{ fontSize: 11.5, color: "var(--muted)", fontWeight: 500 }}>{investigation.title}</span> : undefined}>
              {activeSection?.label}
            </SectionTitle>

            {section === "exec" && <ExecSummary stats={stats} narCount={nars.length} />}
            {section === "risk" && <RiskList nars={nars} />}
            {section === "sentiment" && <SentimentBars sentiment={stats?.sentiment} />}
          </Card>
        </div>
      )}
    </div>
  );
}

function ExecSummary({ stats, narCount }: { stats: AnalysisStats | null; narCount: number }) {
  if (!stats) return <div style={{ fontSize: 12.5, color: "var(--muted)" }}>Tak ada data.</div>;
  const coverage = Math.round(stats.coverage * 100);
  return (
    <div>
      <p style={{ fontSize: 13, lineHeight: 1.65, color: "var(--ink-2)", margin: "0 0 16px" }}>
        Dari <b className="tnum">{stats.total.toLocaleString("id")}</b> komentar terkumpul, <b className="tnum">{stats.analyzed.toLocaleString("id")}</b> ({coverage}%) telah dianalisis.
        Sistem mengidentifikasi <b className="tnum">{narCount}</b> narasi{stats.bot_suspect > 0 ? <> dan <b className="tnum">{stats.bot_suspect}</b> akun tersangka bot</> : null}.
      </p>
      <div className="grid-stats">
        <Tile label="Total komentar" value={stats.total.toLocaleString("id")} icon="comment" />
        <Tile label="Dianalisis" value={stats.analyzed.toLocaleString("id")} icon="analysis" sub={`${coverage}% cakupan`} />
        <Tile label="Rerata sentimen" value={stats.avg_sentiment != null ? stats.avg_sentiment.toFixed(2) : "–"} icon="spark" tone={stats.avg_sentiment != null && stats.avg_sentiment < -0.1 ? "crit" : undefined} />
        <Tile label="Tersangka bot" value={stats.bot_suspect} icon="agents" tone={stats.bot_suspect > 0 ? "warn" : undefined} />
        <Tile label="Narasi" value={narCount || "–"} icon="graph" />
      </div>
    </div>
  );
}

function RiskList({ nars }: { nars: Narrative[] }) {
  if (nars.length === 0) return <div style={{ fontSize: 12.5, color: "var(--muted)" }}>Belum ada narasi.</div>;
  const sorted = [...nars].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));
  const shown = sorted.slice(0, 10);
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{sorted.length} narasi · diurutkan berdasarkan skor risiko</div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {shown.map((n, i) => (
          <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: i < shown.length - 1 ? "1px solid var(--line-2)" : "none" }}>
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
          </div>
        ))}
      </div>
      {sorted.length > shown.length && (
        <div style={{ fontSize: 11.5, color: "var(--faint)", marginTop: 10 }}>+{sorted.length - shown.length} narasi lainnya</div>
      )}
    </div>
  );
}

function SentimentBars({ sentiment }: { sentiment: Record<string, number> | undefined }) {
  const items = arr(sentiment);
  if (items.length === 0) return <div style={{ fontSize: 12.5, color: "var(--muted)" }}>Tak ada data sentimen.</div>;
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {items.map((it) => {
        const pct = Math.round((it.value / total) * 100);
        const tone = SENT_TONE[it.name] ?? "muted";
        return (
          <div key={it.name}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 7 }}>
              <span style={{ color: "var(--ink-2)", fontWeight: 600 }}>{SENT_LABEL[it.name] || it.name}</span>
              <span className="tnum" style={{ color: "var(--muted)" }}>{it.value.toLocaleString("id")} · {pct}%</span>
            </div>
            <ProgressBar value={pct} tone={tone} />
          </div>
        );
      })}
    </div>
  );
}
