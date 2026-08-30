// Verifikasi Klaim (Fase 5) — verdict DRAF dari Graph E: bukti internal + ground-truth resmi (BPS/BMKG).
import { useEffect, useState } from "react";
import { api, ApiError, type ClaimVerdict } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, Spinner, Tile } from "../components/ui";
import { Icon } from "../components/icons";

type Tone = "ok" | "crit" | "muted" | "warn";
const VERDICT: Record<string, { label: string; tone: Tone }> = {
  supported: { label: "Didukung", tone: "ok" },
  refuted: { label: "Dibantah", tone: "crit" },
  conflicting: { label: "Bertentangan", tone: "warn" },
  insufficient: { label: "Tak Cukup Bukti", tone: "muted" },
};

export function VerifikasiKlaim({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [claims, setClaims] = useState<ClaimVerdict[]>([]);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => {
    if (selected) load(selected);
    else setClaims([]);
  }, [selected]);

  async function load(inv: string) {
    setLoading(true);
    try { setClaims(await api.claims(inv)); }
    catch { setClaims([]); }
    finally { setLoading(false); }
  }

  async function verify() {
    if (!selected || verifying) return;
    setVerifying(true); setNote("");
    try {
      const res = await api.verifyClaims(selected);
      setNote(`Selesai · ${res.claims} klaim dinilai · ${res.with_authoritative} pakai sumber resmi`);
      await load(selected);
    } catch (e) {
      setNote(
        e instanceof ApiError && e.status === 422
          ? "Bangun narasi dulu (AI Analysis / Agent Monitor) sebelum verifikasi klaim."
          : "Gagal memverifikasi klaim.",
      );
    } finally { setVerifying(false); }
  }

  const counts = {
    supported: claims.filter((c) => c.verdict === "supported").length,
    disputed: claims.filter((c) => c.verdict === "refuted" || c.verdict === "conflicting").length,
    withAuth: claims.filter((c) => c.authoritative.length > 0).length,
  };
  const empty = !loading && claims.length === 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ marginRight: "auto", fontSize: 12, color: note.startsWith("Gagal") || note.startsWith("Bangun") ? "var(--crit)" : "var(--muted)" }}>{note}</span>
        <Button variant="ghost" icon="refresh" onClick={() => selected && load(selected)}>Segarkan</Button>
        <Button icon="audit" onClick={verify} disabled={!selected || verifying}>
          {verifying ? "Memverifikasi…" : "Verifikasi Klaim"}
        </Button>
      </div>

      <div style={{ display: "flex", alignItems: "flex-start", gap: 9, padding: "10px 14px", marginBottom: 14, borderRadius: "var(--radius-sm)", background: "var(--surface-2)", border: "1px solid var(--line)", fontSize: 11.5, color: "var(--muted)", lineHeight: 1.5 }}>
        <Icon name="audit" size={15} style={{ flexShrink: 0, marginTop: 1, color: "var(--faint)" }} />
        <span>Verdict adalah <b>penilaian AI berstatus draf</b> — dinilai terhadap bukti terkumpul <b>plus sumber resmi</b> (BPS statistik, BMKG kebencanaan), memakai taksonomi AVeriTeC. Perlu tinjauan analis sebelum dijadikan kesimpulan.</span>
      </div>

      {verifying && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", marginBottom: 14, borderRadius: "var(--radius-sm)", background: "var(--accent-soft)", color: "var(--accent-ink)", fontSize: 12.5 }}>
          <Spinner size={15} /> Graph E menilai klaim vs bukti internal + ground-truth resmi… (±30–60 detik)
        </div>
      )}

      {claims.length > 0 && (
        <div className="grid-stats" style={{ marginBottom: 16 }}>
          <div className="rise rise-1"><Tile label="Klaim dinilai" value={claims.length} icon="audit" /></div>
          <div className="rise rise-2"><Tile label="Didukung" value={counts.supported} icon="reports" tone={undefined} /></div>
          <div className="rise rise-3"><Tile label="Dibantah / bertentangan" value={counts.disputed} icon="target" tone={counts.disputed ? "crit" : undefined} /></div>
          <div className="rise rise-4"><Tile label="Pakai sumber resmi" value={counts.withAuth} icon="spark" /></div>
        </div>
      )}

      {!selected ? (
        <Empty icon="audit">Pilih investigasi untuk memverifikasi klaimnya.</Empty>
      ) : loading && claims.length === 0 ? (
        <div style={{ display: "grid", placeItems: "center", padding: "80px 0" }}><Spinner size={28} /></div>
      ) : empty ? (
        <Empty icon="audit">Belum ada klaim terverifikasi. Klik <b>Verifikasi Klaim</b> untuk menilai narasi terhadap bukti internal &amp; sumber resmi.</Empty>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {claims.map((c, i) => <ClaimCard key={c.id} c={c} delay={(i % 4) + 1} />)}
        </div>
      )}
    </div>
  );
}

function ClaimCard({ c, delay }: { c: ClaimVerdict; delay: number }) {
  const v = c.verdict ? (VERDICT[c.verdict] ?? { label: c.verdict, tone: "muted" as Tone }) : null;
  return (
    <Card className={`rise rise-${delay}`} style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.4 }}>{c.claim}</div>
          {c.narrative_label && (
            <div style={{ fontSize: 11.5, color: "var(--faint)", marginTop: 3, display: "flex", alignItems: "center", gap: 5 }}>
              <Icon name="graph" size={12} />dari narasi: {c.narrative_label}
            </div>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          {v && <Pill tone={v.tone} dot>{v.label}</Pill>}
          {c.review_status === "draft" && <Pill tone="warn">draf</Pill>}
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "10px 0", fontSize: 11.5, color: "var(--muted)" }}>
        {c.veracity != null && (
          <span>Kebenaran (veracity) <b className="tnum" style={{ color: "var(--ink-2)" }}>{Math.round(c.veracity * 100)}%</b></span>
        )}
        {c.confidence != null && (
          <span>Keyakinan <b className="tnum" style={{ color: "var(--ink-2)" }}>{Math.round(c.confidence * 100)}%</b></span>
        )}
      </div>

      {c.rationale && (
        <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--ink-2)", borderLeft: "2px solid var(--line)", paddingLeft: 11, marginBottom: c.authoritative.length ? 10 : 0 }}>
          {c.rationale}
        </div>
      )}

      {c.authoritative.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--faint)" }}>Sumber resmi:</span>
          {c.authoritative.map((a, i) => (
            a.url ? (
              <a key={i} href={a.url} target="_blank" rel="noopener noreferrer" className="badge"
                style={{ color: "var(--accent-ink)", borderColor: "var(--accent)", background: "var(--accent-soft)", textDecoration: "none" }}>
                {a.source.toUpperCase()}{a.title ? ` · ${a.title.slice(0, 32)}` : ""} ↗
              </a>
            ) : (
              <span key={i} className="badge" style={{ color: "var(--accent-ink)", borderColor: "var(--accent)", background: "var(--accent-soft)" }}>
                {a.source.toUpperCase()}{a.title ? ` · ${a.title.slice(0, 32)}` : ""}
              </span>
            )
          ))}
        </div>
      )}
    </Card>
  );
}
