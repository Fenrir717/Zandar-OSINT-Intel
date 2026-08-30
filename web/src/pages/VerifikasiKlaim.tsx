import { useEffect, useState } from "react";
import { api, type Narrative } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, PreviewBanner, SectionTitle, Spinner, Tile } from "../components/ui";
import { Icon } from "../components/icons";

type VerdictTone = "ok" | "crit" | "muted" | "warn";
const VERDICTS: { label: string; tone: VerdictTone; desc: string }[] = [
  { label: "Didukung", tone: "ok", desc: "Bukti yang ditemukan mendukung klaim." },
  { label: "Dibantah", tone: "crit", desc: "Bukti yang ditemukan membantah klaim." },
  { label: "Tak Cukup Bukti", tone: "muted", desc: "Bukti yang tersedia belum cukup untuk memutuskan." },
  { label: "Bertentangan", tone: "warn", desc: "Bukti yang ditemukan saling bertentangan satu sama lain." },
];

export function VerifikasiKlaim({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [nars, setNars] = useState<Narrative[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => { if (selected) load(); }, [selected]);

  async function load() {
    if (!selected) return;
    setLoading(true);
    try {
      const n = await api.narratives(selected);
      setNars(n);
    } catch { setNars([]); }
    finally { setLoading(false); }
  }

  const sorted = [...nars].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));
  const evidenceTotal = nars.reduce((s, n) => s + (n.evidence_count || 0), 0);
  const empty = !loading && nars.length === 0;

  return (
    <div>
      <PreviewBanner phase="Fase 5">
        Ekstraksi &amp; verifikasi klaim (Graph E) hadir di Fase 5. Di bawah: kandidat klaim NYATA dari narasi + taksonomi verdict yang direncanakan.
      </PreviewBanner>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
        <Button variant="ghost" icon="refresh" onClick={load}>Segarkan</Button>
      </div>

      <div className="grid-stats" style={{ marginBottom: 16 }}>
        <div className="rise rise-1"><Tile label="Kandidat klaim" value={nars.length || "–"} icon="audit" /></div>
        <div className="rise rise-2"><Tile label="Terverifikasi" value={0} icon="reports" /></div>
        <div className="rise rise-3"><Tile label="Menunggu" value={nars.length || "–"} tone="warn" icon="spark" /></div>
        <div className="rise rise-4"><Tile label="Bukti tersedia" value={evidenceTotal} icon="comment" /></div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Card className="rise rise-1" style={{ padding: 18 }}>
          <SectionTitle right={<span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 500 }}>direncanakan · Fase 5</span>}>
            Taksonomi Verdict (AVeriTeC)
          </SectionTitle>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            {VERDICTS.map((v) => (
              <div key={v.label} style={{ padding: 12, borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)" }}>
                <Pill tone={v.tone} dot>{v.label}</Pill>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 9, lineHeight: 1.5 }}>{v.desc}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="rise rise-2" style={{ padding: 18 }}>
          <SectionTitle right={sorted.length > 0 ? <span style={{ fontSize: 11.5, color: "var(--muted)", fontWeight: 500 }}>{sorted.length} narasi · diurutkan berdasarkan skor risiko</span> : undefined}>
            Kandidat Klaim
          </SectionTitle>
          <div style={{ fontSize: 11.5, color: "var(--faint)", marginBottom: 12, lineHeight: 1.5 }}>
            Narasi di bawah adalah kandidat yang diusulkan untuk diverifikasi sebagai klaim. Ekstraksi klaim, pencarian bukti, dan penentuan verdict adalah pekerjaan Fase 5 — belum berjalan.
          </div>

          {loading ? (
            <div style={{ display: "grid", placeItems: "center", padding: "48px 0" }}><Spinner size={24} /></div>
          ) : empty ? (
            <Empty icon="audit">Belum ada narasi untuk investigasi ini — bangun narasi dulu (Agent Monitor).</Empty>
          ) : (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {sorted.map((n, i) => (
                <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderBottom: i < sorted.length - 1 ? "1px solid var(--line-2)" : "none", flexWrap: "wrap" }}>
                  <span className="tnum" style={{ width: 20, fontSize: 12, color: "var(--faint)", fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.label}</div>
                    {n.summary && <div style={{ fontSize: 11.5, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.summary}</div>}
                  </div>
                  <span className="hide-sm tnum" style={{ fontSize: 11, color: "var(--muted)", flexShrink: 0 }}>{n.evidence_count} bukti</span>
                  <Pill tone="muted">Menunggu verifikasi</Pill>
                  <button className="btn btn-ghost" type="button" disabled title="Fase 5" style={{ flexShrink: 0, padding: "6px 12px", fontSize: 12 }}>
                    <Icon name="audit" size={14} /> Verifikasi
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
