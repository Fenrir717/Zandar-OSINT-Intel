// Riset Pasar Geospasial — pilar general: kategori + lokasi → peta kompetitor,
// jarak antar-kompetitor, radius aman (estimasi), ranking sub-zona. Sumber OSM (gratis).
import { useEffect, useState } from "react";
import { api, type MarketCategory, type MarketResult } from "../lib/api";
import { Button, Card, Empty, Field, SectionTitle, Spinner } from "../components/ui";
import { Icon } from "../components/icons";

const DEMAND_COLOR: Record<string, string> = {
  kampus: "var(--info)", "asrama/kos": "var(--violet)", apartemen: "var(--accent)",
};
const RADII = [2000, 3000, 4000, 5000];

export function MarketResearch({ headerSlot }: { headerSlot: (n: React.ReactNode) => void }) {
  const [cats, setCats] = useState<MarketCategory[]>([]);
  const [category, setCategory] = useState("laundry");
  const [location, setLocation] = useState("");
  const [radius, setRadius] = useState(4000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState<MarketResult | null>(null);

  useEffect(() => { headerSlot(null); }, []);
  useEffect(() => {
    api.marketCategories().then((c) => {
      setCats(c);
      if (c.length && !c.some((x) => x.key === "laundry")) setCategory(c[0].key);
    }).catch(() => { /* biarkan default */ });
  }, []);

  async function run() {
    const loc = location.trim();
    if (!loc) { setError("Isi lokasi (kota/kecamatan/alamat)."); return; }
    setBusy(true); setError(""); setRes(null);
    try {
      setRes(await api.marketScan({ category, location: loc, radius_m: radius }));
    } catch (e) {
      setError(e instanceof Error && e.message.includes("404")
        ? "Lokasi tak ditemukan. Coba lebih spesifik (mis. 'Sewon, Bantul, Yogyakarta')."
        : "Gagal mengambil data OSM (sumber gratis kadang sibuk). Coba lagi sebentar.");
    } finally {
      setBusy(false);
    }
  }

  const catNote = cats.find((c) => c.key === category)?.note;

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 13, marginBottom: 16 }}>
        <span style={{ width: 44, height: 44, borderRadius: 12, background: "var(--accent-grad)", display: "grid", placeItems: "center", color: "#fff", flexShrink: 0 }}>
          <Icon name="target" size={22} />
        </span>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, letterSpacing: "-.02em" }}>Riset Pasar Geospasial</h2>
          <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 2 }}>
            Peta kompetitor · jarak aman · radius · sub-zona efektif — dari OpenStreetMap (gratis). General untuk banyak kategori bisnis.
          </div>
        </div>
      </div>

      <Card style={{ padding: 18, marginBottom: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 2fr 1fr auto", gap: 12, alignItems: "end" }} className="market-form">
          <Field label="Kategori bisnis">
            <select className="select" value={category} onChange={(e) => setCategory(e.target.value)} style={{ height: 40 }}>
              {cats.length === 0 && <option value="laundry">Laundry</option>}
              {cats.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
          </Field>
          <Field label="Lokasi" hint="kota / kecamatan / alamat">
            <input className="input" value={location} onChange={(e) => setLocation(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !busy) run(); }}
              placeholder="mis. Sewon, Bantul, Yogyakarta" style={{ height: 40 }} autoFocus />
          </Field>
          <Field label="Radius">
            <select className="select" value={radius} onChange={(e) => setRadius(Number(e.target.value))} style={{ height: 40 }}>
              {RADII.map((r) => <option key={r} value={r}>{r / 1000} km</option>)}
            </select>
          </Field>
          <Button icon="target" onClick={run} disabled={busy}>{busy ? "Menganalisis…" : "Analisis"}</Button>
        </div>
        {catNote && <div style={{ fontSize: 11.5, color: "var(--faint)", marginTop: 10 }}>{catNote}</div>}
        {error && <div style={{ fontSize: 12.5, color: "var(--crit-ink)", marginTop: 10 }}>{error}</div>}
      </Card>

      {busy && (
        <Card style={{ padding: 40 }}>
          <div style={{ display: "grid", placeItems: "center", gap: 12, color: "var(--muted)" }}>
            <Spinner size={26} />
            <div style={{ fontSize: 13 }}>Menarik data OpenStreetMap & menghitung… (bisa 30–90 detik)</div>
          </div>
        </Card>
      )}

      {!busy && !res && (
        <Empty icon="target">Pilih kategori & lokasi, lalu klik Analisis. Contoh: laundry di Sewon, kafe di Tembalang, minimarket di Depok.</Empty>
      )}

      {!busy && res && <MarketReport res={res} />}
    </div>
  );
}

