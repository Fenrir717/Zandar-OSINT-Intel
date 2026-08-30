"""Orchestrator Riset Pasar Geospasial: kategori + lokasi → analisis lengkap.

    python -m geo.market laundry "Sewon, Bantul, Yogyakarta" --radius 4000

GENERAL: `category` apa pun dari geo.catalog; `location` nama tempat apa pun
(digeocode). Radius menentukan area lingkaran analisis.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from geo.analyze import circle_area_km2, grid_zones, spacing_stats
from geo.catalog import get_category
from geo.sources import fetch_pois, geocode


def run_market_research(category_key: str, location: str, radius_m: int = 4000,
                        cell_m: int = 250, score_radius_m: int = 600, top_zones: int = 8) -> dict:
    cat = get_category(category_key)
    place = geocode(location)
    pois = fetch_pois(place.lat, place.lon, radius_m, cat.competitor, cat.demand)

    comps = [p for p in pois if p.kind == "competitor"]
    demand = [p for p in pois if p.kind == "demand"]
    comp_pts = [(p.lat, p.lon) for p in comps]
    demand_pts = [(p.lat, p.lon, p.weight, p.demand_label) for p in demand]

    area = circle_area_km2(radius_m)
    stats = spacing_stats(comp_pts, area)
    zones = grid_zones(place.lat, place.lon, radius_m, comp_pts, demand_pts,
                       cell_m=cell_m, score_radius_m=score_radius_m, top=top_zones)

    # ringkasan pendorong permintaan per label
    demand_by_label: dict = {}
    for p in demand:
        demand_by_label[p.demand_label] = demand_by_label.get(p.demand_label, 0) + 1

    return {
        "category": {"key": cat.key, "label": cat.label, "note": cat.note,
                     "competitor_selectors": cat.competitor},
        "location": {"query": location, "display_name": place.display_name,
                     "lat": place.lat, "lon": place.lon, "radius_m": radius_m,
                     "area_km2": round(area, 3)},
        "competitors": {
            "count": len(comps),
            "spacing": asdict(stats),
            "points": [{"name": p.name or "(tanpa nama)", "lat": p.lat, "lon": p.lon,
                        "selector": p.selector, "osm_id": p.osm_id} for p in comps],
        },
        "demand": {"count": len(demand), "by_label": demand_by_label,
                   "points": [{"name": p.name or "", "lat": p.lat, "lon": p.lon,
                               "label": p.demand_label, "weight": p.weight} for p in demand]},
        "best_zones": [asdict(z) for z in zones],
        "caveats": [
            "Cakupan OpenStreetMap tidak lengkap: usaha kecil/informal (mis. laundry "
            "rumahan tanpa papan) sering belum terpetakan. Angka kompetitor = BATAS BAWAH.",
            "Pendorong permintaan (kos/kampus/hunian) adalah PROKSI dari OSM, bukan data "
            "sensus penduduk; kos tanpa tag tak terhitung.",
            "'Radius aman' bukan angka universal — ia estimasi berbasis densitas & jarak "
            "antar-kompetitor terpetakan, dengan asumsi permintaan tersebar merata.",
        ],
    }


def _fmt(res: dict) -> str:
    c = res["competitors"]; s = c["spacing"]; loc = res["location"]; cat = res["category"]
    lines = [
        f"=== RISET PASAR: {cat['label']} @ {loc['query']} ===",
        f"Area analisis: lingkaran r={loc['radius_m']}m (~{loc['area_km2']} km²) "
        f"pusat {loc['lat']:.4f},{loc['lon']:.4f}",
        f"  {loc['display_name'][:80]}",
        "",
        f"[#3 JARAK ANTAR-KOMPETITOR]  kompetitor terpetakan: {c['count']}",
        f"  densitas: {s['density_km2']} /km²   pola sebaran: {s['pattern']} (R={s['clark_evans_r']})",
        f"  jarak ke tetangga terdekat (NN): min {s['nn_min']}m · p25 {s['nn_p25']}m · "
        f"median {s['nn_median']}m · mean {s['nn_mean']}m · p75 {s['nn_p75']}m · max {s['nn_max']}m",
        "",
        f"[#1 RADIUS AMAN (estimasi)]",
        f"  radius katchment ekuivalen tiap kompetitor: ~{s['catchment_radius_m']}m",
        f"  patokan jarak dari kompetitor terdekat (median NN pasar): ~{s['nn_median']}m",
        "",
        f"[#2 SUB-ZONA PALING EFEKTIF]  (permintaan tinggi × kompetitor renggang)",
    ]
    for i, z in enumerate(res["best_zones"], 1):
        items = ", ".join(f"{k}×{v}" for k, v in z["demand_items"].items())
        gap = f"{z['dist_nearest_comp']}m" if z["dist_nearest_comp"] >= 0 else "tak ada kompetitor dekat"
        lines.append(f"  {i}. {z['lat']:.5f},{z['lon']:.5f}  skor {z['score']} · "
                     f"demand [{items}] · kompetitor≤600m: {z['comp_near']} · terdekat: {gap}")
    lines += ["", "[CATATAN JUJUR]"]
    lines += [f"  - {c}" for c in res["caveats"]]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Riset pasar geospasial (OSM, gratis)")
    ap.add_argument("category", help="kunci kategori (laundry, cafe, resto, minimarket, ...)")
    ap.add_argument("location", help='nama tempat, mis. "Sewon, Bantul, Yogyakarta"')
    ap.add_argument("--radius", type=int, default=4000, help="radius area analisis (m)")
    ap.add_argument("--out", default="", help="tulis hasil JSON ke file")
    args = ap.parse_args()

    res = run_market_research(args.category, args.location, radius_m=args.radius)
    print(_fmt(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print(f"\nJSON → {args.out}")


if __name__ == "__main__":
    main()
