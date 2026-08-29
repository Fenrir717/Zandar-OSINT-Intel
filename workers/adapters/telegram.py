"""Adapter Telegram — channel publik via MTProto (Telethon).

Belum diimplementasikan di Fase 1 awal: butuh kredensial api_id/api_hash per
akun dan sesi persisten. Direncanakan menyusul dalam Fase 1 (PRD §5: prioritas v1).
"""

from collections.abc import Iterator

from workers.adapters.base import BaseAdapter, RawItem


class TelegramAdapter(BaseAdapter):
    platform = "telegram"

    def collect(self, query: dict) -> Iterator[RawItem]:
        raise NotImplementedError(
            "Adapter Telegram menyusul (butuh TELEGRAM_API_ID/HASH + sesi Telethon). "
            "Gunakan rss/youtube/reddit dulu."
        )
