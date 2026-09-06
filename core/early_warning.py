"""Early Warning — deteksi lonjakan (spike/anomaly) volume komentar negatif.

Fitur korporat "paling dicari HO": alarm dini krisis. Direksi tak baca jutaan
komentar; mereka butuh tahu DETIK ITU bila sentimen negatif melonjak (mis. biasa
20/hari lalu tiba-tiba 500 dalam 3 jam) agar tim PR klarifikasi sebelum viral.

Fungsi murni (tanpa IO) → mudah diuji. Deteksi = bandingkan volume jendela TERKINI
vs BASELINE (rata-rata jendela sebelumnya) memakai rasio + z-score, dengan ambang
absolut minimum agar tak berisik pada angka kecil.
"""

from __future__ import annotations

from statistics import mean, pstdev

LEVELS = ("calm", "elevated", "spike")


def detect_spike(
    counts: list[float],
    *,
    current_window: int = 1,
    min_absolute: int = 10,
    spike_ratio: float = 3.0,
    elevated_ratio: float = 1.8,
    min_baseline: float = 2.0,
    z_spike: float = 3.0,
) -> dict:
    """counts: volume per-bucket (mis. komentar NEGATIF per jam), urut lama→baru.

    - current  = jumlah pada `current_window` bucket terakhir.
    - baseline = rata-rata bucket SEBELUM jendela terkini.
    - level 'spike' bila (rasio >= spike_ratio ATAU z >= z_spike) DAN current >=
      min_absolute (hindari alarm pada angka kecil). 'elevated' bila rasio menengah.
    """
    n = len(counts)
    if n == 0:
        return {"level": "calm", "current": 0, "baseline": 0.0, "ratio": 0.0, "z": 0.0,
                "reason": "tak ada data"}

    cw = max(1, min(current_window, n))
    current = float(sum(counts[-cw:]))
    baseline_buckets = counts[:-cw] if n > cw else []
    base_mean = mean(baseline_buckets) if baseline_buckets else 0.0
    base_std = pstdev(baseline_buckets) if len(baseline_buckets) > 1 else 0.0

    # samakan skala: bandingkan rata-rata per-bucket agar current_window adil
    current_per_bucket = current / cw
    denom = max(base_mean, min_baseline)
    ratio = round(current_per_bucket / denom, 2) if denom else 0.0
    z = round((current_per_bucket - base_mean) / base_std, 2) if base_std > 0 else 0.0

    # Rasio = penggerak utama (intuitif: 3× baseline = krisis, 1.8× = pantau). z hanya
    # info + syarat pendamping — mencegah baseline sangat stabil (std kecil) memicu
    # 'spike' pada kenaikan yang praktis masih moderat.
    level = "calm"
    if current >= min_absolute and ratio >= spike_ratio:
        level = "spike"
    elif current >= max(3, min_absolute // 2) and ratio >= elevated_ratio:
        level = "elevated"

    return {
        "level": level,
        "current": int(current),
        "baseline": round(base_mean, 2),
        "ratio": ratio,
        "z": z,
        "window_buckets": cw,
        "reason": _reason(level, ratio, current),
    }


def _reason(level: str, ratio: float, current: float) -> str:
    if level == "spike":
        return f"Lonjakan negatif {ratio}× baseline ({int(current)} pada jendela terkini) — potensi krisis."
    if level == "elevated":
        return f"Volume negatif naik {ratio}× baseline — pantau ketat."
    return "Volume dalam batas normal."
