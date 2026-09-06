"""Buat StringSession Telegram SEKALI (login interaktif) untuk adapter telegram.

Worker Celery tak bisa login interaktif (butuh kode OTP), jadi session dibuat di sini
lalu ditempel ke .env (TELEGRAM_SESSION) atau Sources.config. Jalankan LOKAL:

    python scripts/telegram_session.py

Butuh TELEGRAM_API_ID + TELEGRAM_API_HASH (dari https://my.telegram.org). Diambil
dari .env/environment; kalau kosong akan ditanyakan. Kamu akan diminta nomor HP,
lalu KODE yang dikirim Telegram (dan password 2FA bila aktif). Output = satu baris
StringSession — SIMPAN RAHASIA (setara akses akun); jangan commit.
"""

import os
import sys


def main() -> int:
    try:
        from telethon.sessions import StringSession
        from telethon.sync import TelegramClient
    except ImportError:
        print("Telethon belum terpasang. Jalankan: pip install telethon", file=sys.stderr)
        return 1

    # Ambil dari settings (.env) bila ada; else environment; else tanya.
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    try:
        from core.config import get_settings

        s = get_settings()
        api_id = api_id or s.telegram_api_id
        api_hash = api_hash or s.telegram_api_hash
    except Exception:  # noqa: BLE001 — skrip berdiri sendiri, settings opsional
        pass

    api_id = api_id or input("api_id (my.telegram.org): ").strip()
    api_hash = api_hash or input("api_hash: ").strip()
    if not api_id or not api_hash:
        print("api_id/api_hash wajib.", file=sys.stderr)
        return 1

    print("\nLogin Telegram — masukkan nomor HP (format +62...), lalu KODE dari Telegram.\n")
    with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        session_str = client.session.save()
        me = client.get_me()
        who = getattr(me, "username", None) or getattr(me, "first_name", "?")
        print(f"\nBerhasil login sebagai: {who}")
        print("\n=== TEMPEL ke TELEGRAM_SESSION di .env (RAHASIA, jangan commit) ===\n")
        print(session_str)
        print("\n===================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
