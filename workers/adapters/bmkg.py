"""Adapter BMKG — data gempa resmi (ground truth) via API publik.

Publik, tanpa key, sangat andal. Ground truth untuk verifikasi klaim bencana:
narasi "gempa besar M8 di X" → cek fakta BMKG. Tiap gempa jadi dokumen berlabel
platform="bmkg" (sumber otoritatif).

query = {
    "feed": "gempaterkini",     # autogempa (1 terkini) | gempaterkini (15) | gempadirasakan
    "min_magnitude": 5.0,       # opsional
    "keywords": ["jawa"],       # opsional filter wilayah
}
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from workers.adapters.base import BaseAdapter, RawItem

BASE = "https://data.bmkg.go.id/DataMKG/TEWS"
_FEEDS = {"autogempa", "gempaterkini", "gempadirasakan"}


class BMKGAdapter(BaseAdapter):
    platform = "bmkg"
    key = "bmkg"
    tier = "free"
    requires_credentials = False
    rate_note = "API publik BMKG tanpa key; data gempa (terkini/dirasakan)."
    legal_note = "Data resmi BMKG. Sumber otoritatif untuk verifikasi klaim bencana."

    def collect(self, query: dict) -> Iterator[RawItem]:
        feed = query.get("feed", "gempaterkini")
        if feed not in _FEEDS:
            feed = "gempaterkini"
        min_mag = float(query.get("min_magnitude", 0))
        keywords = [k.lower() for k in query.get("keywords", [])]

        try:
            resp = httpx.get(f"{BASE}/{feed}.json", timeout=30, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return

        gempa = data.get("Infogempa", {}).get("gempa")
        events = [gempa] if isinstance(gempa, dict) else (gempa or [])

        for ev in events:
            try:
                mag = float(ev.get("Magnitude", 0))
            except (ValueError, TypeError):
                mag = 0.0
            if mag < min_mag:
                continue
            wilayah = str(ev.get("Wilayah", "")).strip()
            dt = ev.get("DateTime")
            if not wilayah or not dt:
                continue

            parts = [
                f"Gempa Magnitudo {ev.get('Magnitude')} di {wilayah}",
                f"pada {ev.get('Tanggal')} {ev.get('Jam')}",
                f"kedalaman {ev.get('Kedalaman')}",
            ]
            if ev.get("Potensi"):
                parts.append(f"Potensi: {ev['Potensi']}")
            if ev.get("Dirasakan"):
                parts.append(f"Dirasakan: {ev['Dirasakan']}")
            content = ". ".join(parts) + "."

            if keywords and not any(k in content.lower() for k in keywords):
                continue

            yield RawItem(
                platform=self.platform,
                external_id=f"bmkg:{dt}",
                author="BMKG",
                content=content,
                published_at=_parse_dt(dt),
                title=f"Gempa M{ev.get('Magnitude')} {wilayah}",
                raw=ev,
            )


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
