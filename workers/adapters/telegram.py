"""Adapter Telegram — channel PUBLIK via MTProto (Telethon).

Sumber gratis, genuinely-Indonesia, skala besar: channel berita, komunitas, dan
channel kampanye/buzzer. Kredensial (api_id/api_hash dari my.telegram.org + session
StringSession) via Sources.config ATAU .env (settings fallback). Session dibuat
SEKALI lewat `scripts/telegram_session.py` (login interaktif) — worker tak bisa auth
interaktif, jadi ini disiapkan analis lalu ditempel.

Hanya channel PUBLIK (username / @name / t.me/name). Invite link privat (t.me/+... /
joinchat) DILEWATI — kita tidak bergabung ke grup privat.

collect() sinkron tapi Telethon async → dijalankan di thread terpisah dgn event loop
sendiri (aman walau worker sudah punya loop berjalan). Volume dibatasi per-channel.

query = {
    "channels": ["@detikcom", "t.me/kompascom", "cnbcindonesia"],  # WAJIB (publik)
    "keywords": ["stimulus", "phk"],       # opsional: search server-side per keyword
    "limit": 200,                            # maks pesan per channel
    "min_date": "2026-01-01",                # opsional: hanya pesan >= tanggal ini
}
"""

import asyncio
import threading
from collections.abc import Iterator
from datetime import datetime

from core.config import get_settings
from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem

_PER_CHANNEL_CAP = 2000


class TelegramAdapter(BaseAdapter):
    platform = "telegram"
    key = "telegram"
    tier = "free"
    requires_credentials = True
    required_config = ("api_id", "api_hash", "session")
    rate_note = "MTProto; Telethon auto-handle FloodWait. Hanya channel/grup publik."
    legal_note = "Hanya channel publik; tidak bergabung ke grup privat / invite link."

    def collect(self, query: dict) -> Iterator[RawItem]:
        s = get_settings()
        api_id = self.config.get("api_id") or s.telegram_api_id
        api_hash = self.config.get("api_hash") or s.telegram_api_hash
        session = self.config.get("session") or s.telegram_session
        if not (api_id and api_hash and session):
            raise AdapterNotConfigured(
                "Telegram butuh api_id + api_hash + session. Ambil api_id/api_hash di "
                "my.telegram.org; buat session via scripts/telegram_session.py lalu isi "
                "TELEGRAM_SESSION (.env) atau Sources.config."
            )
        channels = _channels(query)
        if not channels:
            raise AdapterNotConfigured(
                "Telegram butuh 'channels' (daftar username/@/t.me channel publik) pada query"
            )

        # Telethon async → jalankan di thread + loop sendiri, kumpulkan, lalu yield.
        results: list[RawItem] = []
        err: list[Exception] = []

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self._collect_async(str(api_id), str(api_hash), str(session),
                                        channels, query, results)
                )
            except Exception as exc:  # noqa: BLE001 — teruskan ke thread utama
                err.append(exc)
            finally:
                loop.close()

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join()
        if err:
            raise RuntimeError(f"Telegram gagal: {err[0]}") from err[0]
        yield from results

    async def _collect_async(
        self, api_id: str, api_hash: str, session: str,
        channels: list[str], query: dict, out: list[RawItem],
    ) -> None:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        keywords = [k for k in query.get("keywords", []) if k]
        per_channel = max(1, min(int(query.get("limit", 200)), _PER_CHANNEL_CAP))
        min_date = _parse_dt(query.get("min_date"))

        client = TelegramClient(StringSession(session), int(api_id), api_hash)
        client.flood_sleep_threshold = 60
        await asyncio.wait_for(client.connect(), timeout=30)
        try:
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "Sesi Telegram tak terotorisasi — buat ulang StringSession "
                    "(scripts/telegram_session.py)"
                )
            for uname in channels:
                try:
                    await self._one_channel(client, uname, keywords, per_channel, min_date, out)
                except Exception:  # noqa: BLE001 — satu channel gagal tak menghentikan sisanya
                    continue
        finally:
            await client.disconnect()

    async def _one_channel(
        self, client, uname: str, keywords: list[str],
        per_channel: int, min_date: datetime | None, out: list[RawItem],
    ) -> None:
        seen: set[int] = set()
        # keyword → search server-side per term (efisien di histori); tanpa keyword → terbaru.
        for term in (keywords or [None]):
            if len(seen) >= per_channel:
                break
            async for msg in client.iter_messages(uname, limit=per_channel, search=term):
                text = (msg.message or "").strip()
                if not text:
                    continue
                if min_date and msg.date and msg.date.replace(tzinfo=None) < min_date:
                    break  # iter terbaru→terlama → sudah lebih tua dari min_date
                if msg.id in seen:
                    continue
                seen.add(msg.id)
                out.append(RawItem(
                    platform=self.platform,
                    external_id=f"tg:{uname}:{msg.id}"[:255],
                    author=uname,
                    content=text,
                    url=f"https://t.me/{uname}/{msg.id}",
                    published_at=msg.date,
                    title=None,
                    raw={
                        "channel": uname, "message_id": msg.id,
                        "views": getattr(msg, "views", None),
                        "forwards": getattr(msg, "forwards", None),
                        "date": msg.date.isoformat() if msg.date else None,
                    },
                ))
                if len(seen) >= per_channel:
                    break


def _channels(query: dict) -> list[str]:
    raw = query.get("channels") or query.get("channel") or []
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for c in raw:
        u = _channel_username(str(c))
        if u and u not in out:
            out.append(u)
    return out


def _channel_username(raw: str) -> str | None:
    """Normalisasi ke username channel publik. Invite link privat → None (dilewati)."""
    s = raw.strip()
    for pref in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if s.startswith(pref):
            s = s[len(pref):]
            break
    s = s.split("/")[0].split("?")[0].strip()
    if not s or s.startswith("+") or s.lower() == "joinchat":
        return None
    return s


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return None
