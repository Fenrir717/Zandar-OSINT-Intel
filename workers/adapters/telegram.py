"""Adapter Telegram — channel publik via MTProto (Telethon).

Belum diimplementasikan: butuh api_id/api_hash per akun dan sesi persisten yang
harus dibuat interaktif sekali (login kode OTP), jadi tidak bisa disiapkan
sepenuhnya dari kode saja. Direncanakan menyusul di Fase 1.
"""

from collections.abc import Iterator

from workers.adapters.base import BaseAdapter, RawItem


class TelegramAdapter(BaseAdapter):
    platform = "telegram"
    tier = "free"
    requires_credentials = True
    required_config = ("api_id", "api_hash", "session")
    rate_note = "MTProto; batas longgar. Hanya channel/grup publik."
    legal_note = "Hanya channel publik; tidak bergabung ke grup privat."

    def collect(self, query: dict) -> Iterator[RawItem]:
        raise NotImplementedError(
            "Adapter Telegram menyusul (butuh TELEGRAM_API_ID/HASH + sesi Telethon "
            "yang dibuat sekali secara interaktif). Sementara pakai rss/news/youtube/reddit."
        )
