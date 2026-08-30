// Reports (Fase 4) — laporan intelijen ber-sitasi dari Graph D (nyata, bukan pratinjau).
import { useEffect, useState } from "react";
import { api, ApiError, type ReportContent, type ReportDoc, type ReportMeta } from "../lib/api";
import { InvestigationPicker, useInvestigations } from "../lib/useInvestigations";
import { Button, Card, Empty, Pill, Spinner } from "../components/ui";
import { Icon } from "../components/icons";

export function Reports({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const { list, selected, choose } = useInvestigations();
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [active, setActive] = useState<ReportContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => { headerSlot(<InvestigationPicker list={list} selected={selected} onChange={choose} />); }, [list, selected]);
  useEffect(() => {
    if (selected) loadList(selected);
    else { setReports([]); setActive(null); }
  }, [selected]);

  async function loadList(inv: string, openId?: string) {
    setLoading(true);
    try {
      const r = await api.reports(inv);
      setReports(r);
      const target = openId || (r.length ? r[0].id : null);
      if (target) openReport(target); else setActive(null);
    } catch { setReports([]); setActive(null); }
    finally { setLoading(false); }
  }

  async function openReport(id: string) {
    if (active?.id === id) return;
    try { setActive(await api.report(id)); }
    catch { setActive(null); }
  }

  async function build() {
    if (!selected || building) return;
    setBuilding(true); setNote("");
    try {
      const res = await api.buildReport(selected);
      setNote(`Laporan dibuat · ${res.sections} bagian · ${res.cited_sources} sitasi`);
      await loadList(selected, res.report_id);
    } catch (e) {
      setNote(
        e instanceof ApiError && e.status === 422
          ? "Bangun narasi dulu (halaman AI Analysis / Agent Monitor) sebelum menyusun laporan."
          : "Gagal membuat laporan.",
      );
    } finally { setBuilding(false); }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {note && <span style={{ fontSize: 12, color: note.startsWith("Gagal") || note.startsWith("Bangun") ? "var(--crit)" : "var(--muted)", marginRight: "auto" }}>{note}</span>}
        {!note && <span style={{ marginRight: "auto" }} />}
        <Button variant="ghost" icon="download" onClick={() => window.print()} disabled={!active?.content}>Ekspor PDF</Button>
        <Button variant="ghost" icon="refresh" onClick={() => selected && loadList(selected)}>Segarkan</Button>
        <Button icon="reports" onClick={build} disabled={!selected || building}>
          {building ? "Menyusun…" : "Bangun Laporan"}
        </Button>
      </div>

      {building && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", marginBottom: 14, borderRadius: "var(--radius-sm)", background: "var(--accent-soft)", color: "var(--accent-ink)", fontSize: 12.5 }}>
          <Spinner size={15} /> Graph D menyusun laporan ber-sitasi dari narasi & bukti… (±15–30 detik)
        </div>
      )}

      {!selected ? (
        <Empty icon="reports">Pilih investigasi untuk melihat atau menyusun laporan.</Empty>
      ) : loading && reports.length === 0 ? (
        <div style={{ display: "grid", placeItems: "center", padding: "80px 0" }}><Spinner size={28} /></div>
      ) : reports.length === 0 ? (
        <Empty icon="reports">Belum ada laporan. Klik <b>Bangun Laporan</b> untuk membuat laporan intelijen ber-sitasi dari narasi investigasi ini.</Empty>
      ) : (
        <div className="grid-split" style={{ display: "grid", gridTemplateColumns: "270px 1fr", gap: 16, alignItems: "start" }}>
          <Card className="rise rise-1" style={{ padding: 8 }}>
            {reports.map((r) => (
              <button key={r.id} type="button" onClick={() => openReport(r.id)}
                className={`nav-item${active?.id === r.id ? " active" : ""}`}
                style={{ display: "block", width: "100%", textAlign: "left", fontSize: 12.5, padding: "10px 12px", borderRadius: 9, border: "none", background: active?.id === r.id ? "var(--accent-soft)" : "transparent", cursor: "pointer" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon name="reports" size={14} />
                  <span style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {r.created_at ? new Date(r.created_at).toLocaleString("id", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "Laporan"}
                  </span>
                </div>
                <div style={{ marginTop: 5, display: "flex", gap: 5 }}>
                  <Pill tone={r.status === "final" ? "ok" : "muted"}>{r.status}</Pill>
                  <Pill tone="warn">{r.classification}</Pill>
                </div>
              </button>
            ))}
          </Card>

          <Card className="rise rise-2 report-print" style={{ padding: 20 }}>
            {active?.content ? <ReportView doc={active.content} meta={active} />
              : <div style={{ display: "grid", placeItems: "center", padding: 40 }}><Spinner size={24} /></div>}
          </Card>
        </div>
      )}
    </div>
  );
}

function ReportView({ doc, meta }: { doc: ReportDoc; meta: ReportContent }) {
  return (
    <div>
      <div style={{ marginBottom: 18, borderBottom: "1px solid var(--line)", paddingBottom: 14 }}>
        <h2 style={{ margin: 0, fontSize: 19, lineHeight: 1.3 }}>{doc.title}</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginTop: 8 }}>
          <Pill tone="warn">{meta.classification}</Pill>
          <Pill tone={meta.status === "final" ? "ok" : "muted"}>{meta.status}</Pill>
          {meta.created_at && <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{new Date(meta.created_at).toLocaleString("id", { dateStyle: "medium", timeStyle: "short" })}</span>}
          <span style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--faint)" }}>{doc.meta?.cited_sources ?? doc.citations.length} sitasi · {doc.meta?.narratives ?? "–"} narasi</span>
        </div>
      </div>

      {doc.sections.map((s, i) => (
        <section key={i} style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 15, margin: "0 0 8px", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--accent)" }}><Icon name="target" size={15} /></span>{s.heading}
          </h3>
          {renderBody(s.body)}
        </section>
      ))}

      {doc.citations.length > 0 && (
        <section style={{ marginTop: 6, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
          <h3 style={{ fontSize: 14, margin: "0 0 10px", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--accent)" }}><Icon name="audit" size={15} /></span>Sumber ({doc.citations.length})
          </h3>
          <ol style={{ margin: 0, paddingLeft: 22, display: "flex", flexDirection: "column", gap: 9 }}>
            {doc.citations.map((c) => (
              <li key={c.n} id={`cit-${c.n}`} value={c.n} style={{ fontSize: 12, color: "var(--muted)" }}>
                <span style={{ fontWeight: 600, color: "var(--ink-2)" }}>{c.platform || "sumber"}</span>
                {c.published_at && <span> · {new Date(c.published_at).toLocaleDateString("id")}</span>}
                {c.snippet && <div style={{ fontSize: 11.5, lineHeight: 1.5, margin: "2px 0" }}>{c.snippet}</div>}
                {c.url && <a href={c.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 4 }}>buka sumber ↗</a>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

// Render body: paragraf + token sitasi [n] jadi tautan superskrip ke daftar sumber.
function renderBody(body: string) {
  return body.split(/\n{2,}|\n/).filter((p) => p.trim()).map((para, pi) => (
    <p key={pi} style={{ fontSize: 13, lineHeight: 1.7, color: "var(--ink-2)", margin: "0 0 12px" }}>
      {para.split(/(\[\d+\])/).map((seg, si) => {
        const m = seg.match(/^\[(\d+)\]$/);
        if (m) return (
          <a key={si} href={`#cit-${m[1]}`} style={{ fontSize: 10, verticalAlign: "super", fontWeight: 700, color: "var(--accent)", textDecoration: "none", padding: "0 1px" }}>[{m[1]}]</a>
        );
        return <span key={si}>{seg}</span>;
      })}
    </p>
  ));
}
