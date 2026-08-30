"""Adapter BPS (Badan Pusat Statistik) — siaran pers resmi via WebAPI.

Sumber berkredibilitas tertinggi & legal: pernyataan statistik resmi pemerintah
(inflasi, ekonomi, kemiskinan). Berguna dua arah:
- Koleksi: siaran pers sebagai dokumen untuk analisis narasi/sentimen.
- GROUND TRUTH: fondasi verifikasi klaim (Graph E, Fase 5) — saat narasi mengklaim
  "inflasi X%", cek ke angka resmi BPS.

Butuh token gratis: daftar di https://webapi.bps.go.id/developer/ lalu isi BPS_TOKEN.

query = {
    "domain": "0000",         # 0000 nasional | kode provinsi (2 digit) | kabupaten (4)
    "keywords": ["inflasi"],  # filter judul/abstrak
    "max_items": 50,
}
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from core.config import get_settings
from workers.adapters.base import BaseAdapter, RawItem

BASE = "https://webapi.bps.go.id/v1/api/list"


class BPSAdapter(BaseAdapter):
    platform = "bps"
    key = "bps"
    tier = "free"
    requires_credentials = True
    rate_note = "WebAPI BPS gratis dengan token; siaran pers resmi."
    legal_note = "Data pemerintah terbuka (BPS). Sumber otoritatif untuk verifikasi klaim."

    def collect(self, query: dict) -> Iterator[RawItem]:
        token = self.config.get("token") or get_settings().bps_token
        if not token:
            from workers.adapters.base import AdapterNotConfigured

            raise AdapterNotConfigured(
                "BPS butuh token. Daftar di https://webapi.bps.go.id/developer/ lalu isi BPS_TOKEN."
            )

        domain = query.get("domain", "0000")
        keywords = [k.lower() for k in query.get("keywords", [])]
        max_items = int(query.get("max_items", 50))
        url = f"{BASE}/model/pressrelease/lang/ind/domain/{domain}/key/{token}/"

        try:
            resp = httpx.get(url, timeout=60, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return
        if payload.get("status") != "OK":
            return

        emitted = 0
        for item in _items(payload.get("data")):
            if emitted >= max_items:
                return
            title = str(item.get("title") or "").strip()
            abstract = str(item.get("abstract") or "").strip()
            brs_id = item.get("brs_id")
            if not title or not brs_id:
                continue
            text = f"{title}\n\n{abstract}".strip()
            if keywords and not any(k in text.lower() for k in keywords):
                continue
            yield RawItem(
                platform=self.platform,
                external_id=f"bps:{brs_id}",
                author="Badan Pusat Statistik",
                content=text,
                url=item.get("pdf"),
                published_at=_parse_date(item.get("rl_date")),
                title=title,
                raw=item,
            )
            emitted += 1


def _items(data) -> list[dict]:
    """BPS membungkus data sebagai [meta, [items]] atau langsung [items]."""
    if isinstance(data, list) and len(data) == 2 and isinstance(data[1], list):
        return data[1]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None
