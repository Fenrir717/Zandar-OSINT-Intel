"""Adapter TikTok — HANYA lewat penyedia data pihak ketiga berkontrak.

Research API resmi TikTok terbatas ke akademisi US/EEA/UK/CH (komersial tidak
eligible) dan tak ada akses komersial gratis. Scraping langsung melanggar ToS dan
perang tanpa akhir melawan anti-bot. Jalur tersisa: vendor data (lihat VendorAdapter).
"""

from workers.adapters.vendor_base import VendorAdapter


class TikTokAdapter(VendorAdapter):
    platform = "tiktok"
    rate_note = "Mengikuti kuota kontrak vendor."
    cost_note = "Berbayar sesuai kontrak vendor (per-call atau snapshot)."
    legal_note = (
        "Tidak ada akses komersial resmi ke data publik TikTok. Wajib memakai vendor "
        "patuh GDPR/UU PDP yang hanya mengumpulkan data publik. Jangan scraping langsung."
    )
