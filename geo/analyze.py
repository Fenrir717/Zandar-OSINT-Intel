"""Analisis geospasial murni (tanpa IO): jarak, nearest-neighbour, densitas,
radius katchment, dan skoring sub-zona (grid). Semua fungsi determinsitik & teruji
lewat run nyata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, median

_R_EARTH = 6371000.0  # meter


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _R_EARTH * math.asin(math.sqrt(a))


def _pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = q * (len(sorted_vals) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def nearest_neighbour_dists(points: list[tuple[float, float]]) -> list[float]:
    """Untuk tiap titik, jarak (m) ke titik terdekat lainnya. O(n^2) — cukup untuk
    ratusan POI."""
    out = []
    for i, (la, lo) in enumerate(points):
        best = math.inf
        for j, (lb, ln) in enumerate(points):
            if i == j:
                continue
            d = haversine(la, lo, lb, ln)
            if d < best:
                best = d
        if best != math.inf:
            out.append(best)
    return out


@dataclass
class SpacingStats:
    n: int
    area_km2: float
    density_km2: float
    nn_min: float
    nn_p25: float
    nn_median: float
    nn_mean: float
    nn_p75: float
    nn_max: float
    clark_evans_r: float          # <1 mengelompok, ~1 acak, >1 menyebar
    pattern: str
    catchment_radius_m: float     # radius ekuivalen "wilayah" tiap kompetitor


def spacing_stats(comp_points: list[tuple[float, float]], area_km2: float) -> SpacingStats:
    n = len(comp_points)
    nn = sorted(nearest_neighbour_dists(comp_points)) if n >= 2 else []
    density = n / area_km2 if area_km2 > 0 else 0.0
    # Clark-Evans: R = mean_NN_obs / mean_NN_exp ; exp = 1/(2*sqrt(density_per_m2))
    dens_m2 = n / (area_km2 * 1_000_000) if area_km2 > 0 else 0.0
    r_ce = 0.0
    if nn and dens_m2 > 0:
        exp = 1 / (2 * math.sqrt(dens_m2))
        r_ce = mean(nn) / exp if exp > 0 else 0.0
    pattern = ("mengelompok (klaster)" if r_ce and r_ce < 0.85
               else "menyebar merata" if r_ce > 1.15
               else "acak/seimbang")
    catchment = math.sqrt((area_km2 / n) / math.pi) * 1000 if n else 0.0
    return SpacingStats(
        n=n, area_km2=round(area_km2, 3), density_km2=round(density, 3),
        nn_min=round(nn[0], 1) if nn else 0.0,
        nn_p25=round(_pct(nn, 0.25), 1) if nn else 0.0,
        nn_median=round(median(nn), 1) if nn else 0.0,
        nn_mean=round(mean(nn), 1) if nn else 0.0,
        nn_p75=round(_pct(nn, 0.75), 1) if nn else 0.0,
        nn_max=round(nn[-1], 1) if nn else 0.0,
        clark_evans_r=round(r_ce, 3), pattern=pattern,
        catchment_radius_m=round(catchment, 1),
    )


@dataclass
class Zone:
    lat: float
    lon: float
    demand: float               # skor permintaan berbobot dalam score_radius
    demand_items: dict          # label → hitung (mis. {"kampus":2,"asrama/kos":5})
    comp_near: int              # kompetitor dalam score_radius
    dist_nearest_comp: float    # m ke kompetitor terdekat (inf → tak ada)
    score: float


def grid_zones(
    center_lat: float, center_lon: float, radius_m: int,
    comp_points: list[tuple[float, float]],
    demand_points: list[tuple[float, float, float, str]],  # lat,lon,weight,label
    cell_m: int = 250, score_radius_m: int = 600, top: int = 8,
) -> list[Zone]:
    """Grid dalam lingkaran (center,radius). Skor sub-zona = permintaan berbobot /
    (1 + kompetitor dekat). Non-max suppression agar top-zona tak menumpuk."""
    dlat = cell_m / 111_320
    dlon = cell_m / (111_320 * math.cos(math.radians(center_lat)))
    steps_lat = int(radius_m / cell_m) + 1
    steps_lon = int(radius_m / cell_m) + 1

    cells: list[Zone] = []
    for i in range(-steps_lat, steps_lat + 1):
        for j in range(-steps_lon, steps_lon + 1):
            la = center_lat + i * dlat
            lo = center_lon + j * dlon
            if haversine(center_lat, center_lon, la, lo) > radius_m:
                continue
            demand = 0.0
            items: dict = {}
            for dla, dlo, w, lbl in demand_points:
                if haversine(la, lo, dla, dlo) <= score_radius_m:
                    demand += w
                    items[lbl] = items.get(lbl, 0) + 1
            if demand <= 0:
                continue  # tak ada pendorong permintaan → lewati (bukan kandidat)
            comp_near = 0
            nearest = math.inf
            for cla, clo in comp_points:
                d = haversine(la, lo, cla, clo)
                if d <= score_radius_m:
                    comp_near += 1
                if d < nearest:
                    nearest = d
            score = demand / (1 + comp_near)
            cells.append(Zone(round(la, 6), round(lo, 6), round(demand, 2), items,
                              comp_near, round(nearest, 1) if nearest != math.inf else -1.0,
                              round(score, 3)))

    cells.sort(key=lambda z: z.score, reverse=True)
    # non-max suppression: buang kandidat < score_radius dari kandidat lebih tinggi
    picked: list[Zone] = []
    for z in cells:
        if all(haversine(z.lat, z.lon, p.lat, p.lon) > score_radius_m for p in picked):
            picked.append(z)
        if len(picked) >= top:
            break
    return picked


def circle_area_km2(radius_m: int) -> float:
    return math.pi * (radius_m / 1000) ** 2
