"""Adapter CKAN — portal data terbuka pemerintah (Satu Data Indonesia & portal daerah).

Portal Satu Data daerah memakai CKAN: `/api/3/action/package_search`. Tanpa key.
Satu adapter melayani semua portal — beri base_url yang benar.

PENTING (gotcha terverifikasi): situs pemerintah RI banyak memblokir IP datacenter/
cloud (AWS/GCP/DO) dan portal nasional data.go.id sudah migrasi (404 di path CKAN
standar). Jalankan koleksi ini dari IP RUMAH Indonesia, bukan cloud VM. Tak ada
default base_url karena tak ada yang andal universal — wajib diisi.

query = {
    "base_url": "https://data.jakarta.go.id",   # portal CKAN daerah yang hidup
    "search": "kemiskinan",
    "rows": 20,
}
"""

from collections.abc import Iterator

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT


class CkanAdapter(BaseAdapter):
    platform = "satudata"
    key = "satudata"
    tier = "free"
    requires_credentials = False
    rate_note = "API CKAN publik (package_search) tanpa key; lintas portal Satu Data."
    legal_note = "Data pemerintah terbuka (Satu Data Indonesia). Sumber kebijakan resmi."

    def collect(self, query: dict) -> Iterator[RawItem]:
        base = (query.get("base_url") or self.config.get("base_url") or "").rstrip("/")
        if not base:
            raise AdapterNotConfigured(
                "CKAN butuh 'base_url' portal Satu Data yang hidup (mis. https://data.jakarta.go.id). "
                "Portal nasional data.go.id migrasi; jalankan dari IP Indonesia (gov blokir IP cloud)."
            )
        search = query.get("search", "")
        rows = int(query.get("rows", 20))

        try:
            resp = httpx.get(
                f"{base}/api/3/action/package_search",
                params={"q": search, "rows": rows},
                headers={"User-Agent": USER_AGENT},
                timeout=45,
                follow_redirects=True,
            )
            resp.raise_for_status()
            body = resp.json()
        except (httpx.HTTPError, ValueError):
            return
        if not body.get("success"):
            return

        for ds in body.get("result", {}).get("results", []):
            title = str(ds.get("title") or "").strip()
            notes = str(ds.get("notes") or "").strip()
            name = ds.get("name") or ds.get("id")
            if not title or not name:
                continue
            org = (ds.get("organization") or {}).get("title") or "Satu Data Indonesia"
            yield RawItem(
                platform=self.platform,
                external_id=f"ckan:{base}:{name}"[:255],
                author=org,
                content=f"{title}\n\n{notes}".strip(),
                url=f"{base}/dataset/{name}",
                title=title,
                raw=ds,
            )
