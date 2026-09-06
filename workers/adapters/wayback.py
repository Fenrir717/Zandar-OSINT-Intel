"""Adapter Wayback Machine — konten historis dari arsip publik Archive.org.

Menemukan snapshot lewat CDX API (gratis, tanpa key). Dua mode:

- mode="extract" (default): ekstrak teks artikel tiap snapshot terpilih via trafilatura
  → cocok untuk pipeline sentimen/narasi. Mahal (1 fetch/HTML per snapshot) → dibatasi
  `max_snapshots` + jeda sopan.
- mode="index": HANYA metadata CDX (URL + waktu arsip + status), TANPA fetch → murah,
  volume besar (ratusan ribu per domain). Untuk "bukti keberadaan" (URL pernah ada di
  waktu tertentu meski kini dihapus) & pemetaan frontier URL. Konten = deskriptor arsip,
  BUKAN badan artikel.

Bulk CDX: paginasi via resumeKey (tembus batas 1 respons), sampling temporal supaya
output tersebar lintas waktu (bukan hanya N teratas), cap keras agar tak membanjiri
pipeline / tak membebani Archive.org.

query = {
    "url": "cnnindonesia.com/nasional*",   # pola URL (CDX matchType), WAJIB
    "from": "20200101", "to": "20261231",   # opsional (YYYYMMDD)
    "keywords": ["stimulus"],               # opsional filter teks (mode extract)
    "mode": "extract",                       # "extract" | "index"
    "collapse": "digest",                    # "digest" (default) | "timestamp:6" (≈bulanan)
    "max_snapshots": 50,                     # cap item yang DIKELUARKAN (alias lama: "limit")
    "max_index": 2000,                       # cap baris CDX yang ditelusuri (keluasan sampling)
    "page_size": 1000,                       # baris CDX per request paginasi
    "delay": 0.4,                            # jeda detik antar-fetch (mode extract)
}
"""

import time
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import urlparse

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT, fetch_and_extract

CDX = "http://web.archive.org/cdx/search/cdx"

_MAX_SNAPSHOTS_CAP = 20000   # batas keras item keluar (lindungi pipeline)
_MAX_INDEX_CAP = 50000       # batas keras baris CDX yang ditelusuri
_PAGE_SIZE_CAP = 5000


