"""Adapter yt-dlp — metadata/caption publik dari TikTok/YouTube/dll (tanpa unduh video).

yt-dlp tool matang & luas dipakai, memakai endpoint publik/mobile situs (request polos,
BUKAN evasion agresif). Untuk platform ini kita ambil METADATA + CAPTION (teks) via
`extract_info(download=False)` — video-nya TIDAK diunduh (hemat + hanya butuh teks utk
analisis). Cocok untuk TikTok (caption + views) yang jalur gratisnya sempit.

Batas jujur: yt-dlp mengambil caption/metadata, BUKAN komentar. TikTok/situs bisa
rate-limit/ubah endpoint → fail-soft. Tanpa proxy/spoofing (kalau situs blokir, kita
berhenti sopan, bukan lawan anti-bot).

query = {
    "url": "https://www.tiktok.com/@user",   # profil/playlist/sound/video, WAJIB
    "max_items": 50,                          # batas entri feed
    # pacing sopan (opsional, native yt-dlp) — BUKAN evasion:
    "delay_min": 0.5, "delay_max": 2.0,       # jeda acak antar-request ekstraksi
    "delay_requests": 1.0,                    # jeda tetap tiap request (sleep_interval_requests)
    "user_agent": "...", "accept_language": "id-ID,...",  # UA jujur + bahasa (override default)
}
"""

from collections.abc import Iterator
from datetime import datetime

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.pacing import accept_language, q_float, user_agent

_MAX_CAP = 500


class YtDlpAdapter(BaseAdapter):
    platform = "ytdlp"
    key = "ytdlp"
    tier = "free"
    requires_credentials = False
    rate_note = "Endpoint publik situs via yt-dlp; tanpa proxy/spoofing. Hormati rate-limit situs."
    legal_note = "Metadata/caption publik; video tak diunduh. Tunduk ToS situs sumber."

    def collect(self, query: dict) -> Iterator[RawItem]:
        url = query.get("url")
        if not url:
            raise AdapterNotConfigured("yt-dlp butuh 'url' (profil/playlist/video) pada query")
        try:
            import yt_dlp  # lazy — hanya perlu bila adapter dipakai
        except ImportError as exc:
            raise AdapterNotConfigured('yt-dlp belum terpasang: pip install -e ".[social]"') from exc

        max_items = max(1, min(int(query.get("max_items", 50)), _MAX_CAP))
        # Pacing sopan (native yt-dlp) + UA jujur + bahasa ID — config-driven, BUKAN evasion.
        d_min = q_float(query, "delay_min", 0.5)
        d_max = max(d_min, q_float(query, "delay_max", 2.0))
        opts = {
            "skip_download": True, "quiet": True, "no_warnings": True,
            "ignoreerrors": True, "playlistend": max_items, "extract_flat": False,
            "user_agent": user_agent(query),
            "http_headers": {"Accept-Language": accept_language(query)},
            "sleep_interval_requests": q_float(query, "delay_requests", 1.0),
            "sleep_interval": d_min, "max_sleep_interval": d_max,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:  # noqa: BLE001 — situs blokir/berubah → berhenti sopan
            return
        if not info:
            return

        entries = info.get("entries") if isinstance(info.get("entries"), list) else [info]
        for e in entries[:max_items]:
            if not e:
                continue
            caption = (e.get("description") or e.get("title") or "").strip()
            vid = e.get("id")
            if not vid or not caption:
                continue
            site = (e.get("extractor_key") or e.get("extractor") or "ytdlp").lower()
            plat = "tiktok" if "tiktok" in site else "youtube" if "youtube" in site else site
            yield RawItem(
                platform=plat,
                external_id=f"{plat}:{vid}"[:255],
                author=e.get("uploader") or e.get("channel") or e.get("uploader_id") or "unknown",
                content=caption,
                url=e.get("webpage_url") or e.get("url"),
                published_at=_parse_upload(e.get("upload_date") or e.get("timestamp")),
                title=e.get("title"),
                raw={"id": vid, "views": e.get("view_count"), "likes": e.get("like_count"),
                     "comments": e.get("comment_count"), "site": site},
            )


def _parse_upload(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.utcfromtimestamp(v)
        except (ValueError, OSError):
            return None
    try:
        return datetime.strptime(str(v)[:8], "%Y%m%d")
    except ValueError:
        return None