function MarketReport({ res }: { res: MarketResult }) {
  const sp = res.competitors.spacing;
  const dl = res.demand.by_label;
  const loc = res.location;
  const [dl_busy, setDlBusy] = useState(false);
  const [pr_busy, setPrBusy] = useState(false);
  const [dlErr, setDlErr] = useState("");

  async function downloadReport() {
    setDlBusy(true);
    try {
      const { filename, html } = await api.marketReport(res);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { /* abaikan */ } finally { setDlBusy(false); }
  }

  async function downloadPdf() {
    setPrBusy(true); setDlErr("");
    try {
      const blob = await api.marketReportPdf(res);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `riset-pasar-${res.category.key}-${res.location.query.split(",")[0].toLowerCase().replace(/[^a-z0-9]+/g, "-")}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setDlErr("PDF gagal dibuat di server (Chromium/Edge tak tersedia?). Sementara pakai Unduh HTML → cetak dari browser.");
    } finally { setPrBusy(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div style={{ fontSize: 13, color: "var(--muted)" }}>
          Laporan siap — PDF dirender di server (rapi, link bisa diklik, tak tergantung browser):
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <Button variant="ghost" icon="download" onClick={downloadReport} disabled={dl_busy}>
            {dl_busy ? "Menyiapkan…" : "Unduh HTML"}
          </Button>
          <Button icon="reports" onClick={downloadPdf} disabled={pr_busy}>
            {pr_busy ? "Merender PDF…" : "Unduh PDF"}
          </Button>
        </div>
      </div>
      {dlErr && <div style={{ fontSize: 12.5, color: "var(--crit-ink)" }}>{dlErr}</div>}
      <div style={{ padding: "11px 14px", borderRadius: "var(--radius-sm)", background: "var(--warn-soft)", border: "1px solid var(--warn)", color: "var(--warn-ink)", fontSize: 12.5, display: "flex", gap: 9 }}>
        <Icon name="spark" size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        <span><b>Batas bawah, bukan sensus.</b> Cakupan OSM tak lengkap — usaha kecil/informal & banyak kos belum terpetakan. Angka kompetitor = minimum; verifikasi lapangan tetap perlu.</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }} className="grid-3-market">
        <AnswerCard q="#1 · Radius aman" value={`~${(sp.catchment_radius_m / 1000).toFixed(1)} km`}
          unit="katchment ekuivalen tiap kompetitor"
          note={`Patokan: cari titik ≥ ${sp.nn_median.toFixed(0)} m dari kompetitor terdekat (median pasar). Bukan angka universal.`} />
        <AnswerCard q="#3 · Jarak antar-kompetitor" value={`${sp.nn_median.toFixed(0)} m`}
          unit="median jarak ke kompetitor terdekat"
          note={`Sebaran ${sp.pattern} (R=${sp.clark_evans_r}). Rentang ${sp.nn_min.toFixed(0)}–${sp.nn_max.toFixed(0)} m · densitas ${sp.density_km2}/km².`} />
        <AnswerCard q="#2 · Lokasi efektif" value={`${res.best_zones.length} zona`}
          unit="permintaan tinggi × kompetitor renggang"
          note={`Dinilai dari kepadatan pendorong permintaan dibagi kepadatan kompetitor. Peringkat di bawah peta.`} />
      </div>

      <Card style={{ padding: 16 }}>
        <SectionTitle right={<span style={{ fontSize: 12, color: "var(--faint)" }}>utara = atas · arahkan kursor ke titik</span>}>
          Peta pasar — {res.category.label} @ {loc.query.split(",")[0]}
        </SectionTitle>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 190px", gap: 16, alignItems: "start" }} className="map-row">
          <MarketMap res={res} />
          <div style={{ fontSize: 13, color: "var(--muted)", display: "flex", flexDirection: "column", gap: 9 }}>
            <LegItem color="var(--crit)"><b>Kompetitor</b> — {res.competitors.count}</LegItem>
            <LegItem color="var(--info)">Kampus — {dl["kampus"] || 0}</LegItem>
            <LegItem color="var(--violet)">Asrama / kos — {dl["asrama/kos"] || 0}</LegItem>
            <LegItem color="var(--accent)">Apartemen — {dl["apartemen"] || 0}</LegItem>
            <LegItem color="var(--ok)" ring><b>Zona rekomendasi</b></LegItem>
            <div style={{ fontSize: 11.5, color: "var(--faint)" }}>Cincin = jarak 1–{Math.floor(loc.radius_m / 1000)} km dari pusat.</div>
          </div>
        </div>
      </Card>

      <Card style={{ padding: "6px 6px 2px", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: "var(--faint)" }}>
              {["#", "Koordinat", "Skor", "Pendorong ≤600m", "Terdekat", ""].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "8px 10px", borderBottom: "1px solid var(--line)", fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {res.best_zones.map((z, i) => (
              <tr key={i}>
                <td style={td}><span style={{ display: "inline-grid", placeItems: "center", width: 22, height: 22, borderRadius: "50%", background: "var(--ok-soft)", color: "var(--ok-ink)", fontWeight: 700, fontSize: 11 }}>{i + 1}</span></td>
                <td style={{ ...td, fontFamily: "var(--font-mono)" }}>{z.lat.toFixed(5)}, {z.lon.toFixed(5)}</td>
                <td style={{ ...td, fontFamily: "var(--font-mono)", fontWeight: 700 }}>{z.score.toFixed(0)}</td>
                <td style={td}>{Object.entries(z.demand_items).map(([k, v]) => `${k} ×${v}`).join(" · ")}</td>
                <td style={{ ...td, fontFamily: "var(--font-mono)" }}>{z.dist_nearest_comp >= 0 ? `${z.dist_nearest_comp.toFixed(0)} m` : "—"}</td>
                <td style={td}><a href={`https://www.google.com/maps?q=${z.lat},${z.lon}`} target="_blank" rel="noopener" style={{ color: "var(--accent-ink)", textDecoration: "none", fontWeight: 600 }}>peta ↗</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card style={{ padding: 16 }}>
        <SectionTitle>Kompetitor terpetakan · {res.competitors.count}</SectionTitle>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {res.competitors.points.map((p, i) => (
            <span key={i} style={{ fontSize: 12, padding: "3px 10px", borderRadius: 999, background: "var(--surface-2)", border: "1px solid var(--line)" }}>{p.name || "(tanpa nama)"}</span>
          ))}
        </div>
      </Card>

      <div style={{ background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: "var(--radius)", padding: "14px 18px" }}>
        <b style={{ fontSize: 13.5 }}>Catatan jujur & metode</b>
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: "var(--muted)", fontSize: 12.5 }}>
          {res.caveats.map((c, i) => <li key={i} style={{ margin: "5px 0" }}>{c}</li>)}
        </ul>
      </div>
    </div>
  );
}

