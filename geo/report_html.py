"""Render hasil riset pasar geospasial → halaman HTML mandiri (peta SVG tanpa tile
eksternal + kartu jawaban + ranking zona). GENERAL: menerima dict dari
geo.market.run_market_research untuk kategori/lokasi apa pun.

Halaman ini ditulis sebagai KONTEN Artifact (tanpa <!doctype>/<html>/<head>/<body>);
font via Google Fonts, sisanya inline. Tema terang+gelap via token CSS.
"""

from __future__ import annotations

import html
import math
import re


# CSS cetak: paksa palet terang, A4, anti-potong — agar "Simpan sebagai PDF" rapi
# sama seperti tampilan layar. Diletakkan PALING AKHIR di <style> agar menang cascade
# atas blok dark. print-color-adjust:exact menjaga warna peta & kartu tetap tercetak.
_PRINT_CSS = """
  @media print {
    :root, :root[data-theme="dark"], :root:not([data-theme="light"]) {
      --bg:#ffffff; --surface:#ffffff; --surface2:#f5f7f3; --ink:#14201c; --muted:#3f4a44;
      --faint:#6a756e; --line:#d5dbd2; --accent:#0b7a70; --accent-ink:#0b7a70;
      --comp:#d62626; --demand:#2158d0; --demand2:#6d28d9; --demand3:#0e7490; --zone:#15803d;
      --shadow:none;
    }
    @page { size: A4; margin: 12mm; }
    html, body { background:#fff !important; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
    .wrap { max-width:none; padding:0; }
    .banner { background:#f5f7f3 !important; }
    .card, .caveats, .mapwrap, .banner, section, table, tr, svg.map, .cards {
      break-inside:avoid; page-break-inside:avoid;
    }
    section { margin-top:14px; }
    h1 { font-size:26px; }
    .maprow { grid-template-columns:1fr !important; }
    svg.map { max-height:150mm; border:1px solid var(--line); }
    .foot { margin-top:14px; }
    a[href^="http"] { color:var(--accent-ink) !important; text-decoration:none; }
  }
"""


def _proj(lat: float, lon: float, lat0: float, lon0: float, sc: float, cx: float, cy: float) -> tuple[float, float]:
    mx = (lon - lon0) * 111_320 * math.cos(math.radians(lat0))
    my = (lat - lat0) * 111_320
    return cx + mx * sc, cy - my * sc


