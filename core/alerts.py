"""Kirim alert Early Warning — kanal GRATIS (Telegram bot / email SMTP).

Best-effort: kegagalan/konfigurasi kosong tak pernah meledak (return False). Kanal
diaktifkan dengan mengisi kredensial di .env; tanpa itu, alert hanya tampil di UI.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from core.config import get_settings


def send_telegram(text: str) -> bool:
    """Kirim ke chat/grup tim PR via Bot API (gratis). Butuh bot token + chat id."""
    s = get_settings()
    token = s.telegram_alert_bot_token
    chat = s.telegram_alert_chat_id
    if not token or not chat:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def send_email(subject: str, text: str) -> bool:
    """Kirim email via SMTP. Butuh smtp_host + smtp_from + alert_email_to."""
    s = get_settings()
    if not (s.smtp_host and s.smtp_from and s.alert_email_to):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = s.smtp_from
    msg["To"] = s.alert_email_to
    msg.set_content(text)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as srv:
            srv.starttls()
            if s.smtp_user:
                srv.login(s.smtp_user, s.smtp_password)
            srv.send_message(msg)
        return True
    except Exception:  # jaringan/SMTP gagal — best-effort
        return False


def send_alert(text: str, subject: str = "Zandar Early Warning") -> dict:
    """Kirim ke semua kanal terkonfigurasi. Kembalikan status per kanal."""
    return {"telegram": send_telegram(text), "email": send_email(subject, text)}


def any_channel_configured() -> bool:
    s = get_settings()
    return bool((s.telegram_alert_bot_token and s.telegram_alert_chat_id)
                or (s.smtp_host and s.smtp_from and s.alert_email_to))