class WaybackAdapter(BaseAdapter):
    platform = "wayback"
    key = "wayback"
    tier = "free"
    requires_credentials = False
    rate_note = "CDX API gratis tanpa key; paginasi resumeKey + jeda sopan saat ekstraksi."
    legal_note = "Arsip publik Archive.org; konten yang sudah dipublikasikan."

    def collect(self, query: dict) -> Iterator[RawItem]:
        url = query.get("url")
        if not url:
            raise AdapterNotConfigured("Wayback butuh 'url' (pola CDX) pada query")

        mode = (query.get("mode") or "extract").lower()
        keywords = [k.lower() for k in query.get("keywords", [])]
        collapse = query.get("collapse", "digest")
        # cap output (dukung alias lama "limit")
        max_snap = int(query.get("max_snapshots") or query.get("limit") or 300)
        max_snap = max(1, min(max_snap, _MAX_SNAPSHOTS_CAP))
        # keluasan indeks CDX untuk sampling (default: jauh > output agar sampling bermakna)
        max_index = int(query.get("max_index") or min(max(max_snap * 20, 2000), _MAX_INDEX_CAP))
        max_index = max(max_snap, min(max_index, _MAX_INDEX_CAP))
        page_size = max(1, min(int(query.get("page_size", 1000)), _PAGE_SIZE_CAP))
        delay = max(0.0, float(query.get("delay", 0.4)))

        # Pola '*' di URL di-autodeteksi CDX (prefix untuk 'x/*', domain untuk '*.x') —
        # JANGAN kirim matchType eksplisit bila '*' masih ada (CDX akan cari '*' harfiah).
        candidates = list(self._cdx_paged(
            url, collapse, query.get("from"), query.get("to"), page_size, max_index
        ))
        if not candidates:
            return

        # Sampling temporal: urutkan waktu lalu ambil stride merata → cakupan lintas waktu.
        candidates.sort(key=lambda r: r[0])
        if mode == "index":
            picked = _stride_sample(candidates, max_snap)
            for ts, original in picked:
                yield self._index_item(ts, original)
            return

        # mode extract: over-sample (sebagian ekstraksi gagal) lalu hasilkan hingga cap.
        picked = _stride_sample(candidates, min(len(candidates), max_snap * 3))
        emitted = 0
        for ts, original in picked:
            if emitted >= max_snap:
                break
            snapshot = f"http://web.archive.org/web/{ts}/{original}"
            extracted = fetch_and_extract(snapshot, respect_robots=False)  # arsip, bukan situs asli
            if delay:
                time.sleep(delay)
            if extracted is None:
                continue
            text = extracted["text"]
            if keywords and not any(k in text.lower() for k in keywords):
                continue
            title = extracted["title"] or original
            emitted += 1
            yield RawItem(
                platform=self.platform,
                external_id=f"wb:{ts}:{original}"[:255],
                author=_domain(original),
                content=f"{title}\n\n{text}",
                url=snapshot,
                published_at=_parse_ts(ts),
                title=title,
                raw={"timestamp": ts, "original": original, "snapshot": snapshot, "mode": "extract"},
            )

    def _cdx_paged(
        self, url: str, collapse: str,
        frm: str | None, to: str | None, page_size: int, max_index: int,
    ) -> Iterator[tuple[str, str]]:
        """Yield (timestamp, original) menembus batas 1 respons via resumeKey."""
        params = {
            "url": url, "output": "json", "fl": "timestamp,original",
            "filter": "statuscode:200", "collapse": collapse,
            "limit": page_size, "showResumeKey": "true",
        }
        if frm:
            params["from"] = frm
        if to:
            params["to"] = to

        seen = 0
        resume: str | None = None
        while seen < max_index:
            p = dict(params)
            if resume:
                p["resumeKey"] = resume
            try:
                resp = httpx.get(CDX, params=p, headers={"User-Agent": USER_AGENT}, timeout=60)
                resp.raise_for_status()
                rows = resp.json()
            except (httpx.HTTPError, ValueError):
                return
            if not rows or len(rows) < 2:
                return

            data, resume = _split_resume(rows[1:])  # rows[0] = header
            if not data:
                return
            for row in data:
                if len(row) >= 2:
                    yield row[0], row[1]
                    seen += 1
                    if seen >= max_index:
                        return
            if not resume:
                return
            time.sleep(0.2)  # sopan antar-halaman indeks

    def _index_item(self, ts: str, original: str) -> RawItem:
        snapshot = f"http://web.archive.org/web/{ts}/{original}"
        when = _parse_ts(ts)
        label = _url_label(original)
        content = (
            f"[Arsip Wayback] {label}\n"
            f"URL asli: {original}\n"
            f"Diarsipkan: {when.isoformat() if when else ts}\n"
            f"Snapshot: {snapshot}\n"
            "(mode index — bukti keberadaan URL, bukan isi artikel)"
        )
        return RawItem(
            platform=self.platform,
            external_id=f"wb:{ts}:{original}"[:255],
            author=_domain(original),
            content=content,
            url=snapshot,
            published_at=when,
            title=label,
            raw={"timestamp": ts, "original": original, "snapshot": snapshot, "mode": "index"},
        )


def _split_resume(rows: list[list]) -> tuple[list[list], str | None]:
    """Pisahkan baris data dari resumeKey. Format CDX: data…, [], ['<resumeKey>']."""
    for i, row in enumerate(rows):
        if row == []:
            resume = rows[i + 1][0] if i + 1 < len(rows) and rows[i + 1] else None
            return rows[:i], resume
    return rows, None


def _stride_sample(items: list, n: int) -> list:
    """Ambil n item tersebar merata (stride) dari list terurut. n>=len → semua."""
    total = len(items)
    if n >= total:
        return items
    if n <= 0:
        return []
    step = total / n
    return [items[int(i * step)] for i in range(n)]


def _url_label(url: str) -> str:
    """Label ringkas dari URL (segmen path terakhir dimanusiakan, atau domain)."""
    path = urlparse(url if "//" in url else "http://" + url).path.strip("/")
    seg = path.split("/")[-1] if path else ""
    seg = seg.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    return seg[:120] if seg else _domain(url)


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _domain(url: str) -> str:
    return urlparse(url if "//" in url else "http://" + url).netloc or "unknown"
