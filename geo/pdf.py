"""Render HTML → PDF via Chromium headless (Chrome/Edge yang sudah ada di sistem).

Kenapa server-side, bukan cetak dialog browser: hasil KONSISTEN tak peduli browser
/setelan user, background tercetak, dan link (mis. 'peta ↗' ke Google Maps) tetap
jadi anotasi yang bisa DIKLIK di PDF. Tanpa dependensi Python berat — cukup Chrome/Edge.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Kandidat biner Chromium (Windows umum) + PATH; bisa dioverride via env CHROME_BIN.
_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    shutil.which("chrome") or "",
    shutil.which("msedge") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]


def find_chromium() -> str | None:
    for c in _CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def html_to_pdf(html: str, timeout_s: int = 60) -> bytes:
    """HTML (dokumen lengkap) → bytes PDF A4 memakai @media print halaman. Raise bila
    Chromium tak ada / gagal."""
    chrome = find_chromium()
    if not chrome:
        raise RuntimeError(
            "Chromium (Chrome/Edge) tak ditemukan untuk render PDF. Pasang salah satu "
            "atau set env CHROME_BIN ke path biner."
        )
    tmp = Path(tempfile.mkdtemp(prefix="zandar_pdf_"))
    try:
        src = tmp / "report.html"
        out = tmp / "report.pdf"
        src.write_text(html, encoding="utf-8")
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--no-sandbox",
            f"--user-data-dir={tmp / 'profile'}",  # profil sementara (hindari clash Chrome aktif)
            "--virtual-time-budget=8000",           # tunggu font Google & peta selesai
            "--run-all-compositor-stages-before-draw",
            "--print-to-pdf-no-header",              # tanpa header/footer tanggal-URL bawaan
            f"--print-to-pdf={out}",
            src.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
        if not out.exists() or out.stat().st_size == 0:
            err = proc.stderr.decode("utf-8", "ignore")[-300:]
            raise RuntimeError(f"Chromium gagal membuat PDF (rc={proc.returncode}): {err}")
        return out.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
