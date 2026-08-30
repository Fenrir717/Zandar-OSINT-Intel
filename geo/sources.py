"""Sumber data geospasial GRATIS: Nominatim (geocode) + Overpass (POI OSM).

Prinsip pemakaian santun: satu query Overpass gabungan (bukan beruntun — memicu
disconnect/rate-limit), retry backoff, User-Agent jelas, endpoint mirror cadangan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

_UA = {"User-Agent": "ZandarOSINT-MarketResearch/0.1 (geospatial market research; contact via app)"}
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


@dataclass
class Place:
    query: str
    display_name: str
    lat: float
    lon: float
    bbox: tuple[float, float, float, float]  # south, north, west, east


@dataclass
class POI:
    osm_id: str
    kind: str            # "competitor" | "demand"
    selector: str        # tag yang mencocokkan (mis. "shop=laundry")
    demand_label: str    # label ramah untuk pendorong permintaan ("kampus"), else ""
    weight: float        # bobot permintaan (0 untuk kompetitor)
    lat: float
    lon: float
    name: str
    tags: dict


def geocode(query: str) -> Place:
    """Nama tempat → koordinat + bbox (Nominatim). 1 request."""
    r = httpx.get(_NOMINATIM, params={"q": query, "format": "json", "limit": 1},
                  headers=_UA, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"Lokasi tak ditemukan: {query!r}")
    o = data[0]
    s, n, w, e = (float(x) for x in o["boundingbox"])  # Nominatim: [S, N, W, E]
    return Place(query=query, display_name=o["display_name"],
                 lat=float(o["lat"]), lon=float(o["lon"]), bbox=(s, n, w, e))


def _selector_filters(selectors: list[str], around: str) -> str:
    """Ubah ["shop=laundry", ...] → blok node/way Overpass ber-around."""
    lines = []
    for sel in selectors:
        key, _, val = sel.partition("=")
        f = f'["{key}"="{val}"]' if val else f'["{key}"]'
        lines.append(f"  node{f}({around});")
        lines.append(f"  way{f}({around});")
    return "\n".join(lines)


def fetch_pois(
    center_lat: float, center_lon: float, radius_m: int,
    competitor_selectors: list[str],
    demand_selectors: list[tuple[str, float, str]],
    timeout_s: int = 90, retries: int = 3,
) -> list[POI]:
    """SATU query Overpass gabungan (kompetitor + permintaan) dalam radius. Klasifikasi
    hasil berdasarkan tag-nya (kompetitor vs pendorong permintaan)."""
    around = f"around:{radius_m},{center_lat},{center_lon}"
    all_sel = list(competitor_selectors) + [s for s, _, _ in demand_selectors]
    body = (
        f"[out:json][timeout:{timeout_s}];\n(\n"
        + _selector_filters(all_sel, around)
        + "\n);\nout center tags;"
    )
    # peta selector kompetitor & permintaan untuk klasifikasi cepat
    comp_set = set(competitor_selectors)
    demand_map = {s: (w, lbl) for s, w, lbl in demand_selectors}

    elements = _post_overpass(body, timeout_s, retries)
    out: list[POI] = []
    for el in elements:
        tags = el.get("tags", {}) or {}
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        sel = _match_selector(tags, comp_set | set(demand_map))
        if sel is None:
            continue
        if sel in comp_set:
            kind, weight, dlabel = "competitor", 0.0, ""
        else:
            kind, (weight, dlabel) = "demand", demand_map[sel]
        out.append(POI(
            osm_id=f"{el.get('type','?')}/{el.get('id','?')}", kind=kind, selector=sel,
            demand_label=dlabel, weight=weight, lat=float(lat), lon=float(lon),
            name=tags.get("name", ""), tags=tags,
        ))
    return out


def _match_selector(tags: dict, selectors: set[str]) -> str | None:
    for sel in selectors:
        key, _, val = sel.partition("=")
        if key in tags and (not val or tags[key] == val):
            return sel
    return None


def _post_overpass(body: str, timeout_s: int, retries: int) -> list[dict]:
    last = ""
    for attempt in range(retries):
        for ep in _OVERPASS:
            try:
                r = httpx.post(ep, data={"data": body}, headers=_UA, timeout=timeout_s + 20)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    return r.json().get("elements", [])
                last = f"{ep} -> HTTP {r.status_code} ({r.text[:80]!r})"
            except Exception as exc:  # disconnect/timeout → coba mirror/retry
                last = f"{ep} -> {type(exc).__name__}: {exc}"
        time.sleep(2 + attempt * 3)  # backoff sopan sebelum ronde berikut
    raise RuntimeError(f"Overpass gagal setelah {retries} ronde. Terakhir: {last}")