function MarketMap({ res }: { res: MarketResult }) {
  const VB = 760, CX = 380, CY = 380, ringMax = 340;
  const { lat: lat0, lon: lon0, radius_m: radius } = res.location;
  const sc = ringMax / radius;
  const proj = (lat: number, lon: number): [number, number] => {
    const mx = (lon - lon0) * 111320 * Math.cos((lat0 * Math.PI) / 180);
    const my = (lat - lat0) * 111320;
    return [CX + mx * sc, CY - my * sc];
  };
  const rings: number[] = [];
  for (let km = 1; km * 1000 <= radius; km++) rings.push(km);

  return (
    <svg viewBox={`0 0 ${VB} ${VB}`} role="img" style={{ width: "100%", height: "auto", display: "block", borderRadius: 12, background: "var(--surface-2)" }}
      aria-label={`Peta kompetitor ${res.category.label} dan zona rekomendasi di ${res.location.query}`}>
      {rings.map((km) => {
        const r = km * 1000 * sc;
        return (
          <g key={km}>
            <circle cx={CX} cy={CY} r={r} fill="none" stroke="var(--line)" strokeWidth={1} strokeDasharray="3 5" />
            <text x={CX} y={CY - r - 3} fill="var(--faint)" fontSize={10} textAnchor="middle" fontFamily="var(--font-mono)">{km} km</text>
          </g>
        );
      })}
      {res.demand.points.map((p, i) => {
        const [x, y] = proj(p.lat, p.lon);
        const col = DEMAND_COLOR[p.label || ""] || "var(--info)";
        const rr = 3.2 + (p.weight || 3) * 0.35;
        return <circle key={`d${i}`} cx={x} cy={y} r={rr} fill={col} fillOpacity={0.5} stroke={col} strokeWidth={0.6}><title>{`${p.name || p.label} · ${p.label}`}</title></circle>;
      })}
      {res.competitors.points.map((p, i) => {
        const [x, y] = proj(p.lat, p.lon);
        return <circle key={`c${i}`} cx={x} cy={y} r={5} fill="var(--crit)" stroke="var(--surface)" strokeWidth={1.5}><title>{`${p.name || "(tanpa nama)"} · kompetitor`}</title></circle>;
      })}
      {res.best_zones.map((z, i) => {
        const [x, y] = proj(z.lat, z.lon);
        return (
          <g key={`z${i}`}>
            <circle cx={x} cy={y} r={13} fill="color-mix(in srgb, var(--ok) 20%, transparent)" stroke="var(--ok)" strokeWidth={2} />
            <text x={x} y={y + 4} fill="var(--ok)" fontSize={12} fontWeight={700} textAnchor="middle" fontFamily="var(--font-mono)">{i + 1}</text>
          </g>
        );
      })}
      {(() => { const [x, y] = proj(lat0, lon0); return (
        <g>
          <path d={`M${x} ${y - 8} l5 12 h-10 z`} fill="var(--ink)" stroke="var(--surface)" strokeWidth={1} />
          <text x={x} y={y + 20} fill="var(--muted)" fontSize={10} textAnchor="middle" fontFamily="var(--font-mono)">pusat</text>
        </g>
      ); })()}
    </svg>
  );
}

const td: React.CSSProperties = { padding: "8px 10px", borderBottom: "1px solid var(--line)", verticalAlign: "top" };

function AnswerCard({ q, value, unit, note }: { q: string; value: string; unit: string; note: string }) {
  return (
    <Card style={{ padding: 17 }}>
      <div style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>{q}</div>
      <div className="tnum" style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-.02em", margin: "5px 0 2px" }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "var(--faint)" }}>{unit}</div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 9, paddingTop: 9, borderTop: "1px solid var(--line)" }}>{note}</div>
    </Card>
  );
}

function LegItem({ color, children, ring }: { color: string; children: React.ReactNode; ring?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
      <span style={{ width: 14, height: 14, borderRadius: "50%", flex: "none", background: ring ? "color-mix(in srgb, " + color + " 30%, transparent)" : color, border: ring ? `2px solid ${color}` : "none" }} />
      <span>{children}</span>
    </div>
  );
}