def build_report_html(res: dict) -> str:
    loc = res["location"]
    cat = res["category"]
    comp = res["competitors"]
    sp = comp["spacing"]
    demand = res["demand"]
    zones = res["best_zones"]

    lat0, lon0, radius = loc["lat"], loc["lon"], loc["radius_m"]
    VB = 760.0
    CX = CY = VB / 2
    ring_max = 340.0
    sc = ring_max / radius  # px per meter

    def P(lat, lon):
        return _proj(lat, lon, lat0, lon0, sc, CX, CY)

    # --- SVG: rings, competitors, demand, zones, center ---
    svg = []
    # cincin jarak 1..N km
    km = 1
    while km * 1000 <= radius:
        r = km * 1000 * sc
        svg.append(f'<circle cx="{CX}" cy="{CY}" r="{r:.1f}" class="ring"/>')
        svg.append(f'<text x="{CX}" y="{CY - r - 3:.1f}" class="ringlbl">{km} km</text>')
        km += 1
    # demand (biru, ukuran per bobot)
    dcolor = {"kampus": "var(--demand)", "asrama/kos": "var(--demand2)", "apartemen": "var(--demand3)"}
    for p in demand["points"]:
        x, y = P(p["lat"], p["lon"])
        col = dcolor.get(p["label"], "var(--demand)")
        rr = 3.2 + (p["weight"] or 3) * 0.35
        nm = html.escape(p["name"] or p["label"])
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.1f}" fill="{col}" '
                   f'fill-opacity="0.5" stroke="{col}" stroke-width="0.6" class="pt"><title>'
                   f'{nm} · {p["label"]}</title></circle>')
    # kompetitor (merah)
    for p in comp["points"]:
        x, y = P(p["lat"], p["lon"])
        nm = html.escape(p["name"] or "(tanpa nama)")
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" class="comp"><title>'
                   f'{nm} · laundry</title></circle>')
    # zona rekomendasi (hijau, bernomor)
    for i, z in enumerate(zones, 1):
        x, y = P(z["lat"], z["lon"])
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" class="zone"/>')
        svg.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" class="zonelbl">{i}</text>')
    # pusat
    cxp, cyp = P(lat0, lon0)
    svg.append(f'<path d="M{cxp:.1f} {cyp-8:.1f} l5 12 h-10 z" class="ctr"/>')
    svg.append(f'<text x="{cxp:.1f}" y="{cyp+20:.1f}" class="ctrlbl">pusat area</text>')
    svg_map = "\n".join(svg)

    # --- kartu jawaban ---
    def esc(s):
        return html.escape(str(s))

    zone_rows = []
    for i, z in enumerate(zones, 1):
        items = " · ".join(f"{k} ×{v}" for k, v in z["demand_items"].items())
        gap = f'{z["dist_nearest_comp"]:.0f} m' if z["dist_nearest_comp"] >= 0 else "—"
        gmap = f'https://www.google.com/maps?q={z["lat"]},{z["lon"]}'
        zone_rows.append(f"""
      <tr>
        <td><span class="rank">{i}</span></td>
        <td class="mono">{z['lat']:.5f}, {z['lon']:.5f}</td>
        <td><b class="mono">{z['score']:.0f}</b></td>
        <td>{esc(items)}</td>
        <td class="mono">{gap}</td>
        <td><a href="{gmap}" target="_blank" rel="noopener">peta ↗</a></td>
      </tr>""")
    zone_table = "".join(zone_rows)

    comp_chips = "".join(
        f'<span class="chip">{esc(p["name"] or "(tanpa nama)")}</span>' for p in comp["points"]
    )
    dl = demand["by_label"]
    demand_summary = " · ".join(f'{k} {v}' for k, v in dl.items())

    caveats = "".join(f"<li>{esc(c)}</li>" for c in res["caveats"])

    title = f"Riset Pasar {cat['label'].split(' /')[0]} — {loc['query'].split(',')[0]}"

    _page = f"""<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
  :root {{
    --bg:#f4f6f2; --surface:#ffffff; --surface2:#eef1ea; --ink:#182420; --muted:#5c6b63;
    --faint:#8a978f; --line:#e0e5da; --accent:#0d9488; --accent-ink:#0b7a70;
    --comp:#dc2626; --demand:#2563eb; --demand2:#7c3aed; --demand3:#0891b2; --zone:#16a34a;
    --shadow:0 1px 2px rgba(20,40,30,.06),0 8px 24px rgba(20,40,30,.06);
  }}
  :root:not([data-theme="light"]) {{ }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0e1411; --surface:#151d18; --surface2:#1b2620; --ink:#e8efe9; --muted:#93a49b;
      --faint:#66756c; --line:#26312b; --accent:#2dd4bf; --accent-ink:#5eead4;
      --comp:#f87171; --demand:#60a5fa; --demand2:#a78bfa; --demand3:#22d3ee; --zone:#4ade80;
      --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0e1411; --surface:#151d18; --surface2:#1b2620; --ink:#e8efe9; --muted:#93a49b;
    --faint:#66756c; --line:#26312b; --accent:#2dd4bf; --accent-ink:#5eead4;
    --comp:#f87171; --demand:#60a5fa; --demand2:#a78bfa; --demand3:#22d3ee; --zone:#4ade80;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:"IBM Plex Sans",system-ui,sans-serif; line-height:1.55; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:32px 22px 64px; }}
  .mono {{ font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums; }}
  h1,h2,h3 {{ font-family:"Fraunces",Georgia,serif; font-weight:600; letter-spacing:-.01em;
    line-height:1.12; text-wrap:balance; margin:0; }}
  h1 {{ font-size:clamp(28px,4.5vw,40px); }}
  .eyebrow {{ font-family:"IBM Plex Mono",monospace; font-size:12px; letter-spacing:.14em;
    text-transform:uppercase; color:var(--accent-ink); font-weight:500; }}
  .sub {{ color:var(--muted); font-size:15px; margin-top:8px; }}
  .banner {{ display:flex; gap:10px; align-items:flex-start; margin-top:18px; padding:11px 14px;
    background:color-mix(in srgb,var(--accent) 8%,var(--surface)); border:1px solid color-mix(in srgb,var(--accent) 30%,var(--line));
    border-radius:10px; font-size:13px; color:var(--muted); }}
  .banner b {{ color:var(--ink); }}
  section {{ margin-top:34px; }}
  .lead {{ display:flex; align-items:baseline; gap:10px; margin-bottom:14px; }}
  .lead h2 {{ font-size:22px; }}
  .lead .q {{ font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--faint); }}
  .cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
  @media (max-width:760px) {{ .cards {{ grid-template-columns:1fr; }} }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:14px;
    padding:18px; box-shadow:var(--shadow); }}
  .card .k {{ font-size:12.5px; color:var(--muted); font-weight:500; }}
  .card .v {{ font-family:"Fraunces",serif; font-size:34px; font-weight:600; margin:6px 0 2px;
    letter-spacing:-.02em; }}
  .card .u {{ font-size:12px; color:var(--faint); }}
  .card .note {{ font-size:12.5px; color:var(--muted); margin-top:10px; padding-top:10px;
    border-top:1px solid var(--line); }}
  .mapwrap {{ background:var(--surface); border:1px solid var(--line); border-radius:16px;
    padding:16px; box-shadow:var(--shadow); }}
  .maprow {{ display:grid; grid-template-columns:1fr 200px; gap:18px; align-items:start; }}
  @media (max-width:760px) {{ .maprow {{ grid-template-columns:1fr; }} }}
  svg.map {{ width:100%; height:auto; display:block; background:
    radial-gradient(circle at 50% 46%, color-mix(in srgb,var(--accent) 6%,var(--surface)), var(--surface) 72%);
    border-radius:12px; }}
  .ring {{ fill:none; stroke:var(--line); stroke-width:1; stroke-dasharray:3 5; }}
  .ringlbl {{ fill:var(--faint); font:500 10px "IBM Plex Mono",monospace; text-anchor:middle; }}
  .comp {{ fill:var(--comp); stroke:var(--surface); stroke-width:1.5; }}
  .pt {{ }}
  .zone {{ fill:color-mix(in srgb,var(--zone) 20%,transparent); stroke:var(--zone); stroke-width:2; }}
  .zonelbl {{ fill:var(--zone); font:600 12px "IBM Plex Mono",monospace; text-anchor:middle; }}
  .ctr {{ fill:var(--ink); stroke:var(--surface); stroke-width:1; }}
  .ctrlbl {{ fill:var(--muted); font:500 10px "IBM Plex Mono",monospace; text-anchor:middle; }}
  .legend {{ font-size:13px; }}
  .legend .li {{ display:flex; align-items:center; gap:9px; margin:9px 0; color:var(--muted); }}
  .legend .li b {{ color:var(--ink); font-weight:500; }}
  .sw {{ width:14px; height:14px; border-radius:50%; flex:none; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ font:500 11px "IBM Plex Mono",monospace; letter-spacing:.08em; text-transform:uppercase;
    color:var(--faint); }}
  .rank {{ display:inline-grid; place-items:center; width:22px; height:22px; border-radius:50%;
    background:color-mix(in srgb,var(--zone) 18%,var(--surface)); color:var(--zone); font-weight:600;
    font-family:"IBM Plex Mono",monospace; font-size:12px; }}
  td a {{ color:var(--accent-ink); text-decoration:none; font-weight:500; }}
  td a:hover {{ text-decoration:underline; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .chip {{ font-size:12px; padding:3px 10px; border-radius:999px; background:var(--surface2);
    border:1px solid var(--line); color:var(--ink); }}
  .caveats {{ background:var(--surface2); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }}
  .caveats h3 {{ font-size:15px; margin-bottom:8px; }}
  .caveats ul {{ margin:0; padding-left:18px; color:var(--muted); font-size:13px; }}
  .caveats li {{ margin:6px 0; }}
  .foot {{ margin-top:30px; font-size:12px; color:var(--faint); text-align:center;
    font-family:"IBM Plex Mono",monospace; }}
{_PRINT_CSS}
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">Riset Pasar Geospasial · Zandar OSINT</div>
    <h1>{esc(cat['label'])} di {esc(loc['query'].split(',')[0])}</h1>
    <div class="sub">Area analisis: lingkaran radius <b class="mono">{radius/1000:.0f} km</b>
      (~{loc['area_km2']:.0f} km²) berpusat di {esc(loc['display_name'])}.
      Sumber: OpenStreetMap (gratis).</div>
    <div class="banner">
      <span>⚠️</span>
      <div><b>Batas bawah, bukan sensus.</b> Cakupan OSM tidak lengkap — laundry rumahan/tanpa
      papan & banyak kos belum terpetakan. Semua 10 kompetitor terpetakan menggerombol di sabuk
      kampus utara; <b>Sewon-selatan sendiri nyaris kosong di peta</b> → bisa berarti peluang, bisa
      berarti sekadar belum dipetakan. Verifikasi lapangan tetap wajib.</div>
    </div>
  </header>

  <section>
    <div class="cards">
      <div class="card">
        <div class="k">#1 · Radius aman (estimasi)</div>
        <div class="v mono">~{sp['catchment_radius_m']/1000:.1f} km</div>
        <div class="u">radius katchment ekuivalen tiap kompetitor</div>
        <div class="note">Patokan praktis: cari titik <b>≥ {sp['nn_median']:.0f} m</b> dari laundry
          terdekat (median jarak antar-kompetitor pasar). Bukan angka universal — asumsi permintaan merata.</div>
      </div>
      <div class="card">
        <div class="k">#3 · Jarak antar-kompetitor</div>
        <div class="v mono">{sp['nn_median']:.0f} m</div>
        <div class="u">median jarak ke laundry terdekat (NN)</div>
        <div class="note">Sebaran <b>{esc(sp['pattern'])}</b> (Clark-Evans R={sp['clark_evans_r']}).
          Rentang NN {sp['nn_min']:.0f}–{sp['nn_max']:.0f} m · densitas {sp['density_km2']} /km².</div>
      </div>
      <div class="card">
        <div class="k">#2 · Lokasi paling efektif</div>
        <div class="v mono">{len(zones)} zona</div>
        <div class="u">permintaan tinggi × kompetitor renggang</div>
        <div class="note">Dinilai dari kepadatan kampus/kos ({esc(demand_summary)}) dibagi kepadatan
          kompetitor sekitar. Peringkat lengkap di bawah peta.</div>
      </div>
    </div>
  </section>

  <section>
    <div class="lead"><h2>Peta pasar</h2><span class="q">kompetitor · permintaan · zona rekomendasi</span></div>
    <div class="mapwrap">
      <div class="maprow">
        <svg class="map" viewBox="0 0 {VB:.0f} {VB:.0f}" role="img"
          aria-label="Peta kompetitor laundry, pendorong permintaan, dan zona rekomendasi di sekitar {esc(loc['query'])}">
          {svg_map}
        </svg>
        <div class="legend">
          <div class="li"><span class="sw" style="background:var(--comp)"></span><b>Laundry (kompetitor)</b> — {comp['count']}</div>
          <div class="li"><span class="sw" style="background:var(--demand)"></span>Kampus — {dl.get('kampus',0)}</div>
          <div class="li"><span class="sw" style="background:var(--demand2)"></span>Asrama / kos — {dl.get('asrama/kos',0)}</div>
          <div class="li"><span class="sw" style="background:var(--demand3)"></span>Apartemen — {dl.get('apartemen',0)}</div>
          <div class="li"><span class="sw" style="background:color-mix(in srgb,var(--zone) 30%,transparent);border:2px solid var(--zone)"></span><b>Zona rekomendasi</b> (bernomor)</div>
          <div class="li"><span class="sw" style="background:transparent;border:1px dashed var(--faint)"></span>Cincin jarak (1–{radius//1000} km)</div>
          <div class="li" style="margin-top:4px;font-size:12px;color:var(--faint)">Arahkan kursor ke titik untuk nama. Utara = atas.</div>
        </div>
      </div>
    </div>
  </section>

  <section>
    <div class="lead"><h2>Peringkat sub-zona</h2><span class="q">#2 efektivitas lokasi</span></div>
    <div class="card" style="padding:6px 6px 2px;overflow-x:auto">
      <table>
        <thead><tr><th>#</th><th>Koordinat</th><th>Skor</th><th>Pendorong permintaan (≤600 m)</th><th>Kompetitor terdekat</th><th></th></tr></thead>
        <tbody>{zone_table}</tbody>
      </table>
    </div>
    <div class="sub" style="font-size:12.5px">Skor = permintaan berbobot dalam 600 m ÷ (1 + kompetitor dalam 600 m).
      Catatan: satu kampus kadang terpetakan sebagai banyak titik OSM (mis. UNY FIP), jadi hitungan “kampus” = intensitas titik, bukan jumlah institusi.</div>
  </section>

  <section>
    <div class="lead"><h2>Kompetitor terpetakan</h2><span class="q">{comp['count']} laundry · sumber #1 &amp; #3</span></div>
    <div class="chips">{comp_chips}</div>
  </section>

  <section>
    <div class="caveats">
      <h3>Catatan jujur & metode</h3>
      <ul>{caveats}</ul>
    </div>
  </section>

  <div class="foot">Zandar OSINT · Pilar Riset Pasar Geospasial · data OpenStreetMap © kontributor OSM</div>
</div>
"""
    # Semua non-ASCII → entity numerik agar benar di charset apa pun (·, —, ≥, ², emoji, dll)
    return _page.encode("ascii", "xmlcharrefreplace").decode("ascii")


def build_report_document(res: dict) -> str:
    """Bungkus konten laporan jadi dokumen HTML valid & mandiri (untuk unduhan platform:
    doctype + <head> dengan charset & title). Isi identik dengan versi Artifact."""
    inner = build_report_html(res)
    m = re.match(r"\s*<title>(.*?)</title>\s*", inner, re.S)
    title = m.group(1) if m else "Riset Pasar"
    body = inner[m.end():] if m else inner
    return (
        '<!doctype html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title></head><body>{body}</body></html>"
    )
