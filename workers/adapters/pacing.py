"""Pacing sopan untuk scraper self-hosted — jeda acak + batching + UA jujur.

BUKAN evasion. Tujuan: kurangi beban server & risiko rate-limit lewat (a) jeda
acak antar-request (ritme lebih manusiawi, lebih ringan utk server), (b) istirahat
antar-batch, (c) SATU User-Agent browser jujur + Accept-Language (menyajikan diri
sbg klien browser normal — tetap SATU identitas persisten yg bisa diatribusi &
diblokir server; TANPA rotasi/spoofing/stealth utk menembus deteksi-bot).

Batasnya jelas: kita TIDAK menghapus navigator.webdriver, TIDAK rotasi UA/proxy
utk memecah atribusi, TIDAK melawan bot-challenge. Kalau server memblokir, adapter
berhenti sopan — bukan lawan anti-bot.

Semua config-driven via query; default ringan, bisa dimatikan (delay_min=0).
CATATAN: batch_rest_sec berjalan SINKRON di dalam task Celery — nilai besar (mis.
1800 dtk) menahan 1 slot worker selama itu. Default 0 (mati); aktifkan secara sadar.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

# Satu UA browser jujur (BUKAN rotasi). Override via query["user_agent"].
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
# Indonesia-first (fokus platform). Override via query["accept_language"].
DEFAULT_ACCEPT_LANGUAGE = "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"


def q_float(query: dict, key: str, default: float) -> float:
    """Baca angka pecahan dari query dgn fallback aman bila kosong/salah tipe."""
    try:
        v = (query or {}).get(key)
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def q_int(query: dict, key: str, default: int) -> int:
    try:
        v = (query or {}).get(key)
        return int(v) if v is not None else int(default)
    except (TypeError, ValueError):
        return int(default)


def user_agent(query: dict) -> str:
    ua = (query or {}).get("user_agent")
    return str(ua) if ua else DEFAULT_USER_AGENT


def accept_language(query: dict) -> str:
    al = (query or {}).get("accept_language")
    return str(al) if al else DEFAULT_ACCEPT_LANGUAGE


@dataclass
class PolitePacer:
    """Jeda acak antar-unit-kerja + istirahat antar-batch. Panggil wait() sekali per unit."""

    delay_min: float = 0.0
    delay_max: float = 0.0
    batch_size: int = 0          # 0 = tanpa batching
    batch_rest_sec: float = 0.0
    _count: int = field(default=0, init=False, repr=False)

    @classmethod
    def from_query(cls, query: dict, *, delay_min: float = 0.0, delay_max: float = 0.0,
                   batch_size: int = 0, batch_rest_sec: float = 0.0) -> PolitePacer:
        """Argumen = default rekomendasi per-adapter; nilai di query menimpanya."""
        dmin = max(0.0, q_float(query, "delay_min", delay_min))
        dmax = max(dmin, q_float(query, "delay_max", delay_max))
        return cls(
            delay_min=dmin,
            delay_max=dmax,
            batch_size=max(0, q_int(query, "batch_size", batch_size)),
            batch_rest_sec=max(0.0, q_float(query, "batch_rest_sec", batch_rest_sec)),
        )

    def wait(self) -> None:
        """Jeda acak; tiap `batch_size` unit, istirahat `batch_rest_sec`."""
        if self.delay_max > 0:
            time.sleep(random.uniform(self.delay_min, self.delay_max))
        self._count += 1
        if self.batch_size and self.batch_rest_sec > 0 and self._count % self.batch_size == 0:
            time.sleep(self.batch_rest_sec)
